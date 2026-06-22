"""Vector upsert worker for consent-gated learning images."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.learning.embeddings import EmbeddingError, EmbeddingInput, EmbeddingProvider
from src.learning.object_storage import LearningImageObjectStore, LearningObjectStorageError
from src.learning.vector_store import VectorRecord, VectorStore, VectorStoreError
from src.models.db.learning import ImageEmbeddingJob, LearningImageObject

JOB_STATUS_PENDING = "pending"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_SUCCEEDED = "succeeded"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_DEAD = "dead"
JOB_STATUS_CANCELLED = "cancelled"
IMAGE_STATUS_EMBEDDED = "embedded"
DEFAULT_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class LearningVectorUpsertWorkerResult:
    """Summary returned by one worker batch.

    Attributes:
        claimed: Number of jobs claimed.
        succeeded: Number of jobs completed successfully.
        failed: Number of jobs failed or moved to dead-letter state.
        cancelled: Number of jobs cancelled because the source object was gone.
    """

    claimed: int
    succeeded: int
    failed: int
    cancelled: int


class LearningVectorUpsertWorker:
    """Process pending learning image embedding jobs."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        object_store: LearningImageObjectStore,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        worker_id: str | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        """Initialize the worker.

        Args:
            session: Worker-scoped async session.
            object_store: Learning image object store.
            embedding_provider: Embedding runner.
            vector_store: Vector persistence adapter.
            worker_id: Optional worker identifier for leases.
            max_attempts: Attempts before a job is marked dead.
        """
        self._session = session
        self._object_store = object_store
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._worker_id = worker_id or f"learning-vector-worker-{uuid4().hex}"
        self._max_attempts = max_attempts

    async def run_once(self, *, limit: int = 10) -> LearningVectorUpsertWorkerResult:
        """Claim and process one batch of jobs.

        Args:
            limit: Maximum jobs to process.

        Returns:
            Batch summary.
        """
        jobs = await self._claim_jobs(limit=limit)
        succeeded = 0
        failed = 0
        cancelled = 0
        for job in jobs:
            outcome = await self._process_job(job)
            if outcome == JOB_STATUS_SUCCEEDED:
                succeeded += 1
            elif outcome == JOB_STATUS_CANCELLED:
                cancelled += 1
            else:
                failed += 1
        return LearningVectorUpsertWorkerResult(
            claimed=len(jobs),
            succeeded=succeeded,
            failed=failed,
            cancelled=cancelled,
        )

    async def _claim_jobs(self, *, limit: int) -> list[ImageEmbeddingJob]:
        """Claim pending or retryable jobs with row locks.

        Args:
            limit: Maximum jobs to claim.

        Returns:
            Claimed jobs.
        """
        now = datetime.now(UTC)
        result = await self._session.scalars(
            select(ImageEmbeddingJob)
            .where(
                ImageEmbeddingJob.status.in_([JOB_STATUS_PENDING, JOB_STATUS_FAILED]),
                ImageEmbeddingJob.next_run_at <= now,
                ImageEmbeddingJob.attempt_count < self._max_attempts,
            )
            .order_by(ImageEmbeddingJob.next_run_at, ImageEmbeddingJob.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = list(result.all())
        for job in jobs:
            job.status = JOB_STATUS_RUNNING
            job.locked_at = now
            job.locked_by = self._worker_id
        await self._session.commit()
        return jobs

    async def _process_job(self, job: ImageEmbeddingJob) -> str:
        """Process one claimed job.

        Args:
            job: Claimed embedding job.

        Returns:
            Final job status for this processing attempt.
        """
        image_object = await self._session.get(LearningImageObject, job.image_object_id)
        if image_object is None or image_object.deleted_at is not None:
            await self._mark_cancelled(job, "source_image_object_unavailable")
            return JOB_STATUS_CANCELLED
        try:
            image_bytes = await self._object_store.get_image(
                image_object.object_uri,
                image_object.object_version_id,
            )
            embedding = await self._embedding_provider.embed(
                EmbeddingInput(
                    image_bytes=image_bytes,
                    text=None,
                    model=job.embedding_model,
                )
            )
            await self._vector_store.upsert_image_embedding(
                VectorRecord(
                    owner_subject_hash=job.owner_subject_hash,
                    analysis_id=job.analysis_id,
                    image_object_id=job.image_object_id,
                    image_sha256=image_object.image_sha256,
                    embedding=embedding.vector,
                    embedding_model=embedding.model,
                    metadata=job.metadata_snapshot,
                )
            )
        except (EmbeddingError, LearningObjectStorageError, VectorStoreError) as exc:
            await self._mark_failed(job, error_code=exc.__class__.__name__, error_message=str(exc))
            return JOB_STATUS_FAILED

        job.status = JOB_STATUS_SUCCEEDED
        job.error_code = None
        job.error_message = None
        job.locked_at = None
        job.locked_by = None
        image_object.status = IMAGE_STATUS_EMBEDDED
        await self._session.commit()
        return JOB_STATUS_SUCCEEDED

    async def _mark_failed(
        self,
        job: ImageEmbeddingJob,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        """Mark a job failed or dead-lettered.

        Args:
            job: Failed job.
            error_code: Stable error code.
            error_message: Safe failure summary.
        """
        job.attempt_count += 1
        job.status = (
            JOB_STATUS_DEAD if job.attempt_count >= self._max_attempts else JOB_STATUS_FAILED
        )
        job.error_code = error_code[:80]
        job.error_message = error_message[:512]
        job.locked_at = None
        job.locked_by = None
        job.next_run_at = datetime.now(UTC) + timedelta(minutes=min(job.attempt_count, 5))
        await self._session.commit()

    async def _mark_cancelled(self, job: ImageEmbeddingJob, error_code: str) -> None:
        """Cancel a job that can no longer be processed.

        Args:
            job: Job to cancel.
            error_code: Stable cancellation reason.
        """
        job.status = JOB_STATUS_CANCELLED
        job.error_code = error_code
        job.error_message = "Source learning image object is unavailable."
        job.locked_at = None
        job.locked_by = None
        await self._session.commit()
