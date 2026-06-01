# 03. 로깅 레다크션 버그 수정 (uvicorn AccessFormatter)

> 브랜치 성격: fix(logging)
> 대응 커밋: `6e1b42c` (일부)
> 핵심 파일: `backend/Nutrition-backend/src/utils/logger.py`

---

## 1. 증상

백엔드 로그에 매 요청마다 반복 출력:

```
--- Logging error ---
Traceback (most recent call last):
TypeError: cannot unpack non-iterable NoneType object
  File ".../starlette/middleware/errors.py", line 161, in _send
Message: '... "POST /api/v1/supplements/analyses/.../explain HTTP/1.1" 200'
```

요청 자체는 200으로 정상 처리되지만, **액세스 로그 방출이 깨졌다**.

---

## 2. 근본 원인

이전 보안 라운드(H2)에서 추가한 `RedactingFilter.filter()`가 모든 로그 레코드에 대해 `record.args = None`으로 비웠다.

- 이 필터는 `uvicorn.access` 로거에도 부착됨
- uvicorn `AccessFormatter`는 `(client_addr, method, path, http_version, status) = record.args`로 args를 **직접 언패킹**
- args가 None → "cannot unpack non-iterable NoneType" 매 액세스 라인마다 발생

---

## 3. 수정

args를 None으로 비우지 않고 **구조(튜플/딕트)를 보존한 채 문자열 원소만 redact**:

```python
if isinstance(record.msg, str):
    record.msg = _redact_text(record.msg)
if isinstance(record.args, tuple):
    record.args = tuple(
        _redact_text(a) if isinstance(a, str) else a for a in record.args
    )
elif isinstance(record.args, dict):
    record.args = {
        k: (_redact_text(v) if isinstance(v, str) else v)
        for k, v in record.args.items()
    }
```

- 표준 `msg % args` 경로와 args 소비형 포매터(uvicorn) 둘 다 정상 동작
- 시크릿/PII 마스킹은 그대로 유지

---

## 4. 검증 ✅

- `py_compile` 통과, `record.args = None` 제거(0건) 확인
- 배포 컨테이너에서 `logger_argsNone=0` 런타임 확인
- 액세스 로그 "cannot unpack" 에러 소멸
