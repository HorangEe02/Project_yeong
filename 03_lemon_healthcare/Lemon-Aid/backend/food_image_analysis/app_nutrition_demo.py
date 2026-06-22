"""음식 분류 + 영양소 정보 데모 (Streamlit).

업로드(또는 test_data 선택) 이미지에서 YOLO26s(taxo59, exp12) 모델로 음식을 탐지하고:
  - 탐지 박스 + 음식종류를 이미지에 오버레이
  - 모델 Top-5 후보(신뢰도순)
  - 탐지 음식의 영양소 정보(100g 기준) + 만성질환 관점 참고 정보
  - 음식이 안 잡히면 "음식이 없습니다 다시 찍어주세요"

Run:
    streamlit run backend/food_image_analysis/app_nutrition_demo.py

Reference:
    모델: runs/food_yolo/exp12_yolo26s_taxo59tako_*  (best.pt)
    영양소: data/food_images/manifests/class_nutrition_taxo59.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
import torch
from PIL import Image
from ultralytics import YOLO

# --- 경로 상수 ---
MODEL_PATH = Path(
    r"C:\Lemon-sin\runs\food_yolo"
    r"\exp12_yolo26s_taxo59tako_pc1_s42_b16_w8_cache_disk_det_true\weights\best.pt"
)
NUTRITION_CSV = Path(r"C:\Lemon-sin\data\food_images\manifests\class_nutrition_taxo59.csv")
TEST_DIR = Path(r"C:\Lemon-sin\data\food_images\raw\test_data")

# --- 영문 클래스 -> 한글 표시명 (59클래스) ---
KR_NAME: dict[str, str] = {
    "barbecue-ribs": "갈비",
    "black-bean-noodles": "짜장면",
    "braised-chicken": "찜닭",
    "braised-pork-hock": "족발",
    "bread": "빵",
    "bulgogi": "불고기",
    "cake": "케이크",
    "cold-noodles": "냉면",
    "curry": "카레",
    "dim-sum": "딤섬(찐만두)",
    "dumplings": "만두",
    "fish-cake": "어묵",
    "fried-chicken": "후라이드치킨",
    "fried-food-platter": "튀김(모둠)",
    "fried-rice": "볶음밥",
    "grilled-beef": "소고기구이",
    "grilled-fish": "생선구이",
    "grilled-pork-belly": "삼겹살",
    "hamburger": "햄버거",
    "hot-pot": "전골",
    "korean-blood-sausage": "순대",
    "mixed-rice-bowl": "비빔밥",
    "pasta": "파스타",
    "pizza": "피자",
    "raw-fish": "회",
    "rice-bowl": "덮밥",
    "rice-porridge": "죽",
    "rice-soup": "국밥",
    "salad": "샐러드",
    "sandwich": "샌드위치",
    "savory-pancake": "전/부침개",
    "seaweed-rice-roll": "김밥",
    "shrimp-dish": "새우요리",
    "spicy-mixed-noodles": "비빔국수",
    "squid-dish": "오징어요리",
    "sushi": "초밥",
    "takoyaki": "타코야키",
    "udon": "우동",
    "korean-clear-soup": "맑은국",
    "korean-red-soup": "빨간국",
    "western-cream-soup": "양식수프",
    "japanese-ramen": "일본라멘",
    "korean-ramyeon-red": "라면",
    "cold-ramen": "냉라멘",
    "tteokbokki-red": "떡볶이",
    "tteokbokki-cream-rose": "로제떡볶이",
    "tteokbokki-jajang": "짜장떡볶이",
    "pork-cutlet-dry": "돈가스",
    "pork-cutlet-sauced": "소스돈가스",
    "seafood-spicy-tang": "해물매운탕",
    "seafood-clear-tang": "해물맑은탕",
    "seafood-jjim": "해물찜",
    "kalguksu": "칼국수",
    "rice-noodle-soup": "쌀국수",
    "noodle-plain": "국수",
    "jjigae-red": "빨간찌개",
    "doenjang-jjigae": "된장찌개",
    "jjamppong": "짬뽕",
    "nagasaki-champon": "나가사끼짬뽕",
}


def kr(name: str) -> str:
    """영문 클래스명을 한글 표시명으로 변환한다 (없으면 원문)."""
    return KR_NAME.get(name, name)


def _iou(a, b) -> float:
    """두 xyxy 박스의 IoU를 계산한다."""
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def agnostic_nms_keep(res, iou_thresh: float = 0.5) -> list[int]:
    """클래스 무시(agnostic) NMS — 겹치는 박스는 최고 신뢰도 1개만 남긴다.

    yolo26은 end-to-end라 전통 NMS를 돌리지 않아, 한 음식에 서로 다른 클래스
    박스가 중첩(IoU≈1.0)되는 경우가 있다. 후처리로 IoU>thresh 박스를 병합한다.

    Args:
        res: ultralytics Results (한 장).
        iou_thresh: 이 값을 넘게 겹치면 같은 객체로 보고 억제.

    Returns:
        남길 박스 인덱스 리스트 (정렬됨).
    """
    xy = res.boxes.xyxy.cpu().numpy()
    cf = res.boxes.conf.cpu().numpy()
    order = cf.argsort()[::-1]
    keep: list[int] = []
    suppressed: set[int] = set()
    for i in order:
        if int(i) in suppressed:
            continue
        keep.append(int(i))
        for j in order:
            if int(j) != int(i) and int(j) not in suppressed and _iou(xy[i], xy[j]) > iou_thresh:
                suppressed.add(int(j))
    return sorted(keep)


@st.cache_resource
def load_model() -> YOLO:
    """YOLO 모델을 1회 로드한다."""
    return YOLO(str(MODEL_PATH))


@st.cache_data
def load_nutrition() -> dict[str, dict[str, float]]:
    """클래스별 영양소(100g 기준)를 dict로 로드한다."""
    table: dict[str, dict[str, float]] = {}
    with NUTRITION_CSV.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            table[row["class"]] = {
                k: (float(v) if v not in ("", None) else float("nan"))
                for k, v in row.items()
                if k not in ("class",)
            }
    return table


def top5_candidates(model: YOLO, img_bgr: np.ndarray) -> list[tuple[str, float]]:
    """저신뢰 임계값으로 추론해 클래스별 최고 신뢰도 Top-5 후보를 추출한다.

    detection 파이프라인(predict)을 그대로 사용해 전처리 불일치가 없도록 한다.
    yolo26은 end-to-end(NMS-free)라 conf=0.01로 여러 후보 박스를 얻어 클래스별로 정리.

    Args:
        model: 로드된 YOLO 모델.
        img_bgr: OpenCV BGR 이미지.

    Returns:
        (영문클래스, 신뢰도) Top-5 리스트 (중복 클래스 제거, 신뢰도 내림차순).
    """
    res = model.predict(img_bgr, conf=0.01, iou=0.5, verbose=False)[0]
    pairs = sorted(
        zip((int(c) for c in res.boxes.cls.tolist()), res.boxes.conf.tolist()),
        key=lambda x: -x[1],
    )
    result: list[tuple[str, float]] = []
    seen: set[int] = set()
    for c, cf in pairs:
        if c not in seen:
            seen.add(c)
            result.append((model.names[c], float(cf)))
        if len(result) >= 5:
            break
    return result


def nutrition_notes(n: dict[str, float]) -> list[str]:
    """영양소 기반 참고 정보(만성질환 관점, 정보 제공용)를 생성한다."""
    notes: list[str] = []
    na = n.get("sodium_mg", float("nan"))
    sug = n.get("sugar_g", float("nan"))
    fat = n.get("fat_g", float("nan"))
    kcal = n.get("kcal_100g", float("nan"))
    if na == na and na >= 500:
        notes.append(
            f"🧂 나트륨이 높은 편이에요 ({na:.0f}mg/100g) — 혈압 관리 중이라면 참고하세요."
        )
    if sug == sug and sug >= 10:
        notes.append(f"🍬 당류가 높은 편이에요 ({sug:.0f}g/100g) — 혈당 관리에 참고하세요.")
    if fat == fat and fat >= 15:
        notes.append(f"🥓 지방이 높은 편이에요 ({fat:.0f}g/100g).")
    if kcal == kcal and kcal <= 100:
        notes.append(f"🥗 열량이 낮은 편이에요 ({kcal:.0f}kcal/100g) — 가벼운 한 끼로 좋아요.")
    if not notes:
        notes.append("ℹ️ 특이 주의 영양소는 없어요. 균형 잡힌 편입니다.")
    return notes


def macro_ratio(n: dict[str, float]) -> tuple[float, float, float]:
    """탄·단·지 칼로리 비율(%)을 계산한다 (탄4·단4·지9 kcal/g)."""
    carb = (n.get("carb_g", 0) or 0) * 4
    pro = (n.get("protein_g", 0) or 0) * 4
    fat = (n.get("fat_g", 0) or 0) * 9
    tot = carb + pro + fat
    if tot <= 0:
        return 0.0, 0.0, 0.0
    return carb / tot * 100, pro / tot * 100, fat / tot * 100


# ============================ UI ============================
st.set_page_config(page_title="음식 분류 + 영양소 데모", page_icon="🍱", layout="wide")
st.title("🍱 음식 분류 + 영양소 정보 데모")
st.caption(f"모델: YOLO26s · taxo59(59클래스) · exp12  |  영양소: AIHub 100g 기준 클래스 평균")

model = load_model()
nutrition = load_nutrition()

with st.sidebar:
    st.header("⚙️ 설정")
    # 로드된 체크포인트 확인용 (캐시된 모델이 최종본인지 검증)
    import datetime as _dt

    _mt = _dt.datetime.fromtimestamp(MODEL_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    st.caption(f"📦 모델: `{MODEL_PATH.parent.parent.name}`\n\nbest.pt 수정: {_mt}")
    conf_th = st.slider("탐지 신뢰도 임계값", 0.02, 0.9, 0.10, 0.01)
    st.caption(
        "exp12 기준 0.10 권장 — test_data 음식 15/16·not_food 3/3. (0.08은 not_food 1건(salad) 오탐, 음식 1건은 maxconf 0.03이라 임계 무관 미검출)"
    )
    nms_iou = st.slider("중복 박스 병합 IoU", 0.3, 0.95, 0.5, 0.05)
    st.caption("한 음식에 박스가 여러 개 겹치면 최고 신뢰도 1개로 합칩니다 (낮을수록 적극 병합)")
    st.divider()
    st.subheader("📂 test_data에서 선택")
    test_imgs = sorted([p.name for p in TEST_DIR.glob("*.jpg")]) if TEST_DIR.exists() else []
    picked = st.selectbox("샘플 이미지", ["(업로드 사용)"] + test_imgs)

uploaded = st.file_uploader("이미지 업로드 (jpg/png/webp)", type=["jpg", "jpeg", "png", "webp"])

# 입력 이미지 결정
img_bgr = None
src_label = None
if uploaded is not None:
    pil = Image.open(uploaded).convert("RGB")
    img_bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    src_label = uploaded.name
elif picked and picked != "(업로드 사용)":
    img_bgr = cv2.imread(str(TEST_DIR / picked))
    src_label = picked

if img_bgr is None:
    st.info("👆 이미지를 업로드하거나 사이드바에서 test_data 샘플을 선택하세요.")
    st.stop()

# 추론 + 클래스 무시 NMS(중복 박스 병합)
res = model.predict(img_bgr, conf=conf_th, verbose=False)[0]
if len(res.boxes) > 1:
    keep = agnostic_nms_keep(res, nms_iou)
    res.boxes = res.boxes[torch.tensor(keep, device=res.boxes.cls.device)]
n_boxes = len(res.boxes)

col_img, col_info = st.columns([3, 2])

with col_img:
    if n_boxes == 0:
        # 음식 미탐지 -> 안내 (not_food 등)
        st.image(
            cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB), caption=src_label, use_container_width=True
        )
        st.error("## 🚫 음식이 없습니다. 다시 찍어주세요.")
        st.caption("음식 객체가 탐지되지 않았어요. 음식이 화면에 잘 보이게 다시 촬영해 주세요.")
        st.stop()
    annotated = res.plot()  # BGR, 박스+라벨
    st.image(
        cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB),
        caption=f"{src_label} — {n_boxes}개 탐지",
        use_container_width=True,
    )

with col_info:
    # 대표(최고 신뢰도) 탐지
    confs = res.boxes.conf.tolist()
    clss = [int(c) for c in res.boxes.cls.tolist()]
    best_i = int(np.argmax(confs))
    best_cls = model.names[clss[best_i]]
    st.subheader(f"🍽️ {kr(best_cls)}  ·  {confs[best_i] * 100:.1f}%")
    st.caption(f"`{best_cls}`  |  이미지에서 {n_boxes}개 음식 탐지")

    # 여러 개 탐지 시 목록
    if n_boxes > 1:
        st.markdown("**탐지된 음식**")
        for c, cf in sorted(zip(clss, confs), key=lambda x: -x[1]):
            st.write(f"- {kr(model.names[c])} ({cf * 100:.1f}%)")

st.divider()

# Top-5 후보
st.subheader("🔢 모델 Top-5 후보 (신뢰도순)")
top5 = top5_candidates(model, img_bgr)
cols = st.columns(5)
for col, (name, cf) in zip(cols, top5):
    col.metric(kr(name), f"{cf * 100:.1f}%")

st.divider()

# 영양소 볼 음식 선택 — 모델 예측이 틀렸으면 Top-5에서 정답을 고른다
top5_classes = [name for name, _ in top5] or [best_cls]
if best_cls not in top5_classes:
    top5_classes = [best_cls] + top5_classes
default_idx = top5_classes.index(best_cls)
selected_cls = st.selectbox(
    "🍽️ 영양소를 볼 음식 (모델 예측이 틀렸다면 Top-5에서 정답을 고르세요)",
    top5_classes,
    index=default_idx,
    format_func=lambda c: f"{kr(c)}  ({c})",
)
if selected_cls != best_cls:
    st.info(
        f"✏️ 사용자가 **{kr(selected_cls)}**(으)로 선택 — 모델 예측({kr(best_cls)})과 다릅니다."
    )

# 영양소 정보 (선택 음식 기준)
st.subheader(f"🥗 영양소 정보 — {kr(selected_cls)}")
n = nutrition.get(selected_cls)
if n is None:
    st.warning("이 클래스의 영양소 정보를 찾을 수 없습니다.")
else:
    serving = n.get("serving_g", 200) or 200

    # 섭취량 기준 선택 (1인분/2인분/100g/직접입력)
    mode = st.radio(
        "🍚 섭취량 기준",
        ["1인분", "2인분", "100g", "직접 입력"],
        horizontal=True,
        index=0,
    )
    if mode == "1인분":
        grams = serving
    elif mode == "2인분":
        grams = serving * 2
    elif mode == "100g":
        grams = 100.0
    else:
        grams = st.number_input(
            "먹은 양 (g)", min_value=1, max_value=3000, value=int(serving), step=10
        )
    scale = grams / 100.0
    st.caption(
        f"기준: **{grams:.0f}g** 섭취  ·  1인분 ≈ {serving:.0f}g  ·  아래 값은 섭취량 기준 환산"
    )

    def sc(key: str) -> float:
        """100g 기준 값을 선택 섭취량(grams)으로 환산한다."""
        return n[key] * scale

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("열량", f"{sc('kcal_100g'):.0f} kcal")
    c2.metric("탄수화물", f"{sc('carb_g'):.1f} g")
    c3.metric("단백질", f"{sc('protein_g'):.1f} g")
    c4.metric("지방", f"{sc('fat_g'):.1f} g")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("당류", f"{sc('sugar_g'):.1f} g")
    c6.metric("나트륨", f"{sc('sodium_mg'):.0f} mg")
    c7.metric("포화지방", f"{sc('sat_fat_g'):.1f} g")
    c8.metric("콜레스테롤", f"{sc('chol_mg'):.0f} mg")

    # 일일 권장 대비 (성인 기준 2000kcal · 나트륨 2000mg · 당류 50g)
    st.caption(
        f"📊 이번 섭취 ≈ 일일 열량의 **{sc('kcal_100g') / 2000 * 100:.0f}%**, "
        f"나트륨 **{sc('sodium_mg') / 2000 * 100:.0f}%**, "
        f"당류 **{sc('sugar_g') / 50 * 100:.0f}%** (성인 2000kcal·나트륨 2000mg·당류 50g 기준)"
    )

    # 탄단지 비율
    carb_p, pro_p, fat_p = macro_ratio(n)
    st.markdown("**탄·단·지 칼로리 비율**")
    st.progress(int(carb_p), text=f"탄수화물 {carb_p:.0f}%")
    st.progress(int(pro_p), text=f"단백질 {pro_p:.0f}%")
    st.progress(int(fat_p), text=f"지방 {fat_p:.0f}%")

    # 만성질환 관점 참고
    st.markdown("**💡 참고 정보**")
    for note in nutrition_notes(n):
        st.write(note)
    st.caption(
        "※ 본 정보는 AIHub 데이터의 클래스 평균(데모용 추정치)이며, 진단·처방이 아닌 참고용입니다. "
        "건강 상태에 따른 식단은 전문가와 상담하세요."
    )
