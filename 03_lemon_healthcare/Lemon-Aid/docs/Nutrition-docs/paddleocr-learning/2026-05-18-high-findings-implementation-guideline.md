# HIGH 발견 사항 상세 설계 + 구현 가이드라인

> 작성일: 2026-05-18
> 대상 결함: H1 (EXIF/GPS 미제거) · H2 (PIL 디컴프레션 폭탄) · H3 (모바일 cert pinning + Android NSC + iOS ATS)
> 역참조: `Brand-New-update/2026-05-17-current-implementation-audit.md` §3 HIGH
> 산출물 정의: **이 문서를 받은 개발자가 외부 추가 조사 없이 PR 1~3개로 구현을 완료할 수 있어야 한다.**

---

## 0. 읽는 순서와 PR 분할 권장

| PR | 범위 | 예상 LOC | 위험도 | 머지 순서 |
|----|------|---------|-------|----------|
| PR-A | H1+H2 백엔드 — `image_safety.py` 유틸 + 호출처 2곳 + 테스트 픽스처 | ~250 | 낮음 (단위 테스트로 회귀 가능) | 1순위 |
| PR-B | H3 Android — NSC XML + Manifest 속성 + flavor 자원 분리 + instrument test | ~150 | 중간 (잘못된 NSC는 prod 트래픽 차단 가능 — staging 14일 필수) | 2순위, PR-A 머지 후 |
| PR-C | H3 iOS — Info.plist ATS + PinnedURLSessionDelegate.swift + MethodChannel + XCTest | ~250 | 중간 (delegate 미스 시 모든 요청 거부) | 3순위, PR-B 안정 확인 후 |

PR 의존성: A↔B↔C는 독립. 단 H3 핀 값은 운영팀이 SPKI 추출 후 별도 비밀 저장소(GitHub Secrets / 1Password)에 보관, PR-B/PR-C는 placeholder로 머지하고 release 빌드 직전에 핀 주입.

---

## 1. H1 — EXIF/GPS 메타데이터 server-side strip

### 1.1 결함 재진술
업로드된 영양제 라벨 이미지의 원본 바이트가 EXIF(GPS·단말 시리얼·촬영 시각 포함)를 보유한 채 **학습용 객체 스토리지에 verbatim 저장**된다. 저장소 → 어노테이션·재학습 파이프라인 → 운영팀 콘솔 경로 어디서든 사용자의 자택 좌표가 노출 가능. 한국 위치정보보호법상 사전 별도 동의 없이 위치정보를 수집·보유한 셈이 되어 **앱 스토어 심사 차단 + 법적 리스크**.

### 1.2 현 상태 코드 스냅샷
- 엔트리: `backend/Nutrition-backend/src/services/supplement_intake.py:127` `read_and_validate_supplement_image()` — 데이터 읽기·MIME 검증·픽셀 검증까지 수행하지만 EXIF/메타데이터 제거 없음.
- 검증: `backend/Nutrition-backend/src/services/supplement_intake.py:658-695` `_validate_decodable_image()` — `image.verify()`만 호출 후 원본 바이트 그대로 반환.
- 실제 누출점: `backend/Nutrition-backend/src/learning/object_storage.py:165` `LocalLearningImageObjectStore.put_image()` + S3 변형(`:289`) — `payload.image_bytes`를 verbatim write/upload.
- 자동 strip 경로(이미 안전): `backend/Nutrition-backend/src/ocr/preprocessing.py:35` `normalize_image_for_ocr()`이 PNG 재인코딩하므로 외부 OCR API(Google Vision/CLOVA)로의 GPS 송신은 발생 안 함.

### 1.3 브레인스토밍: 접근안 비교

| 옵션 | 방식 | 구현 복잡도 | 운영 부담 | 보안 강도 | 잔존 리스크 | 결정 |
|------|------|------------|----------|----------|------------|------|
| **A (추천)** | 엔트리(`read_and_validate_supplement_image`) 직후 1회 strip → 다운스트림은 정화 바이트만 봄 | 낮음 (호출 1곳) | 없음 (CPU ~5ms/이미지) | 높음 (저장·학습·향후 신규 consumer 모두 보호) | 정화 실패 시 업로드 거부 정책 결정 필요 | ✅ 채택 |
| B | 저장소 직전(`LocalLearningImageObjectStore.put_image`, `S3LearningImageObjectStore.put_image`) strip | 중간 (두 곳 + 인터페이스 변경) | 낮음 | 중간 (학습 외 신규 consumer 추가 시 재누락 가능) | 추가된 consumer가 strip 누락하면 누출 부활 | ❌ |
| C | `piexif` 라이브러리 의존 — EXIF만 정밀 제거 | 낮음 | 의존성 +1 | 낮음 (XMP/IPTC/ICC 미처리) | XMP에 GPS 미러링되는 경우 누출 | ❌ |

**결정 사유**: 옵션 A는 (1) 단일 진입점에서 강제하여 "잊고 추가하는" 회귀를 원천 차단, (2) Pillow 표준 API만 사용해 의존성 신규 추가 없음, (3) PNG 재인코딩하는 OCR 경로와 일관된 패턴.

### 1.4 추천 설계 상세

**데이터 흐름**
```
UploadFile
    │
    ▼
read_and_validate_supplement_image()
    ├─ _read_limited_upload (size cap)
    ├─ detect_image_mime          ─┐
    ├─ ALLOWED_IMAGE_MIME_TYPES    │ (변경 없음)
    ├─ _validate_decodable_image  ─┘
    ├─ ★ strip_image_metadata(data, detected_mime)   ← 신규 삽입
    └─ ★ safe_load_with_bomb_guard(data, max_pixels) ← H2와 통합
        ▼
ValidatedSupplementImage(image_bytes=정화된 바이트, …)
        ▼
모든 다운스트림 (OCR, YOLO, 품질, 학습 스토어)
```

**모듈 경계**
- 신규 파일 `backend/Nutrition-backend/src/utils/image_safety.py` — 외부 의존성: `PIL.Image`, `PIL.ImageOps`. 다른 서비스 모듈에 의존하지 않음.
- `services/supplement_intake.py`만 위 유틸을 import → 순환 의존 없음.

**인터페이스 결정**
- 함수 시그니처: `strip_image_metadata(data: bytes, mime: str) -> bytes`
- 실패 시 `ImageSafetyError`(신규 예외) raise → 호출자가 `SupplementImageValidationError(code="invalid_image", status=422)`로 변환.
- 지원 포맷: JPEG·PNG·WebP (기존 `ALLOWED_IMAGE_MIME_TYPES`와 동일 집합).

### 1.5 구현 패치

**신규** `backend/Nutrition-backend/src/utils/image_safety.py`
```python
"""Image safety utilities: metadata strip + decompression-bomb guard."""

from __future__ import annotations

import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


class ImageSafetyError(Exception):
    """Raised when image bytes cannot be safely normalized."""


_FORMAT_BY_MIME: dict[str, str] = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


def configure_pillow_limits(max_pixels: int) -> None:
    """Apply process-wide Pillow safety limits.

    Call once during application startup. Affects every PIL.Image consumer in
    the process, including downstream YOLO and quality decoders.
    """
    if max_pixels <= 0:
        raise ValueError("max_pixels must be positive")
    Image.MAX_IMAGE_PIXELS = max_pixels


def strip_image_metadata(data: bytes, mime: str) -> bytes:
    """Return image bytes with EXIF, XMP, and IPTC metadata removed.

    Orientation is applied to pixel data before stripping so that the
    visible rotation is preserved.

    Raises:
        ImageSafetyError: If the image cannot be decoded or re-encoded.
    """
    fmt = _FORMAT_BY_MIME.get(mime)
    if fmt is None:
        raise ImageSafetyError(f"unsupported_mime: {mime}")

    try:
        with Image.open(BytesIO(data)) as source:
            oriented = ImageOps.exif_transpose(source)
            buf = BytesIO()
            save_kwargs: dict[str, object] = {
                "format": fmt,
                "exif": b"",
                "xmp": b"",
            }
            if fmt == "JPEG":
                save_kwargs["icc_profile"] = b""
                save_kwargs["optimize"] = True
            oriented.save(buf, **save_kwargs)
            return buf.getvalue()
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise ImageSafetyError("strip_failed") from exc


def safe_load_with_bomb_guard(data: bytes) -> Image.Image:
    """Open image bytes while escalating DecompressionBombWarning to error.

    Returns a fully-loaded PIL Image. Caller owns the returned Image and
    must close it (use ``with`` or ``image.close()``).

    Raises:
        ImageSafetyError: On decompression bomb, decode failure, or
            DecompressionBombWarning escalation.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
            image.load()
            return image
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        UnidentifiedImageError,
    ) as exc:
        raise ImageSafetyError("bomb_or_decode_failure") from exc
```

**수정** `backend/Nutrition-backend/src/services/supplement_intake.py:127-159` — strip 호출 삽입
```python
# (변경 전)
data = await _read_limited_upload(image, settings.supplement_image_max_bytes)
content_type = image.content_type
detected_mime = detect_image_mime(data[:16])
...
width, height = _validate_decodable_image(data, settings.supplement_image_max_pixels)
return ValidatedSupplementImage(image_bytes=data, ...)

# (변경 후)
data = await _read_limited_upload(image, settings.supplement_image_max_bytes)
content_type = image.content_type
detected_mime = detect_image_mime(data[:16])
...
width, height = _validate_decodable_image(data, settings.supplement_image_max_pixels)

# H1 — strip EXIF/XMP/IPTC so downstream OCR/storage never sees user GPS.
try:
    sanitized = strip_image_metadata(data, detected_mime)
except ImageSafetyError as exc:
    raise SupplementImageValidationError(
        code="invalid_image",
        message="Uploaded label image cannot be normalized.",
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
    ) from exc

return ValidatedSupplementImage(image_bytes=sanitized, ...)
```

**수정** `backend/Nutrition-backend/src/main.py` — 앱 시작 시 Pillow 한도 설정 (H2와 공유)
```python
from src.utils.image_safety import configure_pillow_limits
...
@app.on_event("startup")
async def _configure_pillow() -> None:
    configure_pillow_limits(settings.supplement_image_max_pixels)
```

### 1.6 회귀 테스트

**신규** `backend/Nutrition-backend/tests/fixtures/exif/with_gps.jpg`
- 생성 방법(개발자 일회성): `exiftool -GPS:GPSLatitude="37.5665" -GPS:GPSLongitude="126.978" -GPS:GPSLatitudeRef="N" -GPS:GPSLongitudeRef="E" sample.jpg`

**신규** `backend/Nutrition-backend/tests/unit/utils/test_image_safety.py`
```python
import io
from pathlib import Path

import pytest
from PIL import Image
from src.utils.image_safety import (
    ImageSafetyError,
    strip_image_metadata,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "exif" / "with_gps.jpg"


def test_strip_removes_gps_exif() -> None:
    data = FIXTURE.read_bytes()
    sanitized = strip_image_metadata(data, "image/jpeg")
    with Image.open(io.BytesIO(sanitized)) as im:
        assert im.getexif().get(0x8825) is None  # GPSInfo IFD pointer absent
        assert "xmp" not in im.info


def test_strip_preserves_orientation() -> None:
    # build a 100x50 image with EXIF Orientation=6 (rotate 270 CW)
    src = Image.new("RGB", (100, 50), color="red")
    buf = io.BytesIO()
    exif = src.getexif()
    exif[0x0112] = 6
    src.save(buf, format="JPEG", exif=exif.tobytes())
    sanitized = strip_image_metadata(buf.getvalue(), "image/jpeg")
    with Image.open(io.BytesIO(sanitized)) as im:
        assert im.size == (50, 100)  # transposed
        assert im.getexif().get(0x0112) is None


def test_strip_rejects_unsupported_mime() -> None:
    with pytest.raises(ImageSafetyError):
        strip_image_metadata(b"\x00\x01", "image/gif")
```

**신규** `backend/Nutrition-backend/tests/integration/test_supplement_intake_exif.py`
```python
async def test_uploaded_label_is_stripped_before_learning_store(
    async_client, learning_store_spy
):
    response = await async_client.post(
        "/supplements/analyze",
        files={"image": ("label.jpg", FIXTURE_WITH_GPS, "image/jpeg")},
    )
    assert response.status_code == 202
    stored_bytes = learning_store_spy.last_payload.image_bytes
    with Image.open(BytesIO(stored_bytes)) as im:
        assert im.getexif().get(0x8825) is None
```

### 1.7 롤아웃·롤백

- **머지**: PR-A는 dev → staging → prod 순. feature flag 불필요 (정화는 보안 디폴트).
- **카나리 신호**: staging에서 24시간 운영 후 `image_safety.strip.failure_total == 0` 확인. 비제로면 prod 차단.
- **롤백**: revert PR-A. 학습 스토어에 이미 들어간 정화 이미지는 그대로 유효(시각적 변경 없음). 정화 실패로 거부된 사용자 업로드 로그만 별도 분석.

### 1.8 운영 모니터링/알림

| 메트릭 | 타입 | 알림 임계 |
|--------|------|----------|
| `image_safety.strip.success_total` | Counter | — |
| `image_safety.strip.failure_total{reason}` | Counter | 분당 > 5 → Slack #ops |
| `image_safety.strip.duration_seconds` p95 | Histogram | > 100ms (이미지 1장) → 조사 |

로그 필드: `image_sha256`(이미 존재), `mime`, `strip_outcome`("ok"/"failed:{reason}"). GPS·EXIF 원본 절대 로깅 금지.

### 1.9 컴플라이언스 매핑

- 위치정보의 보호 및 이용 등에 관한 법률 제15조(개인위치정보의 수집 등의 금지) — 수집 자체를 회피하여 동의 의무 면제.
- 개인정보 보호법 제15조·제22조 — 수집 항목 최소화 원칙 부합.
- Apple App Store Review 5.1.2 — Data Minimization. Google Play Privacy & Security — Location handling.

---

## 2. H2 — PIL 디컴프레션 폭탄 방어

### 2.1 결함 재진술
`_validate_decodable_image`가 `image.verify()`만 호출하므로 헤더 디코드 시점에서 일부 폭탄은 막히지만, **다운스트림 `.load()` 호출(`supplement_image_quality._decode_image`)에서 실제 픽셀 디코드가 일어나며 메모리 폭주**가 가능. `Image.MAX_IMAGE_PIXELS` 글로벌 미설정 → Pillow 기본값 ~179Mpx로 너무 헐거움. 악의적 PNG 1장으로 워커 OOM 유발 가능.

### 2.2 현 상태 코드 스냅샷
- `backend/Nutrition-backend/src/services/supplement_intake.py:672-686` — `image.verify()`만 호출.
- `backend/Nutrition-backend/src/services/supplement_image_quality.py:61` — `_decode_image(image_bytes)` 호출, 내부에서 `Image.open(...).load()` 수행(에이전트 보고). `MAX_IMAGE_PIXELS` 미설정 / `DecompressionBombError` 미캐치.
- `backend/Nutrition-backend/src/config.py` — `supplement_image_max_pixels: int = Field(default=12_000_000)` 이미 존재.

### 2.3 브레인스토밍: 접근안 비교

| 옵션 | 방식 | 구현 복잡도 | 운영 부담 | 보안 강도 | 잔존 리스크 | 결정 |
|------|------|------------|----------|----------|------------|------|
| **A (추천)** | 앱 시작 시 `Image.MAX_IMAGE_PIXELS = settings.supplement_image_max_pixels` 1회 설정 + 모든 `.load()` 호출을 `safe_load_with_bomb_guard()`로 감싸기 | 낮음 (호출처 3-5곳) | 없음 | 높음 (프로세스 전역 + 명시적 예외 처리) | 동일 프로세스 내 향후 신규 `.load()` 호출 시 가드 누락 위험 → linter 규칙 권장 | ✅ 채택 |
| B | 서브프로세스 격리(이미지 디코딩을 별도 워커 프로세스에서 수행) | 높음 (IPC, 직렬화, 풀 관리) | 중간 (워커 수명·메모리 모니터링) | 매우 높음 (메모리 폭주가 메인에 영향 없음) | 50ms+ 지연 추가, 코드 복잡도 폭증 | ❌ MVP 과잉 |
| C | Pillow 대체(opencv-python으로 디코드) | 중간 (재작성) | 낮음 | 중간 (cv2도 자체 폭탄 취약점 있음) | 신규 의존성 + 회귀 위험 | ❌ |

**결정 사유**: 옵션 A는 Pillow가 이미 제공하는 안전 메커니즘(`MAX_IMAGE_PIXELS` + `DecompressionBombWarning`)을 적극 활용. H1과 동일한 `image_safety.py` 모듈에 통합되어 코드 위치도 자연스러움.

### 2.4 추천 설계 상세

**시점 모델**
- 앱 시작 시 1회: `configure_pillow_limits(settings.supplement_image_max_pixels)` 호출 → `Image.MAX_IMAGE_PIXELS`가 12,000,000 (현재 settings 기본값)으로 고정.
- 호출 시점: `warnings.catch_warnings()`로 `DecompressionBombWarning`을 error로 escalate. 이렇게 하면 *MAX_IMAGE_PIXELS와 그 2배 사이*의 폭탄도 즉시 차단(Pillow는 이 구간에서 warning만 띄움).

**의도된 한계**
- `MAX_IMAGE_PIXELS` 자체는 모듈 전역(스레드 안전 X)이지만 시작 시 1회 설정 후 변경 없으므로 무관.
- `.load()`가 호출되는 모든 지점에 가드를 두는 것이 핵심 — linter/CI 검사로 강제(아래 §2.7 참조).

### 2.5 구현 패치

**§1.5의 `image_safety.py`에 이미 포함됨**: `configure_pillow_limits`, `safe_load_with_bomb_guard`.

**수정** `backend/Nutrition-backend/src/services/supplement_image_quality.py:61-71` — `_decode_image` 가드 적용
```python
# (변경 전)
def _decode_image(image_bytes: bytes) -> Image.Image:
    with Image.open(BytesIO(image_bytes)) as image:
        image.load()
        return image.copy()  # 또는 동등 패턴

# (변경 후)
from src.utils.image_safety import ImageSafetyError, safe_load_with_bomb_guard

def _decode_image(image_bytes: bytes) -> Image.Image:
    try:
        return safe_load_with_bomb_guard(image_bytes)
    except ImageSafetyError as exc:
        raise ImageQualityAnalysisError("decompression_blocked") from exc
```

**수정** `_validate_decodable_image` (`supplement_intake.py:658-695`) — `verify()` 후 `safe_load_with_bomb_guard`로 2단계 검증
```python
# (변경 후, 발췌)
def _validate_decodable_image(data: bytes, max_pixels: int) -> tuple[int, int]:
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            if width <= 0 or height <= 0:
                raise SupplementImageValidationError(...)
            if width * height > max_pixels:
                raise SupplementImageValidationError(
                    code="payload_too_large",
                    message="...",
                    status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                )
            image.verify()
    except (OSError, UnidentifiedImageError) as exc:
        raise SupplementImageValidationError(...) from exc

    # H2 — second pass forces full decode under bomb guard.
    try:
        with safe_load_with_bomb_guard(data) as image:
            return image.size
    except ImageSafetyError as exc:
        raise SupplementImageValidationError(
            code="payload_too_large",
            message="Uploaded label image is too large to decode.",
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        ) from exc
```

### 2.6 회귀 테스트

**신규 픽스처 생성 스크립트** `tests/fixtures/bombs/make_bomb.py`
```python
"""Generates a small-on-disk PNG that decodes to >200 Mpx (test only)."""
from PIL import Image
img = Image.new("L", (20000, 20000), color=0)
img.save("tests/fixtures/bombs/large_dim.png", format="PNG", optimize=False)
```
(픽스처는 `.gitignore`되거나 generator 스크립트만 커밋. 실파일은 ~80KB로 가벼움)

**신규** `tests/unit/utils/test_image_safety_bomb.py`
```python
def test_bomb_guard_blocks_oversized() -> None:
    bomb = (FIXTURE_DIR / "large_dim.png").read_bytes()
    configure_pillow_limits(12_000_000)
    with pytest.raises(ImageSafetyError):
        safe_load_with_bomb_guard(bomb)


def test_normal_image_passes() -> None:
    configure_pillow_limits(12_000_000)
    with safe_load_with_bomb_guard(SMALL_PNG_BYTES) as im:
        assert im.size == (100, 100)
```

**신규** `tests/integration/test_supplement_intake_bomb.py`
```python
async def test_bomb_upload_rejected_with_413(async_client):
    response = await async_client.post(
        "/supplements/analyze",
        files={"image": ("bomb.png", BOMB_BYTES, "image/png")},
    )
    assert response.status_code == 413
```

### 2.7 롤아웃·롤백

- PR-A에 묶여 동시 머지 (H1과 분리 가치 낮음).
- **CI 가드**: ruff custom 규칙 또는 `grep -rn "Image.open" src/` 비교 → 신규 발생 시 PR 리뷰에서 `safe_load_with_bomb_guard` 사용 여부 확인.
- 롤백: H1 롤백과 동일. 디코드 동작 자체는 보존 호환.

### 2.8 운영 모니터링/알림

| 메트릭 | 타입 | 알림 임계 |
|--------|------|----------|
| `image_safety.bomb_blocked_total` | Counter | 분당 > 1 → Slack (공격 시도 가능) |
| `image_safety.decode.duration_seconds` p95 | Histogram | > 500ms → 조사 |
| 워커 메모리 RSS | Gauge | > 90% baseline → 폭탄 누수 의심 |

### 2.9 컴플라이언스 매핑

- OWASP API Security Top 10 (2023) **API4: Unrestricted Resource Consumption**.
- ISO 27001 A.8.7 Capacity Management — DoS 방어 일환.

---

## 3. H3 — 모바일 cert pinning + Android NSC + iOS ATS

### 3.1 결함 재진술
Flutter `package:http` 클라이언트가 인증서 핀닝 없이 동작 + Android `network_security_config.xml` 부재 + iOS `NSAppTransportSecurity` 명시 부재. MDM·기업 프록시·악성 프로파일로 사용자 단말에 신뢰된 임의 루트가 설치되면 Authorization 헤더 + 헬스 데이터가 가로채짐. **Apple/Google 의료 카테고리 reviewer가 가장 흔히 지적하는 항목**.

### 3.2 현 상태 코드 스냅샷

**Android Manifest** (`mobile/flutter_app/android/app/src/main/AndroidManifest.xml:5-8`)
```xml
<application
    android:label="Lemon Aid"
    android:name="${applicationName}"
    android:icon="@mipmap/ic_launcher">
```
→ `android:networkSecurityConfig` 속성 없음. `usesCleartextTraffic` 미선언.

**iOS Info.plist** (`mobile/flutter_app/ios/Runner/Info.plist:29-32`)
```xml
<key>NSCameraUsageDescription</key>
<string>Lemon Aid uses camera photos to create supplement label OCR previews for your review.</string>
<key>NSPhotoLibraryUsageDescription</key>
<string>Lemon Aid uses selected supplement label images to create OCR previews for your review.</string>
```
→ `NSAppTransportSecurity` 키 없음. iOS 기본 ATS만 적용.

**Dart 클라이언트** (`mobile/flutter_app/lib/core/api/api_client.dart:15-25`)
```dart
ApiClient({...}) : _httpClient = httpClient ?? http.Client();
```
→ `http.Client()` 직접 인스턴스화. `SecurityContext` 커스텀 없음.

### 3.3 브레인스토밍: 접근안 비교

| 옵션 | 방식 | 구현 복잡도 | 운영 부담 | 보안 강도 | 잔존 리스크 | 결정 |
|------|------|------------|----------|----------|------------|------|
| **A (추천)** | Platform-native — Android NSC + iOS URLSession delegate. Dart는 핀 상태 텔레메트리만 수신 | 중간 (Android XML + Swift delegate + MethodChannel) | 분기별 SPKI 핀 회전 1회 | 매우 높음 (OS-level 강제) | 핀 만료 누락 시 silent disable (Android) — 만료일 alert 필수 | ✅ 채택 |
| B | Dart `http_security_pinning` 패키지(SPKI) | 낮음 | 패키지 유지보수 의존 | 중간 (Dart 레이어 우회 가능) | 패키지 abandonware 위험, OS 업데이트 호환 추적 필요 | ❌ |
| C | Dio 마이그레이션 + interceptor 핀닝 | 높음 | HTTP 클라이언트 전면 교체 | 중간 | 본 결함 외 변경 폭발 | ❌ MVP 과잉 |

**결정 사유**: Medical-grade 앱에서 OS 레벨 강제가 OWASP MASVS·Apple/Google 리뷰어 모두에서 가장 신뢰. Dart 패키지는 dynamic interception으로 우회 가능. Dio 전면 교체는 본 결함 해결에 비해 변경 폭이 과대.

### 3.4 추천 설계 상세

**아키텍처**
```
              ┌─────────────────────────┐
   Dart →     │ ApiClient (변경 최소)    │
              └────────────┬────────────┘
                           │ HTTP request
                           ▼
   ┌───────────────────────────────────────────┐
   │ Android: NSC XML이 시스템 TrustManager에   │
   │   pin-set 주입 → SSLHandshakeException     │
   │   자동 throw                              │
   │ iOS: PinnedURLSessionDelegate가           │
   │   URLAuthenticationChallenge에서 SPKI      │
   │   비교 → completionHandler(.cancelAuth.)   │
   └────────────┬──────────────────────────────┘
                │ 실패 이벤트
                ▼
   MethodChannel(lemonaid/pinning) → Dart로 전달
                │
                ▼
   Sentry / Crashlytics 텔레메트리
```

**핀 정책**
- SPKI SHA-256 핀 2개 유지: 현재 production 키 + 사전 생성 backup 키.
- 만료 정책: Android NSC `expiration` 12개월. 만료 6개월 전 캘린더 알림. 만료 시 NSC는 silent disable되므로 만료 30일 전부터 매일 alert.
- 핀 저장: GitHub Secrets `LEMON_SPKI_PIN_PRIMARY`, `LEMON_SPKI_PIN_BACKUP`. CI 빌드 시 XML/plist에 주입(템플릿 치환).
- 핀 추출 스크립트는 §3.5 마지막에 별도 제공.

**도메인 결정**
- 본 문서는 placeholder `api.lemonaid.example.com` 사용. 운영팀이 실제 도메인 확정 시 모든 XML/plist에 치환. (CI 환경변수 `LEMON_PROD_HOST`로 처리 권장.)

### 3.5 구현 패치

#### 3.5.1 Android — Network Security Config

**신규** `mobile/flutter_app/android/app/src/main/res/xml/network_security_config.xml`
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system"/>
        </trust-anchors>
    </base-config>

    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">api.lemonaid.example.com</domain>
        <pin-set expiration="2027-05-18">
            <pin digest="SHA-256">${LEMON_SPKI_PIN_PRIMARY}</pin>
            <pin digest="SHA-256">${LEMON_SPKI_PIN_BACKUP}</pin>
        </pin-set>
    </domain-config>

    <debug-overrides>
        <trust-anchors>
            <certificates src="system"/>
            <certificates src="user"/>
        </trust-anchors>
    </debug-overrides>
</network-security-config>
```

**신규** `mobile/flutter_app/android/app/src/dev/res/xml/network_security_config.xml` (dev flavor)
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system"/>
            <certificates src="user"/>
        </trust-anchors>
    </base-config>
</network-security-config>
```
→ dev/staging만 cleartext + user CA 허용. prod는 위 main 버전만 적용.

**수정** `mobile/flutter_app/android/app/src/main/AndroidManifest.xml:5-8`
```xml
<application
    android:label="Lemon Aid"
    android:name="${applicationName}"
    android:icon="@mipmap/ic_launcher"
    android:networkSecurityConfig="@xml/network_security_config">
```

**수정** `mobile/flutter_app/android/app/build.gradle.kts` — release buildType에서 placeholder 치환
```kotlin
buildTypes {
    release {
        manifestPlaceholders["spkiPinPrimary"] = System.getenv("LEMON_SPKI_PIN_PRIMARY") ?: ""
        manifestPlaceholders["spkiPinBackup"]  = System.getenv("LEMON_SPKI_PIN_BACKUP")  ?: ""
        // ...
    }
}
```
→ XML은 `${LEMON_SPKI_PIN_PRIMARY}` 대신 `${spkiPinPrimary}` Gradle placeholder 사용. (Android는 NSC에 직접 환경변수 치환을 지원하지 않으므로 빌드 단계에서 Gradle task로 XML을 generate.)

대안 — Gradle task로 XML 생성:
```kotlin
val generateNsc by tasks.registering {
    val outFile = layout.buildDirectory.file("generated/res/xml/network_security_config.xml")
    doLast {
        val template = file("src/main/res/xml/network_security_config.template.xml").readText()
        val resolved = template
            .replace("\${LEMON_SPKI_PIN_PRIMARY}", System.getenv("LEMON_SPKI_PIN_PRIMARY") ?: error("missing pin"))
            .replace("\${LEMON_SPKI_PIN_BACKUP}",  System.getenv("LEMON_SPKI_PIN_BACKUP")  ?: error("missing pin"))
        outFile.get().asFile.apply { parentFile.mkdirs(); writeText(resolved) }
    }
}
tasks.matching { it.name == "preReleaseBuild" }.configureEach { dependsOn(generateNsc) }
```

#### 3.5.2 iOS — ATS + URLSession 델리게이트

**수정** `mobile/flutter_app/ios/Runner/Info.plist` — 다음 dict 추가
```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <false/>
    <key>NSExceptionDomains</key>
    <dict>
        <key>api.lemonaid.example.com</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <false/>
            <key>NSExceptionMinimumTLSVersion</key>
            <string>TLSv1.2</string>
            <key>NSIncludesSubdomains</key>
            <true/>
            <key>NSRequiresCertificateTransparency</key>
            <true/>
        </dict>
    </dict>
</dict>
```

**신규** `mobile/flutter_app/ios/Runner/PinnedURLSessionDelegate.swift`
```swift
import Foundation
import CommonCrypto
import Flutter

final class PinnedURLSessionDelegate: NSObject, URLSessionDelegate {
    private let spkiPins: Set<String>
    private let channel: FlutterMethodChannel

    init(pins: [String], channel: FlutterMethodChannel) {
        self.spkiPins = Set(pins)
        self.channel = channel
    }

    func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        guard
            challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
            let trust = challenge.protectionSpace.serverTrust,
            let chain = SecTrustCopyCertificateChain(trust) as? [SecCertificate]
        else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        for cert in chain {
            if let pin = spkiHash(of: cert), spkiPins.contains(pin) {
                completionHandler(.useCredential, URLCredential(trust: trust))
                return
            }
        }

        channel.invokeMethod("pinningFailure", arguments: [
            "host": challenge.protectionSpace.host,
            "expectedPins": Array(spkiPins),
        ])
        completionHandler(.cancelAuthenticationChallenge, nil)
    }

    private func spkiHash(of cert: SecCertificate) -> String? {
        guard
            let publicKey = SecCertificateCopyKey(cert),
            let data = SecKeyCopyExternalRepresentation(publicKey, nil) as Data?
        else { return nil }
        var sha = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        data.withUnsafeBytes { _ = CC_SHA256($0.baseAddress, CC_LONG(data.count), &sha) }
        return Data(sha).base64EncodedString()
    }
}
```

**수정** `mobile/flutter_app/ios/Runner/AppDelegate.swift` — 델리게이트 등록 + MethodChannel
```swift
import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate {
    var pinningDelegate: PinnedURLSessionDelegate?

    override func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        let controller = window?.rootViewController as! FlutterViewController
        let channel = FlutterMethodChannel(
            name: "lemonaid/pinning",
            binaryMessenger: controller.binaryMessenger
        )
        let pins = [
            Bundle.main.object(forInfoDictionaryKey: "LemonSpkiPinPrimary") as? String,
            Bundle.main.object(forInfoDictionaryKey: "LemonSpkiPinBackup")  as? String,
        ].compactMap { $0 }
        pinningDelegate = PinnedURLSessionDelegate(pins: pins, channel: channel)

        // Swizzle URLSession.shared replacement: provide a delegate-bound session
        // for the Flutter http plugin via a shared singleton accessor.
        PinnedSession.shared = URLSession(
            configuration: .default,
            delegate: pinningDelegate,
            delegateQueue: nil
        )

        GeneratedPluginRegistrant.register(with: self)
        return super.application(application, didFinishLaunchingWithOptions: launchOptions)
    }
}

enum PinnedSession { static var shared: URLSession = .shared }
```

> 주의: Flutter `package:http`는 내부적으로 `dart:io HttpClient`를 사용하며, iOS에서는 `NSURLSession`이 아니라 Dart VM의 자체 HTTP 스택을 탄다. **본 OS-level delegate는 native code path(예: native push, app-managed downloads)에만 적용된다.** Dart 측 HTTP에도 SPKI 핀을 강제하려면 Dart `SecurityContext`에 trusted certs를 수동 등록하거나 `cupertino_http`/`cronet_http` 같은 native HTTP adapter를 도입해야 한다. 이 가이드의 H3 채택안은 두 가지 보완을 함께 둔다:
> 1. **OS-level**: NSC(Android) + URLSession delegate(iOS native code path) — 향후 native 통합 채널 보호.
> 2. **Dart-level (보완 필수)**: `package:cupertino_http` + `package:cronet_http`로 `http.Client`를 native session에 위임. 신규 `lib/core/api/secure_http_client.dart` 작성.

**신규** `mobile/flutter_app/lib/core/api/secure_http_client.dart`
```dart
import 'dart:io' show Platform;
import 'package:http/http.dart' as http;
import 'package:cupertino_http/cupertino_http.dart';
import 'package:cronet_http/cronet_http.dart';

http.Client buildSecureHttpClient() {
  if (Platform.isIOS || Platform.isMacOS) {
    final URLSessionConfiguration config =
        URLSessionConfiguration.ephemeralSessionConfiguration()
          ..tlsMinimumSupportedProtocolVersion = TLSProtocolVersion.tlsv12;
    return CupertinoClient.fromSessionConfiguration(config);
  }
  if (Platform.isAndroid) {
    final CronetEngine engine = CronetEngine.build(
      cacheMode: CacheMode.disabled,
      userAgent: 'lemonaid-mobile',
    );
    return CronetClient.fromCronetEngine(engine);
  }
  return http.Client();
}
```

**수정** `mobile/flutter_app/lib/main.dart` — `ApiClient` 생성 시 secure client 주입
```dart
final apiClient = ApiClient(
  baseUrl: config.apiBaseUrl,
  bearerToken: config.apiToken,
  httpClient: buildSecureHttpClient(),
);
```

**수정** `pubspec.yaml` — 의존성 추가
```yaml
dependencies:
  cupertino_http: ^2.0.0
  cronet_http: ^1.3.0
```

> 이렇게 하면 (a) iOS는 `URLSession` delegate를 자동 활용 (Dart `http`가 native session에 위임), (b) Android는 Cronet이 NSC를 자동 적용. **이중 보호 달성.**

#### 3.5.3 SPKI 핀 추출 스크립트

**신규** `mobile/flutter_app/scripts/extract_spki_pin.sh`
```bash
#!/usr/bin/env bash
# Usage: scripts/extract_spki_pin.sh api.lemonaid.example.com
set -euo pipefail
HOST="${1:?usage: $0 <host>}"
openssl s_client -servername "$HOST" -connect "${HOST}:443" </dev/null 2>/dev/null \
  | openssl x509 -outform pem \
  | openssl x509 -pubkey -noout \
  | openssl pkey -pubin -outform der \
  | openssl dgst -sha256 -binary \
  | base64
```

### 3.6 회귀 테스트

#### 3.6.1 Android — instrumentation test

**신규** `mobile/flutter_app/android/app/src/androidTest/java/com/lemonaid/PinningTest.kt`
```kotlin
@RunWith(AndroidJUnit4::class)
class PinningTest {
    @Test
    fun connectionToWrongPinFails() {
        val server = MockWebServer()
        server.useHttps(buildSelfSignedSocketFactory(), false)
        server.enqueue(MockResponse().setResponseCode(200))
        server.start()

        val url = server.url("/health")
        val expected = assertThrows<SSLHandshakeException> {
            URL(url.toString()).openConnection().connect()
        }
        assertTrue(expected.message?.contains("Pin verification failed") == true)
    }
}
```

#### 3.6.2 iOS — XCTest

**신규** `mobile/flutter_app/ios/RunnerTests/PinnedURLSessionDelegateTests.swift`
```swift
final class PinnedURLSessionDelegateTests: XCTestCase {
    func testWrongPinIsRejected() {
        let delegate = PinnedURLSessionDelegate(pins: ["AAAA..."], channel: FakeChannel())
        let challenge = makeMockChallenge(spki: "BBBB...")
        let exp = expectation(description: "completion")
        delegate.urlSession(URLSession.shared, didReceive: challenge) { disp, _ in
            XCTAssertEqual(disp, .cancelAuthenticationChallenge)
            exp.fulfill()
        }
        wait(for: [exp], timeout: 1)
    }
}
```

#### 3.6.3 Flutter — integration

**신규** `mobile/flutter_app/test/integration/pinning_failure_test.dart`
```dart
test('pinning failure surfaces ApiError(network)', () async {
  final client = MockClient((req) async {
    throw const SocketException('Pin verification failed');
  });
  final api = ApiClient(baseUrl: 'https://api.lemonaid.example.com/api/v1', httpClient: client);
  await expectLater(api.getJson('/health'), throwsA(isA<ApiError>()));
});
```

### 3.7 롤아웃·롤백

| 단계 | 환경 | 기간 | 합격 조건 |
|------|------|------|----------|
| 1 | dev flavor | 7일 | 사내 테스터 100% 정상 응답, `pinningFailure` 이벤트 0건 |
| 2 | staging flavor | 14일 | TestFlight/Internal Testing 대상자 50명 누적 응답 200 ≥ 99.9% |
| 3 | prod 카나리 | 7일 | 점진 10% → 50% → 100% 출시. 핀 실패율 < 0.01% |

**롤백 명령**
- Android: NSC XML에서 `<pin-set>` 블록 주석 처리 + 핫픽스 release publish. (Play Console 단계적 출시 일시정지로 즉시 차단 후 픽스 빌드 푸시.)
- iOS: `PinnedSession.shared = .shared`로 환원 + 재서명. App Store에 expedited review 신청.
- 핵심: 핀 실패가 인증서 회전 누락 때문이라면 backup 핀이 자동 활성화되므로 별도 조치 불요. 양쪽 핀이 모두 실패하면 운영팀이 새 SPKI 추출 후 즉시 OTA 가능한 remote config로 fallback 도메인 교체 검토.

### 3.8 운영 모니터링/알림

| 메트릭 | 타입 | 알림 임계 |
|--------|------|----------|
| `mobile.pinning.failure_total{platform, app_version, host}` | Counter | 5분 누적 > 10 → PagerDuty (인증서 회전 사고 가능) |
| `mobile.pinning.cert_expiry_days_remaining` | Gauge (NSC `expiration` 파싱) | < 30 → 매일 Slack #mobile |
| `mobile.pinning.success_total` | Counter | — (rate 비교용) |
| Sentry fingerprint | "SSLHandshakeException + pinning" | unique device count 급등 시 알림 |

수집 경로: iOS는 `PinnedURLSessionDelegate`가 `lemonaid/pinning` MethodChannel로 Dart에 통지 → Dart에서 Sentry 전송. Android는 `NetworkSecurityPolicy` 핀 실패가 `SSLHandshakeException`으로 throw되므로 ApiClient try/catch에서 fingerprint 부여.

### 3.9 컴플라이언스 매핑

- OWASP MASVS-NETWORK-1, MASVS-NETWORK-2 (2024).
- Apple App Store Review Guideline 2.5.1 (Software Requirements), 5.1.1(v) (Privacy — Data Collection).
- Google Play Policy: User Data — Secure Networking.
- KISA 모바일 앱 보안 가이드라인 §4.2 TLS 적용 및 인증서 검증.

---

## 부록 A. SPKI 핀 운영 체크리스트 (분기 1회)

- [ ] 운영 인증서 만료일 확인 (`openssl s_client -servername $HOST -connect $HOST:443 </dev/null | openssl x509 -noout -enddate`)
- [ ] 현재 핀(primary)이 운영 키와 일치하는지 재확인
- [ ] backup 핀이 차기 키 쌍과 일치하는지 확인. 미일치 시 새 backup 핀 생성
- [ ] Android NSC `expiration` 속성이 현재 시점 기준 ≥ 6개월 남았는지 확인. 그렇지 않으면 갱신 PR
- [ ] iOS Info.plist의 `LemonSpkiPinPrimary`/`Backup` 빌드 환경변수 매핑 확인
- [ ] 신규 release 빌드 산출물 1회 device install + 정상 통신 확인
- [ ] Sentry/모니터링에 핀 실패 0건 확인

## 부록 B. 컴플라이언스 조항 ID 매핑

| 결함 | 한국 법규 | 국제 가이드라인 |
|------|-----------|---------------|
| H1 | 위치정보의 보호 및 이용 등에 관한 법률 §15 / 개인정보 보호법 §15 §22 | Apple Review 5.1.2, Google Play User Data |
| H2 | (해당 없음 — 안정성 이슈) | OWASP API Top10 API4 (2023), ISO 27001 A.8.7 |
| H3 | KISA 모바일 앱 보안 가이드라인 §4.2 / 정보통신망법 §28 (기술적 보호조치) | OWASP MASVS-NETWORK-1/2, Apple Review 2.5.1·5.1.1(v), Google Play Secure Networking |

## 부록 C. 외부 참고 문서

- Pillow 12.x — [Image module reference](https://pillow.readthedocs.io/en/stable/reference/Image.html), [ImageOps](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html)
- Android Developers — [Network Security Configuration](https://developer.android.com/privacy-and-security/security-config)
- Apple Developer — [NSAppTransportSecurity](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity)
- Flutter — [`cupertino_http`](https://pub.dev/packages/cupertino_http), [`cronet_http`](https://pub.dev/packages/cronet_http)
- KISA — [의료기관 개인정보보호 가이드라인](https://www.kisa.or.kr/2060203/form?postSeq=16&lang_type=KO&page=1)
- MFDS — [디지털의료제품법 안내서](https://www.mfds.go.kr/brd/m_1060/list.do)

## 부록 D. 변경/신규 파일 인덱스

### 신규
- `backend/Nutrition-backend/src/utils/image_safety.py`
- `backend/Nutrition-backend/tests/unit/utils/test_image_safety.py`
- `backend/Nutrition-backend/tests/unit/utils/test_image_safety_bomb.py`
- `backend/Nutrition-backend/tests/integration/test_supplement_intake_exif.py`
- `backend/Nutrition-backend/tests/integration/test_supplement_intake_bomb.py`
- `backend/Nutrition-backend/tests/fixtures/exif/with_gps.jpg`
- `backend/Nutrition-backend/tests/fixtures/bombs/make_bomb.py`
- `mobile/flutter_app/android/app/src/main/res/xml/network_security_config.xml`
- `mobile/flutter_app/android/app/src/dev/res/xml/network_security_config.xml`
- `mobile/flutter_app/android/app/src/androidTest/java/com/lemonaid/PinningTest.kt`
- `mobile/flutter_app/ios/Runner/PinnedURLSessionDelegate.swift`
- `mobile/flutter_app/ios/RunnerTests/PinnedURLSessionDelegateTests.swift`
- `mobile/flutter_app/lib/core/api/secure_http_client.dart`
- `mobile/flutter_app/test/integration/pinning_failure_test.dart`
- `mobile/flutter_app/scripts/extract_spki_pin.sh`

### 수정
- `backend/Nutrition-backend/src/services/supplement_intake.py:127-159` (strip 삽입) / `:658-695` (bomb guard)
- `backend/Nutrition-backend/src/services/supplement_image_quality.py:61` (`_decode_image` 가드)
- `backend/Nutrition-backend/src/main.py` (startup hook에 `configure_pillow_limits`)
- `mobile/flutter_app/android/app/src/main/AndroidManifest.xml:5-8` (`networkSecurityConfig` 속성)
- `mobile/flutter_app/android/app/build.gradle.kts` (release buildType + Gradle task)
- `mobile/flutter_app/ios/Runner/Info.plist` (NSAppTransportSecurity dict)
- `mobile/flutter_app/ios/Runner/AppDelegate.swift` (PinnedURLSessionDelegate 등록)
- `mobile/flutter_app/lib/main.dart` (secure client 주입)
- `mobile/flutter_app/pubspec.yaml` (`cupertino_http`, `cronet_http`)

---

## 마무리 — 다음 행동

PR-A부터 순서대로 머지. 각 PR에서 §1.6/§2.6/§3.6 회귀 테스트를 함께 통과시킬 것. PR-C 머지 후 H1·H2·H3 모두 닫힘을 §1.9·§2.9·§3.9 조항 기준으로 회의록에 기록 → 감사 보고서 §3 HIGH 절을 `[CLOSED]` 마킹.

이 가이드라인의 모호한 부분이 있으면 본 문서 작성자에게 질문 후 가이드를 보강할 것 — 코드만 임의 변경 금지(컴플라이언스 회귀 위험).

— *가이드 종료* —
