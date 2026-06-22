# AI Hub 통합 클래스 재분리(re-split) 작업 핸드오프

> **작성일**: 2026-05-29 · **상태**: 조사·타당성 검증 완료, **재라벨링 미실행** (다음 세션에서 진행)
> **목적**: 50클래스로 통합 라벨링된 YOLO 데이터셋을, 원본 AI Hub 코드 단위(예: 찌개 → 김치찌개/된장찌개/부대찌개…)로 **다시 분리**한다.
> **이 문서 하나만 읽으면 작업을 이어갈 수 있도록** 사실관계·검증결과·절차·결정사항·재현 명령을 모두 담았다.

---

## 0. TL;DR (핵심 결론)

1. **val 원본만으로 복구 가능한가? → 부분적으로 가능.**
   - train에 등장하는 **430개 AI Hub 코드 중 402개**는 살아있는 **val 원본**에서 한글 음식명을 정확히 복구할 수 있다. (검증 완료)
   - 나머지 **28개 코드는 val 원본에도 없어 복구 불가** → 별도 출처(AI Hub 공식 카테고리표) 또는 수동 보완 필요.
   - 사용자 1차 목표인 **찌개(stew)는 7개 중 5개 복구 가능, 2개(B12086·B12104) 누락.**
2. 복구 방법은 **검증됨**: val 라벨 JSON의 `data.image_info.file_name` 토큰에서 한글명이 그대로 나온다. (예: `A_13_A13045_황태부대찌개_30_09.jpg` → `황태부대찌개`)
3. 라벨 파일은 **전부 객체 1개(1줄)** → 리매핑은 "파일명의 코드 → 새 클래스 인덱스"로 첫 토큰만 치환하면 되는 단순 작업.
4. **아직 결정 안 된 것**: 분리 granularity(찌개만? 전체?), in-place 수정 vs 새 데이터셋 변형, 28개 누락코드 처리 방침. → §6 참고.

---

## 1. 배경 / 왜 이 작업을 하는가

- 데이터셋 `data/food_images/aihub_yolo_50` 은 AI Hub "건강관리용 음식 이미지"의 수백 개 세부 음식 카테고리를 **Roboflow 50클래스로 통합(merge)** 하여 만들어졌다.
- 그 과정에서 예: 김치찌개·된장찌개·부대찌개·순두부찌개·김치찜 등이 전부 단일 클래스 **`stew`(index 15)** 로 합쳐졌다.
- 사용자는 이를 **원래 세부 음식 단위로 되돌려 라벨링**하길 원한다. 1차 목표는 찌개류, 추가로 **"매핑을 찾으면 찌개 말고 다른 음식도 분리"** 요청함.

---

## 2. 데이터셋 / 파일 구조 사실관계 (검증됨)

### 2.1 변환된 YOLO 데이터셋 (작업 대상, C: 드라이브)
- 루트: `C:\Lemon-Aid\Lemon-sin\data\food_images\aihub_yolo_50\`
  - `data.yaml` — `nc: 50`, `names:` 50개
  - `train/images` (**108,580장**), `train/labels`
  - `val/images`, `val/labels`
  - `yolo_class_index_50.json` — `{class_names:[...], aihub_to_yolo:{CODE:{yolo_index, roboflow_class}}}`
  - `_audit/class_counts.csv` — 클래스별 개수
- **파일명 규칙**: `{split}_{CODE}_s{set}_p{photo}_{sha8}.jpg` / `.txt`
  - 예: `train_A13045_s03_p01_7dd92b62.jpg` → CODE = `A13045`
  - **한글 음식명은 파일명에 없음. 오직 AI Hub 코드만 보존됨.** (이게 복구가 필요한 이유)
  - 정규식: `^(?:train|val)_([ABC][0-9]{5})_`
- **라벨 포맷**: `{yolo_index} {cx} {cy} {w} {h}` — **파일당 정확히 1줄(객체 1개)**. (train/val 표본 전수 1줄 확인)
- 또 다른 변형: `data/food_images/aihub_yolo_50_balanced_500\` (동일 50클래스 체계, 다운샘플본) — **함께 갱신해야 일관성 유지.**

### 2.2 매핑 정의 파일
- `data/food_images/manifests/roboflow_aihub_class_map_50.csv`
  - 컬럼: `roboflow_class, aihub_class_ids(파이프 | 구분), status, notes`
  - 예: `stew,A13045|B12027|B12032|B12086|B12104|B12138|B12167,exact_or_close,Jjigae and steamed kimchi style dishes`
  - **이 CSV에는 코드별 한글명이 없음** (그룹 단위 영어 설명만).
- `data/food_images/manifests/roboflow_autolabel_food_prompts_50_aihub_aligned.csv`
  - `class, korean_examples, visual_description` — 클래스 그룹 단위 예시 한글명(코드 단위 아님, 보조용).

### 2.3 변환 스크립트
- `data/food_images/scripts/convert_aihub_50_to_yolo.py`
  - 원본 AI Hub JSON을 읽어 50클래스 YOLO로 변환. **`class_name_ko`를 파싱하지만 출력에 저장하지 않고 버린다.**
  - 한글명 파싱 로직(`split_tokens_from_name`): 파일명 stem을 `_`로 분리, `class_name_ko = "_".join(parts[3:-2])`.
  - 라벨 JSON 경로: `<root>/{Training|Validation}/labeling_data/{TL|VL}/{TL1|VL1|...}/{A|B|C|D}/{2자리}/{CODE}/.../*.json`

### 2.4 원본 AI Hub raw 데이터 상태 ⚠️ 중요
- 경로: `D:\Deeplearning\lemon\data\raw\aihub\data\`
- **`Training`(train) 원본은 용량 이슈로 비워짐 → 복구 출처로 사용 불가.**
- **`Validation`(val) 원본은 살아있음.** `Validation\labeling_data\VL\VL1`, `VL2` 아래 A/B/C/D 카테고리, **class_id 폴더 660개 존재**.
- 한글명 복구는 **이 val 원본 JSON에서만** 가능.

---

## 3. 한글명 복구 방법 (검증 완료)

val JSON 하나당 `data.image_info.file_name`에서 한글명이 나온다. 코드당 JSON 1개만 읽으면 충분(같은 코드는 같은 음식명).

**실제 추출 검증 결과 (val 원본에서 직접 읽음):**

| CODE | raw file_name | 복구된 한글명 |
|---|---|---|
| A13004 | `A_13_A13004_나주곰탕_14_10.jpg` | 나주곰탕 |
| A13033 | `A_13_A13033_추어전골_01_10.jpg` | 추어전골 |
| A13045 | `A_13_A13045_황태부대찌개_30_09.jpg` | 황태부대찌개 |
| B11002 | `B_11_B11002_간장반후라이드반치킨(뼈)_04_05.jpg` | 간장반후라이드반치킨(뼈) |
| B12027 | `B_12_B12027_김치찜_02_05.jpg` | 김치찜 |
| B12032 | `B_12_B12032_꽁치김치찌개_12_09.jpg` | 꽁치김치찌개 |
| B12138 | `B_12_B12138_차돌된장찌개_19_07.jpg` | 차돌된장찌개 |
| B12167 | `B_12_B12167_해물순두부찌개_08_09.jpg` | 해물순두부찌개 |
| C03150 | `C_03_C03150_김치낙지죽_13_09.jpg` | 김치낙지죽 |

→ 방법: `parts = Path(file_name).stem.split("_")`; `korean = "_".join(parts[3:-2])`.

---

## 4. 복구 가능성 분석 (전체 데이터로 계산 완료)

- train 고유 코드: **430개**
- raw val class_id 폴더: **660개** (50클래스에 안 쓰인 음식 포함)
- 430개 중 raw val에 존재(=복구 가능): **402개**
- raw val에도 없음(=복구 불가): **28개**

### 4.1 통합 클래스별 복구 커버리지 (원본 코드 2개 이상인 클래스)

| 통합 클래스 | 복구가능/전체 | val 누락 코드 |
|---|---|---|
| barbecue-ribs | 6/7 | B12061 |
| black-bean-noodles | 3/3 | – |
| braised-chicken | 3/3 | – |
| braised-pork-hock | 1/3 | B11017, B11041 |
| bread | 40/45 | C02006, C02007, C02106, C02125, C02137 |
| bulgogi | 3/3 | – |
| cake | 8/8 | – |
| chicken-galbi | 1/2 | B12003 |
| cold-noodles | 3/4 | A14107 |
| curry | 9/9 | – |
| dim-sum | 2/2 | – |
| dumplings | 8/9 | B12008 |
| fish-cake | 2/2 | – |
| fried-chicken | 40/42 | B11027, B11069 |
| fried-food-platter | 3/3 | – |
| fried-rice | 2/2 | – |
| grilled-beef | 2/3 | B12160 |
| grilled-fish | 7/7 | – |
| hamburger | 5/5 | – |
| hot-pot | 6/8 | B12005, B12091 |
| korean-blood-sausage | 3/3 | – |
| mixed-rice-bowl | 4/5 | B12126 |
| noodle-soup | 18/20 | A14094, B12161 |
| pasta | 18/18 | – |
| pizza | 29/29 | – |
| pork-cutlet | 8/8 | – |
| ramen | 9/9 | – |
| raw-fish | 6/6 | – |
| rice-bowl | 15/17 | B11012, B11050 |
| rice-porridge | 8/8 | – |
| rice-soup | 3/3 | – |
| salad | 12/12 | – |
| sandwich | 25/26 | B11112 |
| savory-pancake | 2/2 | – |
| seafood-stew | 10/10 | – |
| seaweed-rice-roll | 10/10 | – |
| shrimp-dish | 5/6 | A13010 |
| soup | 22/22 | – |
| spicy-mixed-noodles | 2/2 | – |
| spicy-rice-cakes | 10/11 | B11009 |
| spicy-seafood-noodles | 6/7 | B12110 |
| **stew (찌개)** | **5/7** | **B12086, B12104** |
| sushi | 8/9 | B12140 |
| udon | 4/4 | – |

(코드 1개짜리 클래스 — takoyaki, grilled-pork-belly, stir-fried-pork, sweet-and-sour-pork, mala-hot-pot, squid-dish — 는 애초에 통합이 아니므로 분리 대상 아님.)

### 4.2 복구 불가 28개 코드 (val 원본에 없음)

| 통합 클래스 | 누락 코드 |
|---|---|
| barbecue-ribs | B12061 |
| braised-pork-hock | B11017, B11041 |
| bread | C02006, C02007, C02106, C02125, C02137 |
| chicken-galbi | B12003 |
| cold-noodles | A14107 |
| dumplings | B12008 |
| fried-chicken | B11027, B11069 |
| grilled-beef | B12160 |
| hot-pot | B12005, B12091 |
| mixed-rice-bowl | B12126 |
| noodle-soup | A14094, B12161 |
| rice-bowl | B11012, B11050 |
| sandwich | B11112 |
| shrimp-dish | A13010 |
| spicy-rice-cakes | B11009 |
| spicy-seafood-noodles | B12110 |
| **stew** | **B12086, B12104** |
| sushi | B12140 |

### 4.3 찌개(stew) 7개 코드 상세 (1차 목표)

| CODE | 한글명 | val 복구 |
|---|---|---|
| A13045 | 황태부대찌개 | ✅ |
| B12027 | 김치찜 | ✅ |
| B12032 | 꽁치김치찌개 | ✅ |
| B12138 | 차돌된장찌개 | ✅ |
| B12167 | 해물순두부찌개 | ✅ |
| B12086 | (미상 — val 없음) | ❌ |
| B12104 | (미상 — val 없음) | ❌ |

---

## 5. 28개 누락 코드 대응 방안 (택1, 사용자 결정 필요)

1. **AI Hub 공식 카테고리 코드표 확보** — AI Hub "음식 이미지" 데이터셋 문서/메타에 전체 코드→한글명 표가 있을 가능성이 높음. 가장 정확. (다음 Claude가 raw 데이터 메타파일/문서 또는 AI Hub 사이트에서 확인.)
2. **수동 입력** — 28개뿐이므로 사용자가 직접 한글명 제공.
3. **해당 코드 이미지를 통합 클래스에 그대로 둠** — 분리하지 않고 기존 umbrella 클래스 유지(예: B12086·B12104는 `stew`로 남김). 단 분리 일관성 깨짐.
4. **격리(quarantine)** — 해당 train 이미지를 별도 폴더로 이동(삭제 금지 규칙 준수)하고 분리 대상에서 제외.

> ⚠️ 추가 고려: 이 28개 코드는 **val 데이터가 전혀 없다.** 분리해서 새 클래스로 만들면 그 클래스는 **검증셋(val) 샘플이 0** → 평가 지표를 낼 수 없다. (train-only 클래스가 됨)

---

## 6. 결정해야 할 설계 사항 (작업 전 사용자 확인)

1. **분리 granularity**
   - (A) **찌개(stew)만** 분리 — 최소 범위, 안전.
   - (B) **broad_semantic + 통합도 큰 클래스만** 분리 (예: soup, fried-chicken, bread, pizza, sandwich, noodle-soup 등).
   - (C) **전체 코드 완전 분리** (≈430 클래스) — 표본 수십 개짜리 희소 클래스 대량 발생, 모델링 성격이 크게 바뀜. 비권장(또는 단계적).
2. **출력 방식**: in-place 수정 ❌ 비권장 → **새 데이터셋 변형 디렉터리 생성** 권장 (예: `aihub_yolo_split` 또는 `aihub_yolo_<N>`). CLAUDE.md "삭제 금지·이동" 규칙 준수.
3. **28개 누락 코드 처리**: §5 중 택1.
4. **balanced_500 변형**도 동일 처리할지.

---

## 7. 작업 절차 (다음 Claude 실행 가이드)

> 전제: §6 결정 완료 후 진행. 모든 산출물은 **새 디렉터리**에 생성하고, 원본 `aihub_yolo_50`은 건드리지 않는다. 커밋은 사용자 승인 후.

**Step 1. 코드→한글명 사전 구축 (val 원본 스캔, 1회)**
- raw val을 walk하며 코드별 JSON 1개에서 `file_name` 파싱 → `code, korean_name, roboflow_class, in_val` CSV 생성.
- 출력 예: `data/food_images/manifests/aihub_code_korean_names.csv`
- 402개 채워지고, 28개는 `in_val=false`로 표시. (skeleton 스크립트 §9.2)

**Step 2. 28개 누락 코드 한글명 보완** — §5 결정에 따라 채움.

**Step 3. 새 클래스 체계 확정**
- granularity 결정에 따라 (분리 대상 코드)→(새 클래스명) 결정.
- 새 클래스명 정규화: 한글명 그대로 쓸지, 영문 슬러그로 변환할지 결정(YOLO names는 한글도 가능).
- **새 인덱스 맵** 작성: `code → new_yolo_index` (분리 안 하는 클래스는 기존 그룹 유지).

**Step 4. 라벨 리매핑**
- 새 디렉터리에 train/val 이미지·라벨 복사(또는 라벨만 재생성).
- 각 라벨 `.txt`: 파일명에서 CODE 추출 → `code → new_yolo_index` 로 **첫 토큰만 치환** (파일당 1줄이므로 안전). bbox 좌표는 그대로.
- ⚠️ **old yolo_index가 아니라 CODE 기준으로 리매핑**할 것(통합 안 된 클래스도 안전하게 처리됨).

**Step 5. 메타데이터 재생성**
- `data.yaml` (`nc`, `names` 갱신), `yolo_class_index_*.json`, `_audit/class_counts.csv` 재생성.

**Step 6. balanced_500 변형** — 동일 `code→new_index` 맵으로 재라벨(결정 시).

**Step 7. 검증**
- 새 클래스별 train/val 개수표 출력, val=0 클래스 경고.
- 라벨 인덱스 범위가 `[0, nc)` 인지 전수 검사.
- 무작위 N장 시각화로 bbox·클래스 육안 확인.

**Step 8. 다운스트림 고지**
- 클래스 수 변경 → 기존 학습 산출물(exp03~05)·balanced_500 모델 **무효, 재학습 필요**.

---

## 8. 리스크 / 주의

- **삭제 금지**: 무엇이든 지우지 말고 별도 폴더로 이동(루트 CLAUDE.md 규칙).
- **커밋은 항상 사전 확인**, 커밋 메시지는 한국어(Conventional Commits 본문).
- **val=0 새 클래스**(28개 코드 분리 시): 평가 불가 → 모델링 영향 사전 합의.
- **희소 클래스**: 완전 분리(C안) 시 표본 극소 클래스 다수 → 학습 불안정.
- **balanced_500 정합성**: 두 데이터셋 클래스 체계가 어긋나지 않도록 동일 맵 사용.
- 라벨 멀티객체 가정: 현재 전부 1줄이지만, 재생성 시에도 1객체 유지.

---

## 9. 부록 — 재현용 명령 / 스크립트

### 9.1 복구 가능성 재계산 (read-only)
```bash
cd "C:/Lemon-Aid/Lemon-sin/data/food_images/aihub_yolo_50"
PYTHONIOENCODING=utf-8 python -u - <<'PY'
import json, re, os
from pathlib import Path
from collections import defaultdict
a2y = json.loads(Path("yolo_class_index_50.json").read_text(encoding="utf-8"))["aihub_to_yolo"]
cr = re.compile(r'^(?:train|val)_([ABC][0-9]{5})_')
train_codes = {cr.match(f.name).group(1) for f in os.scandir("train/images") if cr.match(f.name)}
rawval=set(); cc=re.compile(r'^[ABC][0-9]{5}$')
for root,dirs,_ in os.walk(r"D:\Deeplearning\lemon\data\raw\aihub\data\Validation\labeling_data"):
    rawval |= {d for d in dirs if cc.match(d)}
unrec = sorted(train_codes - rawval)
print("train", len(train_codes), "rawval", len(rawval), "복구불가", len(unrec))
print(unrec)
PY
```

### 9.2 코드→한글명 사전 구축 (Step 1 skeleton)
```python
import json, os, re, csv
from pathlib import Path
RAW = r"D:\Deeplearning\lemon\data\raw\aihub\data\Validation\labeling_data"
IDX = json.loads(Path(r"C:\Lemon-Aid\Lemon-sin\data\food_images\aihub_yolo_50\yolo_class_index_50.json").read_text(encoding="utf-8"))["aihub_to_yolo"]
cc = re.compile(r'^[ABC][0-9]{5}$')
name = {}
for root, dirs, files in os.walk(RAW):
    hit = set(root.replace("/", "\\").split("\\")) & set(IDX)
    if not hit:
        continue
    code = next(iter(hit))
    if code in name:
        continue
    js = [f for f in files if f.lower().endswith(".json")]
    if not js:
        continue
    fn = json.loads(Path(root, js[0]).read_text(encoding="utf-8"))["data"]["image_info"]["file_name"]
    p = Path(fn).stem.split("_")
    name[code] = "_".join(p[3:-2]) if len(p) >= 6 else ""
out = Path(r"C:\Lemon-Aid\Lemon-sin\data\food_images\manifests\aihub_code_korean_names.csv")
with out.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["code", "korean_name", "roboflow_class", "in_val"])
    for code, info in sorted(IDX.items()):
        w.writerow([code, name.get(code, ""), info["roboflow_class"], "true" if code in name else "false"])
print("wrote", out, "코드", len(IDX), "복구", len(name))
```

### 9.3 주요 경로 요약
| 항목 | 경로 |
|---|---|
| 작업 대상 데이터셋 | `C:\Lemon-Aid\Lemon-sin\data\food_images\aihub_yolo_50\` |
| balanced 변형 | `C:\Lemon-Aid\Lemon-sin\data\food_images\aihub_yolo_50_balanced_500\` |
| 클래스 매핑 CSV | `...\data\food_images\manifests\roboflow_aihub_class_map_50.csv` |
| 클래스 인덱스 JSON | `...\aihub_yolo_50\yolo_class_index_50.json` |
| 변환 스크립트 | `...\data\food_images\scripts\convert_aihub_50_to_yolo.py` |
| val 원본(복구 출처) | `D:\Deeplearning\lemon\data\raw\aihub\data\Validation\labeling_data\` |
| train 원본 | ⚠️ 비어있음(용량 이슈) — 사용 불가 |

---

**다음 세션 시작 시 권장 첫 행동**: 사용자에게 §6의 4가지 결정사항을 확인 → 결정되면 §7 절차대로 새 디렉터리에 진행.
