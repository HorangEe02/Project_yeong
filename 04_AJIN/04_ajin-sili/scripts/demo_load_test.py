"""AJIN 시연 직전 API 부하 테스트 (D-7 ~ D-1).

3개 핵심 시연 endpoint에 대해 결정적 부하 패턴으로 p50/p95/p99 latency + RPS 측정.

사용법:
    # 1. locust 설치
    pip install locust>=2.31

    # 2. 환경 변수 설정
    export AJIN_BACKEND_URL=https://<cloud-run-url>  # 또는 http://localhost:8000
    export AJIN_AUTH_TOKEN=<service_role_or_user_jwt>

    # 3. 실행 (10 RPS × 60초, 헤드리스)
    locust -f scripts/demo_load_test.py \
        --host "$AJIN_BACKEND_URL" \
        --users 10 --spawn-rate 2 --run-time 60s \
        --headless --csv=outputs/load_test --html=outputs/load_test.html

    # 4. UI 모드 (실시간 모니터)
    locust -f scripts/demo_load_test.py --host "$AJIN_BACKEND_URL"
    # → 브라우저 http://localhost:8089

판정 기준 (시연 안전):
    - p95 latency  < 2000ms (검색·초안 모두)
    - error rate   < 1.0%
    - throughput   ≥ 8 RPS sustained

본 스크립트는 시연 차단요인 발견용이며, 운영 capacity planning과는 다름.
"""
from __future__ import annotations

import os
import random
from locust import HttpUser, task, between, events


AUTH_TOKEN = os.environ.get("AJIN_AUTH_TOKEN", "")

# 시연 결정성 보장 입력 (demo_check.py C1·C2·C4와 일치)
SEARCH_QUERIES = [
    "프레스 트라이 8D Report",
    "압축기 누유 B3라인",
    "PPAP 작성 절차",
    "도금 공정 SVHC",
    "안전관리자 책임",
]

DRAFT_INPUTS = [
    "압축기 누유 발생, 3월 15일, B3라인",  # demo_seed 캐시 hit
    "프레스 안전거리 변경 ECN 작성",
    "쿼터패널 PPAP 16종 자료 정리",
]

CHATBOT_QUESTIONS = [
    "PPAP가 뭐예요?",       # safety_classifier False
    "이 기계 만져도 돼요?",   # safety_classifier True
    "신입사원 SOP 어디?",
    "8D Report 누가 작성?",
]


class AjinDemoUser(HttpUser):
    """시연 3 endpoint를 라운드로빈 호출."""

    wait_time = between(0.5, 2.0)
    host = os.environ.get("AJIN_BACKEND_URL", "http://localhost:8000")

    def on_start(self):
        if AUTH_TOKEN:
            self.client.headers.update({
                "Authorization": f"Bearer {AUTH_TOKEN}",
                "Content-Type": "application/json",
            })
        else:
            self.client.headers.update({"Content-Type": "application/json"})

    @task(3)
    def search_hybrid(self):
        """가중치 3 — 가장 빈번한 시연 1 검색."""
        query = random.choice(SEARCH_QUERIES)
        with self.client.post(
            "/api/search",
            json={"q": query, "limit": 5, "doc_type": None},
            name="POST /api/search",
            catch_response=True,
            timeout=10,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json() if resp.text else {}
                if not data.get("results") and not data.get("hits"):
                    resp.failure("empty results")
                else:
                    resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(2)
    def draft_generate(self):
        """가중치 2 — 시연 2 초안. demo_seed 캐시 hit 확인."""
        prompt = random.choice(DRAFT_INPUTS)
        with self.client.post(
            "/api/draft",
            json={"input": prompt, "doc_type": "8d_report"},
            name="POST /api/draft",
            catch_response=True,
            timeout=15,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(2)
    def chatbot(self):
        """가중치 2 — 시연 3 챗봇."""
        question = random.choice(CHATBOT_QUESTIONS)
        with self.client.post(
            "/api/onboarding/chat",
            json={"message": question, "user_id": "demo-user"},
            name="POST /api/onboarding/chat",
            catch_response=True,
            timeout=10,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(1)
    def alarms_list(self):
        """가중치 1 — 시연 4 법규 알람 조회."""
        with self.client.get(
            "/api/compliance/alarms?severity=CRITICAL&limit=10",
            name="GET /api/compliance/alarms",
            catch_response=True,
            timeout=8,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")


@events.test_stop.add_listener
def print_demo_gate(environment, **kwargs):
    """테스트 종료 시 시연 안전 게이트 평가."""
    stats = environment.stats.total

    p95 = stats.get_response_time_percentile(0.95)
    p99 = stats.get_response_time_percentile(0.99)
    fail_rate = (stats.num_failures / max(stats.num_requests, 1)) * 100

    print("\n" + "=" * 60)
    print(" AJIN 시연 안전 게이트 평가")
    print("=" * 60)
    print(f"  총 요청    : {stats.num_requests}")
    print(f"  실패 건수  : {stats.num_failures} ({fail_rate:.2f}%)")
    print(f"  p50 latency: {stats.median_response_time}ms")
    print(f"  p95 latency: {p95}ms")
    print(f"  p99 latency: {p99}ms")
    print(f"  RPS        : {stats.current_rps:.2f}")
    print()

    gates = [
        ("p95 < 2000ms", p95 < 2000),
        ("error rate < 1%", fail_rate < 1.0),
        ("RPS ≥ 5", stats.current_rps >= 5.0),
    ]
    for label, passed in gates:
        mark = "✓" if passed else "✗"
        print(f"  [{mark}] {label}")

    all_pass = all(p for _, p in gates)
    print()
    print("  결과: " + ("✅ 시연 안전" if all_pass else "❌ 시연 차단요인 발견"))
    print("=" * 60)
