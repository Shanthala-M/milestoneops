import re
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Milestone, Release
from app.audit_helper import log_action

releases_bp = Blueprint(
    "releases", __name__,
    url_prefix="/projects/<int:project_id>/milestones/<int:milestone_id>/releases"
)

VALID_STATUSES = {"Draft", "Pending Approval", "Approved", "Released", "Rolled Back"}

# Enforced state machine: defines which transitions are legally allowed
ALLOWED_TRANSITIONS = {
    "Draft": {"Pending Approval"},
    "Pending Approval": {"Approved", "Draft"},
    "Approved": {"Released", "Pending Approval"},
    "Released": {"Rolled Back"},
    "Rolled Back": {"Draft"},
}


def _validate_release_form(version, status, current_status=None):
    """
    Server-side validation for release form fields including
    workflow state machine enforcement.
    Returns a list of error strings; empty list means valid.
    """
    errors = []
    version = (version or "").strip()

    if not version:
        errors.append("Version is required.")
    elif not re.match(r'^v?\d+\.\d+(\.\d+)?(-[\w\.]+)?$', version):
        errors.append(
            "Version must follow semantic versioning "
            "(e.g. v1.0.0 or 2.3.1-beta)."
        )

    if status not in VALID_STATUSES:
        errors.append("Invalid status value.")

    # Enforce state machine on edits
    if current_status and current_status != status:
        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if status not in allowed:
            errors.append(
                f"Transition from '{current_status}' to '{status}' "
                f"is not permitted. "
                f"Allowed next states: {', '.join(allowed)}."
            )

    return errors


@releases_bp.route("/new", methods=["GET", "POST"])
def create_release(project_id, milestone_id):
    """Create a new release draft for a milestone."""
    milestone = Milestone.query.get_or_404(milestone_id)

    if request.method == "POST":
        version = request.form.get("version", "").strip()
        release_notes = request.form.get("release_notes", "").strip()
        released_by = request.form.get("released_by", "system").strip()
        status = "Draft"  # New releases always start as Draft

        errors = _validate_release_form(version, status)

        # Enforce unique version within the same milestone
        if not errors:
            exists = Release.query.filter_by(
                milestone_id=milestone_id, version=version
            ).first()
            if exists:
                errors.append(
                    f"Release {version} already exists for this milestone."
                )

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "releases/form.html",
                action="Create",
                milestone=milestone,
                form_data=request.form,
                project_id=project_id
            )

        release = Release(
            milestone_id=milestone_id,
            version=version,
            release_notes=release_notes,
            released_by=released_by,
            status=status,
        )
        db.session.add(release)
        db.session.flush()

        log_action(
            entity_type="Release",
            entity_id=release.id,
            action="created",
            changed_by=released_by,
            new_value=version,
            project_id=project_id,
        )

        db.session.commit()
        flash(f'Release {version} created as Draft.', "success")
        return redirect(url_for("projects.view_project", project_id=project_id))

    return render_template(
        "releases/form.html",
        action="Create",
        milestone=milestone,
        form_data={},
        project_id=project_id
    )


@releases_bp.route("/<int:release_id>/edit", methods=["GET", "POST"])
def edit_release(project_id, milestone_id, release_id):
    """
    Edit a release and enforce controlled status transitions
    through the defined state machine.
    """
    milestone = Milestone.query.get_or_404(milestone_id)
    release = Release.query.get_or_404(release_id)

    if request.method == "POST":
        version = request.form.get("version", "").strip()
        release_notes = request.form.get("release_notes", "").strip()
        released_by = request.form.get(
            "released_by", release.released_by or "system"
        ).strip()
        new_status = request.form.get("status", release.status).strip()

        errors = _validate_release_form(
            version, new_status, current_status=release.status
        )

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "releases/form.html",
                action="Edit",
                milestone=milestone,
                release=release,
                form_data=request.form,
                project_id=project_id,
                allowed_transitions=ALLOWED_TRANSITIONS.get(release.status, set())
            )

        # Audit status transitions with full traceability
        if release.status != new_status:
            log_action("Release", release.id, "status_change", released_by,
                       "status", release.status, new_status, project_id)

        if release.version != version:
            log_action("Release", release.id, "updated", released_by,
                       "version", release.version, version, project_id)

        release.version = version
        release.release_notes = release_notes
        release.released_by = released_by
        release.status = new_status

        # Stamp released_at timestamp when transitioning to Released
        if new_status == "Released" and not release.released_at:
            release.released_at = datetime.now(timezone.utc)

        db.session.commit()
        flash(f'Release {version} updated to "{new_status}".', "success")
        return redirect(url_for("projects.view_project", project_id=project_id))

    return render_template(
        "releases/form.html",
        action="Edit",
        milestone=milestone,
        release=release,
        form_data=release,
        project_id=project_id,
        allowed_transitions=ALLOWED_TRANSITIONS.get(release.status, set())
    )


@releases_bp.route("/<int:release_id>/delete", methods=["POST"])
def delete_release(project_id, milestone_id, release_id):
    """Delete a release — only allowed if it is still in Draft status."""
    release = Release.query.get_or_404(release_id)

    if release.status != "Draft":
        flash("Only Draft releases can be deleted.", "danger")
        return redirect(url_for("projects.view_project", project_id=project_id))

    log_action("Release", release.id, "deleted", "system",
               old_value=release.version, project_id=project_id)

    db.session.delete(release)
    db.session.commit()
    flash(f'Release {release.version} deleted.', "warning")
    return redirect(url_for("projects.view_project", project_id=project_id))
