"""조직도 시각화 — Plotly Treemap / Sunburst / 바 차트"""

import plotly.graph_objects as go
import plotly.express as px
from features.search.employee.database import EmployeeDatabase, POSITION_HIERARCHY

# HUD 테마에 맞는 색상 팔레트
BRAND_COLORS = [
    "#f9a70d", "#ff8c00", "#4CAF50", "#ffd700", "#ff3b3b",
    "#2e86c1", "#8e44ad", "#1abc9c", "#e74c3c", "#f39c12",
]

def _get_layout_defaults() -> dict:
    """v2.2: 테마에 따라 Plotly 레이아웃 기본값을 반환한다."""
    try:
        from ui.hud_style import get_current_theme
        theme = get_current_theme()
    except Exception:
        theme = "dark"

    if theme == "light":
        return dict(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1a1208", family="Rajdhani, Noto Sans KR, sans-serif"),
            margin=dict(t=50, b=10, l=10, r=10),
        )
    else:
        return dict(
            paper_bgcolor="#0c1018",
            plot_bgcolor="#0c1018",
            font=dict(color="#e8e0d4", family="Rajdhani, Noto Sans KR, sans-serif"),
            margin=dict(t=50, b=10, l=10, r=10),
        )


def _get_hover_style() -> dict:
    """v2.2: 테마에 따라 Plotly 호버 스타일을 반환한다."""
    try:
        from ui.hud_style import get_current_theme
        theme = get_current_theme()
    except Exception:
        theme = "dark"

    if theme == "light":
        return dict(
            bgcolor="#ffffff", bordercolor="#b07800",
            font=dict(family="Noto Sans KR, sans-serif", size=12, color="#1a1208"),
        )
    else:
        return dict(
            bgcolor="#1c2636", bordercolor="#f9a70d",
            font=dict(family="Noto Sans KR, sans-serif", size=12, color="#e8e0d4"),
        )


def _hover(text: str) -> str:
    """hover 문자열의 \\n을 Plotly 호환 <br>로 변환한다."""
    return text.replace("\n", "<br>")


def create_treemap(db: EmployeeDatabase):
    """5레벨 Treemap: 아진산업 → 본부 → 부서 → 직급 → 개인 (클릭 드릴다운)"""
    from collections import defaultdict

    data = db.get_org_tree()
    if not data:
        return None

    total = sum(r["headcount"] for r in data)
    labels, parents, values, hovers = ["아진산업"], [""], [total], [_hover(f"전체: {total}명")]
    added_divisions: set[str] = set()

    # 본부 노드
    for row in data:
        div = row["division"]
        if div not in added_divisions:
            div_total = sum(r["headcount"] for r in data if r["division"] == div)
            labels.append(div)
            parents.append("아진산업")
            values.append(div_total)
            hovers.append(_hover(f"{div}: {div_total}명"))
            added_divisions.add(div)

    # 팀 노드
    for row in data:
        dept, count = row["department"], row["headcount"]
        leader = row.get("team_leader_name", "")
        labels.append(dept)
        parents.append(row["division"])
        values.append(count)
        hovers.append(_hover(f"{dept}: {count}명\n팀장: {leader}" if leader else f"{dept}: {count}명"))

    # ── 직급 노드 + 개인 노드 (v2.0: 계층 체이닝 — 상무→부장→과장→…) ──
    pos_order = ["전무", "상무", "이사", "부장", "차장", "과장", "대리", "주임", "사원", "인턴"]

    for row in data:
        dept = row["department"]
        members = db.get_department_members(dept)

        by_pos: dict[str, list[dict]] = defaultdict(list)
        for m in members:
            by_pos[m["position"]].append(m)

        # 실제 존재하는 직급만 추출, 높은 직급순 정렬
        active_positions = sorted(
            [p for p in pos_order if by_pos.get(p)],
            key=lambda p: POSITION_HIERARCHY.get(p, 0),
            reverse=True,
        )
        if not active_positions:
            continue

        # 누적 인원 계산 (하위→상위): branchvalues="total" 호환
        cumulative: dict[str, int] = {}
        running = 0
        for pos in reversed(active_positions):
            running += len(by_pos[pos])
            cumulative[pos] = running

        # 계층 체이닝: 최고 직급 → dept, 이후 → 상위 직급 노드
        prev_parent = dept
        for pos in active_positions:
            group = by_pos[pos]
            pos_label = f"{dept} - {pos}"
            labels.append(pos_label)
            parents.append(prev_parent)
            values.append(cumulative[pos])
            hovers.append(_hover(f"{dept} {pos}: {len(group)}명"))

            for m in group:
                person_label = f"{m['name']} ({m['position']})"
                badge = " 👑️" if m.get("is_team_leader") else ""
                labels.append(person_label)
                parents.append(pos_label)
                values.append(1)
                hovers.append(_hover(
                    f"🪪 {m['name']}{badge}\n"
                    f"직급: {m['position']}\n"
                    f"☎️ {m.get('phone', '-')}\n"
                    f"📧 {m.get('email', '-')}"
                ))

            prev_parent = pos_label

    # ── v1.6: 해외법인 노드 추가 ──
    try:
        from config import OVERSEAS_SUBSIDIARIES
        labels.append("해외법인")
        parents.append("아진산업")
        overseas_total = len(OVERSEAS_SUBSIDIARIES)
        values.append(overseas_total)
        hovers.append(_hover(f"해외법인: {overseas_total}개소"))

        for sub_id, sub in OVERSEAS_SUBSIDIARIES.items():
            name = sub.get("name", sub_id)
            country = sub.get("country", "")
            products = sub.get("products", [])
            labels.append(name)
            parents.append("해외법인")
            values.append(1)
            hovers.append(_hover(
                f"🌍 {name}\n국가: {country}\n제품: {', '.join(products) if products else '-'}"
            ))
    except ImportError:
        pass

    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values,
        branchvalues="total",
        hovertext=hovers, hoverinfo="text", textinfo="label+value",
        marker=dict(colors=BRAND_COLORS * (len(labels) // len(BRAND_COLORS) + 1)),
        maxdepth=3,
    ))
    fig.update_layout(title="아진산업 조직도 (Treemap) — 부서 클릭 시 상세 보기",
                      height=600, hoverlabel=_get_hover_style(), **_get_layout_defaults())
    return fig


def create_sunburst(db: EmployeeDatabase):
    """5레벨 Sunburst: 아진산업 → 본부 → 부서 → 직급 → 개인 (클릭 드릴다운)"""
    from collections import defaultdict

    data = db.get_org_tree()
    if not data:
        return None

    total = sum(r["headcount"] for r in data)
    ids = ["아진산업"]
    labels = ["아진산업"]
    parents = [""]
    values = [total]
    hovers = [_hover(f"전체: {total}명")]

    added: set[str] = set()
    for row in data:
        div = row["division"]
        if div not in added:
            div_total = sum(r["headcount"] for r in data if r["division"] == div)
            ids.append(div)
            labels.append(div)
            parents.append("아진산업")
            values.append(div_total)
            hovers.append(_hover(f"{div}: {div_total}명"))
            added.add(div)

    for row in data:
        dept = row["department"]
        leader = row.get("team_leader_name", "")
        ids.append(dept)
        labels.append(dept)
        parents.append(row["division"])
        values.append(row["headcount"])
        hovers.append(_hover(f"{dept}: {row['headcount']}명\n팀장: {leader}" if leader else f"{dept}: {row['headcount']}명"))

    # v2.0: 계층 체이닝 — 상무→부장→과장→…
    pos_order = ["전무", "상무", "이사", "부장", "차장", "과장", "대리", "주임", "사원", "인턴"]

    for row in data:
        dept = row["department"]
        members = db.get_department_members(dept)

        by_pos: dict[str, list[dict]] = defaultdict(list)
        for m in members:
            by_pos[m["position"]].append(m)

        active_positions = sorted(
            [p for p in pos_order if by_pos.get(p)],
            key=lambda p: POSITION_HIERARCHY.get(p, 0),
            reverse=True,
        )
        if not active_positions:
            continue

        cumulative: dict[str, int] = {}
        running = 0
        for pos in reversed(active_positions):
            running += len(by_pos[pos])
            cumulative[pos] = running

        prev_parent_id = dept
        for pos in active_positions:
            group = by_pos[pos]
            pos_id = f"{dept}_{pos}"
            ids.append(pos_id)
            labels.append(pos)
            parents.append(prev_parent_id)
            values.append(cumulative[pos])
            hovers.append(_hover(f"{dept} {pos}: {len(group)}명"))

            for m in group:
                person_id = f"{dept}_{pos}_{m['employee_id']}"
                badge = " 👑️" if m.get("is_team_leader") else ""
                ids.append(person_id)
                labels.append(m["name"])
                parents.append(pos_id)
                values.append(1)
                hovers.append(_hover(
                    f"🪪 {m['name']}{badge}\n"
                    f"직급: {m['position']}\n"
                    f"☎️ {m.get('phone', '-')}\n"
                    f"📧 {m.get('email', '-')}"
                ))

            prev_parent_id = pos_id

    # ── v1.6: 해외법인 노드 추가 ──
    try:
        from config import OVERSEAS_SUBSIDIARIES
        ids.append("overseas")
        labels.append("해외법인")
        parents.append("아진산업")
        overseas_total = len(OVERSEAS_SUBSIDIARIES)
        values.append(overseas_total)
        hovers.append(_hover(f"해외법인: {overseas_total}개소"))

        for sub_id, sub in OVERSEAS_SUBSIDIARIES.items():
            name = sub.get("name", sub_id)
            country = sub.get("country", "")
            products = sub.get("products", [])
            ids.append(sub_id)
            labels.append(name)
            parents.append("overseas")
            values.append(1)
            hovers.append(_hover(
                f"🌍 {name}\n국가: {country}\n제품: {', '.join(products) if products else '-'}"
            ))
    except ImportError:
        pass

    fig = go.Figure(go.Sunburst(
        ids=ids, labels=labels, parents=parents, values=values,
        branchvalues="total",
        hovertext=hovers, hoverinfo="text",
        maxdepth=3,
        marker=dict(colors=BRAND_COLORS * (len(ids) // len(BRAND_COLORS) + 1)),
    ))
    fig.update_layout(title="아진산업 조직 구성 (Sunburst) — 부서 클릭 시 상세 보기",
                      height=600, hoverlabel=_get_hover_style(), **_get_layout_defaults())
    return fig


def create_plant_bar(db: EmployeeDatabase):
    data = db.get_plant_headcount()
    if not data:
        return None
    fig = go.Figure(go.Bar(
        x=[d["plant"] for d in data], y=[d["headcount"] for d in data],
        marker_color="#f9a70d",
        text=[f"{d['headcount']}명" for d in data], textposition="auto",
    ))
    fig.update_layout(title="공장별 인원 분포", xaxis_title="공장", yaxis_title="인원 수",
                      height=400, **_get_layout_defaults())
    return fig


def create_position_pie(db: EmployeeDatabase):
    data = db.get_position_distribution()
    if not data:
        return None
    fig = px.pie(
        names=[d["position"] for d in data], values=[d["headcount"] for d in data],
        color_discrete_sequence=BRAND_COLORS, title="직급별 인원 분포",
    )
    fig.update_layout(height=400, **_get_layout_defaults())
    return fig


def create_org_tree(db: EmployeeDatabase):
    """트리형 조직도 — 대표이사 → 본부 → 팀 계층 구조를 노드+엣지로 시각화한다."""
    data = db.get_org_tree()
    if not data:
        return None

    from collections import defaultdict

    # 본부별 그룹핑
    divisions: dict[str, list[dict]] = defaultdict(list)
    for row in data:
        divisions[row["division"]].append(row)

    div_list = list(divisions.keys())
    n_divs = len(div_list)

    # 좌표 계산
    nodes_x, nodes_y, nodes_text, nodes_hover, nodes_color, nodes_size = [], [], [], [], [], []
    edges_x, edges_y = [], []

    # 루트: 대표이사
    root_x, root_y = 0.5, 1.0
    total = db.get_total_headcount()
    nodes_x.append(root_x); nodes_y.append(root_y)
    nodes_text.append("대표이사")
    nodes_hover.append(_hover(f"아진산업 대표이사\n전체 {total}명"))
    nodes_color.append("#f9a70d"); nodes_size.append(28)

    # 본부 노드 (y=0.75)
    div_y = 0.78
    div_positions = {}
    for i, div_name in enumerate(div_list):
        x = (i + 0.5) / n_divs
        div_positions[div_name] = x
        div_total = sum(r["headcount"] for r in divisions[div_name])

        nodes_x.append(x); nodes_y.append(div_y)
        nodes_text.append(div_name.replace("본부", "\n본부").replace("연구소", "\n연구소"))
        nodes_hover.append(_hover(f"{div_name}: {div_total}명"))
        nodes_color.append("#ff8c00"); nodes_size.append(22)

        # 엣지: 루트 → 본부
        edges_x += [root_x, x, None]
        edges_y += [root_y, div_y, None]

    # ── 팀장 연락처 일괄 조회 (v1.2: 호버에 연락처 표시용) ──
    _leader_cache: dict[str, dict] = {}
    for row in data:
        dept_name = row["department"]
        if row.get("team_leader_name"):
            info = db.get_team_leader(dept_name)
            if info:
                _leader_cache[dept_name] = info

    # 팀 노드 (y=0.45)
    team_y = 0.45
    team_positions = {}
    for div_name, teams in divisions.items():
        div_x = div_positions[div_name]
        n_teams = len(teams)
        # 본부 중심 기준으로 팀을 좌우로 펼침
        span = min(0.12, 0.8 / n_divs)
        for j, team in enumerate(teams):
            if n_teams == 1:
                tx = div_x
            else:
                tx = div_x - span / 2 + (span / (n_teams - 1)) * j

            dept_name = team["department"]
            leader = team.get("team_leader_name", "")
            count = team["headcount"]
            team_positions[dept_name] = tx

            nodes_x.append(tx); nodes_y.append(team_y)
            short = dept_name.replace("팀", "\n팀").replace("원", "\n원")
            nodes_text.append(short)
            # v1.4: 부서 호버에 팀장 연락처+이메일 포함 (<br> 줄바꿈)
            hover = f"{dept_name}: {count}명"
            if leader:
                li = _leader_cache.get(dept_name, {})
                phone = li.get("phone", "-") if li else "-"
                email = li.get("email", "-") if li else "-"
                hover += f"\n팀장: {leader}\n📞 {phone}\n✉ {email}"
            nodes_hover.append(_hover(hover))
            nodes_color.append("#4CAF50"); nodes_size.append(16)

            # 엣지: 본부 → 팀
            edges_x += [div_x, tx, None]
            edges_y += [div_y, team_y, None]

    # 팀장 노드 (y=0.15) — v1.2: 이름/직급/대표 연락처 말풍선
    leader_y = 0.18
    for div_name, teams in divisions.items():
        for team in teams:
            dept_name = team["department"]
            leader = team.get("team_leader_name", "")
            leader_pos = team.get("team_leader_position", "")
            if not leader:
                continue
            tx = team_positions[dept_name]

            # v1.2: 팀장 상세 연락처 hover
            li = _leader_cache.get(dept_name, {})
            phone = li.get("phone", "-") if li else "-"
            email = li.get("email", "-") if li else "-"

            nodes_x.append(tx); nodes_y.append(leader_y)
            nodes_text.append(leader)
            nodes_hover.append(_hover(
                f"🪪 {leader}\n"
                f"직급: {leader_pos}\n"
                f"부서: {dept_name}\n"
                f"☎️ {phone}\n"
                f"📧 {email}"
            ))
            nodes_color.append("#ffd700"); nodes_size.append(12)

            edges_x += [tx, tx, None]
            edges_y += [team_y, leader_y, None]

    # ── v1.6: 해외법인 노드 (y=0.05) ──
    try:
        from config import OVERSEAS_SUBSIDIARIES
        overseas_y = 0.05
        overseas_list = list(OVERSEAS_SUBSIDIARIES.values())
        n_overseas = len(overseas_list)
        if n_overseas > 0:
            for i, sub in enumerate(overseas_list):
                ox = (i + 0.5) / n_overseas
                name = sub.get("name", "")
                country = sub.get("country", "")
                city = sub.get("city", "")
                products = sub.get("products", [])

                nodes_x.append(ox); nodes_y.append(overseas_y)
                short_name = name.split("(")[0].strip() if "(" in name else name
                nodes_text.append(short_name[:8])
                nodes_hover.append(_hover(
                    f"🌍 {name}\n"
                    f"국가: {country}\n"
                    f"위치: {city}\n"
                    f"제품: {', '.join(products) if products else '-'}"
                ))
                # 해외법인은 시안(cyan) 색상
                nodes_color.append("#1abc9c"); nodes_size.append(14)

                # 루트 → 해외법인 엣지 (점선 효과를 위해 별도 trace 추가 안 하고 일반 엣지)
                edges_x += [root_x, ox, None]
                edges_y += [root_y, overseas_y, None]
    except ImportError:
        pass

    # 그래프 생성
    fig = go.Figure()

    # 엣지 (선)
    fig.add_trace(go.Scatter(
        x=edges_x, y=edges_y, mode="lines",
        line=dict(color="#D5CFC5", width=1.5),
        hoverinfo="none",
    ))

    # 노드 (점 + 텍스트)
    fig.add_trace(go.Scatter(
        x=nodes_x, y=nodes_y, mode="markers+text",
        marker=dict(size=nodes_size, color=nodes_color, line=dict(width=1, color="#1c2636")),
        text=nodes_text, textposition="bottom center",
        textfont=dict(size=9, color=_get_layout_defaults()["font"]["color"], family="Noto Sans KR, sans-serif"),
        hovertext=nodes_hover, hoverinfo="text",
    ))

    fig.update_layout(
        title="아진산업 조직도 (국내 + 해외법인)",
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.05, 1.05]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.05, 1.08]),
        height=700,
        hoverlabel=_get_hover_style(),
        **_get_layout_defaults(),
    )
    return fig


def create_dept_org_chart(db: EmployeeDatabase, department: str):
    """부서별 트리형 조직도 — 팀장 → 직급별 → 개인을 노드+엣지로 시각화한다."""
    from collections import defaultdict

    members = db.get_department_members(department)
    if not members:
        return None

    leader = next((m for m in members if m.get("is_team_leader")), None)
    leader_name = leader["name"] if leader else department

    # 직급별 그룹핑
    by_position: dict[str, list[dict]] = defaultdict(list)
    for m in members:
        by_position[m["position"]].append(m)

    pos_order = ["전무", "상무", "이사", "부장", "차장", "과장", "대리", "주임", "사원", "인턴"]
    pos_colors = {
        "전무": "#ff3b3b", "상무": "#ff3b3b", "이사": "#e74c3c",
        "부장": "#f9a70d", "차장": "#ff8c00", "과장": "#ffd700",
        "대리": "#4CAF50", "주임": "#2e86c1", "사원": "#8e44ad", "인턴": "#95a5a6",
    }

    # v2.0: 직급 그룹을 수직 계층으로 배치 (상무→부장→과장→…)
    active_positions = sorted(
        [p for p in pos_order if by_position.get(p)],
        key=lambda p: POSITION_HIERARCHY.get(p, 0),
        reverse=True,
    )
    n_levels = len(active_positions)

    nodes_x, nodes_y, nodes_text, nodes_hover, nodes_color, nodes_size = [], [], [], [], [], []
    edges_x, edges_y = [], []

    # 루트: 부서명
    root_x, root_y = 0.5, 1.0
    nodes_x.append(root_x); nodes_y.append(root_y)
    nodes_text.append(f"{department} ({len(members)}명)")
    nodes_hover.append(_hover(f"{department}\n전체 {len(members)}명\n팀장: {leader_name}"))
    nodes_color.append("#f9a70d"); nodes_size.append(30)

    # 직급 그룹 노드 — 수직 체이닝
    # y 범위: 0.85 (최고직급) ~ 0.30 (최저직급), 개인은 그 아래
    level_positions: dict[str, tuple[float, float]] = {}  # pos -> (x, y)
    prev_x, prev_y = root_x, root_y

    for i, pos in enumerate(active_positions):
        count = len(by_position[pos])
        gy = 0.85 - (i * 0.50 / max(n_levels - 1, 1)) if n_levels > 1 else 0.65
        gx = 0.5  # 중앙 정렬

        level_positions[pos] = (gx, gy)
        nodes_x.append(gx); nodes_y.append(gy)
        nodes_text.append(f"{pos} ({count}명)")
        nodes_hover.append(f"{pos}: {count}명")
        nodes_color.append(pos_colors.get(pos, "#888")); nodes_size.append(20)

        # 엣지: 이전 노드(부서 또는 상위 직급) → 현재 직급
        edges_x += [prev_x, gx, None]
        edges_y += [prev_y, gy, None]
        prev_x, prev_y = gx, gy

    # 개인 노드 — 각 직급 옆에 수평 팬아웃
    for pos in active_positions:
        group = by_position[pos]
        gx, gy = level_positions[pos]
        n_people = len(group)
        person_y = gy  # 같은 높이에 좌우로 배치

        # 직급 노드 우측으로 개인 펼침
        for j, m in enumerate(group):
            offset = 0.08 + j * 0.06
            px = gx + offset
            if px > 0.98:
                px = gx - 0.08 - (j - (0.98 - gx - 0.08) / 0.06) * 0.06

            badge = " (팀장)" if m.get("is_team_leader") else ""
            nodes_x.append(px); nodes_y.append(person_y)
            nodes_text.append(m["name"])
            nodes_hover.append(_hover(
                f"🪪 {m['name']} {m['position']}{badge}\n"
                f"☎️ {m.get('phone', '-')}\n"
                f"📧 {m.get('email', '-')}\n"
                f"내선: {m.get('extension', '-')}"
            ))
            color = "#f9a70d" if m.get("is_team_leader") else pos_colors.get(pos, "#888")
            nodes_color.append(color)
            nodes_size.append(14 if m.get("is_team_leader") else 10)

            edges_x += [gx, px, None]
            edges_y += [gy, person_y, None]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=edges_x, y=edges_y, mode="lines",
        line=dict(color="#D5CFC5", width=1.2),
        hoverinfo="none",
    ))

    fig.add_trace(go.Scatter(
        x=nodes_x, y=nodes_y, mode="markers+text",
        marker=dict(size=nodes_size, color=nodes_color, line=dict(width=1, color="#1c2636")),
        text=nodes_text, textposition="bottom center",
        textfont=dict(size=9, color=_get_layout_defaults()["font"]["color"], family="Noto Sans KR, sans-serif"),
        hovertext=nodes_hover, hoverinfo="text",
    ))

    fig.update_layout(
        title=f"{department} 조직도 (팀장: {leader_name})",
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.05, 1.15]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0.2, 1.1]),
        height=600,
        hoverlabel=_get_hover_style(),
        **_get_layout_defaults(),
    )
    return fig


# ─────────────────────────────────────────────
# v2.6: 카드형 조직도 (HTML/CSS)
# ─────────────────────────────────────────────

_AVATAR_COLORS_DIV = ["#2e86c1", "#8e44ad", "#1abc9c", "#e67e22", "#e74c3c", "#27ae60", "#f39c12"]

def _get_theme_colors() -> dict:
    """현재 테마에 맞는 색상 딕셔너리를 반환한다."""
    try:
        from ui.hud_style import get_current_theme
        theme = get_current_theme()
    except Exception:
        theme = "dark"
    if theme == "light":
        return {"bg": "#ffffff", "text": "#1a1208", "sub": "#6b5d4a", "border": "#c8bda8",
                "line": "#c8bda8", "surface": "#f5f0e8", "shadow": "rgba(0,0,0,0.08)"}
    return {"bg": "#141c28", "text": "#e8e0d4", "sub": "#D5CFC5", "border": "#3d2e10",
            "line": "#3d2e10", "surface": "#0c1018", "shadow": "rgba(0,0,0,0.4)"}


def _esc(text: str) -> str:
    """HTML 이스케이프."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _card(name: str, sub: str, avatar_bg: str, avatar_icon: str = "👤",
          tooltip: str = "", wide: bool = False, small: bool = False) -> str:
    """카드 노드 HTML을 생성한다."""
    c = _get_theme_colors()
    w = "min-width:180px;" if wide else ("min-width:70px;" if small else "min-width:100px;")
    fs_name = "13px" if wide else ("9px" if small else "11px")
    fs_sub = "8px" if small else "9px"
    av_size = "34px" if wide else ("20px" if small else "26px")
    pad = "8px 14px" if wide else ("3px 7px" if small else "5px 10px")
    title_attr = f' title="{_esc(tooltip)}"' if tooltip else ""

    return f'''<div class="ocard" style="display:inline-flex;align-items:center;gap:8px;
        padding:{pad};border-radius:8px;background:{c['bg']};
        border:1px solid {c['border']};box-shadow:0 2px 8px {c['shadow']};
        {w}cursor:default;white-space:nowrap;"{title_attr}>
        <div style="width:{av_size};height:{av_size};border-radius:50%;
            background:{avatar_bg};display:flex;align-items:center;
            justify-content:center;font-size:14px;flex-shrink:0;">{avatar_icon}</div>
        <div style="overflow:hidden;">
            <div style="font-family:Rajdhani,sans-serif;font-weight:600;
                font-size:{fs_name};color:{c['text']};overflow:hidden;
                text-overflow:ellipsis;">{_esc(name)}</div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:{fs_sub};
                color:{c['sub']};overflow:hidden;text-overflow:ellipsis;">{_esc(sub)}</div>
        </div>
    </div>'''



def _tree_css() -> str:
    """CSS 트리 레이아웃 (직각 연결선)."""
    c = _get_theme_colors()
    return f'''
    .otree,.otree ul,.otree li{{list-style:none;margin:0;padding:0;}}
    .otree{{display:flex;justify-content:center;padding-top:6px;}}
    .otree li{{display:flex;flex-direction:column;align-items:center;position:relative;
        padding:24px 4px 0;}}
    .otree li::before{{content:'';position:absolute;top:0;left:50%;
        border-left:2px solid {c['line']};height:24px;}}
    .otree > li::before{{display:none;}}
    .otree ul{{display:flex;justify-content:center;position:relative;padding-top:24px;}}
    .otree ul::before{{content:'';position:absolute;top:0;
        border-top:2px solid {c['line']};}}
    .otree ul > li:first-child::before{{left:50%;}}
    .otree ul > li:last-child::before{{left:50%;}}
    .otree ul > li:only-child::before{{left:50%;height:24px;}}
    .otree ul > li{{position:relative;}}
    .otree ul > li:not(:first-child):not(:last-child)::after{{
        content:'';position:absolute;top:0;left:0;right:0;border-top:2px solid {c['line']};}}
    .otree ul > li:first-child::after{{
        content:'';position:absolute;top:0;left:50%;right:0;border-top:2px solid {c['line']};}}
    .otree ul > li:last-child::after{{
        content:'';position:absolute;top:0;left:0;right:50%;border-top:2px solid {c['line']};}}
    .otree ul > li:only-child::after{{display:none;}}
    .ocard:hover{{filter:brightness(1.1);transition:filter 0.15s;}}
    /* v2.6: 스크롤바 오렌지 테마 */
    *::-webkit-scrollbar{{height:14px !important;width:14px !important;}}
    *::-webkit-scrollbar-track{{background:{c['border']} !important;border-radius:7px !important;}}
    *::-webkit-scrollbar-thumb{{background:#ff8c00 !important;border-radius:7px !important;min-height:40px;}}
    *::-webkit-scrollbar-thumb:hover{{background:#f9a70d !important;}}
    '''


def create_org_tree_html(db: EmployeeDatabase, show_overseas: bool = True) -> str:
    """v2.6: 카드형 조직도 HTML을 반환한다."""
    from collections import defaultdict

    data = db.get_org_tree()
    if not data:
        return ""

    total = db.get_total_headcount()
    c = _get_theme_colors()

    # 본부별 그룹
    divs: dict[str, list[dict]] = defaultdict(list)
    for row in data:
        divs[row["division"]].append(row)

    # v2.6: 본부 레벨까지만 표시 (팀 노드 제거 — 부서별 조직도에서 상세 확인)
    div_items = []
    for i, (div_name, teams) in enumerate(divs.items()):
        div_total = sum(t["headcount"] for t in teams)
        n_teams = len(teams)
        color = _AVATAR_COLORS_DIV[i % len(_AVATAR_COLORS_DIV)]

        team_names = ", ".join(t["department"] for t in teams)
        sub = f"{n_teams}팀 · {div_total}명"
        tip = f"{div_name}\n소속: {team_names}"
        div_card = _card(div_name, sub, color, "🏛️", tip)
        div_items.append(f"<li>{div_card}</li>")

    # ── 국내 트리 ──
    root_card = _card("대표이사", f"아진산업 | {total}명", "#e74c3c", "👑", wide=True)
    children_ul = f"<ul>{''.join(div_items)}</ul>"

    # v2.6: 본부 수 기준으로 폭 계산 (팀 노드 없으므로 축소)
    n_divs = len(divs)
    est_width = max(700, n_divs * 160)

    # 국내 섹션 헤더
    domestic_header = f'''<div style="font-family:Orbitron,monospace;font-size:14px;
        color:{c['text']};letter-spacing:3px;margin:12px 0 8px 0;padding-bottom:6px;
        border-bottom:2px solid {c['border']};">
        ■ 국내 — DOMESTIC
    </div>'''

    domestic_tree = f'<ul class="otree"><li>{root_card}{children_ul}</li></ul>'

    # ── 해외 트리 (지역별 그룹핑) ──
    overseas_html = ""
    if show_overseas:
        try:
            from config import OVERSEAS_SUBSIDIARIES
            from collections import OrderedDict

            # 지역별 그룹핑
            _REGION_MAP = {
                "미국": {"color": "#2e86c1", "icon": "🇺🇸"},
                "중국": {"color": "#e74c3c", "icon": "🇨🇳"},
                "베트남": {"color": "#27ae60", "icon": "🇻🇳"},
            }
            regions: dict[str, list[dict]] = OrderedDict()
            for sid, sub_info in OVERSEAS_SUBSIDIARIES.items():
                country = sub_info.get("country", "기타")
                if country not in regions:
                    regions[country] = []
                regions[country].append(sub_info)

            region_lis = []
            for region_name, subs in regions.items():
                rm = _REGION_MAP.get(region_name, {"color": "#8d6e63", "icon": "🌍"})

                sub_lis = []
                for s in subs:
                    name = s.get("name", "")
                    city = s.get("city", "")
                    products = s.get("products", [])
                    tip = f"{name}\n도시: {city}\n제품: {', '.join(products)}" if products else f"{name}\n도시: {city}"
                    sub_lis.append(f"<li>{_card(name, city, rm['color'], rm['icon'], tip, small=True)}</li>")

                region_card = _card(region_name, f"{len(subs)}개 법인", rm["color"], rm["icon"])
                sub_ul = f"<ul>{''.join(sub_lis)}</ul>" if sub_lis else ""
                region_lis.append(f"<li>{region_card}{sub_ul}</li>")

            if region_lis:
                overseas_root = _card("해외법인", f"{len(OVERSEAS_SUBSIDIARIES)}개소", "#1abc9c", "🌍", wide=True)
                overseas_children = f"<ul>{''.join(region_lis)}</ul>"

                overseas_header = f'''<div style="font-family:Orbitron,monospace;font-size:14px;
                    color:{c['text']};letter-spacing:3px;margin:24px 0 8px 0;padding-bottom:6px;
                    border-bottom:2px solid {c['border']};">
                    ■ 해외 — OVERSEAS
                </div>'''

                overseas_html = f'''{overseas_header}
                <ul class="otree"><li>{overseas_root}{overseas_children}</li></ul>'''
        except ImportError:
            pass

    html = f'''<style>{_tree_css()}</style>
    <div id="org-tree-scroll" style="overflow-x:auto;overflow-y:auto;background:{c['surface']};
        border-radius:12px;border:1px solid {c['border']};padding:12px;
        scrollbar-width:auto;scrollbar-color:#f9a70d {c['border']};">
        <div style="min-width:{est_width}px;transform:scale(0.88);transform-origin:top center;">
            <div style="text-align:center;font-family:Orbitron,monospace;font-size:13px;
                color:{c['sub']};letter-spacing:3px;margin-bottom:16px;">
                ORGANIZATIONAL CHART — 아진산업 조직도
            </div>
            {domestic_header}
            {domestic_tree}
            {overseas_html}
        </div>
    </div>
    <script>
    (function(){{
        var f=window.frameElement;
        if(f){{var d=document.documentElement;f.style.height=(d.scrollHeight+40)+'px';}}
    }})();
    </script>'''

    return html


def _dept_chart_css() -> str:
    """v2.6: 부서별 직급 행 그리드 레이아웃 CSS."""
    c = _get_theme_colors()
    return f'''
    .dept-chart{{text-align:center;}}
    .pos-row{{margin:0 auto;padding:4px 0;}}
    .pos-label{{font-family:Rajdhani,sans-serif;font-weight:700;font-size:11px;
        color:{c['sub']};letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;}}
    .pos-cards{{display:flex;flex-wrap:wrap;justify-content:center;gap:10px;}}
    .pcard{{display:inline-flex;align-items:center;gap:8px;
        padding:7px 12px;border-radius:8px;min-width:120px;max-width:200px;
        cursor:default;transition:filter 0.15s;white-space:nowrap;
        box-shadow:0 2px 6px {c['shadow']};}}
    .pcard:hover{{filter:brightness(1.12);}}
    .pcard .av{{width:28px;height:28px;border-radius:50%;display:flex;
        align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}}
    .pcard .nm{{font-family:Rajdhani,'Noto Sans KR',sans-serif;font-weight:700;
        font-size:13px;color:{c['text']};overflow:hidden;text-overflow:ellipsis;}}
    .pcard .ti{{font-family:'Share Tech Mono',monospace;font-size:9px;
        color:{c['sub']};overflow:hidden;text-overflow:ellipsis;}}
    .pcard .ext{{font-family:'Share Tech Mono',monospace;font-size:8px;color:{c['sub']};}}
    .conn-line{{width:2px;height:20px;margin:0 auto;background:{c['line']};}}
    .conn-branch{{display:flex;justify-content:center;align-items:flex-start;}}
    .conn-branch::before{{content:'';display:block;height:2px;
        background:{c['line']};flex:1;max-width:200px;margin-top:0;}}
    /* 직급별 색상 */
    .pcard.lv-exec{{background:{c['bg']};border-left:3px solid #e74c3c;}}
    .pcard.lv-exec .av{{background:#e74c3c33;}}
    .pcard.lv-mgr{{background:{c['bg']};border-left:3px solid #f9a70d;}}
    .pcard.lv-mgr .av{{background:#f9a70d33;}}
    .pcard.lv-senior{{background:{c['bg']};border-left:3px solid #4CAF50;}}
    .pcard.lv-senior .av{{background:#4CAF5033;}}
    .pcard.lv-staff{{background:{c['bg']};border-left:3px solid #2e86c1;}}
    .pcard.lv-staff .av{{background:#2e86c133;}}
    .pcard.lv-leader{{background:#f9a70d18;border:2px solid #f9a70d;}}
    .pcard.lv-leader .av{{background:#f9a70d44;}}
    /* v2.6: 스크롤바 오렌지 테마 */
    *::-webkit-scrollbar{{height:14px !important;width:14px !important;}}
    *::-webkit-scrollbar-track{{background:{c['border']} !important;border-radius:7px !important;}}
    *::-webkit-scrollbar-thumb{{background:#ff8c00 !important;border-radius:7px !important;min-height:40px;}}
    *::-webkit-scrollbar-thumb:hover{{background:#f9a70d !important;}}
    '''


def _pos_level_class(position: str, is_leader: bool = False) -> str:
    """직급에 따른 CSS 클래스를 반환한다."""
    if is_leader:
        return "lv-leader"
    if position in ("전무", "상무", "이사"):
        return "lv-exec"
    if position in ("부장", "차장"):
        return "lv-mgr"
    if position in ("과장", "대리"):
        return "lv-senior"
    return "lv-staff"


def create_dept_org_chart_html(db: EmployeeDatabase, department: str) -> str:
    """v2.6: 부서별 직급 행 그리드 조직도 HTML을 반환한다.

    첨부 이미지 참조 — 직급별로 한 행(Row)에 카드를 배치하여 이름 가독성을 확보한다.
    """
    from collections import defaultdict

    members = db.get_department_members(department)
    if not members:
        return ""

    c = _get_theme_colors()
    leader = next((m for m in members if m.get("is_team_leader")), None)
    leader_name = leader["name"] if leader else department

    pos_order = ["전무", "상무", "이사", "부장", "차장", "과장", "대리", "주임", "사원", "인턴"]

    by_pos: dict[str, list[dict]] = defaultdict(list)
    for m in members:
        by_pos[m["position"]].append(m)

    active = [p for p in pos_order if by_pos.get(p)]

    def _person_card(m: dict) -> str:
        is_lead = bool(m.get("is_team_leader"))
        cls = _pos_level_class(m["position"], is_lead)
        icon = "👑" if is_lead else "👤"
        badge = " · 팀장" if is_lead else ""
        ext = m.get("extension", "")
        ext_html = f'<div class="ext">내선 {_esc(ext)}</div>' if ext else ""
        tip = (f"{m['name']} {m['position']}{badge}\n"
               f"☎️ {m.get('phone', '-')}\n"
               f"📧 {m.get('email', '-')}\n"
               f"내선: {ext or '-'}")
        return f'''<div class="pcard {cls}" title="{_esc(tip)}">
            <div class="av">{icon}</div>
            <div>
                <div class="nm">{_esc(m['name'])}</div>
                <div class="ti">{_esc(m['position'])}{_esc(badge)}</div>
                {ext_html}
            </div>
        </div>'''

    # ── 행 조립 ──
    rows_html = []

    # 팀장 행 (별도 — 최상단)
    if leader:
        rows_html.append(f'''<div class="pos-row">
            <div class="pos-label">TEAM LEADER</div>
            <div class="pos-cards">{_person_card(leader)}</div>
        </div>''')

    # 나머지 직급 행
    for pos in active:
        group = by_pos[pos]
        # 팀장은 이미 표시했으므로 제외
        non_leader = [m for m in group if not m.get("is_team_leader")]
        if not non_leader:
            continue

        cards = "".join(_person_card(m) for m in non_leader)

        # 연결선 + 직급 행
        rows_html.append(f'<div class="conn-line"></div>')
        rows_html.append(f'''<div class="pos-row">
            <div class="pos-label">{_esc(pos)} ({len(non_leader)}명)</div>
            <div class="pos-cards">{cards}</div>
        </div>''')

    body = "\n".join(rows_html)

    html = f'''<style>{_dept_chart_css()}</style>
    <div id="dept-chart-scroll" style="overflow-x:auto;overflow-y:auto;background:{c['surface']};
        border-radius:12px;border:1px solid {c['border']};padding:16px;
        scrollbar-width:auto;scrollbar-color:#f9a70d {c['border']};">
        <div class="dept-chart">
            <div style="text-align:center;font-family:Orbitron,monospace;font-size:12px;
                color:{c['sub']};letter-spacing:2px;margin-bottom:12px;">
                {_esc(department)} — DEPARTMENT CHART
            </div>
            <div style="text-align:center;font-family:Rajdhani,sans-serif;font-size:16px;
                font-weight:700;color:{c['text']};margin-bottom:16px;">
                {_esc(department)} ({len(members)}명)
            </div>
            {body}
        </div>
    </div>
    <script>
    (function(){{
        var f=window.frameElement;
        if(f){{
            var d=document.documentElement;
            f.style.height=(d.scrollHeight+40)+'px';
            if(f.parentElement){{
                f.parentElement.style.overflowX='auto';
                f.parentElement.style.maxWidth='100%';
            }}
        }}
    }})();
    </script>'''

    return html
