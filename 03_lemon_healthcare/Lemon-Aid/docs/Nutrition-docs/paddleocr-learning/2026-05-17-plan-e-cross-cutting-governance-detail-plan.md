# Plan E. Cross-Cutting 평가, 개인정보, 배포 거버넌스 상세 설계 및 구현 기록

## Summary

Plan E의 목적은 Plan A-D가 만든 PaddleOCR local OCR, ROI/촬영 품질, PaddleOCR fine-tuning, parser/domain correction 산출물을 서로 다른 기준으로 승격하지 않도록 공통 governance gate/report layer를 추가하는 것이다. 이번 구현은 새 ML 기능을 추가하지 않고, redacted evaluation report, consent/retention snapshot, artifact provenance, promotion decision, release governance CLI를 표준화했다.

공식 기준:

- NIST AI RMF: https://www.nist.gov/itl/ai-risk-management-framework
- NIST Privacy Framework: https://www.nist.gov/privacy-framework
- OWASP API Security Top 10 2023: https://owasp.org/API-Security/editions/2023/en/0x00-header/
- 개인정보보호위원회 보건의료데이터 활용 가이드라인(2024.12): https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=G010030000&nttId=9901
- Pydantic validators: https://docs.pydantic.dev/latest/concepts/validators/

명시적 한계:

- I cannot find the official documentation for this specific query: supplement-label OCR provider promotion thresholds.
- 따라서 OCR/parser/ROI/domain correction의 승격 기준은 공식 수치가 아니라 frozen fixture, primary metric no-regression, safety metric 0, raw data leak 0, artifact checksum, rollback 가능성, 팀 sign-off 기반 내부 gate로 둔다.

## Implemented Scope

추가된 파일:

- `backend/Nutrition-backend/src/models/schemas/governance.py`
- `backend/Nutrition-backend/src/services/governance.py`
- `backend/scripts/evaluate_release_governance.py`
- `backend/Nutrition-backend/tests/unit/models/test_governance_schema.py`
- `backend/Nutrition-backend/tests/unit/services/test_governance.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_evaluate_release_governance.py`
- `Brand-New-update/2026-05-17-plan-e-cross-cutting-governance-detail-plan.md`

수정된 파일:

- `backend/Nutrition-backend/src/config.py`
- `backend/Nutrition-backend/src/services/readiness.py`
- `backend/.env.example`
- `backend/Nutrition-backend/tests/unit/test_config.py`
- `backend/Nutrition-backend/tests/unit/test_security_middleware.py`

## Governance Schema

`governance.py`는 다음 DTO를 추가한다.

- `ConsentRetentionPolicySnapshot`: image learning, external OCR, prescription OCR, lab result OCR consent bucket과 retention 설정을 redacted snapshot으로 기록한다.
- `ArtifactProvenance`: artifact id/type/version, artifact checksum, dataset checksum, config checksum, optional model checksum, code commit, source documentation URL, approval status, rollback target을 기록한다.
- `RedactedEvaluationReport`: baseline/candidate aggregate metrics와 safety metrics만 저장한다. raw image, raw OCR text, raw provider payload, filename, user id, direct identifier key는 재귀적으로 차단한다.
- `PromotionDecision`: primary metric delta, no-regression, safety metric, artifact provenance 결과를 기록한다.
- `PipelineGovernanceStatus`: 각 pipeline의 pass/warning/fail 상태와 release blocking 여부를 기록한다.
- `GovernanceGateReport`: release target 전체의 cross-pipeline governance 결과를 묶는다.

적용 대상 pipeline:

- `paddleocr_local`
- `roi_quality`
- `paddleocr_finetuning`
- `parser_domain_correction`
- `external_ocr_provider`
- `release_readiness`

## Promotion Gate

공통 승격 조건은 다음과 같다.

1. frozen fixture version과 split version이 명시되어야 한다.
2. candidate artifact에는 artifact checksum, dataset checksum, config checksum, code commit, source documentation URL이 있어야 한다.
3. candidate artifact는 `approval_status=approved`, `approved_by`, `rollback_to`를 가져야 한다.
4. primary metric 중 하나 이상 개선되어야 한다.
5. 어떤 primary metric도 baseline보다 악화되면 안 된다.
6. required safety metric은 모두 0이어야 한다.
7. raw text/image/provider payload/direct identifier key가 report 어디에도 없어야 한다.

기본 primary metric:

- `downstream_field_exact_rate`
- `numeric_exact_rate`
- `unit_exact_rate`
- `parser_success_rate`

기본 safety metric:

- `fabricated_field_count`
- `false_correction_count`
- `raw_text_leak_count`
- `raw_data_leak_count`

## Consent and Retention Gate

`build_consent_retention_policy_snapshot()`은 기존 `evaluate_image_learning_gate()`를 대체하지 않고 래핑한다. image learning export가 필요한 경우 다음 bucket을 요구한다.

- `ocr_image_processing`
- `data_retention`
- `image_learning_dataset`

external OCR, prescription OCR, lab result OCR은 별도 bucket으로 유지한다.

- `external_ocr_processing`
- `prescription_ocr_intake`
- `lab_result_ocr_intake`

동의 철회가 dataset에 영향을 주는 경우 `consent_withdrawal_exclusion_list_required=true`와 `withdrawal_exclusion_list_present=true`를 함께 기록해야 promotion/release gate를 통과할 수 있다.

## Readiness and Release Gate Separation

`/ready`는 기존 원칙대로 configuration-only를 유지한다. 이번 구현은 `governance` component만 추가했고, artifact 파일 읽기, provider smoke, benchmark 실행은 하지 않는다.

heavy check는 별도 CLI에서 수행한다.

```bash
python scripts/evaluate_release_governance.py --manifest path/to/redacted-governance-manifest.json --output-dir outputs/governance
```

`GOVERNANCE_GATE_MODE` 기본값은 `report_only`이다. `block_release`에서는 실패한 policy/report가 public staging 또는 production release를 막는 decision으로 표시된다.

## CLI Manifest Shape

최소 manifest 예시는 다음과 같다. 값은 예시이며 실제 지표가 아니다.

```json
{
  "target_environment": "staging",
  "release_target": "public_staging",
  "gate_mode": "block_release",
  "policy_snapshot": {
    "required_consent_scopes": [],
    "granted_consent_scopes": [],
    "missing_consent_scopes": []
  },
  "evaluation_reports": [
    {
      "report_id": "report-001",
      "pipeline": "paddleocr_finetuning",
      "frozen_fixture_version": "supplement-fixtures-v1",
      "split_version": "split-v1",
      "aggregate_case_count": 12,
      "baseline_metrics": {
        "downstream_field_exact_rate": 0.8,
        "numeric_exact_rate": 0.7,
        "unit_exact_rate": 0.75,
        "parser_success_rate": 0.85
      },
      "candidate_metrics": {
        "downstream_field_exact_rate": 0.82,
        "numeric_exact_rate": 0.7,
        "unit_exact_rate": 0.75,
        "parser_success_rate": 0.85
      },
      "safety_metrics": {
        "fabricated_field_count": 0,
        "false_correction_count": 0,
        "raw_text_leak_count": 0,
        "raw_data_leak_count": 0
      },
      "artifact_provenance": [
        {
          "artifact_id": "artifact-001",
          "artifact_type": "model",
          "artifact_version": "v1",
          "artifact_checksum": "artifact-checksum",
          "dataset_checksum": "dataset-checksum",
          "config_checksum": "config-checksum",
          "model_checksum": "model-checksum",
          "code_commit": "abcdef123456",
          "source_doc_urls": ["https://www.nist.gov/itl/ai-risk-management-framework"],
          "metrics_summary": {"numeric_exact_rate": 0.7},
          "approval_status": "approved",
          "approved_by": "ml-review-board",
          "rollback_to": "artifact-000"
        }
      ],
      "source_doc_urls": ["https://www.nist.gov/privacy-framework"]
    }
  ]
}
```

## Phase Mapping

### E0: Governance Schemas

완료:

- `GovernanceGateReport`, `PipelineGovernanceStatus`, `ArtifactProvenance`, `RedactedEvaluationReport`, `PromotionDecision`, `ConsentRetentionPolicySnapshot` 추가.
- raw data key 재귀 차단 validator 추가.

### E1: Consent and Retention Policy Snapshot

완료:

- 기존 image learning gate wrapper 추가.
- image learning, external OCR, regulated OCR consent bucket 분리.
- 동의 철회 exclusion list 요구 상태 표현.

### E2: Redacted Evaluation Report

완료:

- OCR/provider, ROI, fine-tuning, domain correction metric을 하나의 aggregate report로 표현할 수 있는 schema 추가.
- primary/safety metric contract 추가.

### E3: Artifact Provenance and Promotion Gate

완료:

- checksum/config/code/doc/approval/rollback gate 구현.
- primary metric improvement, no-regression, safety metric 0 조건 구현.

### E4: Release Readiness Gate

완료:

- `/ready`에 `governance` component 추가.
- `scripts/evaluate_release_governance.py` 추가.
- readiness는 secret, raw payload, raw text를 노출하지 않는다.

### E5: Documentation

완료:

- 본 문서에 공식 URL, 한계, 구현 기준, promotion checklist, rollback policy를 기록했다.

## Test Coverage

추가/수정된 테스트는 다음을 검증한다.

- governance schema가 raw OCR/image/provider/user identifier key를 차단한다.
- consent/retention snapshot이 누락되면 gate가 실패한다.
- artifact checksum/config checksum/code commit 누락 시 promotion 실패.
- safety metric이 0보다 크면 promotion 실패.
- primary metric no-regression이 깨지면 promotion 실패.
- `report_only`는 실패 reason을 남기되 release를 block하지 않는다.
- `block_release`는 실패를 release block으로 표시한다.
- readiness response는 secret, raw payload, raw text를 노출하지 않는다.
- release governance CLI는 redacted manifest를 평가하고 raw OCR text를 거부한다.

## Rollback Policy

운영 후보 artifact는 `rollback_to`가 있어야 한다. `rollback_to`가 없으면 `block_release` 모드에서 promotion이 실패한다. rollback은 runtime request path에서 동적으로 shadow 비교하지 않고, CI/release job에서 승인된 이전 artifact version으로 pinning하는 방식으로 처리한다.

## Next Implementation Hooks

- Plan B ROI benchmark script가 생성한 aggregate report를 `RedactedEvaluationReport`로 변환하는 adapter를 추가할 수 있다.
- Plan C fine-tuning report와 Plan D domain correction report도 같은 manifest shape로 출력하도록 점진적으로 연결할 수 있다.
- public staging/production release job에서 `GOVERNANCE_GATE_MODE=block_release`와 `scripts/evaluate_release_governance.py`를 실행하도록 CI step을 추가한다.
