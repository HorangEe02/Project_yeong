"""Supabase Storage signed URL authorization tests."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.dependencies import get_current_user
from backend.routers import storage as storage_router
from backend.services import supabase_storage as storage_service
from backend.services.supabase_storage import StorageObjectMetadata, record_attachment


def _use_tmp_db(monkeypatch, tmp_path) -> None:
    """Point application DB helpers at a temporary SQLite database.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary path fixture.
    """
    monkeypatch.setenv("APP_DB_BACKEND", "sqlite")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'storage.db'}")


def _user(employee_id: str, role: str = "EMPLOYEE") -> SimpleNamespace:
    """Create a minimal auth context for Storage router tests.

    Args:
        employee_id: Authenticated employee id.
        role: RBAC role name.

    Returns:
        SimpleNamespace: User-like object accepted by router helpers.
    """
    return SimpleNamespace(
        employee_id=employee_id,
        user_id=employee_id,
        username=employee_id,
        role=role,
    )


def _client_for(user: SimpleNamespace) -> TestClient:
    """Create a TestClient with the current user dependency overridden.

    Args:
        user: User-like object returned by the auth dependency.

    Returns:
        TestClient: Router-only FastAPI test client.
    """
    app = FastAPI()
    app.include_router(storage_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def _record_attachment(owner: str = "E001") -> str:
    """Insert one attachment metadata row for authorization tests.

    Args:
        owner: Employee id that owns the attachment.

    Returns:
        str: Inserted attachment id.
    """
    return record_attachment(
        employee_id=owner,
        bucket="ajin-attachments",
        object_path=f"uploads/{owner}/2026/05/18/file.txt",
        content_type="text/plain",
        size_bytes=12,
        metadata={"original_name": "file.txt", "bucket_type": "attachments"},
    )


def _patch_storage_success(monkeypatch) -> None:
    """Patch Supabase Storage calls to simulate an uploaded object.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setattr(storage_router, "storage_object_exists", lambda **_: True)
    monkeypatch.setattr(
        storage_router,
        "get_storage_object_metadata",
        lambda **_: StorageObjectMetadata(
            size_bytes=12,
            content_type="text/plain; charset=utf-8",
            raw={"metadata": {"size": 12, "mimetype": "text/plain"}},
        ),
    )
    monkeypatch.setattr(
        storage_router,
        "create_signed_download_url",
        lambda **kwargs: f"https://signed.example/{kwargs['object_path']}",
    )


def test_owner_can_create_signed_download(monkeypatch, tmp_path) -> None:
    """Attachment owner can receive a signed download URL."""
    _use_tmp_db(monkeypatch, tmp_path)
    attachment_id = _record_attachment(owner="E001")
    _patch_storage_success(monkeypatch)

    response = _client_for(_user("E001")).get(f"/api/storage/signed-download/{attachment_id}")

    assert response.status_code == 200
    assert response.json()["attachment_id"] == attachment_id
    assert response.json()["signed_download_url"].startswith("https://signed.example/")


def test_other_employee_cannot_create_signed_download(monkeypatch, tmp_path) -> None:
    """Different non-admin employee is denied before Storage calls run."""
    _use_tmp_db(monkeypatch, tmp_path)
    attachment_id = _record_attachment(owner="E001")

    def fail_if_called(**_):
        raise AssertionError("Storage should not be called for unauthorized users")

    monkeypatch.setattr(storage_router, "storage_object_exists", fail_if_called)
    monkeypatch.setattr(storage_router, "create_signed_download_url", fail_if_called)

    response = _client_for(_user("E002")).get(f"/api/storage/signed-download/{attachment_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "attachment_forbidden"


def test_admin_can_create_signed_download_for_other_owner(monkeypatch, tmp_path) -> None:
    """SYS_ADMIN can receive a signed URL for another owner's attachment."""
    _use_tmp_db(monkeypatch, tmp_path)
    attachment_id = _record_attachment(owner="E001")
    _patch_storage_success(monkeypatch)

    response = _client_for(_user("ADMIN-001", role="SYS_ADMIN")).get(
        f"/api/storage/signed-download/{attachment_id}"
    )

    assert response.status_code == 200
    assert response.json()["signed_download_url"].startswith("https://signed.example/")


def test_signed_download_missing_attachment_returns_404(monkeypatch, tmp_path) -> None:
    """Missing attachment metadata returns 404."""
    _use_tmp_db(monkeypatch, tmp_path)
    _patch_storage_success(monkeypatch)

    response = _client_for(_user("E001")).get("/api/storage/signed-download/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "attachment_not_found"


def test_complete_upload_owner_with_existing_object(
    monkeypatch,
    tmp_path,
) -> None:
    """Owner can complete an upload only after the object exists."""
    _use_tmp_db(monkeypatch, tmp_path)
    attachment_id = _record_attachment(owner="E001")
    _patch_storage_success(monkeypatch)

    response = _client_for(_user("E001")).post(
        "/api/storage/complete-upload",
        json={"attachment_id": attachment_id},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["signed_download_url"].startswith("https://signed.example/")
    metadata = storage_service.get_attachment(attachment_id)["metadata"]
    assert metadata["actual_size_bytes"] == 12
    assert metadata["actual_content_type"] == "text/plain"


def test_complete_upload_other_employee_is_forbidden_before_storage(monkeypatch, tmp_path) -> None:
    """Complete-upload denies non-owners before object lookup or signed URL creation."""
    _use_tmp_db(monkeypatch, tmp_path)
    attachment_id = _record_attachment(owner="E001")

    def fail_if_called(**_):
        raise AssertionError("Storage should not be called for unauthorized users")

    monkeypatch.setattr(storage_router, "storage_object_exists", fail_if_called)
    monkeypatch.setattr(storage_router, "get_storage_object_metadata", fail_if_called)
    monkeypatch.setattr(storage_router, "create_signed_download_url", fail_if_called)

    response = _client_for(_user("E002")).post(
        "/api/storage/complete-upload",
        json={"attachment_id": attachment_id},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "attachment_forbidden"


def test_complete_upload_missing_storage_object_returns_409(monkeypatch, tmp_path) -> None:
    """Complete-upload does not issue a signed URL when the object is missing."""
    _use_tmp_db(monkeypatch, tmp_path)
    attachment_id = _record_attachment(owner="E001")
    monkeypatch.setattr(storage_router, "get_storage_object_metadata", lambda **_: None)

    def fail_if_called(**_):
        raise AssertionError("Signed URL should not be issued for missing objects")

    monkeypatch.setattr(storage_router, "create_signed_download_url", fail_if_called)

    response = _client_for(_user("E001")).post(
        "/api/storage/complete-upload",
        json={"attachment_id": attachment_id},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "upload_not_found"


def test_complete_upload_size_mismatch_returns_409(monkeypatch, tmp_path) -> None:
    """Complete-upload rejects a Storage object whose actual size differs."""
    _use_tmp_db(monkeypatch, tmp_path)
    attachment_id = _record_attachment(owner="E001")
    monkeypatch.setattr(
        storage_router,
        "get_storage_object_metadata",
        lambda **_: StorageObjectMetadata(
            size_bytes=13,
            content_type="text/plain",
            raw={"metadata": {"size": 13, "mimetype": "text/plain"}},
        ),
    )

    def fail_if_called(**_):
        raise AssertionError("Signed URL should not be issued for metadata mismatch")

    monkeypatch.setattr(storage_router, "create_signed_download_url", fail_if_called)

    response = _client_for(_user("E001")).post(
        "/api/storage/complete-upload",
        json={"attachment_id": attachment_id},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "upload_size_mismatch"


def test_complete_upload_content_type_mismatch_returns_409(monkeypatch, tmp_path) -> None:
    """Complete-upload rejects a Storage object whose MIME type differs."""
    _use_tmp_db(monkeypatch, tmp_path)
    attachment_id = _record_attachment(owner="E001")
    monkeypatch.setattr(
        storage_router,
        "get_storage_object_metadata",
        lambda **_: StorageObjectMetadata(
            size_bytes=12,
            content_type="application/pdf",
            raw={"metadata": {"size": 12, "mimetype": "application/pdf"}},
        ),
    )

    def fail_if_called(**_):
        raise AssertionError("Signed URL should not be issued for metadata mismatch")

    monkeypatch.setattr(storage_router, "create_signed_download_url", fail_if_called)

    response = _client_for(_user("E001")).post(
        "/api/storage/complete-upload",
        json={"attachment_id": attachment_id},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "upload_content_type_mismatch"


def test_complete_upload_unavailable_metadata_returns_409(monkeypatch, tmp_path) -> None:
    """Complete-upload rejects objects when Supabase omits size or content type."""
    _use_tmp_db(monkeypatch, tmp_path)
    attachment_id = _record_attachment(owner="E001")
    monkeypatch.setattr(
        storage_router,
        "get_storage_object_metadata",
        lambda **_: StorageObjectMetadata(size_bytes=None, content_type="", raw={}),
    )

    def fail_if_called(**_):
        raise AssertionError("Signed URL should not be issued without object metadata")

    monkeypatch.setattr(storage_router, "create_signed_download_url", fail_if_called)

    response = _client_for(_user("E001")).post(
        "/api/storage/complete-upload",
        json={"attachment_id": attachment_id},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "upload_metadata_unavailable"


def test_signed_download_missing_storage_object_returns_404(monkeypatch, tmp_path) -> None:
    """Signed-download returns 404 when metadata exists but Storage object is missing."""
    _use_tmp_db(monkeypatch, tmp_path)
    attachment_id = _record_attachment(owner="E001")
    monkeypatch.setattr(storage_router, "storage_object_exists", lambda **_: False)

    def fail_if_called(**_):
        raise AssertionError("Signed URL should not be issued for missing objects")

    monkeypatch.setattr(storage_router, "create_signed_download_url", fail_if_called)

    response = _client_for(_user("E001")).get(f"/api/storage/signed-download/{attachment_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "storage_object_not_found"


def test_storage_configuration_errors_still_map_to_503(monkeypatch, tmp_path) -> None:
    """Storage configuration failures keep the existing 503 mapping."""
    _use_tmp_db(monkeypatch, tmp_path)
    attachment_id = _record_attachment(owner="E001")

    def raise_config_error(**_):
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")

    monkeypatch.setattr(storage_router, "storage_object_exists", raise_config_error)

    response = _client_for(_user("E001")).get(f"/api/storage/signed-download/{attachment_id}")

    assert response.status_code == 503
    assert "SUPABASE_URL" in response.json()["detail"]


def test_create_signed_upload_url_uses_storage3_options_object(monkeypatch) -> None:
    """Signed upload URL creation passes the options shape expected by storage3."""
    captured: dict[str, object] = {}

    class BucketApi:
        """Minimal Supabase bucket API test double."""

        def create_signed_upload_url(self, object_path: str, options=None) -> dict[str, str]:
            """Capture signed-upload arguments and return a Supabase-like response.

            Args:
                object_path: Bucket-relative path sent to Supabase Storage.
                options: Signed-upload options passed by the service helper.

            Returns:
                dict[str, str]: Supabase-like signed upload URL payload.
            """
            captured["object_path"] = object_path
            captured["options"] = options
            return {
                "signedUrl": "/object/upload/sign/ajin-attachments/folder/file.txt?token=test-token",
                "token": "test-token",
                "path": object_path,
            }

    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")
    storage_api = SimpleNamespace(from_=lambda bucket: BucketApi())
    monkeypatch.setattr(storage_service, "_client", lambda: SimpleNamespace(storage=storage_api))

    result = storage_service.create_signed_upload_url(
        bucket="ajin-attachments",
        object_path="folder/file.txt",
        upsert=True,
    )

    assert result["signed_url"].startswith("https://project.supabase.co/storage/v1/")
    assert captured["object_path"] == "folder/file.txt"
    assert getattr(captured["options"], "upsert", None) == "true"
    assert captured["options"]["upsert"] == "true"  # type: ignore[index]


def test_storage_object_exists_uses_client_exists(monkeypatch) -> None:
    """Storage existence helper prefers the current storage3 exists method."""
    calls: list[str] = []

    def exists(path: str) -> bool:
        calls.append(path)
        return True

    bucket_api = SimpleNamespace(exists=exists)
    storage_api = SimpleNamespace(from_=lambda bucket: bucket_api)
    monkeypatch.setattr(storage_service, "_client", lambda: SimpleNamespace(storage=storage_api))

    assert storage_service.storage_object_exists(
        bucket="ajin-attachments",
        object_path="folder/file.txt",
    )
    assert calls == ["folder/file.txt"]


def test_storage_object_exists_falls_back_to_list(monkeypatch) -> None:
    """Storage existence helper can fall back to exact-name list search."""

    def list_files(path: str, options: dict) -> list[dict]:
        assert path == "folder/sub"
        assert options["search"] == "file.txt"
        return [{"name": "file.txt"}, {"name": "other.txt"}]

    bucket_api = SimpleNamespace(list=list_files)
    storage_api = SimpleNamespace(from_=lambda bucket: bucket_api)
    monkeypatch.setattr(storage_service, "_client", lambda: SimpleNamespace(storage=storage_api))

    assert storage_service.storage_object_exists(
        bucket="ajin-attachments",
        object_path="folder/sub/file.txt",
    )


def test_get_storage_object_metadata_falls_back_to_list(monkeypatch) -> None:
    """Storage metadata helper normalizes exact-name list results."""

    def list_files(path: str, options: dict) -> list[dict]:
        assert path == "folder/sub"
        assert options["search"] == "file.txt"
        return [
            {"name": "other.txt", "metadata": {"size": 1, "mimetype": "text/plain"}},
            {
                "name": "file.txt",
                "metadata": {"size": "12", "mimetype": "text/plain; charset=utf-8"},
            },
        ]

    bucket_api = SimpleNamespace(list=list_files)
    storage_api = SimpleNamespace(from_=lambda bucket: bucket_api)
    monkeypatch.setattr(storage_service, "_client", lambda: SimpleNamespace(storage=storage_api))

    metadata = storage_service.get_storage_object_metadata(
        bucket="ajin-attachments",
        object_path="folder/sub/file.txt",
    )

    assert metadata is not None
    assert metadata.size_bytes == 12
    assert metadata.content_type == "text/plain; charset=utf-8"


def test_storage_object_exists_returns_false_for_not_found(monkeypatch) -> None:
    """Storage existence helper treats 404-style Storage errors as missing."""

    def exists(path: str) -> bool:
        exc = RuntimeError(f"not found: {path}")
        exc.status_code = 404
        raise exc

    bucket_api = SimpleNamespace(exists=exists)
    storage_api = SimpleNamespace(from_=lambda bucket: bucket_api)
    monkeypatch.setattr(storage_service, "_client", lambda: SimpleNamespace(storage=storage_api))

    assert not storage_service.storage_object_exists(
        bucket="ajin-attachments",
        object_path="folder/file.txt",
    )
