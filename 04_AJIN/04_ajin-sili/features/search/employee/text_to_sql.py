"""
Text-to-SQL 엔진 — 자연어 질의를 SQL로 변환하여 사원 DB 조회
Qwen 3.5를 활용한 SQL 생성 + 안전한 실행
"""
import sqlite3
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("data/employees.db")

# ── employees 테이블 스키마 (LLM 프롬프트용) ──
SCHEMA_PROMPT = """
## SQLite 테이블 스키마

### employees 테이블
| 컬럼명 | 타입 | 설명 | 예시값 |
|--------|------|------|--------|
| id | INTEGER | PK, 자동증가 | 1, 2, 3 |
| name | TEXT | 이름 | 홍길동, 김영희 |
| department | TEXT | 부서명 | 품질보증팀, 생산기술팀, ESG경영팀 |
| position | TEXT | 직급 | 사원, 주임, 대리, 과장, 차장, 부장, 이사, 상무 |
| phone | TEXT | 전화번호 | 010-1234-5678 |
| email | TEXT | 이메일 | hong@ajin.co.kr |
| extension | TEXT | 내선번호 | 1234 |
| plant | TEXT | 근무 사업장 | 경산 본사, 경주공장, 경산 제2공장, AJIN USA, JOON INC |
| hire_date | TEXT | 입사일 (ISO) | 2020-03-15 |
| resign_date | TEXT | 퇴사일 (NULL=재직중) | 2025-12-31 또는 NULL |
| overseas_assignment | TEXT | 해외파견지 (NULL=없음) | AJIN USA, 소주A&T |
| language_skills | TEXT | 외국어 능력 | English(상), 日本語(중) |

### 직급 서열 (높은 순)
상무 > 이사 > 부장 > 차장 > 과장 > 대리 > 주임 > 사원

### 주요 부서 목록 (27개)
내부감사팀, 재무팀, 회계팀, 원가기획팀, 총무인사팀, ESG경영팀, IT전략팀,
기술영업팀, 해외지원팀, 상생협력팀, 구매팀, 자재관리팀,
생산관리팀, 금형생산팀, 용기운영팀, 안전보건팀,
생산기술팀, 자동화기술팀, FA사업팀, 플랜트사업팀,
품질보증팀, 품질경영팀,
제품설계팀, 공법계획팀, 비전연구팀, 바디선행개발팀, 전장선행개발팀

### 사업장 목록
국내: 경산 본사, 경산 제2공장, 경주공장, 경주 입실공장, 경산 하양공장
해외: AJIN USA, JOON INC, 소주A&T, WOOSHIN USA, AJECC USA, 아진베트남, 아진실업 유한공사
""".strip()

# ── SQL 생성 프롬프트 ──
TEXT_TO_SQL_SYSTEM = f"""당신은 SQLite SQL 쿼리 생성 전문가입니다.
사용자의 자연어 질문을 아래 스키마에 맞는 SELECT SQL로 변환하세요.

{SCHEMA_PROMPT}

## 규칙
1. SELECT 문만 생성하세요. INSERT/UPDATE/DELETE/DROP 등은 절대 금지입니다.
2. 결과에는 항상 name, department, position을 포함하세요.
3. 직급 비교 시 CASE WHEN으로 레벨 변환하세요:
   CASE position
     WHEN '상무' THEN 8 WHEN '이사' THEN 7 WHEN '부장' THEN 6
     WHEN '차장' THEN 5 WHEN '과장' THEN 4 WHEN '대리' THEN 3
     WHEN '주임' THEN 2 WHEN '사원' THEN 1 ELSE 0
   END
4. 부서 약어를 정식 명칭으로 변환하세요:
   - 품보팀 → 품질보증팀, 생기팀 → 생산기술팀, 안보팀 → 안전보건팀
   - QA → 품질보증팀, HR → 총무인사팀, IT → IT전략팀
5. 재직 중인 사원만 조회: resign_date IS NULL
6. LIMIT 50을 항상 포함하세요.
7. SQL만 출력하세요. 설명이나 마크다운 코드블록은 제외하세요.
"""

# ── 허용된 SQL 패턴 (보안) ──
ALLOWED_PATTERNS = re.compile(
    r"^\s*SELECT\s+.+\s+FROM\s+employees\b",
    re.IGNORECASE | re.DOTALL,
)

BLOCKED_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX",
    "GRANT", "REVOKE", "--", "/*", "*/", ";;",
}


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    생성된 SQL의 안전성을 검증합니다.
    Returns: (is_valid, error_message)
    """
    sql_upper = sql.upper().strip()

    if not ALLOWED_PATTERNS.match(sql):
        return False, "SELECT FROM employees 패턴이 아닙니다"

    for keyword in BLOCKED_KEYWORDS:
        if keyword.upper() in sql_upper:
            return False, f"차단된 키워드: {keyword}"

    statements = [s.strip() for s in sql.split(";") if s.strip()]
    if len(statements) > 1:
        return False, "다중 SQL 문은 허용되지 않습니다"

    return True, ""


def generate_sql(
    natural_query: str,
    llm_client,
    user_context=None,
) -> Optional[str]:
    """
    자연어 질의를 SQL로 변환합니다.

    Args:
        natural_query: 자연어 질문 (예: "경산 본사에서 근무하는 과장급 이상")
        llm_client: LLM 클라이언트 (core.llm_client)
        user_context: UserContext 객체 (선택)

    Returns:
        검증된 SQL 문자열 또는 None
    """
    context_hint = ""
    if user_context:
        context_hint = f"\n\n[참고] 질문자: {user_context.department} {user_context.position} {user_context.name}"

    messages = [
        {"role": "system", "content": TEXT_TO_SQL_SYSTEM},
        {"role": "user", "content": f"질문: {natural_query}{context_hint}\n\nSQL:"},
    ]

    try:
        response = llm_client.generate(
            messages=messages,
            max_tokens=512,
            temperature=0.1,
            stream=False,
        )

        sql = response.strip()

        # 마크다운 코드블록 제거
        sql = re.sub(r"^```(?:sql)?\s*", "", sql)
        sql = re.sub(r"\s*```$", "", sql)
        sql = sql.strip().rstrip(";")

        is_valid, error = validate_sql(sql)
        if not is_valid:
            logger.warning(f"SQL 검증 실패: {error}\nSQL: {sql}")
            return None

        return sql

    except Exception as e:
        logger.error(f"SQL 생성 실패: {e}")
        return None


def execute_sql(
    sql: str,
    db_path: Path = DB_PATH,
    limit: int = 50,
) -> list[dict]:
    """검증된 SQL을 실행하고 결과를 반환합니다."""
    is_valid, error = validate_sql(sql)
    if not is_valid:
        logger.error(f"SQL 실행 거부: {error}")
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(sql).fetchall()
        return [dict(row) for row in rows[:limit]]
    except sqlite3.Error as e:
        logger.error(f"SQL 실행 오류: {e}\nSQL: {sql}")
        return []
    finally:
        conn.close()


def natural_language_search(
    query: str,
    llm_client,
    user_context=None,
    db_path: Path = DB_PATH,
) -> dict:
    """
    자연어 → SQL → 결과 파이프라인 전체 실행.

    Returns:
        {
            "query": 원본 질의,
            "sql": 생성된 SQL,
            "results": 결과 리스트,
            "count": 결과 수,
            "error": 에러 메시지 (있을 경우)
        }
    """
    result = {"query": query, "sql": None, "results": [], "count": 0, "error": None}

    sql = generate_sql(query, llm_client, user_context)
    if not sql:
        result["error"] = "SQL 생성에 실패했습니다."
        return result

    result["sql"] = sql
    rows = execute_sql(sql, db_path)
    result["results"] = rows
    result["count"] = len(rows)

    return result
