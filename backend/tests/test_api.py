from __future__ import annotations

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

    assignment_response = client.post(
        f"/jobs/{job_id}/assignments",
        headers=manager_headers,
        json={"technician_id": technician_id},
    )
    assert assignment_response.status_code == 201
    assert assignment_response.json()["job_id"] == job_id
    assert assignment_response.json()["technician_id"] == technician_id


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

    check_out_response = client.post(f"/jobs/{job_id}/check-out", headers=technician_headers)
    assert check_out_response.status_code == 201
    assert check_out_response.json()["event_type"] == "check_out"

    job_response = client.get(f"/jobs/{job_id}", headers=technician_headers)
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"


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

    upload_response = client.post(
        f"/jobs/{job_id}/updates/{update_id}/photos",
        headers=technician_headers,
        files={"file": ("before.jpg", b"image-bytes", "image/jpeg")},
    )
    assert upload_response.status_code == 201
    photo = upload_response.json()
    assert photo["file_key"] == "job-updates/before.jpg"

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
