import os
from flask import Flask
from flask_cors import CORS

# Import blueprints from existing modules
from app.api.auth import auth_bp
from app.api.ads_refresh import ads_refresh_bp
from app.api.ads_status import ads_status_bp
from app.api.competitors import competitors_bp
from app.api.daily_metrics import daily_metrics_bp
from app.api.main_dashboard import dashboard_bp
from app.api.targeting_intel import targeting_intel_bp
from app.api.user_analytics import user_analytics_bp


def create_app():
    app = Flask(__name__)
    CORS(app)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(ads_refresh_bp)
    app.register_blueprint(ads_status_bp)
    app.register_blueprint(competitors_bp)
    app.register_blueprint(daily_metrics_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(targeting_intel_bp)
    app.register_blueprint(user_analytics_bp)

    @app.route("/")
    def root():
        return {
            "service": "AdSurveillance API",
            "status": "running",
            "environment": os.getenv("RAILWAY_ENVIRONMENT", "development")
        }

    @app.route("/health")
    def health():
        return {"status": "healthy"}, 200

    return app


# Gunicorn entry point
app = create_app()
