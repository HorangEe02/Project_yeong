# Food Image Dataset

음식 이미지 데이터셋 작업 공간입니다.

## 분류 흐름

1. 수집원을 `aihub`, `web_crawl`, `friend_contributed`로 구분한다.
2. 웹 크롤링 데이터는 `{cuisine_type}_{meal_component}` 형식의 영어 클래스명으로 평탄 저장한다.
3. 음식 계층은 폴더 중첩이 아니라 `manifests/taxonomy.json`과 `manifests/classes.json`으로 관리한다.
4. 학습/검증/테스트 분할은 `splits/train.csv`, `splits/val.csv`, `splits/test.csv`에서만 관리한다.
5. 중복, 저품질, 애매한 라벨은 `quarantine/` 아래로 격리한다.

```text
food_images/
├── raw/
│   ├── aihub/
│   ├── web_crawl/{class_name_en}/
│   │   ├── images/{hash}.jpg
│   │   └── metadata.jsonl
│   └── friend_contributed/
│       ├── inbox/
│       └── ingested/
│           ├── images/{hash}.jpg
│           └── metadata.jsonl
├── interim/
├── processed/
├── splits/
│   ├── train.csv
│   ├── val.csv
│   └── test.csv
├── manifests/
│   ├── taxonomy.json
│   ├── classes.json
│   └── stats/
├── quarantine/
│   ├── duplicates/
│   ├── low_quality/
│   └── ambiguous/
└── scripts/
```
