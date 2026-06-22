"""Allow the async 'processing' state on supplement_analysis_runs.status.

Revision ID: 0046_supplement_analysis_processing_status
Revises: 0045_seed_dyslipidemia_weight_evidence
Create Date: 2026-06-20 00:00:00.000000

The async supplement-analyze flow (``supplement_analyze_async_enabled``) creates
the analysis run up front in a new ``processing`` status, returns 202, and an
in-process worker flips the row to ``requires_confirmation`` (ready) or ``failed``
once the OCR/parse/vision pipeline completes. The pre-existing
``ck_supplement_analysis_runs_status_allowed`` CHECK hard-codes the four
confirmation-lifecycle states, so this migration relaxes it to additionally allow
``processing``.

The new value set is a strict SUPERSET of the old one, so every existing row
already satisfies the relaxed constraint and the ADD never fails. The drop uses
``IF EXISTS`` and the constraint is re-created with its convention-correct name
(``ck_%(table_name)s_%(constraint_name)s``), so the migration is idempotent and
safe on fresh, already-corrected, and already-migrated databases. No data is read
or written and no grants/policies change; only the CHECK definition is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0046_supplement_analysis_processing_status"
down_revision: str | Sequence[str] | None = "0045_seed_dyslipidemia_weight_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "ck_supplement_analysis_runs_status_allowed"
_TABLE = "public.supplement_analysis_runs"
_STATES_WITH_PROCESSING = "'processing', 'requires_confirmation', 'confirmed', 'expired', 'failed'"
_STATES_WITHOUT_PROCESSING = "'requires_confirmation', 'confirmed', 'expired', 'failed'"


def _replace_status_check(allowed_values: str) -> str:
    """Build idempotent SQL that resets the status CHECK to ``allowed_values``.

    Args:
        allowed_values: Comma-separated quoted status literals for the IN list.

    Returns:
        SQL that drops the existing status CHECK (if present) and re-adds it with
        the given allowed value set under the convention-correct constraint name.
    """
    return f"""
        ALTER TABLE {_TABLE} DROP CONSTRAINT IF EXISTS {_CONSTRAINT};
        ALTER TABLE {_TABLE}
            ADD CONSTRAINT {_CONSTRAINT}
            CHECK (status IN ({allowed_values}));
    """


def upgrade() -> None:
    """Relax the status CHECK to additionally allow 'processing'."""
    op.execute(_replace_status_check(_STATES_WITH_PROCESSING))


def downgrade() -> None:
    """Restore the confirmation-only status CHECK (drops the 'processing' value).

    Any rows still in ``processing`` must be resolved before downgrading, or the
    re-added CHECK will reject them. The async flow's stale-timeout means such rows
    are transient, but a downgrade should run with no analysis in flight.
    """
    op.execute(_replace_status_check(_STATES_WITHOUT_PROCESSING))
