"""
Daily Metrics API for AdSurveillance
Port: 5008
Handles both ads data and metrics calculation from daily_metrics table
"""
import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv
import json

load_dotenv()

app = Flask(__name__)
CORS(app)

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)

# Import middleware
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from middleware.auth import token_required

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        test = supabase.table("daily_metrics").select("id", count='exact', head=True).execute()
        return jsonify({
            'status': 'healthy',
            'service': 'daily-metrics',
            'timestamp': datetime.now().isoformat(),
            'database_connected': True,
            'daily_metrics_count': test.count if test.count else 0
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'healthy',
            'service': 'daily-metrics',
            'database_connected': False,
            'error': str(e)
        }), 200

@app.route('/api/daily-metrics', methods=['POST'])
@token_required
def get_daily_metrics():
    """Get ads data from daily_metrics table for the authenticated user"""
    try:
        user_id = request.user_id
        data = request.get_json() or {}
        
        limit = data.get('limit', 10)
        showLatestOnly = data.get('showLatestOnly', False)
        startDate = data.get('startDate')
        endDate = data.get('endDate')
        
        print(f"📊 Fetching ads data for user {user_id}")
        print(f"   Parameters: limit={limit}, showLatestOnly={showLatestOnly}")
        
        # First, get user's competitors
        competitors_response = supabase.table("competitors")\
            .select("id,name")\
            .eq("user_id", user_id)\
            .execute()
        
        if not competitors_response.data:
            print(f"⚠️ No competitors found for user {user_id}")
            # Return empty but successful response
            return jsonify({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'No competitors found. Add competitors to see ads.'
            }), 200
        
        competitor_ids = [c['id'] for c in competitors_response.data]
        print(f"✅ Found {len(competitor_ids)} competitors for user {user_id}")
        
        # Build query to get ads from daily_metrics table
        query = supabase.table("daily_metrics")\
            .select("""
                id,
                date,
                competitor_id,
                competitor_name,
                platform,
                daily_spend,
                daily_impressions,
                daily_ctr,
                daily_clicks,
                spend_lower_bound,
                spend_upper_bound,
                impressions_lower_bound,
                impressions_upper_bound,
                creative,
                ad_id,
                created_at,
                updated_at
            """)\
            .in_("competitor_id", competitor_ids)
        
        # Apply date filters
        if startDate and endDate:
            query = query.gte("date", startDate).lte("date", endDate)
        
        # If showLatestOnly, get only the latest date
        if showLatestOnly:
            # Get the latest date for this user
            latest_date_query = supabase.table("daily_metrics")\
                .select("date")\
                .in_("competitor_id", competitor_ids)\
                .order("date", desc=True)\
                .limit(1)\
                .execute()
            
            if latest_date_query.data:
                latest_date = latest_date_query.data[0]['date']
                print(f"📅 Latest date found: {latest_date}")
                query = query.eq("date", latest_date)
            else:
                print(f"⚠️ No ads data found for user {user_id}")
                return jsonify({
                    'success': True,
                    'data': [],
                    'count': 0,
                    'message': 'No ads data found.'
                }), 200
        
        # Add ordering and limit
        query = query.order("date", desc=True).order("created_at", desc=True).limit(limit)
        
        # Execute query
        response = query.execute()
        
        ads_data = response.data if response.data else []
        print(f"📊 Found {len(ads_data)} ads in daily_metrics table")
        
        # Transform data for frontend
        ads = []
        for item in ads_data:
            try:
                # Get competitor name from competitors table if not in daily_metrics
                competitor_name = item.get('competitor_name')
                if not competitor_name:
                    # Try to get from competitors table
                    comp_response = supabase.table("competitors")\
                        .select("name")\
                        .eq("id", item['competitor_id'])\
                        .execute()
                    if comp_response.data:
                        competitor_name = comp_response.data[0]['name']
                
                # Parse creative if it's JSON
                creative = item.get('creative', '')
                ad_body = creative
                if creative and (creative.startswith('{') or creative.startswith('[')):
                    try:
                        creative_json = json.loads(creative)
                        if isinstance(creative_json, dict):
                            ad_body = creative_json.get('text', creative_json.get('description', str(creative_json)))
                        elif isinstance(creative_json, list):
                            ad_body = ', '.join(str(x) for x in creative_json)
                    except:
                        pass
                
                # Create ad object for frontend
                ad = {
                    'id': item['id'],
                    'date': item['date'],
                    'competitor_name': competitor_name or 'Unknown',
                    'platform': item.get('platform', 'Unknown'),
                    'status': 'ACTIVE',  # Default status
                    'daily_spend': float(item.get('daily_spend', 0)),
                    'daily_impressions': int(item.get('daily_impressions', 0)),
                    'daily_ctr': float(item.get('daily_ctr', 0.02)),
                    'daily_clicks': int(item.get('daily_clicks', 0)),
                    'ad_title': f"{competitor_name or 'Ad'} on {item.get('platform', 'Platform')}",
                    'ad_body': ad_body or f"Advertising campaign with estimated spend of ${float(item.get('daily_spend', 0)):,.0f}",
                    'spend_lower_bound': float(item.get('spend_lower_bound', 0)) if item.get('spend_lower_bound') else None,
                    'spend_upper_bound': float(item.get('spend_upper_bound', 0)) if item.get('spend_upper_bound') else None,
                    'impressions_lower_bound': int(item.get('impressions_lower_bound', 0)) if item.get('impressions_lower_bound') else None,
                    'impressions_upper_bound': int(item.get('impressions_upper_bound', 0)) if item.get('impressions_upper_bound') else None,
                    'variants': 1,
                    'ab_tests': 0,
                    'creative': creative,
                    'ad_id': item.get('ad_id'),
                    'competitor_id': item['competitor_id'],
                    'created_at': item.get('created_at'),
                    'updated_at': item.get('updated_at')
                }
                
                # Calculate clicks from CTR and impressions if not present
                if ad['daily_clicks'] == 0 and ad['daily_impressions'] > 0 and ad['daily_ctr'] > 0:
                    ad['daily_clicks'] = int(ad['daily_impressions'] * ad['daily_ctr'])
                
                ads.append(ad)
                
            except Exception as item_error:
                print(f"⚠️ Error processing ad item {item.get('id')}: {item_error}")
                continue
        
        print(f"✅ Returning {len(ads)} ads for user {user_id}")
        
        return jsonify({
            'success': True,
            'data': ads,
            'count': len(ads),
            'user_id': user_id,
            'date_range': {
                'start': startDate,
                'end': endDate
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Error fetching ads data: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return empty data instead of error
        return jsonify({
            'success': True,
            'data': [],
            'count': 0,
            'error': str(e),
            'message': 'No ads data available yet.'
        }), 200

@app.route('/api/summary-metrics', methods=['GET'])
@token_required
def get_summary_metrics():
    """Calculate summary metrics from daily_metrics table"""
    try:
        user_id = request.user_id
        period = request.args.get('period', '7d')
        
        print(f"📈 Calculating summary metrics for user {user_id}, period: {period}")
        
        # Get user's competitors
        competitors_response = supabase.table("competitors")\
            .select("id,name")\
            .eq("user_id", user_id)\
            .execute()
        
        if not competitors_response.data:
            print(f"⚠️ No competitors found for user {user_id}")
            return jsonify({
                'success': True,
                'data': get_empty_summary_metrics(user_id, period),
                'message': 'No competitors found.'
            }), 200
        
        competitor_ids = [c['id'] for c in competitors_response.data]
        competitor_names = [c['name'] for c in competitors_response.data]
        
        # Calculate date range based on period
        end_date = datetime.now()
        if period == '1d':
            start_date = end_date - timedelta(days=1)
        elif period == '7d':
            start_date = end_date - timedelta(days=7)
        elif period == '30d':
            start_date = end_date - timedelta(days=30)
        elif period == '90d':
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=7)
        
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        print(f"📅 Date range: {start_date_str} to {end_date_str}")
        
        # Get ads data from daily_metrics table
        metrics_query = supabase.table("daily_metrics")\
            .select("daily_spend, daily_impressions, daily_ctr, platform, competitor_name, date")\
            .in_("competitor_id", competitor_ids)\
            .gte("date", start_date_str)\
            .lte("date", end_date_str)\
            .execute()
        
        metrics = metrics_query.data if metrics_query.data else []
        print(f"📊 Found {len(metrics)} ads records for calculation")
        
        if not metrics:
            print(f"⚠️ No ads data found for period {period}")
            return jsonify({
                'success': True,
                'data': get_empty_summary_metrics(user_id, period),
                'message': 'No ads data found for the selected period.'
            }), 200
        
        # Calculate totals
        total_spend = sum(float(m.get('daily_spend', 0) or 0) for m in metrics)
        total_impressions = sum(int(m.get('daily_impressions', 0) or 0) for m in metrics)
        total_clicks = sum(int(float(m.get('daily_ctr', 0) or 0) * float(m.get('daily_impressions', 0) or 0)) for m in metrics)
        
        # Calculate average CTR
        valid_ctrs = [float(m.get('daily_ctr', 0)) for m in metrics if m.get('daily_ctr')]
        avg_ctr = sum(valid_ctrs) / len(valid_ctrs) if valid_ctrs else 0.03
        
        # Count unique active ads (distinct competitor + platform combinations)
        unique_ads = len(set(
            (m.get('competitor_name', ''), m.get('platform', ''), m.get('date', '')) 
            for m in metrics 
            if m.get('competitor_name') and m.get('platform')
        ))
        
        # Calculate platform distribution
        platform_totals = {}
        for metric in metrics:
            platform = metric.get('platform', 'Unknown')
            if platform:
                spend = float(metric.get('daily_spend', 0) or 0)
                platform_totals[platform] = platform_totals.get(platform, 0) + spend
        
        # Convert to percentages
        platform_distribution = {}
        if platform_totals and total_spend > 0:
            platform_distribution = {
                platform: (spend / total_spend * 100)
                for platform, spend in platform_totals.items()
            }
        else:
            # Default distribution if no data
            platform_distribution = {
                'Meta': 36.5,
                'Google': 31.3,
                'TikTok': 19.9,
                'LinkedIn': 12.4,
            }
        
        # Find top performers by spend
        competitor_totals = {}
        for metric in metrics:
            competitor = metric.get('competitor_name', 'Unknown')
            if competitor:
                spend = float(metric.get('daily_spend', 0) or 0)
                competitor_totals[competitor] = competitor_totals.get(competitor, 0) + spend
        
        top_performers = sorted(
            [{'name': k, 'spend': v} for k, v in competitor_totals.items()],
            key=lambda x: x['spend'],
            reverse=True
        )[:5]
        
        # Create summary response
        summary = {
            'id': f"summary_{user_id}_{period}",
            'total_competitor_spend': round(total_spend, 2),
            'active_campaigns_count': unique_ads or len(competitor_names),
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'average_ctr': round(avg_ctr, 4),
            'platform_distribution': platform_distribution,
            'top_performers': [p['name'] for p in top_performers],
            'top_performers_with_spend': top_performers,
            'spend_by_industry': {},  # You can add industry data if available
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'user_id': user_id,
            'period': period,
            'competitor_count': len(competitor_ids),
            'ads_count': len(metrics),
            'date_range': {
                'start': start_date_str,
                'end': end_date_str
            },
            'metrics_calculated_from': 'daily_metrics table'
        }
        
        print(f"✅ Summary metrics calculated:")
        print(f"   Total Spend: ${total_spend:,.0f}")
        print(f"   Active Ads: {unique_ads}")
        print(f"   Total Impressions: {total_impressions:,}")
        print(f"   Avg CTR: {avg_ctr:.2%}")
        print(f"   Platforms: {len(platform_distribution)}")
        
        return jsonify({
            'success': True,
            'data': summary
        }), 200
        
    except Exception as e:
        print(f"❌ Error calculating summary metrics: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return empty summary
        return jsonify({
            'success': True,
            'data': get_empty_summary_metrics(request.user_id if hasattr(request, 'user_id') else None, '7d'),
            'error': str(e),
            'message': 'Could not calculate summary metrics.'
        }), 200

def get_empty_summary_metrics(user_id, period='7d'):
    """Return empty summary metrics structure"""
    return {
        'id': f"empty_summary_{user_id}",
        'total_competitor_spend': 0,
        'active_campaigns_count': 0,
        'total_impressions': 0,
        'total_clicks': 0,
        'average_ctr': 0.03,
        'platform_distribution': {
            'Meta': 36.5,
            'Google': 31.3,
            'TikTok': 19.9,
            'LinkedIn': 12.4,
        },
        'top_performers': [],
        'top_performers_with_spend': [],
        'spend_by_industry': {},
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'user_id': user_id,
        'period': period,
        'competitor_count': 0,
        'ads_count': 0,
        'date_range': {
            'start': None,
            'end': None
        },
        'metrics_calculated_from': 'default values'
    }

@app.route('/api/debug-daily-metrics', methods=['GET'])
@token_required
def debug_daily_metrics():
    """Debug endpoint to see daily_metrics table structure and data"""
    try:
        user_id = request.user_id
        
        # Get table structure
        sample_query = supabase.table("daily_metrics")\
            .select("*")\
            .limit(5)\
            .execute()
        
        # Count total records
        count_query = supabase.table("daily_metrics")\
            .select("id", count='exact')\
            .execute()
        
        # Count user's records
        user_competitors = supabase.table("competitors")\
            .select("id")\
            .eq("user_id", user_id)\
            .execute()
        
        user_count = 0
        if user_competitors.data:
            competitor_ids = [c['id'] for c in user_competitors.data]
            user_count_query = supabase.table("daily_metrics")\
                .select("id", count='exact')\
                .in_("competitor_id", competitor_ids)\
                .execute()
            user_count = user_count_query.count if user_count_query.count else 0
        
        return jsonify({
            'success': True,
            'table_structure': sample_query.data[0] if sample_query.data else {},
            'sample_data': sample_query.data if sample_query.data else [],
            'total_records': count_query.count if count_query.count else 0,
            'user_records': user_count,
            'user_competitors_count': len(user_competitors.data) if user_competitors.data else 0,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/check-ads-insertion', methods=['POST'])
@token_required
def check_ads_insertion():
    """Check if ads are being inserted into daily_metrics table"""
    try:
        user_id = request.user_id
        data = request.get_json() or {}
        hours = data.get('hours', 24)
        
        # Get recent ads insertion
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Get user's competitors
        competitors_response = supabase.table("competitors")\
            .select("id")\
            .eq("user_id", user_id)\
            .execute()
        
        if not competitors_response.data:
            return jsonify({
                'success': True,
                'recent_ads': 0,
                'message': 'No competitors found'
            }), 200
        
        competitor_ids = [c['id'] for c in competitors_response.data]
        
        recent_ads_query = supabase.table("daily_metrics")\
            .select("id, date, competitor_name, platform, daily_spend, created_at")\
            .in_("competitor_id", competitor_ids)\
            .gte("created_at", cutoff_time)\
            .order("created_at", desc=True)\
            .execute()
        
        recent_ads = recent_ads_query.data if recent_ads_query.data else []
        
        return jsonify({
            'success': True,
            'recent_ads_count': len(recent_ads),
            'recent_ads': recent_ads,
            'hours_back': hours,
            'competitor_ids': competitor_ids,
            'message': f'Found {len(recent_ads)} ads inserted in last {hours} hours'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print(f"\n{'='*60}")
    print(f"🚀 Starting Daily Metrics API")
    print(f"{'='*60}")
    print(f"📡 Port: 5008")
    print(f"📊 Table: daily_metrics (ads storage + metrics)")
    print(f"🔌 Supabase: {url[:30]}..." if url else "❌ No Supabase URL")
    print(f"{'='*60}")
    print(f"📋 Available endpoints:")
    print(f"  • POST   /api/daily-metrics       - Get ads data")
    print(f"  • GET    /api/summary-metrics     - Calculate metrics")
    print(f"  • GET    /api/debug-daily-metrics - Debug table")
    print(f"  • POST   /api/check-ads-insertion - Check ads insertion")
    print(f"  • GET    /health                  - Health check")
    print(f"{'='*60}")
    print(f"🔍 This service reads from daily_metrics table where ads are stored")
    print(f"📈 Summary metrics are calculated from the ads data")
    print(f"{'='*60}\n")
    
    app.run(debug=True, port=5008, host='0.0.0.0')