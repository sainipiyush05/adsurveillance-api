"""
Ads Refresh API - Handles refresh button clicks from frontend
Port: 5020
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
import uuid
import time
import os
import sys
import threading
from datetime import datetime, timezone
from supabase import create_client, Client

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

app = Flask(__name__)
CORS(app, origins=["*"], supports_credentials=True)

# Initialize Supabase
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# ========== STRICT ADS FETCHER IMPORT (NO MOCK MODE) ==========
FETCHER_AVAILABLE = False
ads_fetcher = None

# ========== STRICT ADS FETCHER CHECK (NO MOCK) ==========
if not FETCHER_AVAILABLE:
    print("🚫 CRITICAL ERROR: AdsFetcher not available")
    print("💡 System will FAIL instead of using mock mode")
    print("   Create ads_fetcher.py in ad_fetch_service/")
    # Don't set any fallback - let it fail


try:
    # Try to find ad_fetch_service directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    service_path = os.path.join(project_root, 'ad_fetch_service')
    
    print(f"🔍 Looking for ads_fetcher in: {service_path}")
    
    if os.path.exists(service_path):
        print(f"✅ Found ad_fetch_service directory")
        
        # Add to Python path
        if service_path not in sys.path:
            sys.path.insert(0, service_path)
        
        try:
            from ads_fetcher import AdsFetcher
            ads_fetcher = AdsFetcher()
            FETCHER_AVAILABLE = True
            print("✅ AdsFetcher loaded successfully")
            
            # Test the connection
            test_results = ads_fetcher.test_connection()
            print(f"🔧 Node.js version: {test_results.get('node_version', 'Unknown')}")
            print(f"📦 npm version: {test_results.get('npm_version', 'Unknown')}")
            
        except ImportError as e:
            print(f"❌ Could not import AdsFetcher: {e}")
            print(f"   Make sure ads_fetcher.py exists in: {service_path}/")
            FETCHER_AVAILABLE = False
            
        except Exception as e:
            print(f"❌ Error initializing AdsFetcher: {e}")
            FETCHER_AVAILABLE = False
    else:
        print(f"❌ ad_fetch_service directory not found: {service_path}")
        print(f"   Create directory: mkdir -p {service_path}")
        print(f"   Create file: {service_path}/ads_fetcher.py")
        FETCHER_AVAILABLE = False
        
except Exception as e:
    print(f"❌ Unexpected error loading AdsFetcher: {e}")
    FETCHER_AVAILABLE = False

if not FETCHER_AVAILABLE:
    print("🚫 REAL ADS FETCHING DISABLED")
    print("💡 To enable real ads fetching:")
    print(f"   1. Create {service_path}/ads_fetcher.py")
    print(f"   2. Implement the AdsFetcher class")
    print(f"   3. Restart the service")
# ========== END ADS FETCHER IMPORT ==========

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'ads_refresh',
        'port': Config.ADS_REFRESH_PORT,
        'fetcher_available': FETCHER_AVAILABLE,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'node_module_path': Config.ADS_FETCH_DIR,
        'node_module_exists': os.path.exists(Config.ADS_FETCH_DIR),
        'mock_mode': False  # Always false now
    }), 200

def verify_token(token):
    """Verify JWT token and return user_id"""
    try:
        if not token:
            return None
        
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
        return payload.get('user_id')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError as e:
        print(f"Invalid token error: {e}")
        return None
    except Exception as e:
        print(f"Token verification error: {e}")
        return None

def get_user_competitors(user_id):
    """Get all competitors for a user"""
    try:
        response = supabase.table(Config.DB_TABLES['competitors'])\
            .select('id,name,domain,platform')\
            .eq('user_id', user_id)\
            .eq('is_active', True)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting competitors: {e}")
        return []

def create_job_record(user_id, job_id, platform="all"):
    """Create a new job record in database"""
    try:
        competitors = get_user_competitors(user_id)
        
        job_data = {
            'user_id': user_id,
            'job_id': job_id,
            'status': 'pending',
            'platform': platform,
            'total_competitors': len(competitors),
            'ads_fetched': 0,
            'start_time': datetime.now(timezone.utc).isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        response = supabase.table('ads_fetch_jobs').insert(job_data).execute()
        
        if response.data:
            print(f"✅ Job record created: {job_id} for user {user_id}")
            return True
        else:
            print(f"❌ Failed to create job record: {response}")
            return False
            
    except Exception as e:
        print(f"Error creating job record: {e}")
        return False

def run_background_fetch(job_id, user_id, platform):
    """Run ads fetching in background thread - NO MOCK MODE"""
    try:
        print(f"🚀 Starting background fetch for job {job_id}")
        
        # Update job status to running
        supabase.table('ads_fetch_jobs')\
            .update({
                'status': 'running',
                'updated_at': datetime.now(timezone.utc).isoformat()
            })\
            .eq('job_id', job_id)\
            .execute()
        
        # Run the ads fetcher if available
        if FETCHER_AVAILABLE and ads_fetcher:
            success, logs, ads_count = ads_fetcher.run_for_user(user_id, platform)
        else:
            # NO MOCK MODE - Return failure
            print(f"🚫 REAL ADS FETCHING NOT AVAILABLE for job {job_id}")
            success = False
            logs = "=== ADS FETCHING DISABLED ===\n"
            logs += f"Job ID: {job_id}\n"
            logs += f"User ID: {user_id}\n"
            logs += f"Platform: {platform}\n"
            logs += f"Error: Ads fetcher not properly configured\n"
            logs += f"Timestamp: {datetime.now(timezone.utc)}\n"
            logs += f"\n💡 To fix:\n"
            logs += f"   1. Ensure ads_fetcher.py exists in ad_fetch_service/\n"
            logs += f"   2. Check the AdsFetcher class is properly implemented\n"
            ads_count = 0
        
        # Update job with results
        end_time = datetime.now(timezone.utc).isoformat()
        update_data = {
            'status': 'completed' if success else 'failed',
            'ads_fetched': ads_count,
            'end_time': end_time,
            'updated_at': end_time
        }
        
        # Add logs if available (truncate if too long)
        if logs:
            if len(logs) > 10000:  # Limit to 10KB
                logs = logs[:10000] + "\n...[truncated]"
            update_data['logs'] = logs
        
        # Add error message if failed
        if not success and logs:
            error_msg = logs[:500] if len(logs) > 500 else logs
            update_data['error_message'] = error_msg
        
        # Calculate duration
        start_response = supabase.table('ads_fetch_jobs')\
            .select('start_time')\
            .eq('job_id', job_id)\
            .execute()
        
        if start_response.data and start_response.data[0].get('start_time'):
            start_time_str = start_response.data[0]['start_time']
            if isinstance(start_time_str, str):
                # Parse timestamps with timezone handling
                try:
                    if start_time_str.endswith('Z'):
                        start_time_str = start_time_str[:-1] + '+00:00'
                    
                    start_dt = datetime.fromisoformat(start_time_str)
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    
                    end_dt = datetime.now(timezone.utc)
                    
                    duration = int((end_dt - start_dt).total_seconds())
                    update_data['duration_seconds'] = duration
                except Exception as parse_error:
                    print(f"Warning: Could not parse duration: {parse_error}")
        
        # Update database
        supabase.table('ads_fetch_jobs')\
            .update(update_data)\
            .eq('job_id', job_id)\
            .execute()
        
        print(f"✅ Background fetch completed for job {job_id}: {'success' if success else 'failed'}")
        
    except Exception as e:
        print(f"❌ Error in background fetch for job {job_id}: {e}")
        try:
            supabase.table('ads_fetch_jobs')\
                .update({
                    'status': 'failed',
                    'error_message': str(e),
                    'end_time': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })\
                .eq('job_id', job_id)\
                .execute()
        except Exception as update_error:
            print(f"❌ Failed to update job status after error: {update_error}")

@app.route('/api/ads-refresh', methods=['POST', 'OPTIONS'])
def refresh_ads():
    """
    Endpoint called when user clicks refresh button
    Returns: { status, job_id, message, estimated_time }
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    # Get authorization header
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid or expired token'}), 401
    
    # Check if fetcher is available
    if not FETCHER_AVAILABLE:
        return jsonify({
            'error': 'Ads fetching is currently disabled',
            'code': 'FETCHER_NOT_AVAILABLE',
            'message': 'The ads fetcher is not properly configured. Please contact support.',
            'user_id': user_id
        }), 503  # Service Unavailable
    
    # Get request data
    try:
        data = request.get_json() or {}
    except:
        data = {}
    
    platform = data.get('platform', 'all')
    force = data.get('force', False)
    
    # Check if user already has a running job
    if not force:
        running_jobs = supabase.table('ads_fetch_jobs')\
            .select('id')\
            .eq('user_id', user_id)\
            .eq('status', 'running')\
            .execute()
        
        if running_jobs.data and len(running_jobs.data) > 0:
            return jsonify({
                'error': 'You already have an ads fetch in progress',
                'code': 'JOB_ALREADY_RUNNING',
                'existing_jobs': running_jobs.data
            }), 409
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Create job record in database
    if not create_job_record(user_id, job_id, platform):
        return jsonify({'error': 'Failed to create job record in database'}), 500
    
    # Get user's competitors count for estimation
    competitors = get_user_competitors(user_id)
    competitors_count = len(competitors)
    
    # Calculate estimated time (30 seconds per platform per competitor)
    estimated_time = competitors_count * 30
    if platform == 'all':
        estimated_time *= 4  # Assuming 4 platforms
    estimated_time = min(estimated_time, 300)  # Max 5 minutes
    
    # Start ads fetching in background thread
    thread = threading.Thread(
        target=run_background_fetch,
        args=(job_id, user_id, platform),
        daemon=True
    )
    thread.start()
    
    # Return immediate response
    response_data = {
        'status': 'started',
        'job_id': job_id,
        'message': f'Started fetching ads from {platform} for {competitors_count} competitors',
        'estimated_time': estimated_time,
        'competitors_count': competitors_count,
        'platform': platform,
        'start_time': datetime.now(timezone.utc).isoformat(),
        'monitor_url': f'http://localhost:{Config.ADS_STATUS_PORT}/api/ads-status/{job_id}',
        'fetcher_available': FETCHER_AVAILABLE,
        'real_fetching': True  # Always true now (no mock mode)
    }
    
    print(f"✅ Started ads fetch job {job_id} for user {user_id}")
    
    return jsonify(response_data), 202

@app.route('/api/user-jobs', methods=['GET', 'OPTIONS'])
def get_user_jobs():
    """Get all jobs for the current user"""
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    try:
        # Get last 20 jobs for the user
        response = supabase.table('ads_fetch_jobs')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .limit(20)\
            .execute()
        
        # Format jobs for display
        jobs = []
        for job in (response.data if response.data else []):
            formatted_job = job.copy()
            
            # Add status icon
            status = job.get('status', 'unknown')
            icons = {'completed': '✅', 'running': '🔄', 'failed': '❌', 'pending': '⏳'}
            formatted_job['status_icon'] = icons.get(status, '❓')
            
            # Format duration
            duration = job.get('duration_seconds')
            if duration:
                if duration < 60:
                    formatted_job['duration_formatted'] = f"{duration}s"
                elif duration < 3600:
                    minutes = duration // 60
                    seconds = duration % 60
                    formatted_job['duration_formatted'] = f"{minutes}m {seconds}s"
                else:
                    hours = duration // 3600
                    minutes = (duration % 3600) // 60
                    formatted_job['duration_formatted'] = f"{hours}h {minutes}m"
            else:
                formatted_job['duration_formatted'] = 'N/A'
            
            jobs.append(formatted_job)
        
        return jsonify({
            'jobs': jobs,
            'count': len(jobs),
            'has_active_jobs': any(j.get('status') == 'running' for j in jobs),
            'fetcher_available': FETCHER_AVAILABLE
        }), 200
    except Exception as e:
        print(f"Error getting user jobs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/estimate-time', methods=['POST', 'OPTIONS'])
def estimate_time():
    """Estimate how long ads fetching will take"""
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    try:
        data = request.get_json() or {}
    except:
        data = {}
    
    platform = data.get('platform', 'all')
    
    competitors = get_user_competitors(user_id)
    count = len(competitors)
    
    # Estimation logic
    base_time_per_competitor = 30  # seconds
    if platform == 'all':
        platforms_count = 4
    else:
        platforms_count = 1
    
    estimated_seconds = count * base_time_per_competitor * platforms_count
    estimated_seconds = min(estimated_seconds, 300)  # Cap at 5 minutes
    
    return jsonify({
        'estimated_seconds': estimated_seconds,
        'estimated_minutes': round(estimated_seconds / 60, 1),
        'competitors_count': count,
        'platform': platform,
        'platforms_count': platforms_count,
        'realistic_range': {
            'min': max(30, estimated_seconds * 0.5),  # At least 30 seconds
            'max': min(600, estimated_seconds * 1.5)   # Max 10 minutes
        },
        'fetcher_available': FETCHER_AVAILABLE
    }), 200

@app.route('/api/cancel-job/<job_id>', methods=['POST', 'OPTIONS'])
def cancel_job(job_id):
    """Cancel a running job"""
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    try:
        # Verify job belongs to user
        job_response = supabase.table('ads_fetch_jobs')\
            .select('user_id, status')\
            .eq('job_id', job_id)\
            .execute()
        
        if not job_response.data:
            return jsonify({'error': 'Job not found'}), 404
        
        job = job_response.data[0]
        
        if job['user_id'] != user_id:
            return jsonify({'error': 'Unauthorized to cancel this job'}), 403
        
        if job['status'] not in ['pending', 'running']:
            return jsonify({'error': f'Job cannot be cancelled (current status: {job["status"]})'}), 400
        
        # Update job status
        update_response = supabase.table('ads_fetch_jobs')\
            .update({
                'status': 'failed',
                'error_message': 'Cancelled by user',
                'end_time': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })\
            .eq('job_id', job_id)\
            .execute()
        
        return jsonify({
            'success': True,
            'message': 'Job cancelled successfully',
            'job_id': job_id
        }), 200
        
    except Exception as e:
        print(f"Error cancelling job {job_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ads-fetch-config', methods=['GET'])
def get_ads_fetch_config():
    """Get ads fetching configuration"""
    env_ok = False
    node_version = "Unknown"
    npm_version = "Unknown"
    
    if FETCHER_AVAILABLE and ads_fetcher:
        test_results = ads_fetcher.test_connection()
        env_ok = test_results.get('environment_ok', False)
        node_version = test_results.get('node_version', 'Unknown')
        npm_version = test_results.get('npm_version', 'Unknown')
    
    return jsonify({
        'fetcher_available': FETCHER_AVAILABLE,
        'environment_ok': env_ok,
        'node_version': node_version,
        'npm_version': npm_version,
        'ads_fetch_dir': Config.ADS_FETCH_DIR,
        'ads_fetch_dir_exists': os.path.exists(Config.ADS_FETCH_DIR),
        'node_script': Config.NODE_SCRIPT,
        'timeout_seconds': Config.ADS_FETCH_TIMEOUT,
        'supported_platforms': ['meta', 'google', 'linkedin', 'tiktok', 'all'],
        'max_competitors_per_fetch': 50,
        'max_estimated_time': 300,  # 5 minutes
        'mock_mode': False,  # Always false
        'real_fetching_required': True
    }), 200

@app.route('/api/test-fetch', methods=['POST', 'OPTIONS'])
def test_fetch():
    """Test the ads fetcher without creating a job"""
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    if not FETCHER_AVAILABLE:
        return jsonify({
            'success': False,
            'message': 'Ads fetcher not available',
            'real_fetching': False,
            'error': 'AdsFetcher module not properly configured'
        }), 503
    
    try:
        # Run a quick test
        success, logs, ads_count = ads_fetcher.run_for_user(user_id, "meta")
        
        return jsonify({
            'success': success,
            'ads_count': ads_count,
            'has_logs': bool(logs),
            'log_preview': logs[:500] if logs else None,
            'message': 'Test completed successfully' if success else 'Test failed',
            'real_fetching': True
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Test failed with exception',
            'real_fetching': True
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics about ads fetching"""
    try:
        # Total jobs
        total_jobs = supabase.table('ads_fetch_jobs')\
            .select('id', count='exact')\
            .execute()
        
        # Completed jobs
        completed_jobs = supabase.table('ads_fetch_jobs')\
            .select('id', count='exact')\
            .eq('status', 'completed')\
            .execute()
        
        # Total ads fetched
        ads_response = supabase.table('ads_fetch_jobs')\
            .select('ads_fetched')\
            .eq('status', 'completed')\
            .execute()
        
        total_ads = sum([job['ads_fetched'] for job in ads_response.data]) if ads_response.data else 0
        
        # Recent activity
        recent_jobs = supabase.table('ads_fetch_jobs')\
            .select('created_at, status, platform, ads_fetched')\
            .order('created_at', desc=True)\
            .limit(5)\
            .execute()
        
        return jsonify({
            'total_jobs': total_jobs.count if total_jobs.count else 0,
            'completed_jobs': completed_jobs.count if completed_jobs.count else 0,
            'success_rate': (completed_jobs.count / total_jobs.count * 100) if total_jobs.count and total_jobs.count > 0 else 0,
            'total_ads_fetched': total_ads,
            'recent_activity': recent_jobs.data if recent_jobs.data else [],
            'fetcher_available': FETCHER_AVAILABLE,
            'mock_mode': False,
            'service_uptime': datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        print(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print(f"\n{'='*60}")
    print(f"🚀 Starting Ads Refresh Service")
    print(f"{'='*60}")
    print(f"📡 Port: {Config.ADS_REFRESH_PORT}")
    print(f"📁 Ads module path: {Config.ADS_FETCH_DIR}")
    print(f"📁 Path exists: {os.path.exists(Config.ADS_FETCH_DIR)}")
    print(f"🔧 Node script: {Config.NODE_SCRIPT}")
    print(f"⏱️  Timeout: {Config.ADS_FETCH_TIMEOUT}s")
    print(f"{'='*60}")
    
    if FETCHER_AVAILABLE:
        print("✅ AdsFetcher loaded successfully")
        print("🎯 REAL ADS FETCHING ENABLED (NO MOCK MODE)")
    else:
        print("🚫 REAL ADS FETCHING DISABLED")
        print("💡 To enable real ads fetching:")
        print(f"   1. Create ad_fetch_service/ads_fetcher.py")
        print(f"   2. Implement the AdsFetcher class")
        print(f"   3. Restart the service")
    
    print(f"{'='*60}")
    print(f"📊 Available endpoints:")
    print(f"  • POST   /api/ads-refresh     - Start ads fetch")
    print(f"  • GET    /api/user-jobs       - Get user's jobs")
    print(f"  • POST   /api/estimate-time   - Estimate fetch time")
    print(f"  • POST   /api/cancel-job/<id> - Cancel a job")
    print(f"  • GET    /api/ads-fetch-config - Get config")
    print(f"  • POST   /api/test-fetch      - Test fetch")
    print(f"  • GET    /api/stats           - Get statistics")
    print(f"  • GET    /health              - Health check")
    print(f"{'='*60}")
    print(f"⚠️  NO MOCK MODE - Real fetching or nothing")
    print(f"{'='*60}\n")
    
    app.run(host='0.0.0.0', port=Config.ADS_REFRESH_PORT, debug=False, threaded=True)