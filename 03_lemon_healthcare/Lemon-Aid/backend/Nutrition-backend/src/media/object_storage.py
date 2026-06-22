"""Object storage adapters for backend-only retained media objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any


class MediaObjectStorageError(RuntimeError):
    """Raised when a retained media object cannot be deleted safely."""


@dataclass(frozen=True)
class MediaObjectReference:
    """Private object reference persisted in `media_objects`.

    Attributes:
        object_storage_provider: Storage provider label stored with the object row.
        object_ref: Provider-internal object key. Public URLs and absolute paths are forbidden.
        object_version_id: Optional version id for exact deletion in versioned stores.
    """

    object_storage_provider: str
    object_ref: str
    object_version_id: str | None = None


class MediaObjectStore(ABC):
    """Abstract deletion interface for retained private media objects."""

    @abstractmethod
    async def delete_object(self, reference: MediaObjectReference) -> None:
        """Delete one retained private media object.

        Args:
            reference: Private object reference from the database.

        Raises:
            MediaObjectStorageError: If deletion is disabled, unsafe, or rejected.
        """
        ...


class DisabledMediaObjectStore(MediaObjectStore):
    """Fail-closed media object store used until private storage is configured."""

    async def delete_object(self, reference: MediaObjectReference) -> None:
        """Reject retained media deletion when storage is not configured.

        Args:
            reference: Private object reference that will not be deleted.

        Raises:
            MediaObjectStorageError: Always raised.
        """
        _ = reference
        raise MediaObjectStorageError("Media object storage is disabled.")


class LocalMediaObjectStore(MediaObjectStore):
    """Development-only local filesystem store for retained media objects."""

    provider = "local"

    def __init__(self, root: Path) -> None:
        """Initialize the local media object store.

        Args:
            root: Root directory containing private media objects.
        """
        self._root = root

    async def delete_object(self, reference: MediaObjectReference) -> None:
        """Delete one local private media object.

        Args:
            reference: Local media object reference.

        Raises:
            MediaObjectStorageError: If the provider/ref is unsafe or deletion fails.
        """
        _validate_provider(reference.object_storage_provider, self.provider)
        target = self._path_for_ref(reference.object_ref)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise MediaObjectStorageError("Failed to delete local media object.") from exc

    def _path_for_ref(self, object_ref: str) -> Path:
        """Resolve a private object ref beneath the configured root.

        Args:
            object_ref: Provider-internal relative object key.

        Returns:
            Absolute filesystem path.

        Raises:
            MediaObjectStorageError: If traversal is attempted.
        """
        normalized = _normalize_object_ref(object_ref)
        path = (self._root / normalized).resolve()
        root = self._root.resolve()
        if root != path and root not in path.parents:
            raise MediaObjectStorageError("Invalid local media object reference.")
        return path


class S3MediaObjectStore(MediaObjectStore):
    """S3-compatible deletion store for retained media objects."""

    provider = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        provider_name: str = "s3",
        force_path_style: bool = False,
        client: Any | None = None,
    ) -> None:
        """Initialize an S3-compatible media object deletion store.

        Args:
            bucket: Private bucket containing media objects.
            endpoint_url: Optional S3-compatible endpoint URL.
            region_name: Optional region name.
            access_key_id: Optional server-side S3 access key id.
            secret_access_key: Optional server-side S3 secret access key.
            provider_name: Provider label persisted in media object rows.
            force_path_style: Whether to force path-style S3 addressing.
            client: Optional injected boto3-compatible client for tests.

        Raises:
            MediaObjectStorageError: If boto3 is unavailable when no client is injected.
        """
        self._bucket = bucket
        self.provider = provider_name
        self._client = client or self._build_client(
            endpoint_url,
            region_name,
            access_key_id,
            secret_access_key,
            force_path_style,
        )

    async def delete_object(self, reference: MediaObjectReference) -> None:
        """Delete one S3-compatible private media object.

        Args:
            reference: S3 media object reference.

        Raises:
            MediaObjectStorageError: If the provider/ref is unsafe or S3 rejects deletion.
        """
        _validate_provider(reference.object_storage_provider, self.provider)
        key = _normalize_object_ref(reference.object_ref)
        kwargs: dict[str, Any] = {"Bucket": self._bucket, "Key": key}
        if reference.object_version_id:
            kwargs["VersionId"] = reference.object_version_id
        try:
            self._client.delete_object(**kwargs)
        except Exception as exc:
            raise MediaObjectStorageError("Failed to delete S3 media object.") from exc

    def _build_client(
        self,
        endpoint_url: str | None,
        region_name: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
        force_path_style: bool,
    ) -> Any:
        """Build a boto3 S3 client lazily.

        Args:
            endpoint_url: Optional S3-compatible endpoint URL.
            region_name: Optional region name.
            access_key_id: Optional server-side S3 access key id.
            secret_access_key: Optional server-side S3 secret access key.
            force_path_style: Whether to force path-style S3 addressing.

        Returns:
            boto3 S3 client.

        Raises:
            MediaObjectStorageError: If required SDK modules are unavailable.
        """
        try:
            boto3 = import_module("boto3")
        except ImportError as exc:
            raise MediaObjectStorageError(
                "boto3 is required for MEDIA_OBJECT_STORAGE_PROVIDER=s3."
            ) from exc
        kwargs: dict[str, Any] = {
            "endpoint_url": endpoint_url,
            "region_name": region_name,
        }
        if access_key_id is not None:
            kwargs["aws_access_key_id"] = access_key_id
        if secret_access_key is not None:
            kwargs["aws_secret_access_key"] = secret_access_key
        if force_path_style:
            try:
                botocore_config = import_module("botocore.config")
            except ImportError as exc:
                raise MediaObjectStorageError(
                    "botocore is required for path-style S3 configuration."
                ) from exc
            kwargs["config"] = botocore_config.Config(s3={"addressing_style": "path"})
        return boto3.client("s3", **kwargs)


def _validate_provider(actual: str, expected: str) -> None:
    """Fail closed when a row provider does not match the configured store.

    Args:
        actual: Provider label from the database row.
        expected: Provider label supported by the configured store.

    Raises:
        MediaObjectStorageError: If the provider is not supported.
    """
    if actual != expected:
        raise MediaObjectStorageError("Media object provider is not configured.")


def _normalize_object_ref(object_ref: str) -> str:
    """Validate and normalize a private object reference.

    Args:
        object_ref: Candidate provider-internal object key.

    Returns:
        Normalized relative object key.

    Raises:
        MediaObjectStorageError: If the ref is empty, public, absolute, or traversing.
    """
    if object_ref.startswith("/") or "://" in object_ref or "\\" in object_ref:
        raise MediaObjectStorageError("Invalid media object reference.")
    normalized = "/".join(part for part in object_ref.strip("/").split("/") if part)
    if not normalized or any(part == ".." for part in normalized.split("/")):
        raise MediaObjectStorageError("Invalid media object reference.")
    return normalized
