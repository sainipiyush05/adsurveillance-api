import os
from flask import Flask
from flask_cors import CORS

from app.api.auth import auth
from app.api.ads_refresh import ads_refresh
from app.api.ads_status import ads_status
from app.api.competitors import competitors
from app.api.daily_metrics import daily_metrics
from app.api.targeting_intel import targeting_intel
from app.api.user_analytics import user_analytics


def create_app():
    app = Flask(__name__)
    CORS(app)

    # Register blueprints
    app.register_blueprint(auth, url_prefix="/auth")
    app.register_blueprint(ads_refresh, url_prefix="/ads-refresh")
    app.register_blueprint(ads_status, url_prefix="/ads-status")
    app.register_blueprint(competitors, url_prefix="/competitors")
    app.register_blueprint(daily_metrics, url_prefix="/daily-metrics")
    app.register_blueprint(targeting_intel, url_prefix="/targeting-intel")
    app.register_blueprint(user_analytics, url_prefix="/user-analytics")

    @app.route("/")
    def root():
        return {
            "service": "AdSurveillance API",
            "status": "running"
        }

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    return app


app = create_app()
