"""Object storage adapters for consent-retained learning images."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import uuid4

FORBIDDEN_OBJECT_METADATA_KEYS = frozenset(
    {
        "apikey",
        "authorization",
        "credential",
        "credentials",
        "imagebase64",
        "imagebytes",
        "ocrtext",
        "providerpayload",
        "rawimage",
        "rawimagebytes",
        "rawocrtext",
        "rawproviderpayload",
        "requestheaders",
        "secret",
        "servicekey",
        "accesstoken",
    }
)
SECRET_LIKE_OBJECT_METADATA_VALUE_MARKERS = (
    "bearer ",
    "sb_secret_",
    "service_role",
    "aws_secret_access_key",
    "-----begin",
)
MAX_OBJECT_METADATA_KEY_LENGTH = 64
MAX_OBJECT_METADATA_VALUE_LENGTH = 256


class LearningObjectStorageError(RuntimeError):
    """Raised when a learning image object cannot be stored or deleted safely."""


@dataclass(frozen=True)
class LearningImageObjectInput:
    """Payload for retaining a consent-gated learning image.

    Attributes:
        image_bytes: Original image bytes that passed intake validation.
        image_sha256: SHA-256 hash of the original image bytes.
        mime_type: Accepted image MIME type.
        owner_subject_hash: HMAC of the owner subject.
        retained_until: Automatic deletion deadline.
        metadata: Safe object metadata. Raw OCR text and credentials are forbidden.
    """

    image_bytes: bytes
    image_sha256: str
    mime_type: str
    owner_subject_hash: str
    retained_until: datetime
    metadata: dict[str, str]


@dataclass(frozen=True)
class StoredLearningImage:
    """Stored object reference returned by an object storage adapter.

    Attributes:
        object_uri: Storage URI for later worker access.
        provider: Storage provider name.
        version_id: Optional version id for versioned object stores.
    """

    object_uri: str
    provider: str
    version_id: str | None = None


class LearningImageObjectStore(ABC):
    """Abstract storage interface for retained learning images."""

    @abstractmethod
    async def put_image(self, payload: LearningImageObjectInput) -> StoredLearningImage:
        """Store one consent-gated image object.

        Args:
            payload: Validated image bytes and safe metadata.

        Returns:
            Stored object reference.

        Raises:
            LearningObjectStorageError: If the image cannot be retained safely.
        """
        ...

    @abstractmethod
    async def get_image(self, object_uri: str, version_id: str | None = None) -> bytes:
        """Load a retained image object for embedding generation.

        Args:
            object_uri: Storage URI returned by `put_image`.
            version_id: Optional storage version identifier.

        Returns:
            Stored image bytes.

        Raises:
            LearningObjectStorageError: If the object cannot be loaded safely.
        """
        ...

    @abstractmethod
    async def delete_image(self, object_uri: str, version_id: str | None = None) -> None:
        """Delete a retained image object.

        Args:
            object_uri: Storage URI returned by `put_image`.
            version_id: Optional storage version identifier.

        Raises:
            LearningObjectStorageError: If deletion fails.
        """
        ...


class DisabledLearningImageObjectStore(LearningImageObjectStore):
    """Fail-closed object store used before the learning storage gate passes."""

    async def put_image(self, payload: LearningImageObjectInput) -> StoredLearningImage:
        """Reject image retention in disabled environments.

        Args:
            payload: Image object payload that will not be stored.

        Returns:
            Never returns.

        Raises:
            LearningObjectStorageError: Always raised.
        """
        _ = payload
        raise LearningObjectStorageError("Learning image object storage is disabled.")

    async def get_image(self, object_uri: str, version_id: str | None = None) -> bytes:
        """Reject image reads in disabled environments.

        Args:
            object_uri: Object URI that will not be read.
            version_id: Optional version identifier.

        Returns:
            Never returns.

        Raises:
            LearningObjectStorageError: Always raised.
        """
        _ = (object_uri, version_id)
        raise LearningObjectStorageError("Learning image object storage is disabled.")

    async def delete_image(self, object_uri: str, version_id: str | None = None) -> None:
        """Reject image deletion in disabled environments.

        Args:
            object_uri: Object URI that will not be deleted.
            version_id: Optional version identifier.

        Raises:
            LearningObjectStorageError: Always raised.
        """
        _ = (object_uri, version_id)
        raise LearningObjectStorageError("Learning image object storage is disabled.")


class LocalLearningImageObjectStore(LearningImageObjectStore):
    """Development-only local filesystem store for learning images."""

    provider = "local"

    def __init__(self, root: Path, prefix: str = "learning/images") -> None:
        """Initialize the local object store.

        Args:
            root: Root directory for local object files.
            prefix: Logical object prefix beneath the root.
        """
        self._root = root
        self._prefix = _normalize_prefix(prefix)

    async def put_image(self, payload: LearningImageObjectInput) -> StoredLearningImage:
        """Store one image under the local root.

        Args:
            payload: Validated image bytes and safe metadata.

        Returns:
            Local object reference.

        Raises:
            LearningObjectStorageError: If the file cannot be written.
        """
        validate_learning_object_metadata(payload.metadata)
        key = self._build_key(payload)
        target = self._path_for_key(key)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload.image_bytes)
        except OSError as exc:
            raise LearningObjectStorageError("Failed to store local learning image.") from exc
        return StoredLearningImage(object_uri=f"local://{key}", provider=self.provider)

    async def get_image(self, object_uri: str, version_id: str | None = None) -> bytes:
        """Read one local image object.

        Args:
            object_uri: `local://` URI returned by this store.
            version_id: Ignored for local storage.

        Returns:
            Stored image bytes.

        Raises:
            LearningObjectStorageError: If the URI is invalid or unreadable.
        """
        _ = version_id
        key = _key_from_local_uri(object_uri)
        try:
            return self._path_for_key(key).read_bytes()
        except OSError as exc:
            raise LearningObjectStorageError("Failed to read local learning image.") from exc

    async def delete_image(self, object_uri: str, version_id: str | None = None) -> None:
        """Delete one local image object.

        Args:
            object_uri: `local://` URI returned by this store.
            version_id: Ignored for local storage.

        Raises:
            LearningObjectStorageError: If the URI is invalid or deletion fails.
        """
        _ = version_id
        key = _key_from_local_uri(object_uri)
        target = self._path_for_key(key)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise LearningObjectStorageError("Failed to delete local learning image.") from exc

    def _build_key(self, payload: LearningImageObjectInput) -> str:
        """Build a safe object key for a retained image.

        Args:
            payload: Image object payload.

        Returns:
            Relative object key.
        """
        owner_prefix = payload.owner_subject_hash[:16]
        return f"{self._prefix}/{owner_prefix}/{payload.image_sha256}-{uuid4().hex}"

    def _path_for_key(self, key: str) -> Path:
        """Resolve a key beneath the configured root.

        Args:
            key: Relative object key.

        Returns:
            Absolute filesystem path.

        Raises:
            LearningObjectStorageError: If key traversal is attempted.
        """
        normalized = _normalize_key(key)
        path = (self._root / normalized).resolve()
        root = self._root.resolve()
        if root != path and root not in path.parents:
            raise LearningObjectStorageError("Invalid local learning image object key.")
        return path


class S3LearningImageObjectStore(LearningImageObjectStore):
    """S3-compatible object store for retained learning images."""

    provider = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "learning/images",
        endpoint_url: str | None = None,
        region_name: str | None = None,
        server_side_encryption: str | None = "AES256",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        provider_name: str = "s3",
        force_path_style: bool = False,
        client: Any | None = None,
    ) -> None:
        """Initialize an S3 object store.

        Args:
            bucket: Target object bucket.
            prefix: Key prefix for retained learning images.
            endpoint_url: Optional S3-compatible endpoint URL.
            region_name: Optional region name.
            server_side_encryption: Optional server-side encryption mode.
            access_key_id: Optional server-side S3 access key id.
            secret_access_key: Optional server-side S3 secret access key.
            provider_name: Provider label persisted in the DB object row.
            force_path_style: Whether to force path-style S3 addressing.
            client: Optional injected boto3-compatible client for tests.

        Raises:
            LearningObjectStorageError: If boto3 is unavailable when no client is injected.
        """
        self._bucket = bucket
        self._prefix = _normalize_prefix(prefix)
        self._server_side_encryption = server_side_encryption
        self.provider = provider_name
        self._client = client or self._build_client(
            endpoint_url,
            region_name,
            access_key_id,
            secret_access_key,
            force_path_style,
        )

    async def put_image(self, payload: LearningImageObjectInput) -> StoredLearningImage:
        """Store one image in S3.

        Args:
            payload: Validated image bytes and safe metadata.

        Returns:
            S3 object reference.

        Raises:
            LearningObjectStorageError: If S3 rejects the object.
        """
        key = self._build_key(payload)
        metadata = validate_learning_object_metadata(payload.metadata)
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": payload.image_bytes,
            "ContentType": payload.mime_type,
            "Metadata": metadata,
        }
        if self._server_side_encryption:
            kwargs["ServerSideEncryption"] = self._server_side_encryption
        try:
            response = self._client.put_object(**kwargs)
        except Exception as exc:
            raise LearningObjectStorageError("Failed to store S3 learning image.") from exc
        version_id = response.get("VersionId") if isinstance(response, dict) else None
        return StoredLearningImage(
            object_uri=f"s3://{self._bucket}/{key}",
            provider=self.provider,
            version_id=version_id if isinstance(version_id, str) else None,
        )

    async def get_image(self, object_uri: str, version_id: str | None = None) -> bytes:
        """Read one image from S3.

        Args:
            object_uri: `s3://bucket/key` URI.
            version_id: Optional S3 object version id.

        Returns:
            Object body bytes.

        Raises:
            LearningObjectStorageError: If S3 rejects the read.
        """
        bucket, key = _bucket_key_from_s3_uri(object_uri)
        kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key}
        if version_id:
            kwargs["VersionId"] = version_id
        try:
            response = self._client.get_object(**kwargs)
            body = response["Body"]
            return bytes(body.read())
        except Exception as exc:
            raise LearningObjectStorageError("Failed to read S3 learning image.") from exc

    async def delete_image(self, object_uri: str, version_id: str | None = None) -> None:
        """Delete one image from S3.

        Args:
            object_uri: `s3://bucket/key` URI.
            version_id: Optional S3 object version id.

        Raises:
            LearningObjectStorageError: If S3 rejects the delete.
        """
        bucket, key = _bucket_key_from_s3_uri(object_uri)
        kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key}
        if version_id:
            kwargs["VersionId"] = version_id
        try:
            self._client.delete_object(**kwargs)
        except Exception as exc:
            raise LearningObjectStorageError("Failed to delete S3 learning image.") from exc

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
            LearningObjectStorageError: If boto3 is unavailable.
        """
        try:
            boto3 = import_module("boto3")
        except ImportError as exc:
            raise LearningObjectStorageError(
                "boto3 is required for LEARNING_OBJECT_STORAGE_PROVIDER=s3."
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
                raise LearningObjectStorageError(
                    "botocore is required for path-style S3 configuration."
                ) from exc
            kwargs["config"] = botocore_config.Config(s3={"addressing_style": "path"})
        return boto3.client("s3", **kwargs)

    def _build_key(self, payload: LearningImageObjectInput) -> str:
        """Build a safe S3 key for a retained image.

        Args:
            payload: Image object payload.

        Returns:
            Object key.
        """
        owner_prefix = payload.owner_subject_hash[:16]
        return f"{self._prefix}/{owner_prefix}/{payload.image_sha256}-{uuid4().hex}"


def _normalize_prefix(prefix: str) -> str:
    """Normalize a logical object prefix.

    Args:
        prefix: Candidate prefix.

    Returns:
        Slash-trimmed prefix.
    """
    normalized = "/".join(part for part in prefix.strip("/").split("/") if part)
    return normalized or "learning/images"


def validate_learning_object_metadata(metadata: dict[str, str]) -> dict[str, str]:
    """Return metadata only if it is safe for object-store headers.

    Args:
        metadata: Candidate object metadata.

    Returns:
        A shallow copy safe to pass to an S3-compatible client.

    Raises:
        LearningObjectStorageError: If a key or value could leak raw OCR/image data or secrets.
    """
    safe_metadata: dict[str, str] = {}
    for key, value in metadata.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise LearningObjectStorageError("Learning object metadata must be string-only.")
        if not key.strip():
            raise LearningObjectStorageError("Learning object metadata key must not be empty.")
        if len(key) > MAX_OBJECT_METADATA_KEY_LENGTH:
            raise LearningObjectStorageError("Learning object metadata key is too long.")
        if len(value) > MAX_OBJECT_METADATA_VALUE_LENGTH:
            raise LearningObjectStorageError("Learning object metadata value is too long.")
        normalized_key = _normalize_metadata_key(key)
        if any(
            normalized_key.startswith(forbidden) for forbidden in FORBIDDEN_OBJECT_METADATA_KEYS
        ):
            raise LearningObjectStorageError("Learning object metadata contains a forbidden key.")
        value_lower = value.lower()
        if any(marker in value_lower for marker in SECRET_LIKE_OBJECT_METADATA_VALUE_MARKERS):
            raise LearningObjectStorageError("Learning object metadata contains a forbidden value.")
        safe_metadata[key] = value
    return safe_metadata


def _normalize_metadata_key(key: str) -> str:
    """Normalize a metadata key for case-insensitive policy checks.

    Args:
        key: Candidate metadata key.

    Returns:
        Lowercase alphanumeric key.
    """
    return "".join(character for character in key.lower() if character.isalnum())


def _normalize_key(key: str) -> str:
    """Validate and normalize a relative object key.

    Args:
        key: Candidate object key.

    Returns:
        Normalized relative key.

    Raises:
        LearningObjectStorageError: If the key is empty or attempts traversal.
    """
    normalized = "/".join(part for part in key.strip("/").split("/") if part)
    if not normalized or any(part == ".." for part in normalized.split("/")):
        raise LearningObjectStorageError("Invalid learning image object key.")
    return normalized


def _key_from_local_uri(object_uri: str) -> str:
    """Extract an object key from a local URI.

    Args:
        object_uri: Candidate local URI.

    Returns:
        Relative object key.

    Raises:
        LearningObjectStorageError: If the URI is not local.
    """
    prefix = "local://"
    if not object_uri.startswith(prefix):
        raise LearningObjectStorageError("Expected a local learning image object URI.")
    return _normalize_key(object_uri[len(prefix) :])


def _bucket_key_from_s3_uri(object_uri: str) -> tuple[str, str]:
    """Extract bucket and key from an S3 URI.

    Args:
        object_uri: Candidate `s3://bucket/key` URI.

    Returns:
        Bucket and object key.

    Raises:
        LearningObjectStorageError: If the URI is invalid.
    """
    prefix = "s3://"
    if not object_uri.startswith(prefix):
        raise LearningObjectStorageError("Expected an S3 learning image object URI.")
    bucket_and_key = object_uri[len(prefix) :]
    bucket, separator, key = bucket_and_key.partition("/")
    if not bucket or not separator:
        raise LearningObjectStorageError("Invalid S3 learning image object URI.")
    return bucket, _normalize_key(key)
