from app import create_app, db
from app.models import Project, Milestone, Release, AuditLog

app = create_app()


@app.shell_context_processor
def make_shell_context():
    """Expose models in the Flask shell for easy debugging."""
    return {
        "db": db,
        "Project": Project,
        "Milestone": Milestone,
        "Release": Release,
        "AuditLog": AuditLog,
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    