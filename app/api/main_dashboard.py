"""
Main Dashboard API
Port: 5010
"""
from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app, origins=["*"], supports_credentials=True)

# HTML template for the dashboard
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ad Surveillance Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .service-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }
        .service-card.running { border-color: #4CAF50; }
        .service-card.starting { border-color: #FFC107; }
        .service-card.stopped { border-color: #F44336; }
        .service-name {
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 5px;
        }
        .service-port {
            color: #666;
            font-family: monospace;
        }
        .links {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }
        .link {
            display: inline-block;
            margin-right: 15px;
            padding: 10px 15px;
            background: #4CAF50;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }
        .link:hover {
            background: #45a049;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Ad Surveillance Dashboard</h1>
        <p>Welcome to the Ad Surveillance system. All backend services are running.</p>
        
        <div class="status-grid" id="services-status">
            <!-- Service status will be loaded here -->
        </div>
        
        <div class="links">
            <a href="http://localhost:5020/api/ads-fetch-config" class="link" target="_blank">📊 Ads Fetch Config</a>
            <a href="http://localhost:5020/health" class="link" target="_blank">🩺 Health Check</a>
            <a href="http://localhost:5009/api/competitors" class="link" target="_blank">👥 Competitors</a>
        </div>
        
        <p style="margin-top: 30px; color: #666; font-size: 14px;">
            ⚠️ The main React frontend should be running separately on port 3000.
            This is just a status dashboard for the backend services.
        </p>
    </div>
    
    <script>
        async function loadServices() {
            const services = [
                {name: 'Authentication', port: 5003, path: '/health'},
                {name: 'User Analytics', port: 5007, path: '/health'},
                {name: 'Daily Metrics', port: 5008, path: '/health'},
                {name: 'Competitors', port: 5009, path: '/health'},
                {name: 'Targeting Intel', port: 5011, path: '/health'},
                {name: 'Ads Refresh', port: 5020, path: '/health'},
                {name: 'Ads Status', port: 5021, path: '/health'}
            ];
            
            const container = document.getElementById('services-status');
            container.innerHTML = '';
            
            for (const service of services) {
                const card = document.createElement('div');
                card.className = 'service-card starting';
                
                try {
                    const response = await fetch(`http://localhost:${service.port}${service.path}`);
                    if (response.ok) {
                        card.className = 'service-card running';
                        card.innerHTML = `
                            <div class="service-name">✅ ${service.name}</div>
                            <div class="service-port">Port: ${service.port}</div>
                            <div style="color: #4CAF50; font-size: 12px;">RUNNING</div>
                        `;
                    } else {
                        throw new Error('Not OK');
                    }
                } catch (error) {
                    card.className = 'service-card stopped';
                    card.innerHTML = `
                        <div class="service-name">❌ ${service.name}</div>
                        <div class="service-port">Port: ${service.port}</div>
                        <div style="color: #F44336; font-size: 12px;">NOT RESPONDING</div>
                    `;
                }
                
                container.appendChild(card);
            }
        }
        
        // Load services on page load
        loadServices();
        
        // Refresh every 10 seconds
        setInterval(loadServices, 10000);
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    """Render the main dashboard"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'main_dashboard',
        'port': 5010,
        'timestamp': 'N/A',
        'message': 'Dashboard is running. Check individual services for detailed health.'
    })

if __name__ == '__main__':
    print(f"\n{'='*60}")
    print(f"🚀 Starting Main Dashboard")
    print(f"{'='*60}")
    print(f"📡 Port: 5010")
    print(f"🌐 Dashboard: http://localhost:5010")
    print(f"{'='*60}")
    print(f"📋 This is a status dashboard for backend services.")
    print(f"   The main React frontend should be running separately.")
    print(f"{'='*60}\n")
    
    app.run(debug=False, port=5010, host='0.0.0.0')
