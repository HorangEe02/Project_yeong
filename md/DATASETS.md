# 📊 MediWay 프로젝트 활용 가능 데이터셋 목록

> 본 문서는 MediWay(병원 내 환자 동선 가이드 플랫폼) 프로젝트 개발 시 활용 가능한 공개 데이터셋을 정리한 것입니다.
> 데이터셋은 **실내 측위**, **건물 평면도**, **3D 실내 스캔**, **보행자 관성항법(PDR)** 4개 카테고리로 분류하였습니다.

---

## 1. 실내 측위 (Indoor Positioning) 데이터셋

### 1.1 Kaggle — Indoor Location & Navigation Competition (Microsoft)

- **링크**: https://www.kaggle.com/c/indoor-location-navigation
- **제공자**: Microsoft Research (2021)
- **규모**: 수백 개 건물, 수만 개의 경로 데이터
- **내용**: 중국 도시의 쇼핑몰을 대상으로 수집된 대규모 실내 측위 벤치마크 데이터셋입니다. WiFi RSSI, 지자기장(magnetometer), iBeacon, IMU(가속도계/자이로스코프) 데이터와 실제 보행 경로의 위치 정보(waypoint)가 포함되어 있습니다.
- **데이터 포맷**: 경로별 `.txt` 파일 (타임스탬프, WiFi BSSID/RSSI, IMU 데이터, 비콘 데이터, 위치 좌표)
- **활용 방안**: WiFi 핑거프린팅 기반 실내 측위 알고리즘 개발, LSTM/GRU 모델을 활용한 위치 예측 모델 학습, 다층 건물 층 판별 모델 개발

### 1.2 Kaggle — UJIIndoorLoc

- **링크**: https://www.kaggle.com/datasets/giantuji/UjiIndoorLoc
- **제공자**: Universitat Jaume I (스페인)
- **규모**: 3개 건물, 4~5층, 933개 기준점, 21,049개 학습 샘플
- **내용**: 대학 캠퍼스 3개 건물에서 520개 WiFi AP의 RSSI 값을 수집한 실내 측위 표준 벤치마크 데이터셋입니다. 각 샘플에 건물 ID, 층 번호, 2D 좌표(위도/경도), 수집 시점 등이 라벨링되어 있습니다.
- **데이터 포맷**: CSV (520개 WAP RSSI 컬럼 + 위치/메타 정보)
- **활용 방안**: WiFi 기반 층 판별 및 구역 분류 모델의 기초 벤치마크로 사용, KNN/Random Forest/DNN 기반 위치 추정 알고리즘 비교 실험

### 1.3 Kaggle — BLE RSSI Dataset for Indoor Localization

- **링크**: https://www.kaggle.com/datasets/mehdimka/ble-rssi-dataset
- **원본 출처**: UCI Machine Learning Repository (https://archive.ics.uci.edu/ml/datasets/BLE+RSSI+Dataset+for+Indoor+localization+and+Navigation)
- **규모**: 13개 iBeacon, 105개 기준점
- **내용**: 실제 운영 중인 실내 환경에서 BLE iBeacon 13개로부터 수집된 RSSI 데이터셋입니다. 각 기준점에서 여러 비콘의 신호 강도가 기록되어 있으며, 실내 측위 및 네비게이션 목적으로 설계되었습니다.
- **데이터 포맷**: CSV (비콘별 RSSI 값 + 위치 라벨)
- **활용 방안**: BLE 비콘 기반 측위 알고리즘(삼변측량, 핑거프린팅) 개발 및 검증, MediWay의 BLE 비콘 측위 모듈 프로토타이핑에 직접 활용 가능

### 1.4 Kaggle — Indoor Localization using BLE and WiFi

- **링크**: https://www.kaggle.com/datasets/ashkangoharfar/indoor-localization-using-ble-and-wifi
- **내용**: WiFi와 BLE 두 가지 무선 기술의 RSSI 데이터를 동시에 포함하는 실내 측위 데이터셋입니다. WiFi와 BLE를 결합한 하이브리드 측위 방식의 연구에 적합합니다.
- **데이터 포맷**: CSV
- **활용 방안**: WiFi + BLE 하이브리드 측위 알고리즘 개발, 두 기술의 정확도 비교 분석

### 1.5 Kaggle — JUIndoorLoc: WiFi Fingerprint Indoor Localization

- **링크**: https://www.kaggle.com/datasets/priyaroycse/juindoorloc-wifi-fingerprint-indoor-localization
- **내용**: WiFi 신호 강도를 이용한 실내 위치 예측 데이터셋입니다. 사용자의 실내 위치를 WiFi RSS 값으로 추정하는 과제를 위해 설계되었습니다.
- **데이터 포맷**: CSV
- **활용 방안**: WiFi 핑거프린팅 모델의 추가 벤치마크, 다양한 건물 환경에서의 일반화 성능 테스트

### 1.6 Kaggle — WiFi RSS Fingerprint Localization Dataset

- **링크**: https://www.kaggle.com/datasets/tareqalhmiedat/wifi-rss-fingerprint-dataset
- **내용**: WiFi RSS(Received Signal Strength) 기반 핑거프린트 위치 추정 데이터셋입니다.
- **데이터 포맷**: CSV
- **활용 방안**: WiFi 기반 측위 모델 학습 및 교차 검증

### 1.7 Kaggle — Wi-Fi Indoor Localization Dataset (WILD-v2)

- **링크**: https://www.kaggle.com/competitions/wildv2
- **내용**: WiFi 기반 실내 측위 대회 데이터셋으로, 다양한 측위 알고리즘을 비교 평가할 수 있습니다.
- **데이터 포맷**: 대회 규격 (학습/테스트 분리)
- **활용 방안**: 측위 모델의 경쟁적 벤치마킹, 최신 알고리즘 성능 비교

---

## 2. 건물 평면도 (Floor Plan) 데이터셋

### 2.1 Kaggle — CubiCasa5K

- **링크**: https://www.kaggle.com/datasets/qmarva/cubicasa5k
- **GitHub**: https://github.com/CubiCasa/CubiCasa5k
- **논문**: CubiCasa5K: A Dataset and an Improved Multi-Task Model for Floorplan Image Analysis (SCIA 2019)
- **규모**: 5,000개 평면도 이미지, 80+ 객체 카테고리
- **내용**: 핀란드 부동산 마케팅 자료에서 수집된 대규모 평면도 이미지 데이터셋입니다. 각 평면도에 벽, 방, 문, 창문, 가구 등 80개 이상의 카테고리가 폴리곤 기반 SVG 형식으로 정밀하게 어노테이션되어 있습니다. 이미지 해상도는 430×485 ~ 6,316×14,304 픽셀까지 다양합니다.
- **데이터 포맷**: PNG 이미지 + SVG 어노테이션
- **활용 방안**: 평면도 이미지에서 방/벽/문/창문을 자동 인식하는 세그멘테이션 모델 학습, 평면도를 네비게이션 그래프로 자동 변환하는 파이프라인 개발, 병원 평면도 분석 AI 모델의 사전 학습(pre-training) 데이터로 활용

### 2.2 Kaggle — Floor Plan Dataset

- **링크**: https://www.kaggle.com/datasets/asutoshprad/floor-plan-dataset
- **내용**: 다양한 건축 평면도 이미지를 수집한 데이터셋입니다.
- **데이터 포맷**: 이미지 파일
- **활용 방안**: 평면도 인식 모델의 학습 데이터 보강

### 2.3 Kaggle — Floor Plan Images and Their Details

- **링크**: https://www.kaggle.com/datasets/adilmohammed/floor-plan-images-and-their-details
- **내용**: 평면도 이미지와 함께 상세 정보(방 크기, 용도 등)가 포함된 데이터셋입니다.
- **데이터 포맷**: 이미지 + 메타데이터
- **활용 방안**: 평면도에서 공간 정보를 추출하는 모델 학습, 방 유형 분류 모델 개발

### 2.4 Kaggle — 2D Floor Plan Dataset with Text Descriptions

- **링크**: https://www.kaggle.com/datasets/harshratna/2d-floor-plan-dataset-with-text-descriptions-new
- **내용**: 2D 평면도 이미지에 텍스트 설명이 쌍으로 제공되는 데이터셋입니다.
- **데이터 포맷**: 이미지 + 텍스트
- **활용 방안**: 텍스트-이미지 멀티모달 모델 학습, 자연어로 평면도를 설명/검색하는 기능 개발

### 2.5 GitHub/Kaggle — MSD (Modified Swiss Dwellings)

- **링크**: https://www.kaggle.com/datasets/ (Kaggle에서 "MSD Swiss Dwellings"로 검색)
- **GitHub**: https://github.com/caspervanengelenburg/msd
- **논문**: MSD: A Benchmark Dataset for Floor Plan Generation of Building Complexes (ECCV 2024)
- **규모**: 5,372개 평면도, 18,900+ 아파트
- **내용**: 스위스 건물의 상세 평면도를 포함하며, 이미지·벡터·그래프 세 가지 형태(multimodal)로 제공됩니다. 단독 주거뿐 아니라 다세대/복합 건물 평면도를 포함하여 기존 데이터셋보다 규모와 복잡도가 큽니다. 방 간 연결 관계(access graph)가 포함되어 네비게이션 그래프 연구에 적합합니다.
- **데이터 포맷**: 이미지 + GeoJSON/SVG 벡터 + NetworkX 그래프
- **활용 방안**: 건물 내 통로 연결 그래프 자동 생성 알고리즘 개발, 병원과 유사한 대형 복합 건물 구조에서의 최단 경로 탐색 알고리즘 테스트

---

## 3. 3D 실내 스캔 (3D Indoor Scene) 데이터셋

### 3.1 GitHub — ARKitScenes (Apple 공식)

- **링크**: https://github.com/apple/ARKitScenes
- **논문**: ARKitScenes: A Diverse Real-World Dataset for 3D Indoor Scene Understanding (2021)
- **규모**: 1,661개 고유 장면, 5,047개 캡처
- **내용**: Apple LiDAR 스캐너(iPad Pro/iPhone Pro)로 캡처된 최초의 대규모 RGB-D 실내 씬 데이터셋입니다. 각 장면에 카메라 포즈, 표면 재구성(surface reconstruction) 데이터가 포함되며, 고해상도(HR) 및 저해상도(LR) 깊이맵이 제공됩니다. 방을 정의하는 주요 객체(테이블, 의자, 소파 등)의 3D 바운딩 박스 어노테이션이 포함됩니다.
- **데이터 포맷**: RGB 이미지 + Depth 맵 + 카메라 포즈 + 3D 메시 + 바운딩 박스 어노테이션
- **활용 방안**: iPhone LiDAR로 스캔한 3D 맵의 처리/분석 파이프라인 개발, RoomPlan API 결과물과의 비교 검증, 실내 3D 씬에서 POI(관심 지점) 자동 인식 모델 학습, MediWay의 3D 네비게이션(Level 4) 기반 기술 연구

---

## 4. 보행자 관성항법 (PDR) 및 IMU 데이터셋

### 4.1 GitHub — RSSI-Dataset-for-Indoor-Localization-Fingerprinting

- **링크**: https://github.com/pspachos/RSSI-Dataset-for-Indoor-Localization-Fingerprinting
- **논문**: Memoryless Techniques and Wireless Technologies for Indoor Localization with the Internet of Things (IEEE IoT Journal)
- **내용**: Zigbee, BLE, WiFi 세 가지 무선 기술의 RSSI 데이터를 포함하는 실내 측위 데이터셋입니다. 3가지 실험 시나리오(회의실 2곳 + 컴퓨터 실습실 1곳)에서 수집되었으며, 각 시나리오별로 핑거프린트 데이터베이스와 테스트 포인트가 분리되어 있습니다.
- **데이터 포맷**: CSV (시나리오별 / 기술별 폴더 구조)
- **활용 방안**: BLE/WiFi 측위 알고리즘 성능 비교, KNN/Naive Bayes 기반 핑거프린팅 알고리즘 벤치마크

### 4.2 GitHub — RSSI-Dataset (Multi-Technology)

- **링크**: https://github.com/pspachos/RSSI-Dataset
- **논문**: RSSI-Based Indoor Localization with the Internet of Things (IEEE Access)
- **내용**: BLE, WiFi, Zigbee, LoRaWAN 4가지 무선 기술의 RSSI 데이터를 2개의 실내 사무실 환경에서 수집한 데이터셋입니다. 각 기술별 9개 위치에서의 RSSI 측정값이 포함되어 있습니다.
- **데이터 포맷**: CSV (2개 환경 × 4개 기술 × 9개 위치)
- **활용 방안**: 다중 무선 기술 비교 연구, BLE와 WiFi의 신호 특성 차이 분석

### 4.3 GitHub — BBIL (BLE Beacon Indoor Localization)

- **링크**: https://github.com/co60ca/BBIL
- **원본 데이터**: https://doi.org/10.5683/SP2/UTZTFT
- **수집 기간**: 2018년 9월 ~ 2019년 5월
- **내용**: BLE 비콘과 스마트폰을 이용한 실내 측위 데이터셋입니다. 참가자들이 BLE 비콘과 스마트폰을 휴대하고 이동하며 수집했습니다. Raspberry Pi를 수신기로 사용하고, 스마트폰 앱으로 가속도계/자이로스코프 데이터와 자가 보고 위치를 동시에 기록했습니다. 2개의 서로 다른 장소에서 수집되었습니다.
- **데이터 포맷**: CSV (RSSI + 가속도계 + 자이로스코프 + 위치 라벨)
- **활용 방안**: BLE 비콘 기반 실시간 위치 추적 알고리즘 개발, PDR과 BLE 측위의 융합(sensor fusion) 연구

### 4.4 GitHub — Position-Annotated BLE RSSI Dataset

- **Kaggle DOI**: 10.34740/KAGGLE/DS/1662453
- **논문**: An indoor localization dataset and data collection framework with high precision position annotation (2022)
- **내용**: AR 마커 기반 고정밀 위치 어노테이션(오차 0.05m 미만)이 포함된 BLE RSSI 데이터셋입니다. 카메라 포즈 추정과 칼만 필터를 결합하여 BLE 비콘 데이터에 정밀한 2D 위치를 라벨링한 것이 특징입니다.
- **데이터 포맷**: CSV (RSSI + 고정밀 2D 좌표)
- **활용 방안**: BLE 측위 알고리즘의 정밀 정확도 평가, ground truth 위치 데이터가 정밀한 학습 데이터로 활용

### 4.5 IEEE DataPort — PDR IMU Dataset

- **링크**: https://ieee-dataport.org/keywords/indoor-positioning-pedestrian-dead-reckoning-inertial-measurement-unit-accelerometer
- **내용**: 스마트폰 IMU를 이용한 보행자 관성항법(PDR) 데이터셋입니다. 가슴 앞에 고정(chest), 손에 들고 흔들기(swing), 주머니에 넣기(pocket) 등 3가지 패턴으로 수집되었습니다. Google Pixel 3XL/3a 디바이스로 수집되었습니다.
- **데이터 포맷**: 가속도계 + 자이로스코프 시계열 데이터
- **활용 방안**: 스마트폰 IMU 기반 보행 감지(step detection) 및 이동 방향 추정 알고리즘 개발, MediWay의 Wi-Fi + PDR 융합 측위(Level 2) 개발에 활용

---

## 5. 프로젝트 단계별 데이터셋 활용 가이드

| Phase | 목표 | 추천 데이터셋 | 활용 내용 |
|-------|------|-------------|----------|
| Phase 1 (웹 데모) | 2D 지도 + 경로 하이라이트 | CubiCasa5K, MSD | 평면도 렌더링 로직 개발, SVG 기반 경로 표시 |
| Phase 2 (iOS 앱) | Wi-Fi/PDR 대략적 위치 | UJIIndoorLoc, Indoor Location Competition, PDR IMU Dataset | WiFi 핑거프린팅 모델 학습, 층 판별 알고리즘 개발, PDR 보행 감지 구현 |
| Phase 2 (iOS 앱) | 3D 스캔 프로토타입 | ARKitScenes | LiDAR 스캔 데이터 처리 파이프라인 참고, 3D 씬 분석 기법 학습 |
| Phase 3 (BLE 파일럿) | BLE 비콘 실시간 측위 | BLE RSSI Dataset, BBIL, Indoor Localization BLE+WiFi | BLE 핑거프린팅 알고리즘 개발 및 검증, WiFi+BLE 하이브리드 측위 최적화 |
| Phase 4 (확장) | 동선 분석 / AI 추천 | Indoor Location Competition, MSD(그래프 데이터) | 환자 동선 패턴 분석 모델 개발, 최적 동선 추천 알고리즘 학습 |

---

## 6. 참고 자료

### 학술 논문
- Microsoft Indoor Location Competition 2.0 Dataset: https://www.microsoft.com/en-us/research/publication/indoor-location-competition-2-0-dataset/
- ARKitScenes 논문: https://arxiv.org/pdf/2111.08897
- CubiCasa5K 논문: https://dl.acm.org/doi/10.1007/978-3-030-20205-7_3
- MSD (ECCV 2024): https://caspervanengelenburg.github.io/msd-eccv24-page/
- Hybrid Wi-Fi and BLE Fingerprinting Dataset: https://www.mdpi.com/2306-5729/7/11/156

### 데이터 검색 플랫폼
- Kaggle Datasets: https://www.kaggle.com/datasets
- UCI Machine Learning Repository: https://archive.ics.uci.edu/ml/index.php
- IEEE DataPort: https://ieee-dataport.org/
- Google Dataset Search: https://datasetsearch.research.google.com/
- Papers With Code (Datasets): https://paperswithcode.com/datasets

---

*최종 업데이트: 2026년 4월*
