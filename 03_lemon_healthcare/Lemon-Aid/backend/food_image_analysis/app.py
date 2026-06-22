"""YOLOv8n 음식 탐지 데모 앱.

업로드한 이미지에서 50개 음식 클래스를 탐지하고 결과를 시각화한다.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from PIL import Image
from ultralytics import YOLO

MODEL_PATH = Path(
    r"C:\Lemon-sin\runs\food_yolo"
    r"\exp01_yolov8n_baseline_pc1_b48_w8_cache_disk_det_true"
    r"\weights\best.pt"
)

st.set_page_config(page_title="음식 탐지 데모", page_icon="🍱", layout="wide")
st.title("🍱 음식 탐지 데모 — YOLOv8n PC1 Baseline")
st.caption(f"모델: {MODEL_PATH.parent.parent.name} | mAP50=0.8465 @ epoch 45")


@st.cache_resource
def load_model() -> YOLO:
    return YOLO(str(MODEL_PATH))


model = load_model()

with st.sidebar:
    st.header("설정")
    conf = st.slider("Confidence 임계값", 0.1, 0.9, 0.25, 0.05)
    iou = st.slider("IoU 임계값", 0.1, 0.9, 0.7, 0.05)
    max_det = st.number_input("최대 탐지 수", 1, 100, 20)

uploaded = st.file_uploader("이미지 업로드 (jpg, png, webp)", type=["jpg", "jpeg", "png", "webp"])

if uploaded:
    image = Image.open(uploaded).convert("RGB")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("원본 이미지")
        st.image(image, use_container_width=True)

    with st.spinner("탐지 중..."):
        results = model.predict(
            source=image,
            conf=conf,
            iou=iou,
            max_det=max_det,
            verbose=False,
        )
        result = results[0]
        annotated = Image.fromarray(result.plot()[:, :, ::-1])

    with col2:
        st.subheader("탐지 결과")
        st.image(annotated, use_container_width=True)

    boxes = result.boxes
    if boxes and len(boxes):
        st.subheader(f"탐지된 객체 ({len(boxes)}개)")
        rows = []
        for box in boxes:
            cls_id = int(box.cls[0])
            rows.append(
                {
                    "클래스": model.names[cls_id],
                    "Confidence": f"{float(box.conf[0]):.3f}",
                    "x1": int(box.xyxy[0][0]),
                    "y1": int(box.xyxy[0][1]),
                    "x2": int(box.xyxy[0][2]),
                    "y2": int(box.xyxy[0][3]),
                }
            )
        rows.sort(key=lambda r: r["Confidence"], reverse=True)
        st.dataframe(rows, use_container_width=True)
    else:
        st.warning(f"Confidence {conf} 이상 탐지 결과 없음. 임계값을 낮춰보세요.")
else:
    st.info("왼쪽에서 이미지를 업로드하면 탐지 결과가 표시됩니다.")
