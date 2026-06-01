"""인원 검색 결과 포맷터 — 카드 / 테이블 / 조직도 트리"""


def format_person_card(emp: dict) -> str:
    leader_badge = " // 팀장" if emp.get("is_team_leader") else ""
    return f"""**{emp['name']}** 님{leader_badge}

| 항목 | 내용 |
|---|---|
| 직급 | {emp['position']} |
| 소속 | {emp['division']} > {emp['department']} |
| 근무지 | {emp.get('plant', '')} |
| 이메일 | {emp.get('email', '')} |
| 연락처 | {emp.get('phone', '')} |
| 내선 | {emp.get('extension', '')} |
| 입사일 | {emp.get('hire_date', '')} |"""


def format_person_list(results: list[dict]) -> str:
    if not results:
        return "검색 결과가 없습니다."
    lines = [f"총 **{len(results)}명** 검색됨:\n"]
    lines.append("| 이름 | 직급 | 부서 | 연락처 | 이메일 |")
    lines.append("|---|---|---|---|---|")
    for emp in results[:20]:
        leader = " *" if emp.get("is_team_leader") else ""
        lines.append(
            f"| {emp['name']}{leader} | {emp['position']} | "
            f"{emp['department']} | {emp.get('phone', '')} | {emp.get('email', '')} |"
        )
    if len(results) > 20:
        lines.append(f"\n... 외 {len(results) - 20}명")
    return "\n".join(lines)


def format_department_summary(department: str, members: list[dict]) -> str:
    if not members:
        return f"{department}: 인원 정보가 없습니다."
    leader = next((m for m in members if m.get("is_team_leader")), None)
    leader_str = f"팀장: **{leader['name']} {leader['position']}**" if leader else "팀장 미지정"

    lines = [f"## {department} ({len(members)}명)", f"{leader_str}\n",
             "| 이름 | 직급 | 연락처 | 이메일 |", "|---|---|---|---|"]
    for m in members:
        badge = " *" if m.get("is_team_leader") else ""
        lines.append(f"| {m['name']}{badge} | {m['position']} | {m.get('phone', '')} | {m.get('email', '')} |")
    return "\n".join(lines)


def format_headcount_table(headcount_data: list[dict]) -> str:
    lines = ["## 부서별 인원 현황\n", "| 본부 | 부서 | 인원 수 |", "|---|---|---|"]
    current_division = ""
    for row in headcount_data:
        div_display = row["division"] if row["division"] != current_division else ""
        current_division = row["division"]
        lines.append(f"| {div_display} | {row['department']} | {row['headcount']}명 |")
    total = sum(r["headcount"] for r in headcount_data)
    lines.append(f"| **합계** | | **{total}명** |")
    return "\n".join(lines)


def format_org_tree_text(org_data: list[dict]) -> str:
    lines = ["## 아진산업 조직도\n", "```", "대표이사"]
    current_division = ""
    for row in org_data:
        if row["division"] != current_division:
            current_division = row["division"]
            lines.append(f"├── {current_division}")
        leader = f" ({row['team_leader_name']} {row['team_leader_position']})" if row.get("team_leader_name") else ""
        lines.append(f"│   ├── {row['department']} [{row['headcount']}명]{leader}")
    lines.append("```")
    return "\n".join(lines)


def format_search_result(search_result: dict) -> str:
    mode = search_result.get("mode")
    results = search_result.get("results", [])
    message = search_result.get("message", "")

    if mode == "person":
        if len(results) == 1:
            return format_person_card(results[0])
        if results:
            return format_person_list(results)
        return f"검색 결과 없음: {message}"
    if mode == "department":
        dept = search_result.get("query_parsed", {}).get("department", "")
        return format_department_summary(dept, results)
    if mode == "org_chart":
        return format_org_tree_text(results)
    if mode == "stats":
        if results and "headcount" in results[0]:
            return format_headcount_table(results)
        return format_person_list(results)
    return message
