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

    check_out_response = client.post(f"/jobs/{job_id}/check-out", headers=technician_headers)
    assert check_out_response.status_code == 201
    assert check_out_response.json()["event_type"] == "check_out"

    job_response = client.get(f"/jobs/{job_id}", headers=technician_headers)
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"


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
