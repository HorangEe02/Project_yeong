"""협업 시나리오 저장소 (DB 기반).

기존 features/onboarding/collaboration_guide.py 의 하드코딩 5종을 SQLite 로 이관하여
HR_ADMIN 등 관리자가 시나리오 본문을 편집/추가할 수 있게 한다.

- DB: data/scenarios.db (collaboration_scenarios + scenario_history + scenario_favorites + scenario_usage)
- 시드: 첫 실행 시 collaboration_guide.py 의 5종을 is_system_default=1 로 INSERT
- 매칭: repository.match() — DB 우선, 키워드 룰베이스 (LLM 미호출, <10ms)
- Phase 2: scope_division (본부 한정) + lang (ko/en) 컬럼 활용
- Phase 3: scenario_favorites / scenario_usage 통계
"""
