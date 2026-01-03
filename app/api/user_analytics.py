"""
User-specific analytics endpoints for AdSurveillance
"""
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime, timedelta
from dotenv import load_dotenv

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

@app.route('/api/analytics/summary', methods=['GET'])
@token_required
def get_user_analytics_summary():
    """Get analytics summary for the logged-in user"""
    try:
        user_id = request.user_id
        
        # Get user's competitors
        competitors_response = (
            supabase.table("competitors")
            .select("id, name, domain, industry, estimated_monthly_spend, is_active")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .execute()
        )
        
        competitor_ids = [comp['id'] for comp in competitors_response.data]
        competitor_names = [comp['name'] for comp in competitors_response.data]
        
        if not competitor_ids:
            return jsonify({
                'success': True,
                'data': {
                    'summary': None,
                    'analytics': {
                        'competitorSpend': [],
                        'spendRanges': [],
                        'ctrPerformance': [],
                        'spendImpressions': [],
                        'platformCTR': []
                    },
                    'totalCompetitors': 0,
                    'totalSpend': 0,
                    'competitorNames': []
                }
            }), 200
        
        # Get summary metrics for user
        summary_response = (
            supabase.table("summary_metrics")
            .select("*")
            .eq("user_id", user_id)
            .order("period_end_date", desc=True)
            .limit(1)
            .execute()
        )
        
        summary_data = summary_response.data[0] if summary_response.data else None
        
        # Get daily metrics for user's competitors (last 30 days)
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        daily_response = (
            supabase.table("daily_metrics")
            .select("*")
            .in_("competitor_id", competitor_ids)
            .gte("date", thirty_days_ago)
            .order("date", desc=True)
            .limit(100)
            .execute()
        )
        
        # Calculate analytics from daily metrics
        analytics = calculate_user_analytics(daily_response.data, competitors_response.data)
        
        # Calculate total spend from competitors
        total_spend = sum([comp['estimated_monthly_spend'] or 0 for comp in competitors_response.data])
        
        return jsonify({
            'success': True,
            'data': {
                'summary': summary_data,
                'analytics': analytics,
                'totalCompetitors': len(competitor_ids),
                'totalSpend': total_spend,
                'competitorNames': competitor_names
            }
        }), 200
        
    except Exception as e:
        print(f"Error getting user analytics: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def calculate_user_analytics(daily_metrics, competitors_data):
    """Calculate analytics from daily metrics"""
    if not daily_metrics:
        return {
            'competitorSpend': [],
            'spendRanges': [],
            'ctrPerformance': [],
            'spendImpressions': [],
            'platformCTR': []
        }
    
    # Create competitor map for quick lookup
    competitor_map = {comp['id']: comp for comp in competitors_data}
    
    # Group by competitor
    competitor_analytics = {}
    platform_analytics = {}
    
    for metric in daily_metrics:
        comp_id = metric['competitor_id']
        comp_name = competitor_map.get(comp_id, {}).get('name', metric.get('competitor_name', 'Unknown'))
        platform = metric.get('platform', 'Unknown')
        
        if comp_id not in competitor_analytics:
            competitor_analytics[comp_id] = {
                'name': comp_name,
                'total_spend': 0,
                'total_impressions': 0,
                'total_clicks': 0,
                'count': 0
            }
        
        competitor_analytics[comp_id]['total_spend'] += float(metric.get('daily_spend', 0))
        competitor_analytics[comp_id]['total_impressions'] += int(metric.get('daily_impressions', 0))
        competitor_analytics[comp_id]['total_clicks'] += int(metric.get('daily_clicks', 0))
        competitor_analytics[comp_id]['count'] += 1
        
        # Platform analytics
        if platform not in platform_analytics:
            platform_analytics[platform] = {
                'total_spend': 0,
                'total_clicks': 0,
                'total_impressions': 0,
                'count': 0
            }
        
        platform_analytics[platform]['total_spend'] += float(metric.get('daily_spend', 0))
        platform_analytics[platform]['total_impressions'] += int(metric.get('daily_impressions', 0))
        platform_analytics[platform]['total_clicks'] += int(metric.get('daily_clicks', 0))
        platform_analytics[platform]['count'] += 1
    
    # Format competitor spend data
    competitor_spend = []
    for comp_id, data in competitor_analytics.items():
        avg_ctr = (data['total_clicks'] / data['total_impressions']) if data['total_impressions'] > 0 else 0
        competitor_spend.append({
            'competitor_name': data['name'],
            'total_spend': data['total_spend'],
            'ad_count': data['count'],
            'avg_ctr': avg_ctr
        })
    
    # Format platform CTR data
    platform_ctr = []
    platform_colors = {
        'Meta': '#00C2B3',
        'Facebook': '#00C2B3',
        'Google': '#4A90E2',
        'TikTok': '#FF6B6B',
        'LinkedIn': '#FFD166',
        'Twitter': '#1DA1F2',
        'Instagram': '#C13584',
        'YouTube': '#FF0000',
        'Snapchat': '#FFFC00',
        'Pinterest': '#E60023'
    }
    
    for platform, data in platform_analytics.items():
        avg_ctr = (data['total_clicks'] / data['total_impressions']) if data['total_impressions'] > 0 else 0
        platform_ctr.append({
            'platform': platform,
            'avg_ctr': avg_ctr,
            'ad_count': data['count'],
            'total_spend': data['total_spend'],
            'color': platform_colors.get(platform, '#9B51E0')
        })
    
    # Calculate spend ranges
    spend_ranges = calculate_spend_ranges(competitor_analytics)
    
    # Calculate CTR performance
    ctr_performance = calculate_ctr_performance(competitor_analytics)
    
    # Calculate spend impressions correlation
    spend_impressions = calculate_spend_impressions(competitor_analytics)
    
    return {
        'competitorSpend': sorted(competitor_spend, key=lambda x: x['total_spend'], reverse=True)[:8],
        'spendRanges': spend_ranges,
        'ctrPerformance': ctr_performance,
        'spendImpressions': spend_impressions,
        'platformCTR': platform_ctr
    }

def calculate_spend_ranges(competitor_analytics):
    """Calculate spend range distribution"""
    ranges = [
        {'spend_range': 'Under $100', 'ad_count': 0, 'avg_ctr': 0, 'total_spend': 0},
        {'spend_range': '$100-$500', 'ad_count': 0, 'avg_ctr': 0, 'total_spend': 0},
        {'spend_range': '$500-$1K', 'ad_count': 0, 'avg_ctr': 0, 'total_spend': 0},
        {'spend_range': '$1K-$5K', 'ad_count': 0, 'avg_ctr': 0, 'total_spend': 0},
        {'spend_range': 'Over $5K', 'ad_count': 0, 'avg_ctr': 0, 'total_spend': 0}
    ]
    
    for comp_id, data in competitor_analytics.items():
        avg_daily_spend = data['total_spend'] / data['count'] if data['count'] > 0 else 0
        
        if avg_daily_spend < 100:
            ranges[0]['ad_count'] += data['count']
            ranges[0]['total_spend'] += data['total_spend']
            ranges[0]['avg_ctr'] += (data['total_clicks'] / data['total_impressions']) if data['total_impressions'] > 0 else 0
        elif avg_daily_spend < 500:
            ranges[1]['ad_count'] += data['count']
            ranges[1]['total_spend'] += data['total_spend']
            ranges[1]['avg_ctr'] += (data['total_clicks'] / data['total_impressions']) if data['total_impressions'] > 0 else 0
        elif avg_daily_spend < 1000:
            ranges[2]['ad_count'] += data['count']
            ranges[2]['total_spend'] += data['total_spend']
            ranges[2]['avg_ctr'] += (data['total_clicks'] / data['total_impressions']) if data['total_impressions'] > 0 else 0
        elif avg_daily_spend < 5000:
            ranges[3]['ad_count'] += data['count']
            ranges[3]['total_spend'] += data['total_spend']
            ranges[3]['avg_ctr'] += (data['total_clicks'] / data['total_impressions']) if data['total_impressions'] > 0 else 0
        else:
            ranges[4]['ad_count'] += data['count']
            ranges[4]['total_spend'] += data['total_spend']
            ranges[4]['avg_ctr'] += (data['total_clicks'] / data['total_impressions']) if data['total_impressions'] > 0 else 0
    
    # Calculate average CTR for each range
    for r in ranges:
        if r['ad_count'] > 0:
            r['avg_ctr'] = r['avg_ctr'] / (ranges.index(r) + 1)
    
    return [r for r in ranges if r['ad_count'] > 0]

def calculate_ctr_performance(competitor_analytics):
    """Calculate CTR performance distribution"""
    brackets = [
        {'ctr_performance': 'Poor (<1%)', 'ad_count': 0, 'avg_spend': 0, 'percentage': 0},
        {'ctr_performance': 'Average (1-3%)', 'ad_count': 0, 'avg_spend': 0, 'percentage': 0},
        {'ctr_performance': 'Good (3-5%)', 'ad_count': 0, 'avg_spend': 0, 'percentage': 0},
        {'ctr_performance': 'Excellent (5-10%)', 'ad_count': 0, 'avg_spend': 0, 'percentage': 0},
        {'ctr_performance': 'Outstanding (>10%)', 'ad_count': 0, 'avg_spend': 0, 'percentage': 0}
    ]
    
    total_ads = sum([data['count'] for data in competitor_analytics.values()])
    
    for comp_id, data in competitor_analytics.items():
        ctr = (data['total_clicks'] / data['total_impressions']) if data['total_impressions'] > 0 else 0
        avg_spend = data['total_spend'] / data['count'] if data['count'] > 0 else 0
        
        if ctr < 0.01:
            brackets[0]['ad_count'] += data['count']
            brackets[0]['avg_spend'] += data['total_spend']
        elif ctr < 0.03:
            brackets[1]['ad_count'] += data['count']
            brackets[1]['avg_spend'] += data['total_spend']
        elif ctr < 0.05:
            brackets[2]['ad_count'] += data['count']
            brackets[2]['avg_spend'] += data['total_spend']
        elif ctr < 0.10:
            brackets[3]['ad_count'] += data['count']
            brackets[3]['avg_spend'] += data['total_spend']
        else:
            brackets[4]['ad_count'] += data['count']
            brackets[4]['avg_spend'] += data['total_spend']
    
    # Calculate percentages and averages
    for bracket in brackets:
        if bracket['ad_count'] > 0:
            bracket['avg_spend'] = bracket['avg_spend'] / bracket['ad_count']
            bracket['percentage'] = (bracket['ad_count'] / total_ads * 100) if total_ads > 0 else 0
    
    return [b for b in brackets if b['ad_count'] > 0]

def calculate_spend_impressions(competitor_analytics):
    """Calculate spend impressions correlation"""
    result = []
    
    for comp_id, data in competitor_analytics.items():
        impressions_per_dollar = (data['total_impressions'] / data['total_spend']) if data['total_spend'] > 0 else 0
        ctr = (data['total_clicks'] / data['total_impressions']) if data['total_impressions'] > 0 else 0
        
        result.append({
            'competitor_name': data['name'],
            'total_spend': data['total_spend'],
            'total_impressions': data['total_impressions'],
            'impressions_per_dollar': impressions_per_dollar,
            'avg_ctr': ctr
        })
    
    return sorted(result, key=lambda x: x['impressions_per_dollar'], reverse=True)[:10]

@app.route('/api/analytics/competitor-spend', methods=['GET'])
@token_required
def get_competitor_spend():
    """Get competitor spend distribution for the logged-in user"""
    try:
        user_id = request.user_id
        limit = request.args.get('limit', 10, type=int)
        
        # Get user's competitors
        competitors_response = (
            supabase.table("competitors")
            .select("id, name")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .execute()
        )
        
        competitor_ids = [comp['id'] for comp in competitors_response.data]
        
        if not competitor_ids:
            return jsonify({
                'success': True,
                'data': []
            }), 200
        
        # Get daily metrics for competitors
        daily_response = (
            supabase.table("daily_metrics")
            .select("competitor_id, competitor_name, daily_spend, daily_ctr")
            .in_("competitor_id", competitor_ids)
            .execute()
        )
        
        # Group by competitor
        competitor_data = {}
        for metric in daily_response.data:
            comp_id = metric['competitor_id']
            comp_name = metric.get('competitor_name', 'Unknown')
            
            if comp_id not in competitor_data:
                competitor_data[comp_id] = {
                    'competitor_name': comp_name,
                    'total_spend': 0,
                    'ad_count': 0,
                    'avg_ctr': 0,
                    'ctr_sum': 0
                }
            
            competitor_data[comp_id]['total_spend'] += float(metric.get('daily_spend', 0))
            competitor_data[comp_id]['ad_count'] += 1
            competitor_data[comp_id]['ctr_sum'] += float(metric.get('daily_ctr', 0))
        
        # Format data
        result = []
        for comp_id, data in competitor_data.items():
            avg_ctr = data['ctr_sum'] / data['ad_count'] if data['ad_count'] > 0 else 0
            result.append({
                'competitor_name': data['competitor_name'],
                'total_spend': data['total_spend'],
                'ad_count': data['ad_count'],
                'avg_ctr': avg_ctr
            })
        
        # Sort by total spend and limit
        result = sorted(result, key=lambda x: x['total_spend'], reverse=True)[:limit]
        
        return jsonify({
            'success': True,
            'data': result
        }), 200
        
    except Exception as e:
        print(f"Error getting competitor spend: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'daily-metrics',  # Change for each service
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("Starting User Analytics server...")
    app.run(debug=True, port=5007, host='0.0.0.0')