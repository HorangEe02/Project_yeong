#!/usr/bin/env bash
# 화자 구분(diarization) 오픈 모델 다운로드 — HuggingFace 토큰 불필요.
# sherpa-onnx 재배포 모델(k2-fsa GitHub releases)을 models/diarization/ 에 받는다.
set -e
cd "$(dirname "$0")/.."
DEST="models/diarization"
mkdir -p "$DEST"; cd "$DEST"

echo "[1/3] sherpa-onnx 설치 (없으면)"
../../.venv/bin/pip install -q sherpa-onnx 2>/dev/null || pip install -q sherpa-onnx

echo "[2/3] 세그멘테이션 모델"
if [ ! -f "sherpa-onnx-pyannote-segmentation-3-0/model.onnx" ]; then
  curl -sL -o seg.tar.bz2 "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
  tar xjf seg.tar.bz2 && rm -f seg.tar.bz2
fi

echo "[3/3] 화자 임베딩 모델"
if [ ! -f "embedding.onnx" ]; then
  curl -sL -o embedding.onnx "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
fi

echo "완료. DIARIZER=auto 이면 자동 사용됩니다."
ls -la sherpa-onnx-pyannote-segmentation-3-0/model.onnx embedding.onnx | awk '{print "  "$5, $9}'
