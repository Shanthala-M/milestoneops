"""
Test suite for the MilestoneOps application.
Uses an in-memory SQLite database via TestingConfig so no
PostgreSQL is needed in CI.
"""
import pytest
from app import create_app, db
from app.models import Project, Milestone, Release, AuditLog
from config import TestingConfig


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Create a fresh app instance for each test."""
    application = create_app(TestingConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Provide a test client for HTTP-level testing."""
    return app.test_client()


@pytest.fixture
def sample_project(app):
    """Insert a sample project into the test database."""
    with app.app_context():
        p = Project(
            name="Test Project",
            owner="tester",
            status="Active",
            description="A project for testing."
        )
        db.session.add(p)
        db.session.commit()
        return p.id


# ── Project Tests ─────────────────────────────────────────────────────────

class TestProjectRoutes:

    def test_list_projects_empty(self, client):
        """GET /projects/ returns 200 with empty state."""
        response = client.get("/projects/")
        assert response.status_code == 200

    def test_create_project_valid(self, client):
        """POST with valid data creates a project and redirects."""
        response = client.post("/projects/new", data={
            "name": "Alpha Service",
            "owner": "alice",
            "status": "Active",
            "description": "Test description"
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Alpha Service" in response.data

    def test_create_project_missing_name(self, client):
        """POST without a name is rejected with a validation error."""
        response = client.post("/projects/new", data={
            "name": "",
            "owner": "alice",
            "status": "Active"
        })
        assert response.status_code == 200
        assert b"required" in response.data.lower()

    def test_create_project_invalid_status(self, client):
        """POST with an invalid status value is rejected."""
        response = client.post("/projects/new", data={
            "name": "Bad Status Project",
            "owner": "alice",
            "status": "INVALID_STATUS"
        })
        assert response.status_code == 200
        assert b"Invalid status" in response.data

    def test_create_project_duplicate_name(self, client, sample_project):
        """POST with a duplicate project name is rejected."""
        response = client.post("/projects/new", data={
            "name": "Test Project",
            "owner": "bob",
            "status": "Active"
        })
        assert b"already exists" in response.data

    def test_view_project(self, client, sample_project):
        """GET /projects/<id> returns the project detail page."""
        response = client.get(f"/projects/{sample_project}")
        assert response.status_code == 200

    def test_edit_project(self, client, sample_project):
        """POST to edit route updates the project."""
        response = client.post(
            f"/projects/{sample_project}/edit",
            data={
                "name": "Test Project",
                "owner": "tester",
                "status": "On Hold",
                "description": "Updated."
            },
            follow_redirects=True
        )
        assert response.status_code == 200

    def test_delete_project(self, client, sample_project):
        """POST to delete route removes the project."""
        response = client.post(
            f"/projects/{sample_project}/delete",
            follow_redirects=True
        )
        assert response.status_code == 200
        assert Project.query.get(sample_project) is None

    def test_view_nonexistent_project_returns_404(self, client):
        """GET /projects/9999 returns 404."""
        response = client.get("/projects/9999")
        assert response.status_code == 404


# ── Milestone Tests ───────────────────────────────────────────────────────

class TestMilestoneRoutes:

    def test_create_milestone_valid(self, client, sample_project):
        """POST with valid milestone data creates a milestone."""
        response = client.post(
            f"/projects/{sample_project}/milestones/new",
            data={
                "title": "Beta Release",
                "due_date": "2026-06-30",
                "status": "Planned",
                "priority": "High",
                "description": "First beta milestone."
            },
            follow_redirects=True
        )
        assert response.status_code == 200

    def test_create_milestone_missing_due_date(self, client, sample_project):
        """POST without a due date is rejected."""
        response = client.post(
            f"/projects/{sample_project}/milestones/new",
            data={
                "title": "No Date",
                "due_date": "",
                "status": "Planned",
                "priority": "Low"
            }
        )
        assert b"required" in response.data.lower()

    def test_create_milestone_invalid_priority(self, client, sample_project):
        """POST with invalid priority is rejected."""
        response = client.post(
            f"/projects/{sample_project}/milestones/new",
            data={
                "title": "Bad Priority",
                "due_date": "2026-06-01",
                "status": "Planned",
                "priority": "ULTRA"
            }
        )
        assert b"Invalid priority" in response.data


# ── Release Tests ─────────────────────────────────────────────────────────

class TestReleaseWorkflow:

    @pytest.fixture
    def sample_milestone(self, app, sample_project):
        """Insert a sample milestone for release tests."""
        with app.app_context():
            from datetime import date
            ms = Milestone(
                project_id=sample_project,
                title="M1",
                due_date=date(2026, 6, 1),
                status="Planned",
                priority="Medium"
            )
            db.session.add(ms)
            db.session.commit()
            return ms.id

    def test_create_release_draft(self, client, sample_project, sample_milestone):
        """New releases are always created with Draft status."""
        client.post(
            f"/projects/{sample_project}/milestones/{sample_milestone}/releases/new",
            data={
                "version": "v1.0.0",
                "release_notes": "Initial.",
                "released_by": "alice"
            },  
            follow_redirects=True
        )
        release = Release.query.first()
        assert release is not None
        assert release.status == "Draft"

    def test_release_invalid_version_format(self, client, sample_project,
                                            sample_milestone):
        """Invalid semantic version string is rejected."""
        response = client.post(
            f"/projects/{sample_project}/milestones/{sample_milestone}/releases/new",
            data={
                "version": "not-a-version",
                "released_by": "alice"
            }
        )
        assert b"semantic versioning" in response.data

    def test_invalid_state_transition_blocked(self, client, app,
                                              sample_project, sample_milestone):
        """Direct Draft to Released transition is blocked by state machine."""
        with app.app_context():
            r = Release(
                milestone_id=sample_milestone,
                version="v1.0.0",
                status="Draft"
            )
            db.session.add(r)
            db.session.commit()
            rid = r.id

        response = client.post(
            f"/projects/{sample_project}/milestones/"
            f"{sample_milestone}/releases/{rid}/edit",
            data={
                "version": "v1.0.0",
                "status": "Released",
                "released_by": "alice"
            }
        )
        assert b"not permitted" in response.data


# ── Audit Log Tests ───────────────────────────────────────────────────────

class TestAuditLog:

    def test_audit_log_page_loads(self, client):
        """GET /audit/ returns 200."""
        response = client.get("/audit/")
        assert response.status_code == 200

    def test_audit_entry_created_on_project_creation(self, client):
        """Creating a project writes an audit log entry."""
        client.post("/projects/new", data={
            "name": "Audited Project",
            "owner": "tester",
            "status": "Active"
        }, follow_redirects=True)
        assert AuditLog.query.count() >= 1
        log = AuditLog.query.first()
        assert log.action == "created"
        assert log.entity_type == "Project"