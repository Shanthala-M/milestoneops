import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Project
from app.audit_helper import log_action

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")

# Allowed status values — used for server-side validation
VALID_STATUSES = {"Active", "Archived", "On Hold"}


def _validate_project_form(name, owner, status):
    """
    Server-side input validation for project form fields.
    Returns a list of error strings; empty list means valid.
    """
    errors = []
    name = (name or "").strip()
    owner = (owner or "").strip()

    if not name:
        errors.append("Project name is required.")
    elif len(name) > 120:
        errors.append("Project name must not exceed 120 characters.")
    elif not re.match(r'^[\w\s\-\.]+$', name):
        errors.append("Project name contains invalid characters.")

    if not owner:
        errors.append("Owner is required.")
    elif len(owner) > 80:
        errors.append("Owner name must not exceed 80 characters.")
    elif not re.match(r'^[\w\s\-\.@]+$', owner):
        errors.append("Owner contains invalid characters.")

    if status not in VALID_STATUSES:
        errors.append(f"Invalid status. Choose from: {', '.join(VALID_STATUSES)}.")

    return errors


@projects_bp.route("/")
def list_projects():
    """Display all projects with summary statistics."""
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template("projects/list.html", projects=projects)


@projects_bp.route("/new", methods=["GET", "POST"])
def create_project():
    """Handle creation of a new project with full validation."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        owner = request.form.get("owner", "").strip()
        status = request.form.get("status", "Active").strip()

        errors = _validate_project_form(name, owner, status)

        # Check uniqueness
        if not errors and Project.query.filter_by(name=name).first():
            errors.append("A project with this name already exists.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "projects/form.html",
                action="Create",
                form_data=request.form
            )

        project = Project(name=name, description=description,
                          owner=owner, status=status)
        db.session.add(project)
        db.session.flush()

        log_action(
            entity_type="Project",
            entity_id=project.id,
            action="created",
            changed_by=owner,
            new_value=name,
            project_id=project.id,
        )

        db.session.commit()
        flash(f'Project "{name}" created successfully.', "success")
        return redirect(url_for("projects.list_projects"))

    return render_template("projects/form.html", action="Create", form_data={})


@projects_bp.route("/<int:project_id>")
def view_project(project_id):
    """View a single project with its milestones and recent audit log."""
    project = Project.query.get_or_404(project_id)
    return render_template("projects/detail.html", project=project)


@projects_bp.route("/<int:project_id>/edit", methods=["GET", "POST"])
def edit_project(project_id):
    """Edit an existing project and log all field-level changes."""
    project = Project.query.get_or_404(project_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        owner = request.form.get("owner", "").strip()
        status = request.form.get("status", "Active").strip()

        errors = _validate_project_form(name, owner, status)

        existing = Project.query.filter(
            Project.name == name, Project.id != project_id
        ).first()
        if not errors and existing:
            errors.append("Another project with this name already exists.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "projects/form.html",
                action="Edit",
                form_data=request.form,
                project=project
            )

        # Log each changed field individually for fine-grained audit trail
        if project.name != name:
            log_action("Project", project.id, "updated", owner,
                       "name", project.name, name, project.id)
        if project.status != status:
            log_action("Project", project.id, "status_change", owner,
                       "status", project.status, status, project.id)
        if project.owner != owner:
            log_action("Project", project.id, "updated", owner,
                       "owner", project.owner, owner, project.id)
        if project.description != description:
            log_action("Project", project.id, "updated", owner,
                       "description", project.description, description, project.id)

        project.name = name
        project.description = description
        project.owner = owner
        project.status = status

        db.session.commit()
        flash(f'Project "{name}" updated successfully.', "success")
        return redirect(url_for("projects.view_project", project_id=project.id))

    return render_template(
        "projects/form.html", action="Edit", form_data=project, project=project
    )


@projects_bp.route("/<int:project_id>/delete", methods=["POST"])
def delete_project(project_id):
    """Delete a project and all its related data (cascade)."""
    project = Project.query.get_or_404(project_id)
    name = project.name

    log_action(
        entity_type="Project",
        entity_id=project.id,
        action="deleted",
        changed_by=project.owner,
        old_value=name,
        project_id=project.id,
    )

    db.session.delete(project)
    db.session.commit()
    flash(f'Project "{name}" has been deleted.', "warning")
    return redirect(url_for("projects.list_projects"))
