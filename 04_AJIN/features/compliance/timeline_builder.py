"""
규제 데드라인 타임라인 시각화 빌더
- Plotly 간트차트/타임라인으로 전체 규제 데드라인 표시
- 긴급도별 색상 구분
- 리스크 레이더 차트
"""

import plotly.graph_objects as go
from datetime import date
from typing import List
from features.compliance.risk_scorer import RiskScore


GRADE_COLORS = {
    "CRITICAL": "#D32F2F",
    "HIGH": "#F57C00",
    "MEDIUM": "#FBC02D",
    "LOW": "#388E3C",
}


def build_deadline_timeline(scores: List[RiskScore]) -> go.Figure:
    """규제 데드라인 간트차트 생성"""
    items = [s for s in scores if s.deadline and s.days_remaining is not None]

    if not items:
        fig = go.Figure()
        fig.add_annotation(text="데드라인 데이터가 없습니다", showarrow=False,
                           font=dict(size=14, color="#999"))
        fig.update_layout(height=200)
        return fig

    items.sort(key=lambda x: x.days_remaining)
    today = date.today()

    fig = go.Figure()

    for item in items:
        days = max(1, item.days_remaining) if item.days_remaining > 0 else 1
        color = GRADE_COLORS.get(item.grade, "#9E9E9E")
        title_short = item.title[:35] + ("..." if len(item.title) > 35 else "")

        fig.add_trace(go.Bar(
            x=[days],
            y=[title_short],
            orientation="h",
            marker=dict(color=color, opacity=0.8),
            text=f"D-{item.days_remaining}일 | {item.grade} ({item.total_score:.0f}점)",
            textposition="inside",
            textfont=dict(color="white", size=11),
            hovertemplate=(
                f"<b>{item.title}</b><br>"
                f"데드라인: {item.deadline}<br>"
                f"잔여: {item.days_remaining}일<br>"
                f"리스크: {item.total_score:.0f}점 ({item.grade})<br>"
                f"영향 시설: {', '.join(item.affected_plants[:3]) if item.affected_plants else '전체'}<br>"
                "<extra></extra>"
            ),
            showlegend=False,
        ))

    # 레이아웃
    fig.update_layout(
        title=dict(text="규제 데드라인 타임라인", font=dict(size=14)),
        xaxis_title="잔여 일수",
        height=max(250, len(items) * 55 + 80),
        margin=dict(l=10, r=20, t=50, b=40),
        barmode="stack",
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="rgba(128,128,128,0.2)"),
    )

    # 범례 (등급별)
    for grade, color in GRADE_COLORS.items():
        fig.add_trace(go.Bar(
            x=[0], y=[""],
            marker=dict(color=color),
            name=grade, showlegend=True,
        ))

    # 테마 적용
    try:
        from ui.plotly_theme import apply_theme
        apply_theme(fig)
    except Exception:
        pass

    return fig


def build_risk_radar(score: RiskScore) -> go.Figure:
    """개별 시나리오의 리스크 레이더 차트"""
    categories = ["재무 영향", "발생 가능성", "시간 긴급도"]
    normalized = [
        score.financial_impact / 40 * 100,
        score.likelihood / 30 * 100,
        score.urgency / 30 * 100,
    ]

    color = GRADE_COLORS.get(score.grade, "#9E9E9E")
    r, g, b = _hex_to_rgb(color)

    fig = go.Figure(go.Scatterpolar(
        r=normalized + [normalized[0]],
        theta=categories + [categories[0]],
        fill="toself",
        fillcolor=f"rgba({r},{g},{b},0.25)",
        line=dict(color=color, width=2),
        name=score.grade,
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9)),
            bgcolor="rgba(0,0,0,0)",
        ),
        showlegend=False,
        title=dict(
            text=f"{score.title[:25]} ({score.total_score:.0f}점)",
            font=dict(size=11),
        ),
        height=280,
        margin=dict(l=40, r=40, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
    )

    # 테마 적용
    try:
        from ui.plotly_theme import apply_theme
        apply_theme(fig)
    except Exception:
        pass

    return fig


def _hex_to_rgb(hex_color: str) -> tuple:
    """HEX -> RGB 변환"""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
