"""
Targeting intelligence endpoints for AdSurveillance
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

@app.route('/api/targeting-intel', methods=['GET'])
@token_required
def get_user_targeting_intel():
    """Get targeting intelligence for the logged-in user's competitors"""
    try:
        user_id = request.user_id
        
        # Get user's competitors
        competitors_response = (
            supabase.table("competitors")
            .select("id, name, domain, industry, estimated_monthly_spend")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .execute()
        )
        
        competitor_ids = [comp['id'] for comp in competitors_response.data]
        
        if not competitor_ids:
            return jsonify({
                'success': True,
                'data': [],
                'message': 'No competitors found for user'
            }), 200
        
        # Get targeting intelligence for these competitors
        targeting_response = (
            supabase.table("targeting_intel")
            .select("""
                id,
                competitor_id,
                competitor_name,
                age_distribution,
                gender_distribution,
                geographic_spend,
                interest_clusters,
                funnel_stage_prediction,
                bidding_strategy,
                advanced_targeting,
                data_source,
                confidence_score,
                created_at,
                updated_at
            """)
            .in_("competitor_id", competitor_ids)
            .order("created_at", desc=True)
            .execute()
        )
        
        if not targeting_response.data:
            # Generate mock targeting data for user's competitors
            mock_data = []
            for competitor in competitors_response.data:
                mock_data.append(generate_mock_targeting_for_competitor(competitor))
            
            return jsonify({
                'success': True,
                'data': mock_data,
                'count': len(mock_data),
                'user_id': user_id,
                'source': 'mock_generated'
            }), 200
        
        return jsonify({
            'success': True,
            'data': targeting_response.data,
            'count': len(targeting_response.data),
            'user_id': user_id,
            'source': 'database'
        }), 200
        
    except Exception as e:
        print(f"Error getting user targeting intelligence: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/targeting-intel/<competitor_id>', methods=['GET'])
@token_required
def get_targeting_intel_for_competitor(competitor_id):
    """Get targeting intelligence for a specific competitor (user must own it)"""
    try:
        user_id = request.user_id
        
        # Verify competitor belongs to user
        competitor_response = (
            supabase.table("competitors")
            .select("id, name")
            .eq("id", competitor_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        if not competitor_response.data:
            return jsonify({
                'success': False,
                'error': 'Competitor not found or you do not have permission'
            }), 404
        
        # Get targeting intelligence for this competitor
        targeting_response = (
            supabase.table("targeting_intel")
            .select("*")
            .eq("competitor_id", competitor_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        
        if not targeting_response.data:
            # Generate mock targeting data
            mock_data = generate_mock_targeting_for_competitor(competitor_response.data)
            return jsonify({
                'success': True,
                'data': mock_data,
                'source': 'mock_generated'
            }), 200
        
        return jsonify({
            'success': True,
            'data': targeting_response.data[0],
            'source': 'database'
        }), 200
        
    except Exception as e:
        print(f"Error getting targeting for competitor {competitor_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/targeting-intel/latest', methods=['GET'])
@token_required
def get_latest_targeting_intel():
    """Get latest targeting intelligence for the logged-in user"""
    try:
        user_id = request.user_id
        
        # Get user's competitors
        competitors_response = (
            supabase.table("competitors")
            .select("id")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .execute()
        )
        
        competitor_ids = [comp['id'] for comp in competitors_response.data]
        
        if not competitor_ids:
            return jsonify({
                'success': True,
                'data': None,
                'message': 'No competitors found for user'
            }), 200
        
        # Get latest targeting intelligence for these competitors
        targeting_response = (
            supabase.table("targeting_intel")
            .select("*")
            .in_("competitor_id", competitor_ids)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        
        if not targeting_response.data:
            # If no targeting data, get the first competitor and generate mock data
            if competitors_response.data:
                competitor = competitors_response.data[0]
                mock_data = generate_mock_targeting_for_competitor(competitor)
                return jsonify({
                    'success': True,
                    'data': mock_data,
                    'source': 'mock_generated'
                }), 200
            else:
                return jsonify({
                    'success': True,
                    'data': None
                }), 200
        
        return jsonify({
            'success': True,
            'data': targeting_response.data[0],
            'source': 'database'
        }), 200
        
    except Exception as e:
        print(f"Error getting latest targeting intelligence: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def generate_mock_targeting_for_competitor(competitor):
    """Generate mock targeting intelligence data for a competitor"""
    # Base mock data
    base_mock = {
        'competitor_id': competitor['id'],
        'competitor_name': competitor['name'],
        'age_distribution': {
            '18-24': 0.15,
            '25-34': 0.35,
            '35-44': 0.28,
            '45-54': 0.15,
            '55+': 0.07
        },
        'gender_distribution': {
            'male': 0.58,
            'female': 0.40,
            'other': 0.02
        },
        'geographic_spend': {
            'United States': {'spend': 18200, 'percentage': 45},
            'United Kingdom': {'spend': 8900, 'percentage': 22},
            'Canada': {'spend': 6100, 'percentage': 15},
            'Australia': {'spend': 4000, 'percentage': 10},
            'Germany': {'spend': 3200, 'percentage': 8}
        },
        'interest_clusters': [
            {'interest': 'Fitness & Running', 'affinity': 0.95, 'reach': 450000},
            {'interest': 'Athletic Apparel', 'affinity': 0.88, 'reach': 380000},
            {'interest': 'Health & Wellness', 'affinity': 0.82, 'reach': 520000}
        ],
        'funnel_stage_prediction': {
            'awareness': {'label': 'Cold Traffic', 'percentage': 45, 'reach': 2100000},
            'consideration': {'label': 'Engagement', 'percentage': 30, 'reach': 1400000},
            'conversion': {'label': 'Retargeting', 'percentage': 20, 'reach': 940000},
            'retention': {'label': 'Loyalty', 'percentage': 5, 'reach': 235000}
        },
        'bidding_strategy': {
            'hourly': [
                {'time': '12am', 'cpc': 1.1, 'cpm': 8.2},
                {'time': '6am', 'cpc': 1.6, 'cpm': 10.1},
                {'time': '12pm', 'cpc': 2.4, 'cpm': 14.2},
                {'time': '6pm', 'cpc': 2.8, 'cpm': 15.6}
            ],
            'avg_cpc': 2.16,
            'peak_cpm': {'value': 15.6, 'window': '6pm-9pm'},
            'best_time': '3am-6am'
        },
        'advanced_targeting': {
            'purchase_intent': {'level': 'High', 'confidence': 0.62},
            'ai_recommendation': 'Focus on mobile-first advertising with strong retargeting.',
            'device_preference': {'mobile': 0.78, 'desktop': 0.22, 'ios_share': 0.65},
            'competitor_overlap': {'brands': 3.2, 'description': 'Audience overlaps with similar brands'}
        },
        'data_source': 'AI_MODELED',
        'confidence_score': 0.75
    }
    
    # Adjust based on competitor's industry
    if 'industry' in competitor and competitor['industry']:
        industry = competitor['industry'].lower()
        
        if 'tech' in industry or 'software' in industry:
            base_mock.update({
                'age_distribution': {'18-24': 0.10, '25-34': 0.45, '35-44': 0.30, '45-54': 0.12, '55+': 0.03},
                'interest_clusters': [
                    {'interest': 'Technology News', 'affinity': 0.92, 'reach': 680000},
                    {'interest': 'Software Development', 'affinity': 0.88, 'reach': 420000},
                    {'interest': 'Startup Ecosystem', 'affinity': 0.82, 'reach': 350000}
                ]
            })
        elif 'fashion' in industry or 'apparel' in industry:
            base_mock.update({
                'gender_distribution': {'male': 0.40, 'female': 0.58, 'other': 0.02},
                'age_distribution': {'18-24': 0.25, '25-34': 0.45, '35-44': 0.20, '45-54': 0.08, '55+': 0.02}
            })
    
    return base_mock

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'targeting-intel',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("Starting Targeting Intelligence server...")
    print("📡 Port: 5011")
    print("🌐 Endpoints:")
    print("  GET  /api/targeting-intel        - Get all targeting for user's competitors")
    print("  GET  /api/targeting-intel/latest - Get latest targeting")
    print("  GET  /api/targeting-intel/<id>   - Get targeting for specific competitor")
    app.run(debug=True, port=5011, host='0.0.0.0')