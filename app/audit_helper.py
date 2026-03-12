from app import db
from app.models import AuditLog


def log_action(entity_type, entity_id, action, changed_by="system",
               field_changed=None, old_value=None, new_value=None, project_id=None):
    """
    Write an immutable audit log entry for any entity state change.

    Args:
        entity_type (str): 'Project', 'Milestone', or 'Release'
        entity_id (int): Primary key of the affected entity
        action (str): 'created', 'updated', 'deleted', 'status_change'
        changed_by (str): Username or actor identifier
        field_changed (str): The name of the field that was modified
        old_value (str): Previous value before the change
        new_value (str): New value after the change
        project_id (int): Parent project ID for scoped audit queries
    """
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changed_by=changed_by,
        field_changed=field_changed,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        project_id=project_id,
    )
    db.session.add(entry)
    # Flush so the audit row is part of the same transaction as the main change
    db.session.flush()
    