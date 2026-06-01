"""P4 D16 — 2차/3차 협력사 그래프 단위 테스트."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_supplier_db(tmp_path, monkeypatch):
    """suppliers.db 를 임시 경로로 격리."""
    import features.compliance.supplier_compliance as sc
    monkeypatch.setattr(sc, "DB_PATH", tmp_path / "suppliers.db")
    sc.init_suppliers_db()
    return sc


def _add_supplier(
    sc, supplier_id, name="", parent="", tier_depth=1, country="KR",
    annual_volume_krw_mn=0, compliance_score=80, relation_type="direct",
):
    """suppliers row 직접 INSERT."""
    conn = sqlite3.connect(str(sc.DB_PATH))
    conn.execute(
        """INSERT INTO suppliers
           (supplier_id, name, tier, country, parent_supplier_id, tier_depth,
            annual_volume_krw_mn, compliance_score, relation_type)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (supplier_id, name or supplier_id, tier_depth, country, parent,
         tier_depth, annual_volume_krw_mn, compliance_score, relation_type),
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────
# Migration
# ─────────────────────────────────────────────────────────────


class TestMigration:
    def test_alter_table_idempotent(self, tmp_supplier_db):
        # init_suppliers_db 두 번 호출해도 오류 없어야 함
        tmp_supplier_db.init_suppliers_db()
        tmp_supplier_db.init_suppliers_db()
        conn = sqlite3.connect(str(tmp_supplier_db.DB_PATH))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(suppliers)").fetchall()]
        conn.close()
        assert "parent_supplier_id" in cols
        assert "tier_depth" in cols
        assert "relation_type" in cols


# ─────────────────────────────────────────────────────────────
# Traverse
# ─────────────────────────────────────────────────────────────


class TestTraverse:
    def test_down_three_depth(self, tmp_supplier_db):
        from features.compliance.supplier_graph import traverse
        _add_supplier(tmp_supplier_db, "S1", tier_depth=1)
        _add_supplier(tmp_supplier_db, "S2", parent="S1", tier_depth=2)
        _add_supplier(tmp_supplier_db, "S3", parent="S2", tier_depth=3)
        nodes = traverse("S1", max_depth=3, direction="down")
        ids = [n["supplier_id"] for n in nodes]
        assert ids == ["S1", "S2", "S3"]
        assert nodes[0]["depth_from_origin"] == 0
        assert nodes[1]["depth_from_origin"] == 1
        assert nodes[2]["depth_from_origin"] == 2

    def test_max_depth_cap(self, tmp_supplier_db):
        from features.compliance.supplier_graph import traverse
        _add_supplier(tmp_supplier_db, "S1", tier_depth=1)
        _add_supplier(tmp_supplier_db, "S2", parent="S1", tier_depth=2)
        _add_supplier(tmp_supplier_db, "S3", parent="S2", tier_depth=3)
        nodes = traverse("S1", max_depth=1, direction="down")
        ids = [n["supplier_id"] for n in nodes]
        # max_depth=1 — origin 까지만
        assert "S2" in ids  # depth 1 까지 포함
        assert "S3" not in ids

    def test_up_parent_chain(self, tmp_supplier_db):
        from features.compliance.supplier_graph import traverse
        _add_supplier(tmp_supplier_db, "ROOT", tier_depth=1)
        _add_supplier(tmp_supplier_db, "MID", parent="ROOT", tier_depth=2)
        _add_supplier(tmp_supplier_db, "LEAF", parent="MID", tier_depth=3)
        nodes = traverse("LEAF", max_depth=3, direction="up")
        ids = [n["supplier_id"] for n in nodes]
        assert ids[0] == "LEAF"
        assert "MID" in ids
        assert "ROOT" in ids

    def test_invalid_direction(self, tmp_supplier_db):
        from features.compliance.supplier_graph import traverse
        with pytest.raises(ValueError):
            traverse("X", direction="sideways")

    def test_empty_supplier_safe(self, tmp_supplier_db):
        from features.compliance.supplier_graph import traverse
        nodes = traverse("DOES_NOT_EXIST", max_depth=3, direction="down")
        assert nodes == []


# ─────────────────────────────────────────────────────────────
# Cycle
# ─────────────────────────────────────────────────────────────


class TestBfsPerformance:
    """P4.1 §7 — 1회 fetch BFS. 깊이 5 / fanout 2 = 약 31 노드."""

    def test_wide_tree_traverses_correctly(self, tmp_supplier_db):
        from features.compliance.supplier_graph import traverse
        # 깊이 4, fanout 3 트리: 1 + 3 + 9 + 27 = 40 노드
        _add_supplier(tmp_supplier_db, "ROOT")
        for d1 in ("a", "b", "c"):
            _add_supplier(tmp_supplier_db, f"L1_{d1}", parent="ROOT")
            for d2 in ("a", "b", "c"):
                _add_supplier(tmp_supplier_db, f"L2_{d1}_{d2}", parent=f"L1_{d1}")
                for d3 in ("a", "b", "c"):
                    _add_supplier(
                        tmp_supplier_db, f"L3_{d1}_{d2}_{d3}",
                        parent=f"L2_{d1}_{d2}",
                    )
        nodes = traverse("ROOT", max_depth=4, direction="down")
        # ROOT + 3 + 9 + 27 = 40
        assert len(nodes) == 40
        # depth 별 카운트
        by_depth: dict[int, int] = {}
        for n in nodes:
            by_depth[n["depth_from_origin"]] = by_depth.get(n["depth_from_origin"], 0) + 1
        assert by_depth == {0: 1, 1: 3, 2: 9, 3: 27}


class TestRelationType:
    """P4.1 §11 — traverse / cascading 결과에 relation_type 노출."""

    def test_traverse_includes_relation_type(self, tmp_supplier_db):
        from features.compliance.supplier_graph import traverse
        _add_supplier(tmp_supplier_db, "S1", relation_type="direct")
        _add_supplier(tmp_supplier_db, "S2", parent="S1", tier_depth=2,
                       relation_type="raw_material")
        nodes = traverse("S1", max_depth=3, direction="down")
        s2 = next(n for n in nodes if n["supplier_id"] == "S2")
        assert s2["relation_type"] == "raw_material"

    def test_default_relation_type_direct(self, tmp_supplier_db):
        from features.compliance.supplier_graph import traverse
        _add_supplier(tmp_supplier_db, "X1")  # default direct
        nodes = traverse("X1", max_depth=1, direction="down")
        assert nodes[0]["relation_type"] == "direct"


class TestCycles:
    def test_cycle_detected(self, tmp_supplier_db):
        from features.compliance.supplier_graph import detect_cycles, traverse
        _add_supplier(tmp_supplier_db, "A", parent="B")
        _add_supplier(tmp_supplier_db, "B", parent="A")
        cycles = detect_cycles()
        assert cycles  # 비어있지 않음
        # traverse 도 cycle 만나도 멈춰야 함 (TimeoutError 없이 정상 반환)
        nodes = traverse("A", max_depth=5, direction="up")
        assert len(nodes) >= 1


# ─────────────────────────────────────────────────────────────
# affected_suppliers_multi_tier
# ─────────────────────────────────────────────────────────────


class TestAffectedMultiTier:
    def test_max_depth_1_equivalent_to_p2(self, tmp_supplier_db, monkeypatch):
        """max_depth=1 — P2 D6 결과와 동일 (회귀 방지). match_method='primary'."""
        from features.compliance import supplier_graph as sg
        # match_suppliers mock — 1차 후보 1개만
        monkeypatch.setattr(
            "features.compliance.supplier_compliance.match_suppliers",
            lambda change, top_k=20: [{
                "supplier_id": "S1", "name": "1차", "tier": 1,
                "country": "KR", "match_reasons": ["관세"]
            }],
        )
        out = sg.affected_suppliers_multi_tier({"id": 1}, max_depth=1)
        assert len(out) == 1
        assert out[0]["supplier_id"] == "S1"
        assert out[0]["depth_from_match"] == 0
        assert out[0]["cascade_path"] == ["S1"]
        assert out[0]["match_method"] == "primary"

    def test_cascade_filtered_by_keyword(self, tmp_supplier_db, monkeypatch):
        """P5 §1 — keyword 매칭 안 되는 자식은 cascade 결과에서 제외."""
        from features.compliance import supplier_graph as sg
        _add_supplier(tmp_supplier_db, "S1", tier_depth=1)
        _add_supplier(tmp_supplier_db, "S2", parent="S1", tier_depth=2)
        _add_supplier(tmp_supplier_db, "S3", parent="S2", tier_depth=3)
        monkeypatch.setattr(
            "features.compliance.supplier_compliance.match_suppliers",
            lambda change, top_k=20: [{
                "supplier_id": "S1", "name": "1차", "tier": 1,
                "country": "KR", "match_reasons": ["관세"]
            }],
        )
        # change body 에 HS / keyword 가 자식에 매치되지 않음 → cascade 비어있어야
        out = sg.affected_suppliers_multi_tier(
            {"id": 1, "item_title": "전혀 무관한 변경", "summary_ko": ""},
            max_depth=3,
        )
        ids = [r["supplier_id"] for r in out]
        # primary S1 만 포함 (자식 keyword 매치 안 됨)
        assert ids == ["S1"]
        assert out[0]["match_method"] == "primary"

    def test_cascade_includes_children_when_keyword_matches(
        self, tmp_supplier_db, monkeypatch,
    ):
        """P5 §1 — components/HS keyword 매치하는 자식은 cascade 로 포함."""
        from features.compliance import supplier_graph as sg
        _add_supplier(tmp_supplier_db, "S1", tier_depth=1)
        _add_supplier(tmp_supplier_db, "S2", parent="S1", tier_depth=2)
        # S2 에 HS 8708 component 등록
        conn = sqlite3.connect(str(tmp_supplier_db.DB_PATH))
        conn.execute(
            """INSERT INTO supplier_components
               (supplier_id, component_code, hs_code, unit_price_krw, qty_per_year)
               VALUES (?,?,?,?,?)""",
            ("S2", "BRAKE_PAD", "8708.30", 10000, 50000),
        )
        conn.commit()
        conn.close()
        monkeypatch.setattr(
            "features.compliance.supplier_compliance.match_suppliers",
            lambda change, top_k=20: [{
                "supplier_id": "S1", "name": "1차", "tier": 1,
                "country": "KR", "match_reasons": ["관세"]
            }],
        )
        # change 본문에 HS 8708 포함 → S2 cascade 로 포함
        out = sg.affected_suppliers_multi_tier(
            {"id": 1, "item_title": "HS 8708 자동차 부품 관세 변경",
             "summary_ko": "8708 부품 관세율 인상"},
            max_depth=3,
        )
        ids = [r["supplier_id"] for r in out]
        assert "S1" in ids
        assert "S2" in ids
        s1 = next(r for r in out if r["supplier_id"] == "S1")
        s2 = next(r for r in out if r["supplier_id"] == "S2")
        assert s1["match_method"] == "primary"
        assert s2["match_method"] == "cascade"

    def test_no_primary_match_empty(self, tmp_supplier_db, monkeypatch):
        from features.compliance import supplier_graph as sg
        monkeypatch.setattr(
            "features.compliance.supplier_compliance.match_suppliers",
            lambda change, top_k=20: [],
        )
        out = sg.affected_suppliers_multi_tier({"id": 1}, max_depth=3)
        assert out == []
