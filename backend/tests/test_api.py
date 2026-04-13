from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.security import get_password_hash
from app.models import Job, JobAssignment, User
from app.models.user import UserRole
from app.services import storage_service


def create_user(session_factory, *, email: str, password: str, role: UserRole, full_name: str) -> User:
    with session_factory() as db:
        user = User(
            email=email,
            password_hash=get_password_hash(password),
            role=role,
            full_name=full_name,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def login(client, *, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_manager_can_create_user_job_and_assignment(client, session_factory):
    create_user(
        session_factory,
        email="manager@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager One",
    )
    manager_headers = login(client, email="manager@example.com", password="secret123")

    create_user_response = client.post(
        "/users",
        headers=manager_headers,
        json={
            "email": "tech@example.com",
            "password": "secret123",
            "role": "technician",
            "technician_code": "TECH-001",
            "full_name": "Tech One",
            "is_active": True,
        },
    )
    assert create_user_response.status_code == 201
    technician_id = create_user_response.json()["id"]
    assert create_user_response.json()["created_at"].endswith("+04:00")
    assert create_user_response.json()["updated_at"].endswith("+04:00")

    create_job_response = client.post(
        "/jobs",
        headers=manager_headers,
        json={
            "title": "Replace filter",
            "description": "Replace rooftop unit filter",
            "technician_instructions": "Bring ladder",
            "internal_notes": "VIP customer",
            "address_line1": "123 Main St",
            "city": "Dubai",
            "state": "Dubai",
            "postal_code": "00000",
            "country": "UAE",
            "priority": "high",
        },
    )
    assert create_job_response.status_code == 201
    job_id = create_job_response.json()["id"]
    assert create_job_response.json()["created_at"].endswith("+04:00")
    assert create_job_response.json()["updated_at"].endswith("+04:00")

    assignment_response = client.post(
        f"/jobs/{job_id}/assignments",
        headers=manager_headers,
        json={"technician_id": technician_id},
    )
    assert assignment_response.status_code == 201
    assert assignment_response.json()["job_id"] == job_id
    assert assignment_response.json()["technician_id"] == technician_id
    assert assignment_response.json()["assigned_at"].endswith("+04:00")


def test_manager_can_filter_and_search_users(client, session_factory):
    create_user(
        session_factory,
        email="manager-user-filter@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager User Filter",
    )
    create_user(
        session_factory,
        email="active-tech@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Active HVAC Tech",
    )
    create_user(
        session_factory,
        email="inactive-admin@example.com",
        password="secret123",
        role=UserRole.ADMIN,
        full_name="Inactive Admin",
    )

    with session_factory() as db:
        active_tech = db.query(User).filter(User.email == "active-tech@example.com").first()
        active_tech.technician_code = "DXB-100"
        inactive_admin = db.query(User).filter(User.email == "inactive-admin@example.com").first()
        inactive_admin.is_active = False
        db.add(active_tech)
        db.add(inactive_admin)
        db.commit()

    manager_headers = login(client, email="manager-user-filter@example.com", password="secret123")

    response = client.get(
        "/users?role=technician&is_active=true&q=DXB",
        headers=manager_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["email"] == "active-tech@example.com"


def test_create_user_rejects_duplicate_technician_code(client, session_factory):
    create_user(
        session_factory,
        email="manager-dup@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Duplicate",
    )
    create_user(
        session_factory,
        email="existing-tech@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Existing Technician",
    )

    with session_factory() as db:
        existing_technician = db.query(User).filter(User.email == "existing-tech@example.com").first()
        existing_technician.technician_code = "TECH-EXISTING"
        db.add(existing_technician)
        db.commit()

    manager_headers = login(client, email="manager-dup@example.com", password="secret123")

    response = client.post(
        "/users",
        headers=manager_headers,
        json={
            "email": "new-tech@example.com",
            "password": "secret123",
            "role": "technician",
            "technician_code": "TECH-EXISTING",
            "full_name": "New Technician",
            "is_active": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Technician code already exists"


def test_create_user_requires_technician_code_for_technicians(client, session_factory):
    create_user(
        session_factory,
        email="manager-valid@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Valid",
    )
    manager_headers = login(client, email="manager-valid@example.com", password="secret123")

    response = client.post(
        "/users",
        headers=manager_headers,
        json={
            "email": "missing-code-tech@example.com",
            "password": "secret123",
            "role": "technician",
            "full_name": "Missing Code Tech",
            "is_active": True,
        },
    )

    assert response.status_code == 422
    assert "Technician code is required for technicians" in response.text


def test_create_user_rejects_technician_code_for_non_technicians(client, session_factory):
    create_user(
        session_factory,
        email="manager-valid-2@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Valid Two",
    )
    manager_headers = login(client, email="manager-valid-2@example.com", password="secret123")

    response = client.post(
        "/users",
        headers=manager_headers,
        json={
            "email": "manager-with-code@example.com",
            "password": "secret123",
            "role": "manager",
            "technician_code": "INVALID-MANAGER-CODE",
            "full_name": "Manager With Code",
            "is_active": True,
        },
    )

    assert response.status_code == 422
    assert "Technician code is only allowed for technicians" in response.text


def test_assigned_technician_can_complete_job_workflow(client, session_factory):
    manager = create_user(
        session_factory,
        email="manager2@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Two",
    )
    technician = create_user(
        session_factory,
        email="tech2@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Two",
    )

    with session_factory() as db:
        job = Job(
            title="Inspect AC",
            address_line1="456 Service Rd",
            city="Dubai",
            state="Dubai",
            postal_code="00001",
            country="UAE",
            created_by_id=manager.id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        assignment = JobAssignment(
            job_id=job.id,
            technician_id=technician.id,
            assigned_by_id=manager.id,
        )
        db.add(assignment)
        db.commit()
        job_id = job.id

    technician_headers = login(client, email="tech2@example.com", password="secret123")

    jobs_response = client.get("/jobs", headers=technician_headers)
    assert jobs_response.status_code == 200
    assert len(jobs_response.json()) == 1
    assert jobs_response.json()[0]["id"] == job_id

    check_in_response = client.post(f"/jobs/{job_id}/check-in", headers=technician_headers)
    assert check_in_response.status_code == 201
    assert check_in_response.json()["event_type"] == "check_in"
    assert check_in_response.json()["occurred_at"].endswith("+04:00")

    check_out_response = client.post(f"/jobs/{job_id}/check-out", headers=technician_headers)
    assert check_out_response.status_code == 201
    assert check_out_response.json()["event_type"] == "check_out"
    assert check_out_response.json()["occurred_at"].endswith("+04:00")

    job_response = client.get(f"/jobs/{job_id}", headers=technician_headers)
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"
    assert job_response.json()["created_at"].endswith("+04:00")
    assert job_response.json()["updated_at"].endswith("+04:00")


def test_job_list_supports_manager_filters_and_search(client, session_factory):
    manager = create_user(
        session_factory,
        email="manager-job-filter@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Job Filter",
    )
    technician = create_user(
        session_factory,
        email="tech-job-filter@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Job Filter",
    )

    manager_headers = login(client, email="manager-job-filter@example.com", password="secret123")

    urgent_job_response = client.post(
        "/jobs",
        headers=manager_headers,
        json={
            "title": "Emergency compressor repair",
            "address_line1": "12 Marina Walk",
            "city": "Dubai",
            "state": "Dubai",
            "postal_code": "10001",
            "country": "UAE",
            "priority": "urgent",
        },
    )
    assert urgent_job_response.status_code == 201
    urgent_job_id = urgent_job_response.json()["id"]

    normal_job_response = client.post(
        "/jobs",
        headers=manager_headers,
        json={
            "title": "Routine inspection",
            "address_line1": "88 Corniche Rd",
            "city": "Abu Dhabi",
            "state": "Abu Dhabi",
            "postal_code": "10002",
            "country": "UAE",
            "priority": "low",
        },
    )
    assert normal_job_response.status_code == 201

    assignment_response = client.post(
        f"/jobs/{urgent_job_id}/assignments",
        headers=manager_headers,
        json={"technician_id": technician.id},
    )
    assert assignment_response.status_code == 201

    response = client.get(
        f"/jobs?priority=urgent&city=Dubai&q=compressor&technician_id={technician.id}",
        headers=manager_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "Emergency compressor repair"


def test_manager_can_remove_assignment_and_revoke_access(client, session_factory):
    manager = create_user(
        session_factory,
        email="manager-unassign@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Unassign",
    )
    technician = create_user(
        session_factory,
        email="tech-unassign@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Unassign",
    )

    with session_factory() as db:
        job = Job(
            title="Unassign technician",
            address_line1="600 Dispatch St",
            city="Dubai",
            state="Dubai",
            postal_code="00008",
            country="UAE",
            created_by_id=manager.id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        assignment = JobAssignment(
            job_id=job.id,
            technician_id=technician.id,
            assigned_by_id=manager.id,
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        job_id = job.id
        assignment_id = assignment.id

    manager_headers = login(client, email="manager-unassign@example.com", password="secret123")
    technician_headers = login(client, email="tech-unassign@example.com", password="secret123")

    remove_response = client.delete(
        f"/jobs/{job_id}/assignments/{assignment_id}",
        headers=manager_headers,
    )
    assert remove_response.status_code == 204

    list_response = client.get(f"/jobs/{job_id}/assignments", headers=manager_headers)
    assert list_response.status_code == 200
    assert list_response.json() == []

    job_response = client.get(f"/jobs/{job_id}", headers=technician_headers)
    assert job_response.status_code == 403
    assert job_response.json()["detail"] == "No access to this job"


def test_technician_can_send_location_and_manager_can_read_latest(client, session_factory):
    manager = create_user(
        session_factory,
        email="manager-location@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Location",
    )
    technician = create_user(
        session_factory,
        email="tech-location@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Location",
    )

    manager_headers = login(client, email="manager-location@example.com", password="secret123")
    technician_headers = login(client, email="tech-location@example.com", password="secret123")

    ping_response = client.post(
        "/locations/me",
        headers=technician_headers,
        json={
            "latitude": 25.2048,
            "longitude": 55.2708,
            "accuracy_meters": 12.5,
        },
    )
    assert ping_response.status_code == 201
    assert ping_response.json()["technician_id"] == technician.id

    latest_response = client.get(
        f"/locations/technicians/{technician.id}/latest",
        headers=manager_headers,
    )
    assert latest_response.status_code == 200
    assert latest_response.json()["latitude"] == 25.2048
    assert latest_response.json()["longitude"] == 55.2708
    assert latest_response.json()["recorded_at"].endswith("+04:00")


def test_manager_can_list_latest_location_per_technician(client, session_factory):
    create_user(
        session_factory,
        email="manager-location-list@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Location List",
    )
    tech_one = create_user(
        session_factory,
        email="tech-location-one@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Location One",
    )
    tech_two = create_user(
        session_factory,
        email="tech-location-two@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Location Two",
    )

    manager_headers = login(client, email="manager-location-list@example.com", password="secret123")
    tech_one_headers = login(client, email="tech-location-one@example.com", password="secret123")
    tech_two_headers = login(client, email="tech-location-two@example.com", password="secret123")

    older_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    newer_time = datetime.now(timezone.utc)

    client.post(
        "/locations/me",
        headers=tech_one_headers,
        json={
            "latitude": 25.1,
            "longitude": 55.1,
            "recorded_at": older_time.isoformat(),
        },
    )
    client.post(
        "/locations/me",
        headers=tech_one_headers,
        json={
            "latitude": 25.2,
            "longitude": 55.2,
            "recorded_at": newer_time.isoformat(),
        },
    )
    client.post(
        "/locations/me",
        headers=tech_two_headers,
        json={
            "latitude": 24.9,
            "longitude": 54.9,
        },
    )

    response = client.get("/locations/technicians/latest", headers=manager_headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["technician_id"] == tech_two.id
    assert payload[0]["latitude"] == 24.9
    assert payload[1]["technician_id"] == tech_one.id
    assert payload[1]["latitude"] == 25.2
    assert payload[1]["technician_name"] == "Tech Location One"
    assert payload[1]["is_stale"] is False


def test_location_endpoints_enforce_roles(client, session_factory):
    create_user(
        session_factory,
        email="manager-location-role@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Location Role",
    )
    technician = create_user(
        session_factory,
        email="tech-location-role@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Location Role",
    )

    manager_headers = login(client, email="manager-location-role@example.com", password="secret123")
    technician_headers = login(client, email="tech-location-role@example.com", password="secret123")

    manager_ping_response = client.post(
        "/locations/me",
        headers=manager_headers,
        json={
            "latitude": 25.0,
            "longitude": 55.0,
        },
    )
    assert manager_ping_response.status_code == 403
    assert manager_ping_response.json()["detail"] == "Technician role required"

    technician_latest_response = client.get(
        f"/locations/technicians/{technician.id}/latest",
        headers=technician_headers,
    )
    assert technician_latest_response.status_code == 403
    assert technician_latest_response.json()["detail"] == "Insufficient permissions"


def test_manager_can_fetch_location_history_with_latest_first(client, session_factory):
    create_user(
        session_factory,
        email="manager-location-history@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Location History",
    )
    technician = create_user(
        session_factory,
        email="tech-location-history@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Location History",
    )

    manager_headers = login(client, email="manager-location-history@example.com", password="secret123")
    technician_headers = login(client, email="tech-location-history@example.com", password="secret123")

    first_time = datetime.now(timezone.utc) - timedelta(minutes=15)
    second_time = datetime.now(timezone.utc) - timedelta(minutes=5)

    first_response = client.post(
        "/locations/me",
        headers=technician_headers,
        json={
            "latitude": 25.3,
            "longitude": 55.3,
            "recorded_at": first_time.isoformat(),
        },
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/locations/me",
        headers=technician_headers,
        json={
            "latitude": 25.4,
            "longitude": 55.4,
            "recorded_at": second_time.isoformat(),
        },
    )
    assert second_response.status_code == 201

    history_response = client.get(
        f"/locations/technicians/{technician.id}/history?limit=1",
        headers=manager_headers,
    )

    assert history_response.status_code == 200
    payload = history_response.json()
    assert len(payload) == 1
    assert payload[0]["latitude"] == 25.4
    assert payload[0]["longitude"] == 55.4


def test_latest_location_can_be_marked_stale(client, session_factory):
    create_user(
        session_factory,
        email="manager-location-stale@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Location Stale",
    )
    technician = create_user(
        session_factory,
        email="tech-location-stale@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Location Stale",
    )

    manager_headers = login(client, email="manager-location-stale@example.com", password="secret123")
    technician_headers = login(client, email="tech-location-stale@example.com", password="secret123")

    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    ping_response = client.post(
        "/locations/me",
        headers=technician_headers,
        json={
            "latitude": 25.5,
            "longitude": 55.5,
            "recorded_at": stale_time.isoformat(),
        },
    )
    assert ping_response.status_code == 201

    latest_response = client.get(
        f"/locations/technicians/{technician.id}/latest",
        headers=manager_headers,
    )

    assert latest_response.status_code == 200
    assert latest_response.json()["technician_name"] == "Tech Location Stale"
    assert latest_response.json()["is_stale"] is True
    assert latest_response.json()["recorded_at"].endswith("+04:00")


def test_latest_location_list_can_exclude_stale_technicians(client, session_factory):
    create_user(
        session_factory,
        email="manager-location-filter@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Location Filter",
    )
    stale_technician = create_user(
        session_factory,
        email="tech-location-filter-old@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Location Filter Old",
    )
    fresh_technician = create_user(
        session_factory,
        email="tech-location-filter-new@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Location Filter New",
    )

    manager_headers = login(client, email="manager-location-filter@example.com", password="secret123")
    stale_headers = login(client, email="tech-location-filter-old@example.com", password="secret123")
    fresh_headers = login(client, email="tech-location-filter-new@example.com", password="secret123")

    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)

    stale_response = client.post(
        "/locations/me",
        headers=stale_headers,
        json={
            "latitude": 25.6,
            "longitude": 55.6,
            "recorded_at": stale_time.isoformat(),
        },
    )
    assert stale_response.status_code == 201

    fresh_response = client.post(
        "/locations/me",
        headers=fresh_headers,
        json={
            "latitude": 25.7,
            "longitude": 55.7,
        },
    )
    assert fresh_response.status_code == 201

    response = client.get(
        "/locations/technicians/latest?include_stale=false",
        headers=manager_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["technician_id"] == fresh_technician.id
    assert payload[0]["is_stale"] is False

    search_response = client.get(
        "/locations/technicians/latest?q=Filter New",
        headers=manager_headers,
    )
    assert search_response.status_code == 200
    search_payload = search_response.json()
    assert len(search_payload) == 1
    assert search_payload[0]["technician_id"] == fresh_technician.id


def test_technician_presence_heartbeat_and_manager_view(client, session_factory):
    create_user(
        session_factory,
        email="manager-presence@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Presence",
    )
    technician = create_user(
        session_factory,
        email="tech-presence@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Presence",
    )

    manager_headers = login(client, email="manager-presence@example.com", password="secret123")
    technician_headers = login(client, email="tech-presence@example.com", password="secret123")

    location_response = client.post(
        "/locations/me",
        headers=technician_headers,
        json={"latitude": 25.8, "longitude": 55.8},
    )
    assert location_response.status_code == 201

    heartbeat_response = client.post("/presence/me/heartbeat", headers=technician_headers)
    assert heartbeat_response.status_code == 201
    assert heartbeat_response.json()["technician_id"] == technician.id
    assert heartbeat_response.json()["is_logged_in"] is True
    assert heartbeat_response.json()["is_online"] is True
    assert heartbeat_response.json()["session_started_at"].endswith("+04:00")
    assert heartbeat_response.json()["last_seen_at"].endswith("+04:00")
    assert heartbeat_response.json()["latest_location"]["latitude"] == 25.8

    manager_view_response = client.get(
        f"/presence/technicians/{technician.id}",
        headers=manager_headers,
    )
    assert manager_view_response.status_code == 200
    assert manager_view_response.json()["technician_name"] == "Tech Presence"
    assert manager_view_response.json()["is_online"] is True


def test_technician_presence_logout_marks_offline(client, session_factory):
    create_user(
        session_factory,
        email="manager-presence-logout@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Presence Logout",
    )
    technician = create_user(
        session_factory,
        email="tech-presence-logout@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Presence Logout",
    )

    manager_headers = login(client, email="manager-presence-logout@example.com", password="secret123")
    technician_headers = login(client, email="tech-presence-logout@example.com", password="secret123")

    heartbeat_response = client.post("/presence/me/heartbeat", headers=technician_headers)
    assert heartbeat_response.status_code == 201

    logout_response = client.post("/presence/me/logout", headers=technician_headers)
    assert logout_response.status_code == 204

    manager_view_response = client.get(
        f"/presence/technicians/{technician.id}",
        headers=manager_headers,
    )
    assert manager_view_response.status_code == 200
    assert manager_view_response.json()["is_logged_in"] is False
    assert manager_view_response.json()["is_online"] is False


def test_manager_can_list_presence_and_filter_offline(client, session_factory):
    create_user(
        session_factory,
        email="manager-presence-list@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Presence List",
    )
    online_technician = create_user(
        session_factory,
        email="tech-presence-online@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Presence Online",
    )
    offline_technician = create_user(
        session_factory,
        email="tech-presence-offline@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Presence Offline",
    )

    manager_headers = login(client, email="manager-presence-list@example.com", password="secret123")
    online_headers = login(client, email="tech-presence-online@example.com", password="secret123")
    offline_headers = login(client, email="tech-presence-offline@example.com", password="secret123")

    online_heartbeat_response = client.post("/presence/me/heartbeat", headers=online_headers)
    assert online_heartbeat_response.status_code == 201
    offline_heartbeat_response = client.post("/presence/me/heartbeat", headers=offline_headers)
    assert offline_heartbeat_response.status_code == 201

    offline_logout_response = client.post("/presence/me/logout", headers=offline_headers)
    assert offline_logout_response.status_code == 204

    all_response = client.get("/presence/technicians", headers=manager_headers)
    assert all_response.status_code == 200
    all_payload = all_response.json()
    assert len(all_payload) == 2
    assert all_payload[0]["technician_id"] == online_technician.id
    assert all_payload[0]["is_online"] is True
    assert all_payload[1]["technician_id"] == offline_technician.id
    assert all_payload[1]["is_online"] is False

    online_only_response = client.get(
        "/presence/technicians?include_offline=false",
        headers=manager_headers,
    )
    assert online_only_response.status_code == 200
    online_only_payload = online_only_response.json()
    assert len(online_only_payload) == 1
    assert online_only_payload[0]["technician_id"] == online_technician.id

    search_response = client.get(
        "/presence/technicians?q=Presence Online",
        headers=manager_headers,
    )
    assert search_response.status_code == 200
    search_payload = search_response.json()
    assert len(search_payload) == 1
    assert search_payload[0]["technician_id"] == online_technician.id


def test_presence_endpoints_enforce_roles(client, session_factory):
    create_user(
        session_factory,
        email="manager-presence-role@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Presence Role",
    )
    technician = create_user(
        session_factory,
        email="tech-presence-role@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Presence Role",
    )

    manager_headers = login(client, email="manager-presence-role@example.com", password="secret123")
    technician_headers = login(client, email="tech-presence-role@example.com", password="secret123")

    manager_heartbeat_response = client.post("/presence/me/heartbeat", headers=manager_headers)
    assert manager_heartbeat_response.status_code == 403
    assert manager_heartbeat_response.json()["detail"] == "Technician role required"

    technician_view_response = client.get(
        f"/presence/technicians/{technician.id}",
        headers=technician_headers,
    )
    assert technician_view_response.status_code == 403
    assert technician_view_response.json()["detail"] == "Insufficient permissions"

def test_job_workflow_rejects_invalid_check_in_and_check_out_sequences(client, session_factory):
    manager = create_user(
        session_factory,
        email="manager-flow@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Flow",
    )
    technician = create_user(
        session_factory,
        email="tech-flow@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Flow",
    )

    with session_factory() as db:
        job = Job(
            title="Sequence validation",
            address_line1="800 Workflow Ave",
            city="Dubai",
            state="Dubai",
            postal_code="00009",
            country="UAE",
            created_by_id=manager.id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        assignment = JobAssignment(
            job_id=job.id,
            technician_id=technician.id,
            assigned_by_id=manager.id,
        )
        db.add(assignment)
        db.commit()
        job_id = job.id

    technician_headers = login(client, email="tech-flow@example.com", password="secret123")

    early_check_out_response = client.post(f"/jobs/{job_id}/check-out", headers=technician_headers)
    assert early_check_out_response.status_code == 400
    assert early_check_out_response.json()["detail"] == "Job must be in progress before check-out"

    first_check_in_response = client.post(f"/jobs/{job_id}/check-in", headers=technician_headers)
    assert first_check_in_response.status_code == 201

    second_check_in_response = client.post(f"/jobs/{job_id}/check-in", headers=technician_headers)
    assert second_check_in_response.status_code == 400
    assert second_check_in_response.json()["detail"] == "Job is already in progress"

    first_check_out_response = client.post(f"/jobs/{job_id}/check-out", headers=technician_headers)
    assert first_check_out_response.status_code == 201

    second_check_out_response = client.post(f"/jobs/{job_id}/check-out", headers=technician_headers)
    assert second_check_out_response.status_code == 400
    assert second_check_out_response.json()["detail"] == "Job is already completed"

    post_completion_check_in_response = client.post(
        f"/jobs/{job_id}/check-in",
        headers=technician_headers,
    )
    assert post_completion_check_in_response.status_code == 400
    assert post_completion_check_in_response.json()["detail"] == "Completed jobs cannot be checked in"


def test_unassigned_technician_cannot_access_job(client, session_factory):
    manager = create_user(
        session_factory,
        email="manager-authz@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Authz",
    )
    assigned_technician = create_user(
        session_factory,
        email="assigned-tech@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Assigned Tech",
    )
    unassigned_technician = create_user(
        session_factory,
        email="unassigned-tech@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Unassigned Tech",
    )

    with session_factory() as db:
        job = Job(
            title="Restricted job",
            address_line1="500 Secure Blvd",
            city="Dubai",
            state="Dubai",
            postal_code="00005",
            country="UAE",
            created_by_id=manager.id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        assignment = JobAssignment(
            job_id=job.id,
            technician_id=assigned_technician.id,
            assigned_by_id=manager.id,
        )
        db.add(assignment)
        db.commit()
        job_id = job.id

    unassigned_headers = login(client, email="unassigned-tech@example.com", password="secret123")

    response = client.get(f"/jobs/{job_id}", headers=unassigned_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "No access to this job"


def test_inactive_user_token_is_rejected(client, session_factory):
    create_user(
        session_factory,
        email="inactive-tech@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Inactive Tech",
    )
    headers = login(client, email="inactive-tech@example.com", password="secret123")

    with session_factory() as db:
        user = db.query(User).filter(User.email == "inactive-tech@example.com").first()
        user.is_active = False
        db.add(user)
        db.commit()

    response = client.get("/users/me", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "User is inactive"


def test_technician_cannot_create_users_or_jobs(client, session_factory):
    create_user(
        session_factory,
        email="tech-authz@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Authz",
    )
    technician_headers = login(client, email="tech-authz@example.com", password="secret123")

    create_user_response = client.post(
        "/users",
        headers=technician_headers,
        json={
            "email": "blocked-user@example.com",
            "password": "secret123",
            "role": "technician",
            "technician_code": "BLOCKED-001",
            "full_name": "Blocked User",
            "is_active": True,
        },
    )
    assert create_user_response.status_code == 403
    assert create_user_response.json()["detail"] == "Insufficient permissions"

    create_job_response = client.post(
        "/jobs",
        headers=technician_headers,
        json={
            "title": "Blocked job",
            "address_line1": "999 Access Rd",
            "city": "Dubai",
            "state": "Dubai",
            "postal_code": "00006",
            "country": "UAE",
        },
    )
    assert create_job_response.status_code == 403
    assert create_job_response.json()["detail"] == "Insufficient permissions"


def test_manager_cannot_check_in_or_out_of_job(client, session_factory):
    manager = create_user(
        session_factory,
        email="manager-role@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Role",
    )

    with session_factory() as db:
        job = Job(
            title="Manager cannot check in",
            address_line1="700 Policy Ln",
            city="Dubai",
            state="Dubai",
            postal_code="00007",
            country="UAE",
            created_by_id=manager.id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

    manager_headers = login(client, email="manager-role@example.com", password="secret123")

    check_in_response = client.post(f"/jobs/{job_id}/check-in", headers=manager_headers)
    assert check_in_response.status_code == 403
    assert check_in_response.json()["detail"] == "Technician role required"

    check_out_response = client.post(f"/jobs/{job_id}/check-out", headers=manager_headers)
    assert check_out_response.status_code == 403
    assert check_out_response.json()["detail"] == "Technician role required"


def test_job_update_photo_upload_and_download(client, session_factory, monkeypatch):
    manager = create_user(
        session_factory,
        email="manager3@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Three",
    )
    technician = create_user(
        session_factory,
        email="tech3@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Three",
    )

    with session_factory() as db:
        job = Job(
            title="Capture site photo",
            address_line1="789 Field Ave",
            city="Dubai",
            state="Dubai",
            postal_code="00002",
            country="UAE",
            created_by_id=manager.id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        assignment = JobAssignment(
            job_id=job.id,
            technician_id=technician.id,
            assigned_by_id=manager.id,
        )
        db.add(assignment)
        db.commit()
        job_id = job.id

    monkeypatch.setattr(
        storage_service,
        "upload_job_update_photo",
        lambda upload_file: f"job-updates/{upload_file.filename}",
    )
    monkeypatch.setattr(
        storage_service,
        "get_download_url",
        lambda object_key, expires_seconds=3600: f"https://example.test/{object_key}",
    )

    technician_headers = login(client, email="tech3@example.com", password="secret123")

    create_update_response = client.post(
        f"/jobs/{job_id}/updates",
        headers=technician_headers,
        json={"message": "Arrived on site"},
    )
    assert create_update_response.status_code == 201
    update_id = create_update_response.json()["id"]
    assert create_update_response.json()["created_at"].endswith("+04:00")

    upload_response = client.post(
        f"/jobs/{job_id}/updates/{update_id}/photos",
        headers=technician_headers,
        files={"file": ("before.jpg", b"image-bytes", "image/jpeg")},
    )
    assert upload_response.status_code == 201
    photo = upload_response.json()
    assert photo["file_key"] == "job-updates/before.jpg"
    assert photo["created_at"].endswith("+04:00")

    download_response = client.get(
        f"/jobs/{job_id}/updates/{update_id}/photos/{photo['id']}/download",
        headers=technician_headers,
    )
    assert download_response.status_code == 200
    assert download_response.json()["download_url"] == "https://example.test/job-updates/before.jpg"


def test_storage_health_endpoint(client, monkeypatch):
    monkeypatch.setattr(storage_service, "is_available", lambda: True)

    response = client.get("/health/storage")

    assert response.status_code == 200
    assert response.json() == {"storage": "ok"}


def test_storage_health_endpoint_reports_unavailable(client, monkeypatch):
    monkeypatch.setattr(storage_service, "is_available", lambda: False)

    response = client.get("/health/storage")

    assert response.status_code == 200
    assert response.json() == {"storage": "unavailable"}


def test_job_update_photo_can_be_deleted(client, session_factory, monkeypatch):
    manager = create_user(
        session_factory,
        email="manager4@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Four",
    )
    technician = create_user(
        session_factory,
        email="tech4@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Four",
    )

    with session_factory() as db:
        job = Job(
            title="Remove outdated photo",
            address_line1="100 Service Way",
            city="Dubai",
            state="Dubai",
            postal_code="00003",
            country="UAE",
            created_by_id=manager.id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        assignment = JobAssignment(
            job_id=job.id,
            technician_id=technician.id,
            assigned_by_id=manager.id,
        )
        db.add(assignment)
        db.commit()
        job_id = job.id

    deleted_keys: list[str] = []
    monkeypatch.setattr(
        storage_service,
        "upload_job_update_photo",
        lambda upload_file: f"job-updates/{upload_file.filename}",
    )
    monkeypatch.setattr(
        storage_service,
        "delete_object",
        lambda object_key: deleted_keys.append(object_key),
    )

    technician_headers = login(client, email="tech4@example.com", password="secret123")

    create_update_response = client.post(
        f"/jobs/{job_id}/updates",
        headers=technician_headers,
        json={"message": "Uploaded the wrong image"},
    )
    assert create_update_response.status_code == 201
    update_id = create_update_response.json()["id"]

    upload_response = client.post(
        f"/jobs/{job_id}/updates/{update_id}/photos",
        headers=technician_headers,
        files={"file": ("wrong.jpg", b"image-bytes", "image/jpeg")},
    )
    assert upload_response.status_code == 201
    photo_id = upload_response.json()["id"]

    delete_response = client.delete(
        f"/jobs/{job_id}/updates/{update_id}/photos/{photo_id}",
        headers=technician_headers,
    )
    assert delete_response.status_code == 204
    assert deleted_keys == ["job-updates/wrong.jpg"]

    list_response = client.get(
        f"/jobs/{job_id}/updates/{update_id}/photos",
        headers=technician_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_job_update_photo_rejects_non_image_uploads(client, session_factory):
    manager = create_user(
        session_factory,
        email="manager5@example.com",
        password="secret123",
        role=UserRole.MANAGER,
        full_name="Manager Five",
    )
    technician = create_user(
        session_factory,
        email="tech5@example.com",
        password="secret123",
        role=UserRole.TECHNICIAN,
        full_name="Tech Five",
    )

    with session_factory() as db:
        job = Job(
            title="Reject invalid attachment",
            address_line1="101 Service Way",
            city="Dubai",
            state="Dubai",
            postal_code="00004",
            country="UAE",
            created_by_id=manager.id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        assignment = JobAssignment(
            job_id=job.id,
            technician_id=technician.id,
            assigned_by_id=manager.id,
        )
        db.add(assignment)
        db.commit()
        job_id = job.id

    technician_headers = login(client, email="tech5@example.com", password="secret123")

    create_update_response = client.post(
        f"/jobs/{job_id}/updates",
        headers=technician_headers,
        json={"message": "Tried to attach a text file"},
    )
    assert create_update_response.status_code == 201
    update_id = create_update_response.json()["id"]

    upload_response = client.post(
        f"/jobs/{job_id}/updates/{update_id}/photos",
        headers=technician_headers,
        files={"file": ("notes.txt", b"not-an-image", "text/plain")},
    )
    assert upload_response.status_code == 400
    assert upload_response.json()["detail"] == "Only image uploads are allowed"
