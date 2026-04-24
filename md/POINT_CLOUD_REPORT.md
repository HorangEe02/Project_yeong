# 📐 Point Cloud, PointNet, PointNet++ 기술 보고서

> 본 문서는 3D 점군(Point Cloud) 데이터의 개념과 이를 딥러닝으로 처리하기 위한
> 핵심 아키텍처인 PointNet, PointNet++의 등장 배경, 구조, 활용, 한계점을 정리한 보고서입니다.

---

## 목차

1. [Point Cloud (점군)](#1-point-cloud-점군)
2. [PointNet](#2-pointnet)
3. [PointNet++](#3-pointnet)
4. [PointNet vs PointNet++ 비교](#4-pointnet-vs-pointnet-비교)
5. [후속 연구 및 발전 방향](#5-후속-연구-및-발전-방향)
6. [MediWay 프로젝트에서의 활용](#6-mediway-프로젝트에서의-활용)
7. [참고 자료](#7-참고-자료)

---

## 1. Point Cloud (점군)

### 1.1 개념 및 정의

Point Cloud(점군, 點群)는 3차원 공간에서 점(point)들의 집합으로, 각 점은 X, Y, Z 좌표로 정의되며 물체의 표면이나 환경의 형상을 나타내는 데 사용됩니다. 이름 그대로 "점들이 구름처럼 퍼져 있는 형태"의 데이터입니다.

각 점은 좌표 외에도 다양한 속성 정보를 가질 수 있습니다.

- **기본 속성**: X, Y, Z 좌표 (위치)
- **색상 정보**: R, G, B 값
- **반사 강도**: Intensity (LiDAR 신호의 반사율)
- **법선 벡터**: Normal (표면의 방향)
- **시간 정보**: Timestamp (측정 시점)
- **신뢰도**: Confidence (측정 정확도)

### 1.2 생성 방법

Point Cloud는 주로 다음과 같은 센서/기술을 통해 수집됩니다.

| 기술 | 원리 | 대표 장비 | 특징 |
|------|------|----------|------|
| **LiDAR** | 레이저 펄스의 왕복 시간(ToF) 측정 | Velodyne, Hesai, iPhone Pro LiDAR | 가장 보편적, 높은 정밀도 |
| **구조광 스캐너** | 패턴화된 빛의 변형 분석 | Microsoft Kinect, Intel RealSense | 근거리 정밀 스캔에 적합 |
| **스테레오 카메라** | 두 카메라의 시차로 깊이 추정 | ZED 카메라 | 저비용, 색상 정보 풍부 |
| **ToF 카메라** | 빛 펄스의 왕복 시간 측정 | PMD Flexx, Azure Kinect | 전체 씬의 깊이를 한 번에 획득 |
| **Photogrammetry** | 다각도 사진에서 3D 복원 | 일반 카메라 + 소프트웨어 | 저비용, 후처리 필요 |

### 1.3 핵심 특성

Point Cloud 데이터는 2D 이미지나 정형 데이터와 근본적으로 다른 특성을 가지고 있으며, 이 특성들이 딥러닝 적용을 어렵게 만드는 핵심 요인입니다.

#### 1.3.1 비정형 구조 (Irregular/Unstructured)

2D 이미지는 픽셀이 고정된 격자(grid) 위에 규칙적으로 배열되어 있어 CNN을 직접 적용할 수 있습니다. 반면 Point Cloud는 3D 공간에 불규칙하게 분포된 점들의 집합이므로, 기존 CNN의 컨볼루션 연산을 그대로 적용할 수 없습니다.

#### 1.3.2 비순서성 (Unordered)

이미지의 픽셀은 좌상단에서 우하단까지 고정된 순서가 있지만, Point Cloud의 점들에는 내재적인 순서가 없습니다. N개의 점으로 이루어진 Point Cloud를 배열로 표현하면 N!가지의 서로 다른 순열이 가능하지만, 모두 동일한 3D 형상을 나타냅니다. 따라서 입력 순서가 바뀌어도 같은 결과를 출력하는 **순열 불변성(Permutation Invariance)**이 필요합니다.

#### 1.3.3 비균일 밀도 (Non-uniform Density)

LiDAR와 같은 센서로 수집된 Point Cloud는 센서와 가까운 물체에는 점이 조밀하게, 먼 물체에는 점이 희소하게 분포합니다. 이러한 밀도 불균일성은 특징 추출의 어려움을 가중시킵니다.

#### 1.3.4 변환 불변성 (Transformation Invariance)

동일한 물체를 다른 위치에서, 다른 각도로 스캔하면 좌표값이 달라지지만, 물체 자체는 동일합니다. 회전, 이동 등의 기하학적 변환에 대해 강건한(robust) 특징 추출이 필요합니다.

### 1.4 데이터 형식

| 형식 | 확장자 | 특징 |
|------|--------|------|
| PCD | `.pcd` | PCL(Point Cloud Library) 표준 형식, 헤더+데이터 구조 |
| PLY | `.ply` | Stanford 형식, ASCII/Binary 지원 |
| LAS/LAZ | `.las`, `.laz` | 항공 LiDAR 표준, 압축 지원 |
| OBJ | `.obj` | 3D 모델 범용 형식 |
| XYZ | `.xyz`, `.txt` | 단순 좌표 텍스트 |
| USDZ | `.usdz` | Apple 3D 파일 형식 (RoomPlan 출력) |

### 1.5 활용 분야

- **자율주행**: LiDAR Point Cloud에서 보행자, 차량, 장애물 탐지
- **로보틱스**: SLAM(동시적 위치추정 및 맵핑)으로 로봇 네비게이션
- **건축/건설**: 건물 3D 스캔, BIM(Building Information Modeling)
- **실내 측위**: 실내 공간 3D 맵핑 및 네비게이션
- **VR/AR**: 가상/증강 현실 공간 구축
- **문화재 보존**: 유적, 조형물의 3D 디지털 아카이빙
- **제조/품질검사**: 부품의 3D 형상 검사 및 역설계

---

## 2. PointNet

### 2.1 등장 배경

PointNet 이전에 Point Cloud를 딥러닝으로 처리하기 위한 시도들은 주로 **데이터 형태를 변환하는 방식**이었습니다.

**기존 접근법과 문제점**:

| 접근법 | 방식 | 문제점 |
|--------|------|--------|
| **3D Voxel 변환** | Point Cloud를 3D 격자(복셀)로 변환 후 3D CNN 적용 | 빈 공간이 대부분 → 메모리 낭비, 해상도↑ 시 연산량 폭증 (O(n³)) |
| **Multi-view 이미지** | 여러 각도에서 2D 이미지를 렌더링 후 2D CNN 적용 | 3D 구조 정보 손실, 렌더링 비용 |
| **수작업 특징 추출** | 통계적 속성(법선, 곡률 등)을 수동 설계 | 도메인 의존적, 일반화 어려움 |

이러한 변환 과정은 데이터의 3D 기하학적 정보를 손실시키거나, 불필요한 연산을 발생시키는 문제가 있었습니다. **"변환 없이 Point Cloud를 직접 입력받아 처리할 수는 없을까?"**라는 질문에서 PointNet이 탄생했습니다.

### 2.2 논문 정보

- **제목**: PointNet: Deep Learning on Point Sets for 3D Classification and Segmentation
- **저자**: Charles R. Qi, Hao Su, Kaichun Mo, Leonidas J. Guibas (Stanford University)
- **학회**: CVPR 2017 (Oral Presentation)
- **arXiv**: https://arxiv.org/abs/1612.00593
- **GitHub**: https://github.com/charlesq34/pointnet

### 2.3 핵심 아이디어

PointNet의 핵심은 **Point Cloud를 어떤 변환도 거치지 않고 그대로(raw) 입력받아 처리**하는 것입니다. 이를 위해 세 가지 핵심 설계를 도입했습니다.

#### 2.3.1 대칭 함수 (Symmetric Function) — Max Pooling

순열 불변성 문제를 해결하기 위해 **대칭 함수(symmetric function)**를 사용합니다. 대칭 함수란 입력의 순서를 바꿔도 출력이 동일한 함수를 말합니다. 대표적으로 덧셈(sum), 평균(mean), 최대값(max) 등이 있습니다.

PointNet은 각 점을 개별 MLP(Multi-Layer Perceptron)로 고차원 특징 공간에 매핑한 뒤, **Max Pooling**을 적용하여 전체 Point Cloud의 글로벌 특징 벡터(Global Feature)를 추출합니다.

```
입력: N개 점 {p₁, p₂, ..., pₙ} (각 점은 3D 좌표)
  ↓
[개별 MLP] — 각 점을 독립적으로 고차원 특징으로 변환 (64 → 128 → 1024차원)
  ↓
{f(p₁), f(p₂), ..., f(pₙ)} — N개의 1024차원 특징 벡터
  ↓
[Max Pooling] — 각 차원에서 최대값 선택
  ↓
글로벌 특징 벡터 (1×1024) — 전체 Point Cloud를 대표하는 벡터
```

Max Pooling은 순서와 무관하게 동일한 결과를 생성하므로, 입력 점들의 순서가 바뀌어도 같은 글로벌 특징이 추출됩니다.

#### 2.3.2 T-Net (Spatial Transformer Network)

기하학적 변환에 대한 불변성을 확보하기 위해, 입력 데이터를 정규화(canonicalize)하는 **T-Net**을 도입했습니다.

- **Input Transform (3×3)**: 입력 좌표에 대한 정렬 행렬을 학습하여, 서로 다른 시점에서 스캔된 Point Cloud를 일관된 좌표계로 변환
- **Feature Transform (64×64)**: 특징 공간에서의 정렬 행렬을 학습하여, 서로 다른 Point Cloud의 특징을 일관되게 정렬

Feature Transform은 차원이 높아(64×64) 최적화가 어려우므로, 변환 행렬이 직교 행렬에 가깝도록 정규화 손실(regularization loss)을 추가합니다.

#### 2.3.3 네트워크 구조

PointNet은 **분류(Classification)** 네트워크와 **세그멘테이션(Segmentation)** 네트워크로 구성됩니다.

**Classification 네트워크**:
```
입력 (N×3) → T-Net(3×3) → MLP(64,64) → T-Net(64×64) → MLP(64,128,1024)
→ Max Pooling → Global Feature (1024) → MLP(512,256,k) → k개 클래스 스코어
```

**Segmentation 네트워크**:
분류 네트워크를 확장하여, 글로벌 특징과 로컬 특징(각 점의 64차원 특징)을 결합(concatenate)한 뒤, 각 점별로 클래스를 예측합니다.

```
로컬 특징(N×64) + 글로벌 특징(1×1024 → N×1024 복제)
→ 결합 (N×1088) → MLP(512,256,128) → N×m 점별 세그멘테이션 스코어
```

### 2.4 주요 성과

- **ModelNet40 분류**: 89.2% 정확도 (당시 SOTA급)
- **ShapeNet Part Segmentation**: 83.7% mIoU
- **S3DIS Semantic Segmentation**: 실내 씬 시맨틱 세그멘테이션에서 우수한 성능
- Point Cloud를 직접 입력받는 최초의 딥러닝 아키텍처로, 이후 모든 3D 딥러닝 연구의 기반이 됨

### 2.5 한계점

PointNet에는 구조적으로 중요한 한계가 존재합니다.

#### 한계 1 — 로컬 구조(Local Structure) 미포착

PointNet의 가장 큰 한계는 **각 점을 독립적으로 처리**한다는 점입니다. 각 점은 개별 MLP를 통해 독립적으로 특징이 추출되고, Max Pooling으로 글로벌 특징만 생성됩니다. 이 과정에서 **이웃한 점들 사이의 관계(local structure)**가 포착되지 않습니다.

예를 들어 CNN은 인접 픽셀들을 함께 처리하는 컨볼루션 연산을 통해 에지, 텍스처, 패턴 등의 로컬 특징을 계층적으로 학습합니다. PointNet에는 이런 **"이웃 정보를 종합하는 메커니즘"**이 없습니다.

#### 한계 2 — 미세한 패턴 인식 어려움

로컬 구조를 포착하지 못하므로, 세밀한 형상 차이를 구분하는 데 약합니다. 전체적인 윤곽은 잘 잡지만, 부분적인 세부 특징(예: 의자의 팔걸이 유무, 비행기의 날개 형태 차이)을 구분하는 능력이 떨어집니다.

#### 한계 3 — 일반화(Generalizability) 제한

로컬 특징이 없으므로, 학습 데이터에서 보지 못한 새로운 형태의 객체에 대한 일반화 능력이 제한적입니다. CNN이 로컬 패턴의 재조합으로 새로운 이미지를 이해하는 것과 대비됩니다.

#### 한계 4 — 밀도 변화에 취약

Point Cloud의 밀도가 불균일할 때(센서 가까이 조밀, 멀리 희소), 균일한 처리 방식으로는 밀도에 따른 적응적 특징 추출이 어렵습니다.

---

## 3. PointNet++

### 3.1 등장 배경

PointNet++는 PointNet의 저자(Charles R. Qi 등)가 PointNet의 **로컬 구조 미포착 문제**를 해결하기 위해 발표한 후속 연구입니다.

핵심 동기는 **"CNN이 이미지에서 계층적으로 로컬 → 글로벌 특징을 학습하는 것처럼, Point Cloud에서도 계층적으로 점점 더 넓은 영역의 특징을 학습할 수 있는 구조를 만들자"**는 것입니다.

### 3.2 논문 정보

- **제목**: PointNet++: Deep Hierarchical Feature Learning on Point Sets in a Metric Space
- **저자**: Charles R. Qi, Li Yi, Hao Su, Leonidas J. Guibas (Stanford University)
- **학회**: NeurIPS (NIPS) 2017
- **arXiv**: https://arxiv.org/abs/1706.02413
- **GitHub**: https://github.com/charlesq34/pointnet2

### 3.3 핵심 아이디어

PointNet++의 핵심은 **입력 Point Cloud를 겹치는 로컬 영역으로 분할하고, 각 영역에 PointNet을 재귀적으로 적용하여 계층적으로 특징을 추출**하는 것입니다.

#### 3.3.1 Set Abstraction Layer

PointNet++의 기본 구성 단위로, 세 가지 하위 레이어로 구성됩니다.

**① Sampling Layer — "어디를 중심으로 볼 것인가"**

Farthest Point Sampling(FPS) 알고리즘을 사용하여 입력 점들 중 대표점(중심점)을 선택합니다. FPS는 이미 선택된 점들로부터 가장 먼 점을 순차적으로 선택하므로, 랜덤 샘플링보다 전체 공간을 균일하게 커버합니다.

**② Grouping Layer — "주변 점들을 어떻게 묶을 것인가"**

각 중심점 주위로 반경(radius) 내의 이웃 점들을 그룹화합니다. Ball Query 방식을 사용하여 반경 r 이내의 최대 K개 점을 선택합니다. 이 과정은 CNN의 receptive field와 유사한 역할을 합니다.

**③ PointNet Layer — "묶인 점들에서 특징을 추출"**

각 로컬 영역(그룹)에 PointNet을 적용하여 로컬 특징 벡터를 추출합니다. 이 과정을 통해 중심점 위치에 로컬 영역의 정보가 압축됩니다.

```
입력: N개 점 (N×(d+C))
  ↓
[Sampling] — FPS로 N'개 중심점 선택 (N' < N)
  ↓
[Grouping] — 각 중심점 주위 K개 이웃 그룹화 → N'×K×(d+C)
  ↓
[PointNet] — 각 그룹에 PointNet 적용 → N'×C' (로컬 특징 추출)
  ↓
출력: N'개 점 + 로컬 특징 (N'×(d+C'))
```

이 Set Abstraction을 여러 단계로 쌓으면, 점점 더 넓은 영역의 특징이 계층적으로 학습됩니다. CNN에서 layer가 깊어질수록 receptive field가 커지는 것과 동일한 원리입니다.

#### 3.3.2 밀도 적응 레이어 (Density Adaptive Layer)

Point Cloud의 비균일 밀도 문제를 해결하기 위해 두 가지 방법을 제안합니다.

**Multi-Scale Grouping (MSG)**:

각 중심점에 대해 여러 크기의 반경으로 그룹화를 수행하고, 각 스케일에서 추출한 특징을 결합(concatenate)합니다. 다양한 스케일의 정보를 동시에 포착할 수 있지만, 연산량이 큽니다.

**Multi-Resolution Grouping (MRG)**:

계산 효율적인 대안으로, 두 가지 해상도의 특징을 상황에 따라 가중 결합합니다. 점 밀도가 높은 영역에서는 하위 레벨의 상세한 특징에 높은 가중치를, 밀도가 낮은 영역에서는 상위 레벨의 요약된 특징에 높은 가중치를 부여합니다.

#### 3.3.3 Feature Propagation Layer (Segmentation용)

Set Abstraction은 점의 수를 줄이면서 특징을 압축하는 과정(인코더)입니다. Segmentation에서는 원래 모든 점에 대한 라벨이 필요하므로, 압축된 특징을 다시 원래 점들로 전파(propagate)해야 합니다.

PointNet++는 **거리 기반 보간(distance-based interpolation)**과 **skip connection**을 사용하여 특징을 원래 해상도로 복원합니다. 이는 U-Net 구조와 유사합니다.

```
Set Abstraction (인코더)           Feature Propagation (디코더)
N₁=4096 → N₂=1024 → N₃=256      256 → 1024 → 4096 (보간+skip)
  ↓          ↓         ↓            ↑       ↑       ↑
[SA₁]    [SA₂]     [SA₃]      [FP₃]   [FP₂]   [FP₁]
              └──────────────────┘ (skip connection)
```

### 3.4 주요 성과

- **ModelNet40 분류**: 90.7% (PointNet 89.2% 대비 향상)
- **ScanNet Semantic Labeling**: 84.5% 정확도 (PointNet 77.5%, 3D CNN 83.3% 대비 최고)
- **MNIST (2D → Point Cloud 변환)**: PointNet 대비 error rate 30% 이상 감소
- **ShapeNet Part Segmentation**: 85.1% mIoU (PointNet 83.7% 대비 향상)

### 3.5 한계점

#### 한계 1 — 연산 비용

FPS(Farthest Point Sampling)의 시간 복잡도는 O(N²)으로, 점의 수가 많아질수록 연산량이 급격히 증가합니다. 대규모 outdoor Point Cloud(수십만~수백만 점)에서는 실시간 처리가 어렵습니다.

#### 한계 2 — Ball Query의 고정 반경

Grouping에서 사용하는 Ball Query의 반경이 하이퍼파라미터로 고정됩니다. 최적 반경은 데이터의 스케일과 밀도에 따라 달라지므로, 다양한 환경에서 일관된 성능을 보장하기 어렵습니다.

#### 한계 3 — 점 간 관계 모델링의 한계

PointNet++는 로컬 영역 내에서 PointNet을 적용하므로, 결국 개별 점의 독립적 처리 후 Max Pooling이라는 기본 구조는 동일합니다. 점과 점 사이의 명시적 관계(예: 그래프 엣지)를 모델링하지는 않습니다. 이후 DGCNN(Dynamic Graph CNN) 등이 이 문제를 해결하고자 했습니다.

#### 한계 4 — 구현 복잡도

PointNet에 비해 구현이 복잡하고, FPS/Ball Query 등의 커스텀 CUDA 커널이 필요하여 학습 및 배포의 진입 장벽이 높습니다.

---

## 4. PointNet vs PointNet++ 비교

| 항목 | PointNet | PointNet++ |
|------|----------|------------|
| **발표** | CVPR 2017 | NeurIPS 2017 |
| **핵심 구조** | MLP + Max Pooling | 계층적 Set Abstraction + PointNet |
| **특징 추출 범위** | 글로벌 특징만 | 로컬 → 글로벌 계층적 특징 |
| **로컬 구조 포착** | ❌ 불가능 | ✅ 가능 (Ball Query + FPS) |
| **밀도 적응** | ❌ | ✅ (MSG / MRG) |
| **연산 복잡도** | 낮음 (실시간 가능) | 높음 (FPS O(N²)) |
| **구현 난이도** | 낮음 | 높음 (CUDA 커스텀 연산 필요) |
| **ModelNet40 정확도** | 89.2% | 90.7% |
| **Segmentation 성능** | 양호 | 우수 (로컬 특징 덕분) |
| **활용 단계** | 경량 추론, 프로토타입 | 정밀 분석, 연구 |

---

## 5. 후속 연구 및 발전 방향

PointNet/PointNet++ 이후 Point Cloud 딥러닝은 다양한 방향으로 발전했습니다.

### 5.1 그래프 기반 접근

- **DGCNN (Dynamic Graph CNN)**: 가장 가까운 이웃(k-NN)을 기반으로 동적 그래프를 구성하여 점 간 관계를 명시적으로 모델링합니다. Edge Convolution 연산을 도입했습니다.

### 5.2 복셀 + 포인트 하이브리드

- **VoxelNet**: Point Cloud를 복셀로 나누고, 각 복셀 내에서 PointNet으로 특징 추출 후 3D CNN 적용. 자율주행 3D 객체 탐지에 활용.
- **PointPillars**: 3D 복셀 대신 2D "기둥(pillar)"으로 나누어 계산 효율성을 크게 향상.

### 5.3 커널 기반 접근

- **KPConv (Kernel Point Convolution)**: 변형 가능한 커널 포인트를 사용하여 Point Cloud에 직접 컨볼루션을 적용합니다.

### 5.4 Transformer 기반 접근

- **Point Transformer**: Self-attention 메커니즘을 Point Cloud에 적용하여 점 간 관계를 모델링합니다. 최근 가장 활발한 연구 방향입니다.

### 5.5 PointNeXt (NeurIPS 2022)

PointNet++의 잠재력이 충분히 활용되지 않았다는 관점에서, 개선된 학습 전략(데이터 증강, 최적화 기법)과 모델 스케일링을 적용하여 PointNet++의 성능을 크게 향상시켰습니다. ScanObjectNN 분류에서 원본 PointNet++ 대비 9.8% 향상된 87.7% 정확도를 달성했습니다.

---

## 6. MediWay 프로젝트에서의 활용

### 6.1 iPhone LiDAR 스캔 → Point Cloud 처리

iPhone Pro의 LiDAR로 건물 내부를 스캔하면 Point Cloud 데이터가 생성됩니다. 이 데이터를 PointNet/PointNet++로 처리할 수 있는 활용 시나리오는 다음과 같습니다.

| 활용 시나리오 | 적합 모델 | 설명 |
|-------------|----------|------|
| 스캔된 공간의 방 유형 분류 (진료실, 복도, 약국 등) | PointNet | 글로벌 특징만으로 분류 가능, 경량 |
| 벽, 문, 창문, 가구 등 세그멘테이션 | PointNet++ | 로컬 특징 필요, 정밀한 경계 구분 |
| 3D 씬에서 POI(관심 지점) 자동 인식 | PointNet++ | 계층적 특징으로 다양한 크기의 객체 탐지 |
| 평면도 자동 생성을 위한 벽면 추출 | PointNet++ | 벽면의 연속적 구조를 로컬 특징으로 포착 |

### 6.2 현실적 권장

MediWay 프로젝트에서 PointNet/PointNet++를 직접 학습시키기보다는, **Apple의 RoomPlan API가 내부적으로 이미 유사한 뉴럴 네트워크를 사용**하고 있으므로, 다음과 같은 전략을 추천합니다.

- **Phase 1~2**: RoomPlan API의 내장 기능(벽/문/창문/가구 인식)을 활용하여 3D 스캔 → 2D 평면도 변환
- **Phase 3~4**: 병원 특화 객체(진료실 번호판, 안내 표지판, 의료 장비 등)를 인식해야 할 경우, PointNet++ 기반 커스텀 모델을 추가 학습
- **포트폴리오 가치**: ARKitScenes 데이터셋으로 PointNet++를 학습시키고, 실내 씬 세그멘테이션 결과를 시연하면 3D 비전 역량을 강력히 증명 가능

---

## 7. 참고 자료

### 원본 논문
- PointNet: https://arxiv.org/abs/1612.00593
- PointNet++: https://arxiv.org/abs/1706.02413
- PointNeXt: https://arxiv.org/abs/2206.04670

### 공식 프로젝트 페이지
- PointNet: https://stanford.edu/~rqi/pointnet/
- PointNet++: https://stanford.edu/~rqi/pointnet2/

### GitHub 구현
- PointNet (TensorFlow): https://github.com/charlesq34/pointnet
- PointNet++ (TensorFlow): https://github.com/charlesq34/pointnet2
- PointNet (PyTorch): https://github.com/fxia22/pointnet.pytorch
- PointNet++ (PyTorch): https://github.com/erikwijmans/Pointnet2_PyTorch

### 학습 데이터셋
- ModelNet40 (3D CAD 모델 분류): https://modelnet.cs.princeton.edu/
- ShapeNet (3D 객체 부분 세그멘테이션): https://shapenet.org/
- S3DIS (실내 씬 시맨틱 세그멘테이션): http://buildingparser.stanford.edu/dataset.html
- ScanNet (실내 3D 씬 이해): http://www.scan-net.org/
- ARKitScenes (Apple LiDAR 실내 씬): https://github.com/apple/ARKitScenes

### 참고 블로그 및 리뷰
- 3D Point Cloud 데이터의 이해 (Medium): https://jih0.medium.com/3d-point-cloud-이해하기-db6a75316645
- 3D 인공지능 데이터 Point Cloud (테스트웍스): https://blog.testworks.co.kr/3d-ai-data-point-cloud/
- PointNet 논문 리뷰 (Lee-Jaewon): https://lee-jaewon.github.io/deep_learning_study/pointnet/
- PointNet++ 논문 리뷰 (rauleun): https://rauleun.github.io/PointNet++
- Apple RoomPlan ML Research: https://machinelearning.apple.com/research/roomplan

### 라이브러리
- PCL (Point Cloud Library, C++): https://pointclouds.org/
- Open3D (Python/C++): http://www.open3d.org/
- PyTorch3D (Facebook Research): https://pytorch3d.org/
- Kaolin (NVIDIA): https://kaolin.readthedocs.io/

---

*최종 업데이트: 2026년 4월*
