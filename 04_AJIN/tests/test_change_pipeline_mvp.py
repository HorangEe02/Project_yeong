"""MVP 변경 감지 파이프라인 — 단위 테스트.

Stage 2 (diff) → Stage 3 (classify) → Stage 7 (DB save) → Stage 6 (notify) 의
4 시나리오 모두 검증:
  1. 첫 실행 — diff 스킵
  2. 두번째 실행 — modified 감지 + 분류 + DB 적재
  3. 노이즈 변경 — 자동 archive
  4. CRITICAL → Slack route (httpx mock)
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_change_db(monkeypatch, tmp_path):
    """격리된 변경 이력 DB."""
    db_path = str(tmp_path / "change.db")
    import features.compliance.change_detector as cd
    monkeypatch.setattr(cd, "CHANGE_DB_PATH", db_path)
    return db_path


@pytest.fixture(autouse=True)
def _no_slack(monkeypatch):
    """기본적으로 Slack webhook 미설정 — 테스트가 외부 호출 안 하도록."""
    import config
    monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", "")


# ─────────────────────────────────────────────────────────────
# Stage 3 — change_classifier
# ─────────────────────────────────────────────────────────────
class TestChangeClassifier:
    def test_is_substantive_added(self):
        from features.compliance.change_classifier import is_substantive_change
        assert is_substantive_change({"change_type": "added"}) is True
        assert is_substantive_change({"change_type": "removed"}) is True

    def test_is_substantive_real_modification(self):
        from features.compliance.change_classifier import is_substantive_change
        ch = {
            "change_type": "modified",
            "old_value": "penalties: '5년 이하' -> '7년 이하'",
        }
        assert is_substantive_change(ch) is True

    def test_is_substantive_whitespace_only(self):
        from features.compliance.change_classifier import is_substantive_change
        # 띄어쓰기만 다름 → 비실질
        ch = {
            "change_type": "modified",
            "old_value": "name: '제 38 조' -> '제38조'",
        }
        assert is_substantive_change(ch) is False

    def test_rule_based_summary(self):
        from features.compliance.change_classifier import _rule_based_summary
        assert "신설" in _rule_based_summary("프레스 안전기준", "added", "")
        assert "폐지" in _rule_based_summary("구 규제", "removed", "")
        assert "개정" in _rule_based_summary(
            "산안법", "modified", "name: 'a' -> 'b'; penalties: 'X' -> 'Y'"
        )

    def test_summarize_change_uses_rule_when_llm_unavailable(self, monkeypatch):
        """OLLAMA_BASE_URL 빈값 → 룰베이스 요약으로 폴백."""
        import config
        monkeypatch.setattr(config, "OLLAMA_BASE_URL", "")
        from features.compliance.change_classifier import summarize_change
        out = summarize_change({
            "change_type": "added",
            "item_title": "테스트 규제",
            "old_value": "",
        })
        assert "신설" in out
        assert "테스트 규제" in out

    def test_map_impact_uses_keywords(self):
        from features.compliance.change_classifier import map_impact
        ch = {
            "item_title": "프레스 안전거리 기준 강화",
            "new_value": "산안법 개정 — 프레스 라인 광전자 방호장치 추가 의무화",
        }
        map_impact(ch)
        depts = ch["affected_departments"]
        # 프레스 + 산안법 키워드 — 안전보건팀, 생산관리팀 등이 잡혀야 함
        assert "안전보건팀" in depts or "생산관리팀" in depts or "금형생산팀" in depts

    def test_assign_grade_added_with_penalty(self):
        from features.compliance.change_classifier import assign_grade
        ch = {
            "change_type": "added",
            "item_title": "산안법 38조 — 벌금 강화",
            "new_value": "벌금 5천만원 → 1억원, 즉시 시행",
            "old_value": "",
            "severity": "warning",
            "affected_departments": ["안전보건팀", "생산관리팀", "품질경영팀"],
        }
        # added (HIGH) + warning(+1) + dept≥3(+1) + penalty(+1) + 산안법 키워드(+1) → CRITICAL
        assert assign_grade(ch) == "CRITICAL"

    def test_assign_grade_minor_modification(self):
        from features.compliance.change_classifier import assign_grade
        ch = {
            "change_type": "modified",
            "item_title": "기타 규정",
            "new_value": "약간의 표현 변경",
            "old_value": "name: 'a' -> 'b'",
            "severity": "info",
            "affected_departments": [],
        }
        assert assign_grade(ch) in ("LOW", "MEDIUM")

    def test_classify_change_noise_archives(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "OLLAMA_BASE_URL", "")
        from features.compliance.change_classifier import classify_change
        ch = {
            "change_type": "modified",
            "item_id": "X-001",
            "item_title": "산안법",
            "old_value": "name: '제 38 조' -> '제38조'",
        }
        out = classify_change(ch)
        assert out["status"] == "filtered"
        assert out["is_substantive"] is False
        assert out["grade"] == "LOW"

    def test_classify_change_substantive_full_pipeline(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "OLLAMA_BASE_URL", "")
        from features.compliance.change_classifier import classify_change
        ch = {
            "change_type": "added",
            "item_id": "X-002",
            "item_title": "관세 25% 부과",
            "new_value": "자동차 부품 관세 25% 즉시 시행, 위반시 과징금",
            "old_value": "",
            "severity": "warning",
        }
        out = classify_change(ch)
        assert out["status"] == "pending"
        assert out["is_substantive"] is True
        # 관세 키워드 → 구매팀 매핑
        assert "구매팀" in out["affected_departments"]
        # added + warning + 관세 키워드 → 최소 HIGH 이상
        assert out["grade"] in ("HIGH", "CRITICAL")
        # summary 비어있지 않음
        assert out["summary_ko"]


# ─────────────────────────────────────────────────────────────
# Stage 7 — DB workflow
# ─────────────────────────────────────────────────────────────
class TestWorkflow:
    def test_save_then_transition(self, tmp_change_db):
        from features.compliance.change_detector import save_changes, update_change_status
        ids = save_changes([{
            "regulation_type": "test",
            "change_type": "modified",
            "item_id": "T-1",
            "item_title": "테스트",
            "old_value": "x",
            "new_value": "y",
            "severity": "info",
            "summary_ko": "1줄",
            "grade": "MEDIUM",
            "affected_departments": ["A팀"],
            "affected_plants": ["P-1"],
        }])
        assert len(ids) == 1
        cid = ids[0]

        assert update_change_status(cid, "reviewing", "user-x") is True
        assert update_change_status(cid, "done", "user-x") is True

        # audit_trail JSON list 에 두 transition 모두 기록
        conn = sqlite3.connect(tmp_change_db)
        row = conn.execute(
            "SELECT status, audit_trail FROM regulation_changes WHERE id = ?", (cid,)
        ).fetchone()
        conn.close()
        assert row[0] == "done"
        trail = json.loads(row[1])
        assert len(trail) == 2
        assert trail[0]["from"] == "pending" and trail[0]["to"] == "reviewing"
        assert trail[1]["from"] == "reviewing" and trail[1]["to"] == "done"

    def test_invalid_status_rejected(self, tmp_change_db):
        from features.compliance.change_detector import save_changes, update_change_status
        ids = save_changes([{
            "regulation_type": "t", "change_type": "modified",
            "item_id": "T-2", "item_title": "t",
            "old_value": "", "new_value": "",
        }])
        assert update_change_status(ids[0], "invalid_status", "u") is False

    def test_kpi_aggregation(self, tmp_change_db):
        from features.compliance.change_detector import save_changes, get_change_kpi
        save_changes([
            {"regulation_type": "t", "change_type": "added", "item_id": "1",
             "item_title": "a", "old_value": "", "new_value": "", "grade": "CRITICAL"},
            {"regulation_type": "t", "change_type": "added", "item_id": "2",
             "item_title": "b", "old_value": "", "new_value": "", "grade": "HIGH"},
            {"regulation_type": "t", "change_type": "added", "item_id": "3",
             "item_title": "c", "old_value": "", "new_value": "", "grade": "HIGH"},
        ])
        kpi = get_change_kpi()
        assert kpi["month_critical"] == 1
        assert kpi["month_high"] == 2
        assert kpi["open_count"] == 3  # 모두 pending


# ─────────────────────────────────────────────────────────────
# Stage 6 — Slack 라우팅
# ─────────────────────────────────────────────────────────────
class TestSlackRouting:
    def test_no_webhook_skips_silently(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", "")
        from features.compliance.notify_slack import route
        result = route({"grade": "CRITICAL", "item_title": "t"}, change_id=1)
        assert result is True  # graceful skip

    def test_medium_low_skipped_to_weekly(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", "https://hooks.slack/test")
        with patch("features.compliance.notify_slack.httpx.post") as mock_post:
            from features.compliance.notify_slack import route
            assert route({"grade": "MEDIUM", "item_title": "t"}, change_id=1) is True
            assert route({"grade": "LOW", "item_title": "t"}, change_id=2) is True
            # MEDIUM/LOW 는 즉시 발송 안 함
            mock_post.assert_not_called()

    def test_critical_calls_webhook(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", "https://hooks.slack/test")
        with patch("features.compliance.notify_slack.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status = lambda: None
            from features.compliance.notify_slack import route
            ok = route({
                "grade": "CRITICAL",
                "item_title": "관세 25% 시행",
                "summary_ko": "긴급",
                "change_type": "added",
                "affected_departments": ["구매팀"],
            }, change_id=42)
            assert ok is True
            assert mock_post.call_count == 1
            # payload 검증 — channel + grade emoji
            kwargs = mock_post.call_args.kwargs
            payload = kwargs["json"]
            assert payload["channel"] == "#alerts-critical"

    def test_route_batch_counts(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", "https://hooks.slack/test")
        with patch("features.compliance.notify_slack.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status = lambda: None
            from features.compliance.notify_slack import route_batch
            counts = route_batch(
                [
                    {"grade": "CRITICAL", "item_title": "a"},
                    {"grade": "HIGH", "item_title": "b"},
                    {"grade": "MEDIUM", "item_title": "c"},
                    {"grade": "LOW", "item_title": "d"},
                ],
                [1, 2, 3, 4],
            )
            assert counts["sent"] == 2  # CRITICAL + HIGH
            assert counts["skipped"] == 2
            assert counts["failed"] == 0


# ─────────────────────────────────────────────────────────────
# E2E — BaseCrawler._run_diff first-run guard
# ─────────────────────────────────────────────────────────────
class TestBaseCrawlerDiff:
    def test_first_run_no_diff(self, tmp_path, monkeypatch, tmp_change_db):
        """스냅샷 디렉터리가 비어있으면 (= 첫 실행) diff 스킵."""
        from features.compliance.base_crawler import BaseCrawler

        class _StubCrawler(BaseCrawler):
            crawler_name = "test_stub"
            display_name = "Test"
            doc_type = "TEST"
            legacy_filename = "test_stub.json"
            id_key = "id"

            def _credentials_ready(self) -> bool:
                return True

            def _fetch_live(self):
                return [{"id": "X-1", "name": "A", "v": 1}]

            def _curated_fallback(self):
                return [{"id": "X-1", "name": "A", "v": 1}]

        crawler = _StubCrawler(data_dir=tmp_path)
        result = crawler.crawl()
        # 첫 실행 — diff 결과 없거나 detected=0
        assert result.get("change_summary") is None or \
            result.get("change_summary", {}).get("detected", 0) == 0

        # 두 번째 — 다른 데이터로 fetch_live 교체
        class _StubCrawler2(_StubCrawler):
            def _fetch_live(self):
                return [{"id": "X-1", "name": "A", "v": 2}]  # v 변경
            crawler_name = "test_stub"  # 동일 디렉터리 재사용

        crawler2 = _StubCrawler2(data_dir=tmp_path)
        result2 = crawler2.crawl()
        cs = result2.get("change_summary") or {}
        assert cs.get("detected", 0) >= 1, f"두 번째 실행에서 변경 감지 실패: {result2}"
