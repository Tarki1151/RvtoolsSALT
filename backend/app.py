"""
RVTools Visualization Backend - Modular Architecture
Flask API server for serving RVTools data

All routes are organized in the routes/ package.
Blueprints: Core, VMs, Datastores, Risks, DR, Hosts, Reports, Optimization.
"""

from flask import Flask
from flask_cors import CORS

# Import utilities
from utils.db import init_db, DATA_DIR

# Import all blueprints
from routes import (
    core_bp, 
    vms_bp, 
    datastores_bp, 
    risks_bp, 
    dr_bp, 
    hosts_bp,
    reports_bp,
    optimization_bp
)


def create_app():
    """Application factory pattern"""
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
    CORS(app)
    
    # Register all modular blueprints
    app.register_blueprint(core_bp)          # /
    app.register_blueprint(vms_bp)           # /api/vms
    app.register_blueprint(datastores_bp)    # /api/datastores
    app.register_blueprint(risks_bp)         # /api/risks
    app.register_blueprint(dr_bp)            # /api/dr-analysis
    app.register_blueprint(hosts_bp)         # /api/hosts-clusters
    app.register_blueprint(reports_bp)       # /api/reports/*
    app.register_blueprint(optimization_bp)  # /api/rightsizing, /api/capacity-planning, etc.
    
    return app


# Create app instance
app = create_app()


if __name__ == '__main__':
    print("=" * 60)
    print("RVTools Visualization Server - Modular Architecture")
    print("=" * 60)
    print(f"Data directory: {DATA_DIR}")
    print()
    print("Registered Blueprints:")
    for bp_name in app.blueprints:
        print(f"  ✓ {bp_name}")
    print()
    print("Initializing database...")
    init_db()
    print()
    print("Starting server on http://0.0.0.0:5050")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5050, debug=False)
