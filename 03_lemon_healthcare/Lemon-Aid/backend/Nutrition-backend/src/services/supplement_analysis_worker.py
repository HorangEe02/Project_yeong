"""In-process async worker for supplement image analysis (202 + poll).

When ``supplement_analyze_async_enabled`` is on, the POST routes pre-create the
analysis run row(s) in ``processing`` status, capture each image's bytes, and
hand off to one of the job functions here via :func:`asyncio.create_task`. The
job opens a FRESH request-engine session (``get_sessionmaker``), sets the same
owner-subject RLS context the request seam would (so owner reads/writes admit
under the Stage-2 ``lemon_app`` FORCE-RLS posture), runs the existing pipeline,
and flips the run to ``requires_confirmation`` (ready) or ``failed`` — all inside
the pipeline transaction so a partial ``parsed_snapshot`` can never be observed as
ready by a poll.

These jobs are detached background tasks, never awaited by the request: any
exception is logged and swallowed (never re-raised), and the failure path flips
the still-processing rows to ``failed`` with only a safe coded warning.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.datastructures import Headers, UploadFile

from src.config import Settings
from src.db.rls_context import set_request_rls_context
from src.db.session import get_sessionmaker
from src.db.tx import REQUEST_MANAGED_TX, persist_scope
from src.learning.factory import build_learning_object_store
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.privacy import ConsentType
from src.models.schemas.supplement import SupplementAnalysisStatus
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject
from src.services.privacy import record_sensitive_audit_event
from src.services.supplement_image_analysis import (
    SupplementImageAnalysisAdapters,
    analyze_supplement_image,
    store_supplement_learning_artifacts,
)

logger = logging.getLogger(__name__)

# Safe coded warning appended to a run that failed during the worker pipeline.
# NEVER contains raw exception text, OCR text, image bytes, or PII.
ANALYSIS_FAILED_WARNING = "analysis_failed"


class _CapturedClient:
    """Minimal stand-in for ``request.client`` (only ``.host`` is read)."""

    __slots__ = ("host",)

    def __init__(self, host: str | None) -> None:
        self.host = host


@dataclass(frozen=True)
class CapturedRequest:
    """Request network metadata snapshotted at submit time for worker audits.

    The detached worker has no live ``Request``; the audit builder only reads
    ``request.client.host`` and ``request.headers.get(...)``. This snapshot
    captures those so out-of-band audits keep the same IP/user-agent/request-id
    hashes as the synchronous path. It is duck-typed against ``starlette.Request``
    for ``record_sensitive_audit_event`` (which never touches the body).

    Attributes:
        client: Object exposing ``.host`` (the peer IP), or ``None``.
        headers: Header mapping exposing ``.get`` (user-agent / x-request-id).
    """

    client: _CapturedClient
    headers: Headers

    @classmethod
    def from_request(cls, client_host: str | None, raw_headers: dict[str, str]) -> CapturedRequest:
        """Build a snapshot from a live request's host + header values.

        Args:
            client_host: Peer IP from ``request.client.host`` (or ``None``).
            raw_headers: Header values needed for audit hashing (user-agent,
                x-request-id). Other headers are intentionally dropped.

        Returns:
            A request snapshot safe to retain across the response boundary.
        """
        return cls(client=_CapturedClient(client_host), headers=Headers(raw_headers))


@dataclass(frozen=True)
class CapturedImage:
    """Request-local image payload captured before the response is sent.

    The ``UploadFile`` is consumed/closed once the route returns, so the bytes
    and metadata needed to reconstruct it for the detached worker are snapshotted
    at submit time.

    Attributes:
        analysis_id: Pre-created analysis run id this image will populate.
        client_request_id: Owner-scoped idempotency key the worker reuses so
            ``analyze_supplement_image`` re-binds the same pre-created row.
        image_bytes: Raw uploaded image bytes.
        content_type: Declared upload content type (e.g. ``image/png``).
        filename: Original upload filename for the reconstructed ``UploadFile``.
        image_role: Multi-image role label (``unknown`` for single-image).
    """

    analysis_id: UUID
    client_request_id: str | None
    image_bytes: bytes
    content_type: str | None
    filename: str
    image_role: str = "unknown"


def reconstruct_upload_file(captured: CapturedImage) -> UploadFile:
    """Rebuild a Starlette ``UploadFile`` from captured bytes for the worker.

    Verified against starlette 1.2.x: ``UploadFile(file=..., filename=...,
    headers=Headers({"content-type": ...}))`` exposes ``content_type`` from the
    headers so :func:`read_and_validate_supplement_image` re-validates the bytes.

    Args:
        captured: Request-local image payload snapshotted at submit time.

    Returns:
        An ``UploadFile`` wrapping the captured bytes with the original
        content-type and filename.
    """
    headers = Headers({"content-type": captured.content_type or "application/octet-stream"})
    return UploadFile(
        file=io.BytesIO(captured.image_bytes),
        filename=captured.filename,
        headers=headers,
    )


async def _open_owner_rls_session(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
) -> None:
    """Set the owner-subject RLS GUCs + request-managed marker on a fresh session.

    Mirrors ``rls_request_transaction`` setup so ``persist_scope`` participates
    (flush only) and the transaction-local owner GUCs survive the whole pipeline
    transaction. Must be called inside ``async with session.begin()``.

    Args:
        session: Fresh request-engine session already inside a transaction.
        user: Authenticated owner whose subject scopes the RLS GUCs.
        settings: Runtime settings supplying the privacy hash secret.
    """
    await set_request_rls_context(
        session,
        subject=build_owner_subject(user),
        subject_hash=hash_actor_subject(user, settings),
    )
    session.info[REQUEST_MANAGED_TX] = True


async def _mark_run_failed(
    *,
    analysis_id: UUID,
    user: AuthenticatedUser,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Flip a still-processing run to ``failed`` in a fresh short transaction.

    Opens a new owner-scoped transaction (the pipeline transaction was rolled
    back) and sets ``status='failed'`` plus a safe coded warning. Only acts on a
    row still in ``processing`` so a terminal row is never overwritten. Best
    effort: a failure here is logged and swallowed (the task is detached).

    Args:
        analysis_id: Pre-created analysis run id to fail.
        user: Authenticated owner whose subject scopes the RLS GUCs.
        settings: Runtime settings supplying the privacy hash secret.
        session_factory: Request-engine session factory (lemon_app, RLS-enforced).
    """
    try:
        async with session_factory() as session, session.begin():
            await _open_owner_rls_session(session=session, user=user, settings=settings)
            record = await session.get(SupplementAnalysisRun, analysis_id)
            if record is None or record.status != SupplementAnalysisStatus.PROCESSING.value:
                return
            async with persist_scope(session):
                record.status = SupplementAnalysisStatus.FAILED.value
                warnings = list(record.warnings or [])
                if ANALYSIS_FAILED_WARNING not in warnings:
                    warnings.append(ANALYSIS_FAILED_WARNING)
                record.warnings = warnings
    except Exception:
        # The failure-marking transaction is itself best-effort; a stale
        # ``processing`` row is later treated as a timeout by the poll route.
        logger.exception("Failed to mark supplement analysis run %s as failed.", analysis_id)


async def _annotate_group_membership(
    *,
    session: AsyncSession,
    record: SupplementAnalysisRun,
    analysis_group_id: str,
    image_role: str,
    image_count: int,
    merge_strategy: str,
) -> None:
    """Persist multi-image batch metadata so the group poll can find the row.

    Mirrors the route's ``_annotate_multi_image_record``: stamps
    ``multi_image_group_id`` + ``image_role`` on the parsed snapshot (the group
    poll queries by ``parsed_snapshot['multi_image_group_id']``) and updates the
    image count/role in pipeline metadata. Participates in the caller's
    transaction via ``persist_scope``.

    Args:
        session: Owner-scoped session inside the pipeline transaction.
        record: Per-image analysis row to annotate.
        analysis_group_id: Ephemeral batch group identifier.
        image_role: Client-supplied or unknown image role.
        image_count: Number of images in the batch.
    """
    async with persist_scope(session):
        parsed_snapshot = dict(record.parsed_snapshot or {})
        parsed_snapshot["image_role"] = image_role
        parsed_snapshot["multi_image_group_id"] = analysis_group_id
        parsed_snapshot["multi_image_merge_strategy"] = merge_strategy
        pipeline_metadata = dict(parsed_snapshot.get("pipeline_metadata") or {})
        pipeline_metadata["image_count"] = image_count
        pipeline_metadata["image_role"] = image_role
        parsed_snapshot["pipeline_metadata"] = pipeline_metadata
        record.parsed_snapshot = parsed_snapshot


def _provider_warning_codes(codes: tuple[str, ...]) -> list[str]:
    """Return OCR/provider/parser failure codes, excluding image-quality hints.

    Args:
        codes: Warning codes produced by the image analysis service.

    Returns:
        Warning codes excluding ``image_quality:`` review hints.
    """
    return [code for code in codes if not code.startswith("image_quality:")]


async def _record_ocr_provider_audit(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    http_request: CapturedRequest,
    record_id: UUID,
    ocr_attempted: bool,
    warning_codes: tuple[str, ...],
    ocr_provider: str | None,
    ocr_confidence_present: bool,
    merge_strategy: str | None,
) -> None:
    """Emit the OCR-provider completed/failed audit when OCR was attempted.

    Mirrors the synchronous routes' OCR-provider audit. No-op when OCR was not
    attempted (intake-only run). Runs out-of-band on the request-managed session.

    Args:
        session: Owner-scoped request-managed session.
        user: Authenticated owner.
        settings: Runtime settings.
        http_request: Request network snapshot for audit hashing.
        record_id: Analysis run id the audit references.
        ocr_attempted: Whether a primary OCR adapter was configured and called.
        warning_codes: Recoverable OCR/parser warning codes from the pipeline.
        ocr_provider: OCR provider name when available.
        ocr_confidence_present: Whether OCR confidence was produced.
        merge_strategy: Optional batch merge strategy added to metadata.
    """
    if not ocr_attempted:
        return
    provider_warning_codes = _provider_warning_codes(warning_codes)
    event_metadata: dict[str, object] = {
        "ocr_provider": ocr_provider,
        "ocr_confidence_present": ocr_confidence_present,
        "warning_codes": provider_warning_codes,
        "raw_image_stored": False,
        "raw_ocr_text_stored": False,
        "async_worker": True,
    }
    if merge_strategy is not None:
        event_metadata["merge_strategy"] = merge_strategy
    await record_sensitive_audit_event(
        session,
        user,
        action=(
            "supplement_ocr_provider_failed"
            if provider_warning_codes
            else "supplement_ocr_provider_completed"
        ),
        resource_type="supplement_analysis_run",
        resource_id=str(record_id),
        outcome="failed" if provider_warning_codes else "success",
        request=http_request,
        settings=settings,
        event_metadata=event_metadata,
    )


async def run_single_supplement_analysis_job(
    *,
    analysis_id: UUID,
    captured: CapturedImage,
    user: AuthenticatedUser,
    settings: Settings,
    adapters: SupplementImageAnalysisAdapters,
    http_request: CapturedRequest,
    learning_consents: tuple[ConsentType, ...] = (),
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Run the single-image pipeline for a pre-created ``processing`` run.

    Opens a fresh request-engine session, re-applies the owner RLS context, and
    runs ``analyze_supplement_image`` (which REUSES the pre-created processing row
    via the same ``client_request_id``). On success it flips the run to
    ``requires_confirmation`` *in the same transaction* as the pipeline writes, so
    a partial ``parsed_snapshot`` can never be observed as ready. On ANY error the
    transaction rolls back and the row is flipped to ``failed`` with a safe coded
    warning. Detached task: never re-raises. Learning is scheduled by awaiting
    ``store_supplement_learning_artifacts`` post-commit (best-effort).

    Args:
        analysis_id: Pre-created analysis run id (status ``processing``).
        captured: Request-local image payload captured at submit time.
        user: Authenticated owner whose subject scopes the RLS GUCs.
        settings: Runtime settings.
        adapters: OCR/parser/vision adapters selected by the route.
        http_request: Request network snapshot for out-of-band audit hashing.
        learning_consents: Active learning consent grants for the gate + snapshot.
        session_factory: Request-engine session factory override (tests); defaults
            to ``get_sessionmaker`` (lemon_app, RLS-enforced) — NEVER the
            privileged learning factory, which would bypass RLS for the pipeline.
    """
    factory = session_factory or get_sessionmaker()
    learning_artifacts = None
    try:
        async with factory() as session, session.begin():
            await _open_owner_rls_session(session=session, user=user, settings=settings)
            result = await analyze_supplement_image(
                session=session,
                user=user,
                image=reconstruct_upload_file(captured),
                client_request_id=captured.client_request_id,
                settings=settings,
                adapters=adapters,
                learning_consents=learning_consents,
            )
            learning_artifacts = result.learning_artifacts
            # Flip to ready inside the SAME transaction as the pipeline writes so a
            # partial snapshot can never be polled as ready.
            async with persist_scope(session):
                result.record.status = SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value
            # Success audits stay inside the request-managed transaction so they go
            # out-of-band (the privileged audit engine), flip-safe under lemon_app.
            if result.ocr_attempted:
                provider_warning_codes = _provider_warning_codes(result.ocr_warning_codes)
                await record_sensitive_audit_event(
                    session,
                    user,
                    action=(
                        "supplement_ocr_provider_failed"
                        if provider_warning_codes
                        else "supplement_ocr_provider_completed"
                    ),
                    resource_type="supplement_analysis_run",
                    resource_id=str(result.record.id),
                    outcome="failed" if provider_warning_codes else "success",
                    request=http_request,
                    settings=settings,
                    event_metadata={
                        "ocr_provider": (result.ocr_result.provider if result.ocr_result else None),
                        "ocr_confidence_present": (
                            result.ocr_result.confidence is not None if result.ocr_result else False
                        ),
                        "warning_codes": provider_warning_codes,
                        "raw_image_stored": False,
                        "raw_ocr_text_stored": False,
                        "async_worker": True,
                    },
                )
            await record_sensitive_audit_event(
                session,
                user,
                action=(
                    "supplement_image_intake_reused"
                    if result.reused_existing
                    else "supplement_image_intake_created"
                ),
                resource_type="supplement_analysis_run",
                resource_id=str(result.record.id),
                outcome="success",
                request=http_request,
                settings=settings,
                event_metadata={
                    "image_mime_type": result.image_metadata.mime_type,
                    "image_size_bytes": result.image_metadata.size_bytes,
                    "reused_existing": result.reused_existing,
                    "ocr_provider": result.ocr_result.provider if result.ocr_result else None,
                    "parser_used": result.parser_used,
                    "vision_roi_used": result.vision_region is not None,
                    "learning_image_object_scheduled": result.learning_artifacts is not None,
                    "async_worker": True,
                },
            )
    except Exception:
        logger.exception("Supplement analysis worker failed for run %s.", analysis_id)
        await _mark_run_failed(
            analysis_id=analysis_id,
            user=user,
            settings=settings,
            session_factory=factory,
        )
        return

    if learning_artifacts is not None:
        try:
            await store_supplement_learning_artifacts(
                user=user,
                artifacts=learning_artifacts,
                settings=settings,
                object_store=build_learning_object_store(settings),
            )
        except Exception:
            # Best-effort post-commit learning: a learning miss must never affect
            # the now-ready analysis run.
            logger.exception("Post-commit learning scheduling failed for run %s.", analysis_id)


async def run_multi_supplement_analysis_job(
    *,
    analysis_group_id: str,
    captured_images: list[CapturedImage],
    image_roles: list[str],
    merge_strategy: str,
    user: AuthenticatedUser,
    settings: Settings,
    adapters: SupplementImageAnalysisAdapters,
    http_request: CapturedRequest,
    learning_consents: tuple[ConsentType, ...] = (),
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Run the multi-image pipeline for a batch of pre-created ``processing`` rows.

    Runs ``analyze_supplement_image`` per image, reusing each pre-created row
    (always per-image, since the submit pre-creates one row per image; the
    single_product merge is reconstructed at poll time, not via the one-shot
    fusion row which would orphan the pre-created rows). Each row is annotated with
    the ``analysis_group_id`` and ``merge_strategy`` (so the group poll can find it
    and set the response result_mode) and flipped to ``requires_confirmation``
    inside the pipeline transaction. On ANY error every still-``processing`` row in
    the batch is flipped to ``failed``. Detached task: never re-raises. Learning is
    scheduled post-commit (best-effort).

    Args:
        analysis_group_id: Ephemeral batch group id generated at submit time.
        captured_images: Per-image payloads captured at submit time (upload order).
        image_roles: Role labels aligned one-to-one with ``captured_images``.
        merge_strategy: ``single_product`` or ``distinct_products``.
        user: Authenticated owner whose subject scopes the RLS GUCs.
        settings: Runtime settings.
        adapters: OCR/parser/vision adapters selected by the route.
        http_request: Request network snapshot for out-of-band audit hashing.
        learning_consents: Active learning consent grants for the gate + snapshot.
        session_factory: Request-engine session factory override (tests); defaults
            to ``get_sessionmaker`` (lemon_app, RLS-enforced).
    """
    factory = session_factory or get_sessionmaker()
    image_count = len(captured_images)
    learning_artifacts_to_store: list[object] = []
    try:
        async with factory() as session, session.begin():
            await _open_owner_rls_session(session=session, user=user, settings=settings)
            # The async submit pre-creates one 'processing' row per image, so the
            # worker always processes per-image and reuses those rows. (The one-shot
            # fusion path builds its own single row, which would orphan the
            # pre-created rows and conflict on idempotency; the single_product merge
            # is instead reconstructed at poll time from the per-image previews.) The
            # merge_strategy is persisted on each row so the group poll can set the
            # response result_mode / merged_preview correctly.
            for index, captured in enumerate(captured_images):
                result = await analyze_supplement_image(
                    session=session,
                    user=user,
                    image=reconstruct_upload_file(captured),
                    client_request_id=captured.client_request_id,
                    settings=settings,
                    adapters=adapters,
                    learning_consents=learning_consents,
                )
                if result.learning_artifacts is not None:
                    learning_artifacts_to_store.append(result.learning_artifacts)
                await _annotate_group_membership(
                    session=session,
                    record=result.record,
                    analysis_group_id=analysis_group_id,
                    image_role=(image_roles[index] if index < len(image_roles) else "unknown"),
                    image_count=image_count,
                    merge_strategy=merge_strategy,
                )
                async with persist_scope(session):
                    result.record.status = SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value
                await _record_ocr_provider_audit(
                    session=session,
                    user=user,
                    settings=settings,
                    http_request=http_request,
                    record_id=result.record.id,
                    ocr_attempted=result.ocr_attempted,
                    warning_codes=result.ocr_warning_codes,
                    ocr_provider=(result.ocr_result.provider if result.ocr_result else None),
                    ocr_confidence_present=(
                        result.ocr_result.confidence is not None if result.ocr_result else False
                    ),
                    merge_strategy=None,
                )
            await record_sensitive_audit_event(
                session,
                user,
                action="supplement_image_multi_intake_created",
                resource_type="supplement_analysis_run",
                resource_id=None,
                outcome="success",
                request=http_request,
                settings=settings,
                event_metadata={
                    "image_count": image_count,
                    "raw_image_stored": False,
                    "raw_ocr_text_stored": False,
                    "merge_strategy": merge_strategy,
                    "async_worker": True,
                },
            )
    except Exception:
        logger.exception(
            "Supplement multi-image analysis worker failed for group %s.",
            analysis_group_id,
        )
        for captured in captured_images:
            await _mark_run_failed(
                analysis_id=captured.analysis_id,
                user=user,
                settings=settings,
                session_factory=factory,
            )
        return

    for artifacts in learning_artifacts_to_store:
        try:
            await store_supplement_learning_artifacts(
                user=user,
                artifacts=artifacts,  # type: ignore[arg-type]
                settings=settings,
                object_store=build_learning_object_store(settings),
            )
        except Exception:
            logger.exception(
                "Post-commit learning scheduling failed for group %s.",
                analysis_group_id,
            )
