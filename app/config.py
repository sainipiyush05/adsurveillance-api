"""
Updated configuration for AdSurveillance with Ads Fetching Service
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ========== MAIN PORTS ==========
    MAIN_PORT_1 = int(os.getenv('MAIN_PORT_1', 5010))
    
    # ========== EXISTING SERVICE PORTS ==========
    AUTH_PORT = int(os.getenv('AUTH_PORT', 5003))
    ANALYTICS_PORT = int(os.getenv('ANALYTICS_PORT', 5007))
    DAILY_METRICS_PORT = int(os.getenv('DAILY_METRICS_PORT', 5008))
    COMPETITORS_PORT = int(os.getenv('COMPETITORS_PORT', 5009))
    TARGETING_INTEL_PORT = int(os.getenv('TARGETING_INTEL_PORT', 5011))
    
    # ========== NEW ADS FETCHING SERVICE PORTS ==========
    ADS_REFRESH_PORT = int(os.getenv('ADS_REFRESH_PORT', 5020))
    ADS_STATUS_PORT = int(os.getenv('ADS_STATUS_PORT', 5021))
    
    # ========== JWT CONFIGURATION ==========
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-super-secret-jwt-key-change-this-in-production')
    JWT_ALGORITHM = 'HS256'
    
    # ========== SUPABASE CONFIGURATION ==========
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # ========== ADS FETCHING CONFIG ==========
    # Path to your TypeScript ads fetching module
    ADS_FETCH_DIR = os.path.join(os.path.dirname(__file__), 'src')
    # Node.js command to run (default: 'npm start')
    NODE_SCRIPT = os.getenv('NODE_SCRIPT', 'npm start')
    # Timeout for ads fetching in seconds (default: 5 minutes)
    ADS_FETCH_TIMEOUT = int(os.getenv('ADS_FETCH_TIMEOUT', 300))
    
    # ========== CORS CONFIG ==========
    CORS_ORIGINS = ["*"]  # In production, specify your frontend URL
    CORS_SUPPORTS_CREDENTIALS = True
    
    # ========== DATABASE TABLES ==========
    DB_TABLES = {
        'users': 'users',
        'competitors': 'competitors',
        'advertisements': 'advertisements',
        'daily_metrics': 'daily_metrics',
        'summary_metrics': 'summary_metrics',
        'data_source_logs': 'data_source_logs',
        # New table for tracking ads fetch jobs
        'ads_fetch_jobs': 'ads_fetch_jobs'
    }