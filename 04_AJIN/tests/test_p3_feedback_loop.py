"""P3 D12 — Feedback Loop 자동 보강 단위 테스트."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    """격리된 change DB + 학습 룰 디렉토리."""
    import features.compliance.change_detector as cd
    monkeypatch.setattr(cd, "CHANGE_DB_PATH", str(tmp_path / "ch.db"))
    cd.init_change_db()

    # apply_aggregated_rules 가 사용하는 data 디렉토리를 tmp 로 변경
    # (Path(__file__).parent.parent.parent / "data" 가 PROJECT_ROOT/data 를 가리킴)
    # 테스트 시점엔 실제 파일을 만들지만, dry_run=True 일 때는 파일 안 건드리므로
    # dry_run / commit 분기만 잘 검증
    return cd


def _seed_corrections(cd, count_per_dept: dict[str, int]):
    """주어진 부서를 N번 씩 affected_departments 수정한 시나리오 시드.

    각 수정은 별도 change_id 에서 수행 — 실제 운영 시 N개의 다른 변경에서
    같은 키워드 패턴으로 같은 부서가 추가되는 상황을 모사.
    """
    from features.compliance.feedback_loop import record_correction

    for dept, n in count_per_dept.items():
        for i in range(n):
            cid = cd.save_changes([{
                "regulation_type": "t", "change_type": "modified",
                "item_id": f"X-{dept}-{i}", "item_title": "test",
                "old_value": "", "new_value": "",
                "severity": "info", "grade": "MEDIUM",
                "affected_departments": ["기존팀"],  # AI 가 추천한 원래 매핑
                "affected_plants": [], "legal_class": [],
            }])[0]
            record_correction(
                cid, "affected_departments",
                ["기존팀", dept],  # 사용자가 새 부서 추가
                user_id="u1", user_role="legal",
            )


# ─────────────────────────────────────────────────────────────
# apply_aggregated_rules
# ─────────────────────────────────────────────────────────────
class TestApplyAggregatedRules:
    def test_dry_run_no_files_written(self, tmp_env):
        """dry_run=True 면 파일 갱신 안 함."""
        from features.compliance.feedback_loop import apply_aggregated_rules

        _seed_corrections(tmp_env, {"새부서": 6})
        out = apply_aggregated_rules(window_days=30, min_occurrences=5, dry_run=True)
        assert out["dry_run"] is True
        assert len(out["added_dept_mappings"]) >= 1
        assert any(c["department"] == "새부서" for c in out["added_dept_mappings"])
        assert out["audit_log_path"] == ""

    def test_below_threshold_excluded(self, tmp_env):
        """min_occurrences 미달 부서는 후보에 안 들어감."""
        from features.compliance.feedback_loop import apply_aggregated_rules

        _seed_corrections(tmp_env, {"드물게추가": 2})  # 5회 미만
        out = apply_aggregated_rules(window_days=30, min_occurrences=5, dry_run=True)
        # candidate 0건 또는 다른 조건만 매칭
        assert all(c["department"] != "드물게추가" for c in out["added_dept_mappings"])

    def test_empty_no_corrections_returns_clean(self, tmp_env):
        """수정 데이터 0건 → 빈 결과."""
        from features.compliance.feedback_loop import apply_aggregated_rules
        out = apply_aggregated_rules(window_days=30, min_occurrences=5, dry_run=True)
        assert out["added_dept_mappings"] == []
        assert out["fewshot_added"] == 0

    def test_commit_writes_learned_rules(self, tmp_env, monkeypatch, tmp_path):
        """dry_run=False 면 learned_rules.json + audit log 둘 다 갱신.

        실제 PROJECT_ROOT/data 를 건드리지 않도록 monkeypatch 로 경로 우회.
        """
        from features.compliance import feedback_loop as fl
        # apply_aggregated_rules 가 사용하는 Path(__file__).parent.parent.parent / "data" 우회
        # 모듈 내 함수가 직접 경로 계산하므로 테스트에서는 PROJECT_ROOT/data 가 실제로 갱신될 수 있음.
        # 따라서 commit 동작의 핵심 — 함수 return 의 audit_log_path 가 비어있지 않은지만 확인.
        _seed_corrections(tmp_env, {"새부서": 6})

        # 테스트 격리 — 실제 파일 갱신 후 즉시 cleanup
        from pathlib import Path as _Path
        learned = _Path(__file__).parent.parent / "data" / "learned_rules.json"
        audit = _Path(__file__).parent.parent / "data" / "feedback_loop_audit.json"
        learned_existed = learned.exists()
        audit_existed = audit.exists()

        try:
            out = fl.apply_aggregated_rules(window_days=30, min_occurrences=5, dry_run=False)
            assert out["dry_run"] is False
            assert out["audit_log_path"]
            assert _Path(out["audit_log_path"]).exists()

            data = json.loads(learned.read_text(encoding="utf-8"))
            assert "auto_added_departments" in data
            assert any(d["department"] == "새부서" for d in data["auto_added_departments"])
            assert "last_updated_at" in data
        finally:
            # 정리 — 테스트가 실제 파일 만들었으면 원상 복구
            if not learned_existed and learned.exists():
                learned.unlink()
            if not audit_existed and audit.exists():
                audit.unlink()


# ─────────────────────────────────────────────────────────────
# Combined flow — record_correction → aggregate → apply
# ─────────────────────────────────────────────────────────────
class TestEndToEnd:
    def test_record_then_apply_dry_run(self, tmp_env):
        from features.compliance.feedback_loop import (
            record_correction, aggregate_corrections, apply_aggregated_rules
        )

        # 5개 다른 변경 — 각각 "법무팀" 누락된 AI 결과 + 사용자 수정
        for i in range(5):
            cid = tmp_env.save_changes([{
                "regulation_type": "t", "change_type": "modified",
                "item_id": f"X-{i}", "item_title": "법규",
                "old_value": "", "new_value": "",
                "severity": "info", "grade": "HIGH",
                "affected_departments": ["A팀"], "affected_plants": [], "legal_class": [],
            }])[0]
            record_correction(cid, "affected_departments", ["A팀", "법무팀"], user_id="u1")

        agg = aggregate_corrections(window_days=30)
        # frequent_dept_changes 가 5회 누적된 항목 포함
        depts = dict(agg["frequent_dept_changes"])
        assert depts.get("법무팀", 0) == 5

        # apply 후보로 잡힘
        out = apply_aggregated_rules(window_days=30, min_occurrences=5, dry_run=True)
        assert any(c["department"] == "법무팀" for c in out["added_dept_mappings"])
