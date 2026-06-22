# CVAT Docker 설치 및 YOLO 라벨링 가이드

> 목적: 크롤링 수집 이미지에 YOLO bounding box 라벨링을 팀 협업으로 진행하기 위한 CVAT 로컬 서버 구축
>
> 환경: Windows 11, PC2 (RTX 4060 Laptop 8GB)

## 설치 완료 기록

| 항목 | 내용 |
|---|---|
| 완료일 | 2026-05-28 |
| Docker Desktop | 29.5.2 (AMD64, WSL2 백엔드) |
| Docker Compose | v5.1.3 |
| CVAT | cvat-ai/cvat (최신 dev) |
| 접속 URL | http://localhost:8080 |
| 관리자 계정 | bell0925 |
| 상태 | 전체 컨테이너 정상 구동 확인 |

---

## 전체 파이프라인

```
1. 크롤링 → 음식별 폴더로 수집 (mala-hot-pot/, stir-fried-pork/, ...)
2. CVAT 라벨링 → 폴더당 task 1개, 단일 클래스로 bbox 작업
3. YOLO 포맷 export → images/ + labels/ ZIP
4. 파일명 정규화 + 기존 AIHub 데이터에 병합
5. downsample_balanced.py 재실행 → balanced 데이터셋 재생성
6. 모델 재학습
```

---

## 크롤링 우선순위 전략

`docs/superpowers/plans/2026-05-28-class-dataset-ap50-summary.csv` 기준:

| 우선순위 | 조건 | 크롤링 목표 | cap 조정 |
|---|---|---|---|
| 🔴 최우선 | 원본 < 500장 + AP50 낮음 | 500장까지 채우기 | 현행 유지 (500) |
| 🟠 2순위 | 원본 >= 500장 + AP50 낮음 | 다양성 확보용 추가 | 500 → 1000으로 증가 |
| 🟡 3순위 | 원본 < 500장 + AP50 높음 | 다양성 확보 (과적합 방지) | 현행 유지 (500) |
| ⚪ 낮음 | 원본 >= 500장 + AP50 높음 | 불필요 | 현행 유지 |

> - 원본 >= 500 클래스는 다운샘플링에서 희석되므로 cap을 함께 올려야 크롤링 효과가 반영됨.
> - 원본 < 500 + AP50 높음은 표본이 적어 val도 적고, 우연히 높게 나온 과적합 가능성이 있음.
>   실전 다양성 확보를 위해 크롤링으로 데이터를 보강해야 함.
> - 크롤링 이미지는 다양한 각도·조명·배경을 포함해 AIHub 단일 촬영 환경의 한계를 보완함.

### 클래스별 크롤링 목표량

| class | orig_train | val_n | AP50 | 크롤링 목표 | 비고 |
|---|---:|---:|---:|---:|---|
| stir-fried-pork | 240 | 20 | 0.267 | 260장 | 🔴 표본 부족 + 성능 최악 |
| mala-hot-pot | 270 | 60 | 0.267 | 230장 | 🔴 표본 부족 + 성능 최악 |
| sweet-and-sour-pork | 290 | 40 | 0.443 | 210장 | 🔴 표본 부족 + 성능 나쁨 |
| squid-dish | 100 | 20 | 0.995 | 400장 | 🟡 표본 극소 → 과적합 의심 |
| braised-pork-hock | 350 | 30 | 0.972 | 150장 | 🟡 표본 적음 → 과적합 의심 |
| spicy-mixed-noodles | 370 | 60 | 0.956 | 130장 | 🟡 표본 적음 → 과적합 의심 |
| black-bean-noodles | 390 | 50 | 0.995 | 110장 | 🟡 표본 적음 → 과적합 의심 |
| takoyaki | 410 | 40 | 0.582 | 90장 | 🔴 표본 부족 + 성능 나쁨 |
| braised-chicken | 430 | 70 | 0.977 | 70장 | 🟡 표본 적음 → 과적합 의심 |
| rice-soup | 460 | 70 | 0.693 | 40장 | 🔴 표본 부족 + 성능 경계 |
| fish-cake | 480 | 80 | 0.905 | 20장 | 🟡 표본 적음 → 과적합 의심 |
| noodle-soup | 5620 | 100 | 0.551 | 300장+ | 🟠 데이터 충분 + 성능 나쁨, cap 1000 |
| seafood-stew | 3220 | 100 | 0.556 | 300장+ | 🟠 데이터 충분 + 성능 나쁨, cap 1000 |
| spicy-seafood-noodles | 1640 | 100 | 0.478 | 300장+ | 🟠 데이터 충분 + 성능 나쁨, cap 1000 |
| stew | 1620 | 100 | 0.622 | 200장+ | 🟠 데이터 충분 + 성능 나쁨, cap 1000 |

---

## 0. 사전 요구사항 확인

- Windows 11 (WSL2 활성화 필요)
- RAM 16GB 이상 권장 (CVAT + DB + Redis 합산 ~4GB)
- 포트 8080 사용 가능 여부 확인

---

## 1. Docker Desktop 설치

### 1-1. WSL2 활성화 (관리자 PowerShell)

```powershell
wsl --install
```

재부팅 후 WSL2가 기본값으로 설정됐는지 확인:

```powershell
wsl --set-default-version 2
wsl --status
```

### 1-2. Docker Desktop 다운로드 및 설치

1. [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/) 접속
2. **Windows용 Docker Desktop** 다운로드 (AMD64)
3. 설치 옵션: **Use WSL2 instead of Hyper-V** 체크
4. 설치 완료 후 재시작
5. 설치 확인:

```powershell
docker --version
docker compose version
```

예상 출력:
```
Docker version 27.x.x, build ...
Docker Compose version v2.x.x
```

---

## 2. CVAT 설치

### 2-1. CVAT 저장소 클론

```powershell
cd C:\
git clone https://github.com/cvat-ai/cvat.git
cd cvat
```

### 2-2. CVAT 실행

```powershell
docker compose up -d
```

최초 실행 시 이미지 다운로드로 5~15분 소요. 완료 확인:

```powershell
docker compose ps
```

모든 서비스가 `running` 상태여야 함:
- cvat_server
- cvat_worker_default
- cvat_worker_export
- cvat_worker_import
- cvat_db (PostgreSQL)
- cvat_redis
- cvat_proxy (nginx)

### 2-3. 관리자 계정 생성

```powershell
docker exec -it cvat_server python manage.py createsuperuser
```

프롬프트에서 username, email, password 입력.

### 2-4. 브라우저 접속

```
http://localhost:8080
```

생성한 관리자 계정으로 로그인.

---

## 3. YOLO 라벨링 프로젝트 설정

### 3-1. 프로젝트 생성

1. 상단 메뉴 **Projects** → **Create new project**
2. Project name: `aihub-yolo-50-crawl-labeling`
3. **Labels** 탭 → **From file** 선택

### 3-2. Task 생성 방식 — 폴더(음식)당 task 1개 + 단일 클래스

크롤링 이미지는 음식별로 폴더가 구분되어 있으므로, task마다 클래스를 1개만 등록한다.
라벨러는 클래스 선택 없이 해당 음식에 박스만 치면 된다.

**Task 생성 절차:**

1. 프로젝트 내 **Create new task**
2. Task name: 폴더명과 동일하게 설정 (예: `mala-hot-pot`)
3. **Labels** 탭 → **Add label** → 해당 음식 이름만 입력 (예: `mala-hot-pot`)
4. **Select files** → 해당 폴더의 이미지 업로드
5. **Submit & Open**

> 50개 클래스 전체 라벨을 한 task에 넣지 않는다. 음식별로 task를 분리하면
> 라벨러 실수(잘못된 클래스 선택)를 원천 차단할 수 있다.

### 3-3. 팀원 공유

1. CVAT이 실행 중인 PC의 로컬 IP 확인:

```powershell
ipconfig | findstr "IPv4"
```

2. 같은 네트워크 팀원은 `http://<PC-IP>:8080` 으로 접속
3. CVAT 관리자 페이지 → **Admin** → **Users** → 팀원 계정 생성

---

## 4. AI-assisted 자동 라벨링 (선택)

기존 exp03 best.pt 모델로 pre-annotation을 걸면 수작업을 크게 줄일 수 있다.

### 4-1. Nuclio 함수 서버 활성화

```powershell
# cvat 폴더에서
docker compose -f docker-compose.yml -f components/serverless/docker-compose.serverless.yml up -d
```

### 4-2. Nuclio 대시보드 접속

```
http://localhost:8070
```

### 4-3. 커스텀 모델 배포

CVAT 공식 docs의 [Custom detector](https://docs.cvat.ai/docs/manual/advanced/serverless-tutorial/) 참고.
exp03 best.pt를 Ultralytics YOLO detector로 래핑해 Nuclio에 배포하면
**AI Tools → Detectors** 탭에서 자동 라벨링 실행 가능.

---

## 5. YOLO 포맷 Export 및 AIHub 데이터 병합

### 5-1. Export

1. Task 선택 → **Actions** → **Export task dataset**
2. Format: **YOLO 1.1** 선택
3. ZIP 다운로드 → `images/` + `labels/` 구조로 압축됨

### 5-2. 파일명 정규화

AIHub 데이터의 stem 형식: `train_A13001_s02_p02_594f120b`
크롤링 파일명이 중복되지 않도록 rename 필요:

```
crawl_mala_hot_pot_0001.jpg
crawl_mala_hot_pot_0002.jpg
...
```

향후 `scripts/data/` 에 rename + 병합 스크립트를 추가 예정.

### 5-3. 기존 데이터셋에 병합

```
data/food_images/aihub_yolo_50/train/images/  ← 크롤링 이미지 복사
data/food_images/aihub_yolo_50/train/labels/  ← 크롤링 라벨 복사
```

### 5-4. balanced 데이터셋 재생성

병합 후 `downsample_balanced.py` 재실행. cap 조정 전략:

| 조건 | cap | 이유 |
|---|---|---|
| 원본 < 500 + AP50 낮음 (🔴) | 500 유지 | 크롤링으로 채워진 만큼 전부 반영 |
| 원본 < 500 + AP50 높음 (🟡 과적합 의심) | 500 유지 | 크롤링으로 다양성 추가, 전부 반영 |
| 원본 >= 500 + AP50 낮음 (🟠) | 1000으로 증가 | 희석 방지, 크롤링 이미지가 학습에 반영되도록 |

```powershell
# 클래스별 cap을 다르게 설정해야 하므로 향후 per-class cap 기능 추가 예정
# 현재는 전체 cap을 1000으로 올려 일괄 적용
python scripts/data/downsample_balanced.py `
    --src data/food_images/aihub_yolo_50 `
    --dst data/food_images/aihub_yolo_50_crawl_balanced `
    --cap 1000 `
    --val-cap 100 `
    --seed 42
```

---

## 6. CVAT 종료 / 재시작

```powershell
# 종료
docker compose down

# 재시작 (데이터 유지)
docker compose up -d

# 데이터까지 완전 삭제 (주의)
docker compose down -v
```

---

## 참고

- CVAT 공식 문서: https://docs.cvat.ai/
- 클래스별 데이터 수 및 AP50: `docs/superpowers/plans/2026-05-28-class-dataset-ap50-summary.csv`
