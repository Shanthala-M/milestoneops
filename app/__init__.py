from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.routes.projects import projects_bp
    from app.routes.milestones import milestones_bp
    from app.routes.releases import releases_bp
    from app.routes.audit import audit_bp

    app.register_blueprint(projects_bp)
    app.register_blueprint(milestones_bp)
    app.register_blueprint(releases_bp)
    app.register_blueprint(audit_bp)

    return app