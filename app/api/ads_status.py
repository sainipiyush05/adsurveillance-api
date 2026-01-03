"""
Ads Status API - Checks status of ads fetching jobs
Port: 5021
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
import os
import sys
import time

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

app = Flask(__name__)
CORS(app, origins=["*"], supports_credentials=True)

# Initialize Supabase
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

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
        'service': 'ads_status',
        'port': Config.ADS_STATUS_PORT,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'endpoints': {
            'status': '/api/ads-status/<job_id>',
            'recent_ads': '/api/recent-ads-updates',
            'job_logs': '/api/job-logs/<job_id>',
            'user_jobs': '/api/user-jobs',
            'dashboard_stats': '/api/dashboard-stats'
        }
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

def parse_timestamp(timestamp):
    """Parse timestamp string to datetime object with UTC timezone"""
    if not timestamp:
        return None
    
    if isinstance(timestamp, str):
        try:
            # Handle ISO format timestamps with or without timezone
            if timestamp.endswith('Z'):
                timestamp = timestamp[:-1] + '+00:00'
            
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            # If datetime is naive (no timezone), make it UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            return dt
        except Exception as e:
            print(f"Error parsing timestamp {timestamp}: {e}")
            return None
    elif isinstance(timestamp, datetime):
        # If it's already a datetime object, ensure it has timezone
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp
    return timestamp

def calculate_progress(job):
    """Calculate progress percentage based on job status and data"""
    status = job.get('status', 'pending')
    
    if status == 'completed':
        return 100
    elif status == 'failed':
        return 0
    elif status == 'running':
        # Estimate based on time elapsed vs estimated time
        start_time = job.get('start_time')
        if start_time:
            start_dt = parse_timestamp(start_time)
            if start_dt:
                # Get current time with timezone (UTC)
                now = datetime.now(timezone.utc)
                
                # Ensure start_dt has timezone
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                
                # Calculate elapsed seconds
                elapsed = (now - start_dt).total_seconds()
                
                # Rough estimation: assume 30 seconds per platform per competitor
                total_competitors = job.get('total_competitors', 1)
                platform = job.get('platform', 'all')
                
                if platform == 'all':
                    platforms_count = 4
                else:
                    platforms_count = 1
                
                estimated_total = total_competitors * 30 * platforms_count
                estimated_total = min(estimated_total, 300)  # Cap at 5 minutes
                
                if estimated_total > 0:
                    progress = min(95, (elapsed / estimated_total) * 100)
                    return round(progress, 1)
    
    return 0 if status == 'pending' else 5

def format_duration(seconds):
    """Format duration in seconds to human readable string"""
    if not seconds:
        return None
    
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}m {seconds}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

def format_job_for_display(job):
    """Format job data for frontend display"""
    formatted = job.copy()
    
    # Add status icon
    status = job.get('status', 'unknown')
    status_icons = {
        'completed': '✅',
        'running': '🔄',
        'failed': '❌',
        'pending': '⏳'
    }
    formatted['status_icon'] = status_icons.get(status, '❓')
    
    # Calculate progress
    formatted['progress'] = calculate_progress(job)
    
    # Format duration
    duration = job.get('duration_seconds')
    if not duration and job.get('end_time') and job.get('start_time'):
        start_dt = parse_timestamp(job['start_time'])
        end_dt = parse_timestamp(job['end_time'])
        if start_dt and end_dt:
            duration = int((end_dt - start_dt).total_seconds())
            formatted['duration_seconds'] = duration
    
    if duration:
        formatted['duration_formatted'] = format_duration(duration)
    
    # Format timestamps for display
    for time_field in ['start_time', 'end_time', 'created_at', 'updated_at']:
        if job.get(time_field):
            dt = parse_timestamp(job[time_field])
            if dt:
                formatted[f'{time_field}_formatted'] = dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Add flags
    formatted['completed'] = status == 'completed'
    formatted['failed'] = status == 'failed'
    formatted['running'] = status == 'running'
    formatted['pending'] = status == 'pending'
    
    # Add platform icons
    platform = job.get('platform', 'all')
    platform_icons = {
        'meta': '📱',
        'google': '🔍',
        'linkedin': '💼',
        'tiktok': '🎵',
        'all': '🌐'
    }
    formatted['platform_icon'] = platform_icons.get(platform, '🌐')
    
    return formatted

@app.route('/api/ads-status/<job_id>', methods=['GET', 'OPTIONS'])
def get_ads_status(job_id):
    """
    Get status of a specific ads fetching job
    Used for polling from frontend
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    # Optional authentication
    auth_header = request.headers.get('Authorization')
    user_id = None
    
    if auth_header:
        user_id = verify_token(auth_header)
    
    try:
        # Get job from database
        response = supabase.table('ads_fetch_jobs')\
            .select('*')\
            .eq('job_id', job_id)\
            .execute()
        
        if not response.data:
            return jsonify({
                'error': 'Job not found',
                'job_id': job_id,
                'exists': False
            }), 404
        
        job = response.data[0]
        
        # Check if user is authorized to view this job
        if user_id and job.get('user_id') != user_id:
            return jsonify({'error': 'Unauthorized to view this job'}), 403
        
        # Format job for display
        formatted_job = format_job_for_display(job)
        
        # Add real-time data for running jobs
        if job.get('status') == 'running':
            # Check if job is stuck (running for more than 10 minutes)
            start_time = parse_timestamp(job.get('start_time'))
            if start_time:
                now = datetime.now(timezone.utc)
                # Ensure start_time has timezone
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                
                running_for = (now - start_time).total_seconds()
                if running_for > 600:  # 10 minutes
                    formatted_job['stuck'] = True
                    formatted_job['warning'] = 'Job has been running for over 10 minutes'
                else:
                    formatted_job['stuck'] = False
        
        return jsonify(formatted_job), 200
        
    except Exception as e:
        print(f"Error getting ads status for job {job_id}: {e}")
        return jsonify({
            'error': str(e),
            'job_id': job_id,
            'status': 'error'
        }), 500

@app.route('/api/batch-status', methods=['POST', 'OPTIONS'])
def get_batch_status():
    """Get status for multiple jobs at once"""
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_header = request.headers.get('Authorization')
    user_id = None
    
    if auth_header:
        user_id = verify_token(auth_header)
    
    try:
        data = request.get_json() or {}
        job_ids = data.get('job_ids', [])
        
        if not job_ids:
            return jsonify({'jobs': [], 'count': 0}), 200
        
        # Get all jobs in one query
        response = supabase.table('ads_fetch_jobs')\
            .select('*')\
            .in_('job_id', job_ids)\
            .execute()
        
        jobs = response.data if response.data else []
        
        # Filter by user if authenticated
        if user_id:
            jobs = [job for job in jobs if job.get('user_id') == user_id]
        
        # Format all jobs
        formatted_jobs = [format_job_for_display(job) for job in jobs]
        
        # Calculate summary
        summary = {
            'total': len(formatted_jobs),
            'completed': sum(1 for j in formatted_jobs if j.get('status') == 'completed'),
            'running': sum(1 for j in formatted_jobs if j.get('status') == 'running'),
            'failed': sum(1 for j in formatted_jobs if j.get('status') == 'failed'),
            'pending': sum(1 for j in formatted_jobs if j.get('status') == 'pending')
        }
        
        return jsonify({
            'jobs': formatted_jobs,
            'summary': summary,
            'count': len(formatted_jobs)
        }), 200
        
    except Exception as e:
        print(f"Error in batch status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user-jobs', methods=['GET', 'OPTIONS'])
def get_user_jobs():
    """Get all jobs for the authenticated user"""
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    try:
        # Get query parameters
        limit = request.args.get('limit', default=20, type=int)
        status = request.args.get('status', default=None)
        platform = request.args.get('platform', default=None)
        days = request.args.get('days', default=30, type=int)
        
        # Calculate date cutoff with timezone
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        # Build query
        query = supabase.table('ads_fetch_jobs')\
            .select('*')\
            .eq('user_id', user_id)\
            .gte('created_at', cutoff_date)\
            .order('created_at', desc=True)\
            .limit(limit)
        
        # Apply filters
        if status:
            query = query.eq('status', status)
        if platform and platform != 'all':
            query = query.eq('platform', platform)
        
        response = query.execute()
        jobs = response.data if response.data else []
        
        # Format jobs
        formatted_jobs = [format_job_for_display(job) for job in jobs]
        
        # Calculate statistics
        stats = {
            'total': len(formatted_jobs),
            'completed': sum(1 for j in formatted_jobs if j.get('status') == 'completed'),
            'running': sum(1 for j in formatted_jobs if j.get('status') == 'running'),
            'failed': sum(1 for j in formatted_jobs if j.get('status') == 'failed'),
            'pending': sum(1 for j in formatted_jobs if j.get('status') == 'pending'),
            'total_ads_fetched': sum(j.get('ads_fetched', 0) for j in formatted_jobs)
        }
        
        return jsonify({
            'jobs': formatted_jobs,
            'stats': stats,
            'count': len(formatted_jobs),
            'filters': {
                'status': status,
                'platform': platform,
                'days': days,
                'limit': limit
            }
        }), 200
        
    except Exception as e:
        print(f"Error getting user jobs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recent-ads-updates', methods=['GET', 'OPTIONS'])
def get_recent_ads_updates():
    """
    Get recent ads fetched for the user from daily_metrics table
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    try:
        # Get query parameters
        limit = request.args.get('limit', default=20, type=int)
        hours = request.args.get('hours', default=24, type=int)
        
        # Get user's competitors
        competitors_response = supabase.table('competitors')\
            .select('id,name')\
            .eq('user_id', user_id)\
            .execute()
        
        competitor_ids = [c['id'] for c in competitors_response.data] if competitors_response.data else []
        
        if not competitor_ids:
            return jsonify({'ads': [], 'count': 0, 'competitors': 0}), 200
        
        # Calculate cutoff time with timezone
        cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        
        # Get recent ads from daily_metrics table
        ads_response = supabase.table('daily_metrics')\
            .select('id, competitor_id, competitor_name, platform, creative, date, daily_spend, daily_impressions, daily_ctr, created_at')\
            .in_('competitor_id', competitor_ids)\
            .gte('created_at', cutoff_time)\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
        
        ads_with_details = []
        for ad in ads_response.data if ads_response.data else []:
            ad_details = ad.copy()
            
            # Use competitor_name from daily_metrics or fetch from competitors table
            competitor_name = ad.get('competitor_name')
            if not competitor_name:
                # Try to get from competitors table
                for comp in competitors_response.data:
                    if comp['id'] == ad['competitor_id']:
                        competitor_name = comp['name']
                        break
            
            ad_details['competitor_name'] = competitor_name or 'Unknown'
            ad_details['competitor_platform'] = ad.get('platform', 'unknown')
            
            # Add platform icon
            platform_icons = {
                'meta': '📱',
                'facebook': '📱',
                'instagram': '📸',
                'google': '🔍',
                'youtube': '📺',
                'linkedin': '💼',
                'tiktok': '🎵'
            }
            ad_details['platform_icon'] = platform_icons.get(ad.get('platform', '').lower(), '🌐')
            
            # Truncate long creative text
            creative = ad.get('creative', '')
            if creative and len(creative) > 200:
                ad_details['creative_preview'] = creative[:200] + '...'
            else:
                ad_details['creative_preview'] = creative
            
            # Add estimated metrics if not present
            if not ad_details.get('estimated_spend') and ad_details.get('daily_spend'):
                ad_details['estimated_spend'] = float(ad_details['daily_spend'])
            
            if not ad_details.get('estimated_impressions') and ad_details.get('daily_impressions'):
                ad_details['estimated_impressions'] = int(ad_details['daily_impressions'])
            
            ads_with_details.append(ad_details)
        
        # Get recent jobs for context
        recent_jobs = supabase.table('ads_fetch_jobs')\
            .select('id, job_id, status, platform, ads_fetched, created_at')\
            .eq('user_id', user_id)\
            .gte('created_at', cutoff_time)\
            .order('created_at', desc=True)\
            .limit(5)\
            .execute()
        
        return jsonify({
            'ads': ads_with_details,
            'count': len(ads_with_details),
            'competitors_count': len(competitor_ids),
            'timeframe_hours': hours,
            'recent_jobs': recent_jobs.data if recent_jobs.data else [],
            'last_updated': datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        print(f"Error getting recent ads updates: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/job-logs/<job_id>', methods=['GET', 'OPTIONS'])
def get_job_logs(job_id):
    """Get detailed logs for a job (if available)"""
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    try:
        response = supabase.table('ads_fetch_jobs')\
            .select('logs, user_id, status, platform, created_at')\
            .eq('job_id', job_id)\
            .execute()
        
        if not response.data:
            return jsonify({'error': 'Job not found'}), 404
        
        job = response.data[0]
        
        # Verify ownership
        if job.get('user_id') != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        logs = job.get('logs')
        
        # Parse logs if they're in a specific format
        parsed_logs = []
        if logs:
            log_lines = logs.split('\n')
            for line in log_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Add log level detection
                log_entry = {'message': line, 'level': 'info'}
                
                if 'ERROR' in line or 'error' in line.lower():
                    log_entry['level'] = 'error'
                elif 'WARNING' in line or 'warning' in line.lower():
                    log_entry['level'] = 'warning'
                elif 'SUCCESS' in line or 'success' in line.lower():
                    log_entry['level'] = 'success'
                elif 'DEBUG' in line:
                    log_entry['level'] = 'debug'
                
                parsed_logs.append(log_entry)
        
        return jsonify({
            'job_id': job_id,
            'logs': logs,
            'parsed_logs': parsed_logs,
            'has_logs': bool(logs),
            'log_line_count': len(parsed_logs),
            'status': job.get('status'),
            'platform': job.get('platform'),
            'created_at': job.get('created_at')
        }), 200
        
    except Exception as e:
        print(f"Error getting job logs for {job_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard-stats', methods=['GET', 'OPTIONS'])
def get_dashboard_stats():
    """Get dashboard statistics for the authenticated user"""
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    try:
        # Calculate date ranges with timezone
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        week_start = (now - timedelta(days=7)).isoformat()
        month_start = (now - timedelta(days=30)).isoformat()
        
        # Get job statistics
        total_jobs = supabase.table('ads_fetch_jobs')\
            .select('id', count='exact')\
            .eq('user_id', user_id)\
            .execute()
        
        today_jobs = supabase.table('ads_fetch_jobs')\
            .select('id', count='exact')\
            .eq('user_id', user_id)\
            .gte('created_at', today_start)\
            .execute()
        
        completed_jobs = supabase.table('ads_fetch_jobs')\
            .select('id, ads_fetched', count='exact')\
            .eq('user_id', user_id)\
            .eq('status', 'completed')\
            .execute()
        
        running_jobs = supabase.table('ads_fetch_jobs')\
            .select('id', count='exact')\
            .eq('user_id', user_id)\
            .eq('status', 'running')\
            .execute()
        
        # Get ads statistics from daily_metrics table
        competitors_response = supabase.table('competitors')\
            .select('id', count='exact')\
            .eq('user_id', user_id)\
            .execute()
        
        competitor_ids = [c['id'] for c in competitors_response.data] if competitors_response.data else []
        total_ads = 0
        total_spend = 0
        total_impressions = 0
        
        if competitor_ids:
            # Count ads in daily_metrics table
            ads_response = supabase.table('daily_metrics')\
                .select('id, daily_spend, daily_impressions', count='exact')\
                .in_('competitor_id', competitor_ids)\
                .execute()
            
            total_ads = ads_response.count if ads_response.count else 0
            
            # Calculate totals if we have data
            if ads_response.data:
                total_spend = sum(float(ad.get('daily_spend', 0) or 0) for ad in ads_response.data)
                total_impressions = sum(int(ad.get('daily_impressions', 0) or 0) for ad in ads_response.data)
        
        # Calculate total ads fetched from jobs
        total_ads_fetched = 0
        if completed_jobs.data:
            total_ads_fetched = sum(job.get('ads_fetched', 0) for job in completed_jobs.data)
        
        # Get platform distribution from jobs
        platform_response = supabase.table('ads_fetch_jobs')\
            .select('platform')\
            .eq('user_id', user_id)\
            .execute()
        
        platform_stats = {}
        if platform_response.data:
            for job in platform_response.data:
                platform = job.get('platform', 'unknown')
                platform_stats[platform] = platform_stats.get(platform, 0) + 1
        
        # Get recent activity
        recent_activity = supabase.table('ads_fetch_jobs')\
            .select('job_id, status, platform, ads_fetched, created_at')\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .limit(5)\
            .execute()
        
        # Format recent activity
        formatted_activity = []
        for job in recent_activity.data if recent_activity.data else []:
            formatted_job = {
                'job_id': job.get('job_id'),
                'status': job.get('status'),
                'platform': job.get('platform'),
                'ads_fetched': job.get('ads_fetched', 0),
                'created_at': job.get('created_at'),
                'status_icon': '✅' if job.get('status') == 'completed' else '🔄' if job.get('status') == 'running' else '❌' if job.get('status') == 'failed' else '⏳'
            }
            formatted_activity.append(formatted_job)
        
        stats = {
            'jobs': {
                'total': total_jobs.count if total_jobs.count else 0,
                'today': today_jobs.count if today_jobs.count else 0,
                'completed': completed_jobs.count if completed_jobs.count else 0,
                'running': running_jobs.count if running_jobs.count else 0,
                'success_rate': (completed_jobs.count / total_jobs.count * 100) if total_jobs.count and total_jobs.count > 0 else 0
            },
            'ads': {
                'total_in_database': total_ads,
                'total_spend': total_spend,
                'total_impressions': total_impressions,
                'total_fetched': total_ads_fetched,
                'average_per_job': total_ads_fetched / completed_jobs.count if completed_jobs.count and completed_jobs.count > 0 else 0,
                'data_source': 'daily_metrics table'
            },
            'competitors': {
                'total': competitors_response.count if competitors_response.count else 0
            },
            'platforms': platform_stats,
            'recent_activity': formatted_activity,
            'timeframes': {
                'today': today_start,
                'last_7_days': week_start,
                'last_30_days': month_start
            }
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup-stuck-jobs', methods=['POST', 'OPTIONS'])
def cleanup_stuck_jobs():
    """Clean up jobs that have been running for too long"""
    if request.method == 'OPTIONS':
        return '', 200
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing authorization header'}), 401
    
    user_id = verify_token(auth_header)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    try:
        # Find jobs running for more than 30 minutes
        cutoff_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        
        stuck_jobs = supabase.table('ads_fetch_jobs')\
            .select('job_id, start_time, platform')\
            .eq('user_id', user_id)\
            .eq('status', 'running')\
            .lt('start_time', cutoff_time)\
            .execute()
        
        if not stuck_jobs.data:
            return jsonify({
                'message': 'No stuck jobs found',
                'cleaned': 0
            }), 200
        
        # Mark them as failed
        job_ids = [job['job_id'] for job in stuck_jobs.data]
        
        update_response = supabase.table('ads_fetch_jobs')\
            .update({
                'status': 'failed',
                'error_message': 'Job was stuck and automatically cleaned up',
                'end_time': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })\
            .in_('job_id', job_ids)\
            .execute()
        
        cleaned_count = len(update_response.data) if update_response.data else 0
        
        return jsonify({
            'message': f'Cleaned up {cleaned_count} stuck jobs',
            'cleaned': cleaned_count,
            'job_ids': job_ids
        }), 200
        
    except Exception as e:
        print(f"Error cleaning up stuck jobs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/check-service', methods=['GET'])
def check_service():
    """Check if ads fetching service is available"""
    try:
        # Try to connect to ads refresh service
        import requests
        refresh_health = requests.get(f'http://localhost:{Config.ADS_REFRESH_PORT}/health', timeout=5)
        
        return jsonify({
            'ads_status_service': 'healthy',
            'ads_refresh_service': 'healthy' if refresh_health.status_code == 200 else 'unhealthy',
            'refresh_service_url': f'http://localhost:{Config.ADS_REFRESH_PORT}',
            'status_service_url': f'http://localhost:{Config.ADS_STATUS_PORT}',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'ads_status_service': 'healthy',
            'ads_refresh_service': 'unavailable',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200

if __name__ == '__main__':
    print(f"\n{'='*60}")
    print(f"🚀 Starting Ads Status Service")
    print(f"{'='*60}")
    print(f"📡 Port: {Config.ADS_STATUS_PORT}")
    print(f"🔌 Connected to Supabase: {Config.SUPABASE_URL[:30]}...")
    print(f"{'='*60}")
    print(f"📊 Available endpoints:")
    print(f"  • GET    /api/ads-status/<job_id>      - Get job status")
    print(f"  • POST   /api/batch-status             - Get multiple job statuses")
    print(f"  • GET    /api/user-jobs               - Get user's jobs")
    print(f"  • GET    /api/recent-ads-updates      - Get recent ads (from daily_metrics)")
    print(f"  • GET    /api/job-logs/<job_id>       - Get job logs")
    print(f"  • GET    /api/dashboard-stats         - Get dashboard stats")
    print(f"  • POST   /api/cleanup-stuck-jobs      - Clean stuck jobs")
    print(f"  • GET    /api/check-service           - Check service health")
    print(f"  • GET    /health                      - Health check")
    print(f"{'='*60}")
    print(f"👤 Token verification: {'Enabled' if Config.SECRET_KEY else 'Disabled'}")
    print(f"🌐 CORS: Enabled for all origins")
    print(f"⏰ Timezone handling: UTC (Fixed naive/aware datetime issue)")
    print(f"📊 Ads source: daily_metrics table (not advertisements table)")
    print(f"{'='*60}\n")
    
    app.run(host='0.0.0.0', port=Config.ADS_STATUS_PORT, debug=False, threaded=True)