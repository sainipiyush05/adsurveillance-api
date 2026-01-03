"""
AutoCreate API – Production Entry Point (Railway Compatible)
"""

import os
from flask import Flask
from flask_cors import CORS

# Import all blueprints
from autocreate.api.AutoCreate.audience_step import audience_bp
from autocreate.api.AutoCreate.budget_testing import budget_testing_bp
from autocreate.api.AutoCreate.campaign_goal import campaign_goal_bp
from autocreate.api.AutoCreate.copy_messaging import copy_messaging_bp
from autocreate.api.AutoCreate.creative_assets import creative_assets_bp


def create_app():
    """
    Create and configure the Flask application
    """
    app = Flask(__name__)

    # Enable CORS (lock this down later if needed)
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Register blueprints
    app.register_blueprint(audience_bp)
    app.register_blueprint(budget_testing_bp)
    app.register_blueprint(campaign_goal_bp)
    app.register_blueprint(copy_messaging_bp)
    app.register_blueprint(creative_assets_bp)

    # Root endpoint
    @app.route("/", methods=["GET"])
    def root():
        return {
            "service": "AutoCreate",
            "status": "running",
            "environment": os.getenv("RAILWAY_ENVIRONMENT", "development"),
        }

    # Health check endpoint (Railway uses this implicitly)
    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "healthy"}, 200

    return app


# 🔥 Gunicorn entrypoint (THIS IS WHAT RAILWAY USES)
app = create_app()
