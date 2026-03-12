import re
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Project, Milestone
from app.audit_helper import log_action

milestones_bp = Blueprint(
    "milestones", __name__,
    url_prefix="/projects/<int:project_id>/milestones"
)

VALID_STATUSES = {"Planned", "In Progress", "Completed", "Blocked", "Cancelled"}
VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}


def _validate_milestone_form(title, due_date_str, status, priority):
    """
    Server-side validation for milestone form fields.
    Returns a list of error strings; empty list means valid.
    """
    errors = []
    title = (title or "").strip()

    if not title:
        errors.append("Milestone title is required.")
    elif len(title) > 200:
        errors.append("Title must not exceed 200 characters.")
    elif not re.match(r'^[\w\s\-\.\,\(\)\/]+$', title):
        errors.append("Title contains invalid characters.")

    if not due_date_str:
        errors.append("Due date is required.")
    else:
        try:
            date.fromisoformat(due_date_str)
        except ValueError:
            errors.append("Due date must be a valid date (YYYY-MM-DD).")

    if status not in VALID_STATUSES:
        errors.append(f"Invalid status. Choose from: {', '.join(VALID_STATUSES)}.")

    if priority not in VALID_PRIORITIES:
        errors.append(f"Invalid priority. Choose from: {', '.join(VALID_PRIORITIES)}.")

    return errors


@milestones_bp.route("/new", methods=["GET", "POST"])
def create_milestone(project_id):
    """Create a new milestone within a project."""
    project = Project.query.get_or_404(project_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date_str = request.form.get("due_date", "").strip()
        status = request.form.get("status", "Planned").strip()
        priority = request.form.get("priority", "Medium").strip()

        errors = _validate_milestone_form(title, due_date_str, status, priority)

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "milestones/form.html",
                action="Create",
                project=project,
                form_data=request.form
            )

        milestone = Milestone(
            project_id=project_id,
            title=title,
            description=description,
            due_date=date.fromisoformat(due_date_str),
            status=status,
            priority=priority,
        )
        db.session.add(milestone)
        db.session.flush()

        log_action(
            entity_type="Milestone",
            entity_id=milestone.id,
            action="created",
            new_value=title,
            project_id=project_id,
        )

        db.session.commit()
        flash(f'Milestone "{title}" created.', "success")
        return redirect(url_for("projects.view_project", project_id=project_id))

    return render_template(
        "milestones/form.html", action="Create", project=project, form_data={}
    )


@milestones_bp.route("/<int:milestone_id>/edit", methods=["GET", "POST"])
def edit_milestone(project_id, milestone_id):
    """Edit an existing milestone and record all field-level changes."""
    project = Project.query.get_or_404(project_id)
    milestone = Milestone.query.get_or_404(milestone_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date_str = request.form.get("due_date", "").strip()
        status = request.form.get("status", "Planned").strip()
        priority = request.form.get("priority", "Medium").strip()

        errors = _validate_milestone_form(title, due_date_str, status, priority)

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "milestones/form.html",
                action="Edit",
                project=project,
                milestone=milestone,
                form_data=request.form
            )

        new_due_date = date.fromisoformat(due_date_str)

        # Audit each individual field change
        if milestone.title != title:
            log_action("Milestone", milestone.id, "updated", "system",
                       "title", milestone.title, title, project_id)
        if milestone.status != status:
            log_action("Milestone", milestone.id, "status_change", "system",
                       "status", milestone.status, status, project_id)
        if milestone.priority != priority:
            log_action("Milestone", milestone.id, "updated", "system",
                       "priority", milestone.priority, priority, project_id)
        if milestone.due_date != new_due_date:
            log_action("Milestone", milestone.id, "updated", "system",
                       "due_date", str(milestone.due_date), str(new_due_date), project_id)

        milestone.title = title
        milestone.description = description
        milestone.due_date = new_due_date
        milestone.status = status
        milestone.priority = priority

        db.session.commit()
        flash(f'Milestone "{title}" updated.', "success")
        return redirect(url_for("projects.view_project", project_id=project_id))

    return render_template(
        "milestones/form.html",
        action="Edit",
        project=project,
        milestone=milestone,
        form_data=milestone
    )


@milestones_bp.route("/<int:milestone_id>/delete", methods=["POST"])
def delete_milestone(project_id, milestone_id):
    """Delete a milestone and its associated releases."""
    milestone = Milestone.query.get_or_404(milestone_id)
    title = milestone.title

    log_action("Milestone", milestone.id, "deleted", "system",
               old_value=title, project_id=project_id)

    db.session.delete(milestone)
    db.session.commit()
    flash(f'Milestone "{title}" deleted.', "warning")
    return redirect(url_for("projects.view_project", project_id=project_id))