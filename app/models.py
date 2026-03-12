from datetime import datetime, timezone
from app import db


class Project(db.Model):
    """Represents a software project being tracked."""
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    owner = db.Column(db.String(80), nullable=False)
    status = db.Column(
        db.Enum("Active", "Archived", "On Hold", name="project_status"),
        nullable=False,
        default="Active"
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships — deleting a project deletes its milestones and logs too
    milestones = db.relationship(
        "Milestone", backref="project", lazy=True, cascade="all, delete-orphan"
    )
    audit_logs = db.relationship(
        "AuditLog", backref="project", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Project {self.name}>"


class Milestone(db.Model):
    """Represents a release milestone within a project."""
    __tablename__ = "milestones"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(
        db.Enum(
            "Planned", "In Progress", "Completed", "Blocked", "Cancelled",
            name="milestone_status"
        ),
        nullable=False,
        default="Planned"
    )
    priority = db.Column(
        db.Enum("Low", "Medium", "High", "Critical", name="milestone_priority"),
        nullable=False,
        default="Medium"
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    releases = db.relationship(
        "Release", backref="milestone", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Milestone {self.title}>"

    def is_overdue(self):
        """Return True if the milestone due date has passed and it is not completed."""
        return (
            self.due_date < datetime.now(timezone.utc).date()
            and self.status not in ("Completed", "Cancelled")
        )


class Release(db.Model):
    """Represents a versioned release tied to a milestone."""
    __tablename__ = "releases"

    id = db.Column(db.Integer, primary_key=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey("milestones.id"), nullable=False)
    version = db.Column(db.String(50), nullable=False)
    release_notes = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.Enum(
            "Draft", "Pending Approval", "Approved", "Released", "Rolled Back",
            name="release_status"
        ),
        nullable=False,
        default="Draft"
    )
    released_by = db.Column(db.String(80), nullable=True)
    released_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<Release {self.version}>"


class AuditLog(db.Model):
    """Immutable audit trail for all state changes across the system."""
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(50), nullable=False)
    field_changed = db.Column(db.String(100), nullable=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    changed_by = db.Column(db.String(80), nullable=False, default="system")
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<AuditLog {self.entity_type}#{self.entity_id} {self.action}>"