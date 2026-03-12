from flask import Blueprint, render_template, request
from app.models import AuditLog, Project

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


@audit_bp.route("/")
def audit_log():
    """
    Display the full system-wide audit log with optional filtering
    by project, entity type, and action.
    """
    project_id = request.args.get("project_id", type=int)
    entity_type = request.args.get("entity_type", "")
    action = request.args.get("action", "")

    query = AuditLog.query

    if project_id:
        query = query.filter_by(project_id=project_id)
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if action:
        query = query.filter_by(action=action)

    logs = query.order_by(AuditLog.timestamp.desc()).limit(200).all()
    projects = Project.query.order_by(Project.name).all()

    return render_template(
        "audit/list.html",
        logs=logs,
        projects=projects,
        selected_project=project_id,
        selected_entity=entity_type,
        selected_action=action,
    )
