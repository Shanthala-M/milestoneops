import os


class Config:
    """
    Application configuration loaded from environment variables.
    Sensitive values (SECRET_KEY, DATABASE_URL) must never be hardcoded.
    """
    # Secret key for session signing — must be set via environment in production
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

    # PostgreSQL connection string — override via DATABASE_URL env var
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://milestoneops:milestoneops@localhost:5432/milestoneops"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Disable Flask debug mode by default — enable via FLASK_DEBUG=1 locally only
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"


class TestingConfig(Config):
    """Configuration used by the test suite — uses an in-memory SQLite database."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"
    