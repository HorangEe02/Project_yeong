"""
규제 영향 네트워크 시각화
- 규제 → 시설 → 부서/제품 연쇄 영향 그래프
- Plotly scatter 기반 네트워크 다이어그램
- 키워드 기반 관련 부서 자동 추론
"""

import math
import plotly.graph_objects as go
from typing import List, Dict


# 규제 키워드 → 관련 부서 자동 매핑
REGULATION_DEPT_MAP = {
    "관세": ["구매팀", "해외지원팀", "영업팀"],
    "tariff": ["구매팀", "해외지원팀"],
    "REACH": ["품질보증팀", "구매팀", "ESG경영팀"],
    "화학": ["품질보증팀", "ESG경영팀"],
    "안전": ["안전보건팀", "생산관리팀"],
    "OSHA": ["안전보건팀"],
    "산안법": ["안전보건팀", "생산관리팀"],
    "소음": ["안전보건팀", "생산관리팀"],
    "환경": ["ESG경영팀", "안전보건팀"],
    "배터리": ["부품개발팀", "품질보증팀", "생산기술팀"],
    "EV": ["부품개발팀", "전장선행개발팀"],
    "IATF": ["품질보증팀", "품질경영팀"],
    "ISO": ["품질경영팀"],
    "IRA": ["해외지원팀", "영업팀"],
    "USMCA": ["구매팀", "해외지원팀"],
    "원산지": ["구매팀", "해외지원팀"],
    "CBAM": ["ESG경영팀", "구매팀"],
    "탄소": ["ESG경영팀"],
    "금형": ["금형생산팀", "생산기술팀"],
    "프레스": ["생산관리팀", "금형생산팀"],
    "용접": ["자동화기술팀", "품질보증팀"],
}

SEVERITY_COLORS = {
    "critical": "#D32F2F",
    "high": "#F57C00",
    "medium": "#FBC02D",
    "low": "#388E3C",
}


def infer_departments(title: str, description: str = "") -> List[str]:
    """제목/설명에서 관련 부서 자동 추론"""
    text = f"{title} {description}".lower()
    depts = set()
    for keyword, dept_list in REGULATION_DEPT_MAP.items():
        if keyword.lower() in text:
            depts.update(dept_list)
    return sorted(depts) if depts else ["품질보증팀"]


def build_impact_network(
    scenario: Dict,
) -> go.Figure:
    """규제 영향 네트워크 그래프"""

    title = scenario.get("title", "규제")
    title_short = title[:25] + ("..." if len(title) > 25 else "")
    severity = scenario.get("severity", scenario.get("grade", "medium")).lower()
    affected_plants = scenario.get("affected_plants", scenario.get("affected_facility_ids", []))
    affected_depts = scenario.get("affected_departments", [])
    affected_products = scenario.get("affected_products", [])

    # 부서 자동 추론
    if not affected_depts:
        desc = scenario.get("description", scenario.get("summary", ""))
        affected_depts = infer_departments(title, desc)

    nodes_x, nodes_y, nodes_text, nodes_color, nodes_size = [], [], [], [], []
    edges_x, edges_y = [], []

    # 중앙: 규제
    center_color = SEVERITY_COLORS.get(severity, "#9E9E9E")
    nodes_x.append(0)
    nodes_y.append(0)
    nodes_text.append(title_short)
    nodes_color.append(center_color)
    nodes_size.append(35)

    # 1차 링: 시설
    plant_count = max(len(affected_plants), 1)
    plant_indices = []
    for i, plant in enumerate(affected_plants):
        angle = 2 * math.pi * i / plant_count
        px, py = 2.5 * math.cos(angle), 2.5 * math.sin(angle)
        idx = len(nodes_x)
        plant_indices.append(idx)
        nodes_x.append(px)
        nodes_y.append(py)
        plant_name = str(plant)[:15]
        nodes_text.append(f"[시설] {plant_name}")
        nodes_color.append("#1976D2")
        nodes_size.append(22)
        edges_x.extend([0, px, None])
        edges_y.extend([0, py, None])

    # 2차 링: 부서
    for i, dept in enumerate(affected_depts):
        angle = 2 * math.pi * i / max(len(affected_depts), 1) + 0.2
        ox, oy = 4.5 * math.cos(angle), 4.5 * math.sin(angle)
        nodes_x.append(ox)
        nodes_y.append(oy)
        nodes_text.append(f"[부서] {dept}")
        nodes_color.append("#7B1FA2")
        nodes_size.append(16)
        # 가장 가까운 시설 연결 (있으면), 없으면 중앙 연결
        if plant_indices:
            nearest = plant_indices[i % len(plant_indices)]
            edges_x.extend([nodes_x[nearest], ox, None])
            edges_y.extend([nodes_y[nearest], oy, None])
        else:
            edges_x.extend([0, ox, None])
            edges_y.extend([0, oy, None])

    # 2차 링: 제품
    for i, prod in enumerate(affected_products):
        angle = 2 * math.pi * i / max(len(affected_products), 1) + math.pi + 0.5
        ox, oy = 4.5 * math.cos(angle), 4.5 * math.sin(angle)
        nodes_x.append(ox)
        nodes_y.append(oy)
        prod_name = str(prod)[:15]
        nodes_text.append(f"[제품] {prod_name}")
        nodes_color.append("#00796B")
        nodes_size.append(16)
        if plant_indices:
            nearest = plant_indices[i % len(plant_indices)]
            edges_x.extend([nodes_x[nearest], ox, None])
            edges_y.extend([nodes_y[nearest], oy, None])
        else:
            edges_x.extend([0, ox, None])
            edges_y.extend([0, oy, None])

    fig = go.Figure()

    # 엣지
    fig.add_trace(go.Scatter(
        x=edges_x, y=edges_y, mode="lines",
        line=dict(width=1.5, color="rgba(189,189,189,0.5)"),
        hoverinfo="none", showlegend=False,
    ))

    # 노드
    fig.add_trace(go.Scatter(
        x=nodes_x, y=nodes_y, mode="markers+text",
        marker=dict(size=nodes_size, color=nodes_color, line=dict(width=1.5, color="white")),
        text=nodes_text, textposition="bottom center",
        textfont=dict(size=9),
        hoverinfo="text", showlegend=False,
    ))

    fig.update_layout(
        title=dict(text=f"규제 영향 네트워크: {title_short}", font=dict(size=12)),
        showlegend=False, height=380,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-6, 6]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-6, 6]),
        margin=dict(l=0, r=0, t=35, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )

    try:
        from ui.plotly_theme import apply_theme
        apply_theme(fig)
    except Exception:
        pass

    return fig
