"""단일요리 음식 분류기 — exp16b 게이트 + DINOv3 전체분류 + 영양 매핑.

제품 방향: 사용자가 '음식 하나만 나오게' 촬영 → 단일요리 파이프라인.
  ① exp16b(YOLO26s): 음식 유무·위치 게이트 (없으면 None → "다시 찍어주세요")
  ② DINOv3-vitb16 + 선형 프로브: 사진 '전체'를 40종 분류 (크롭 X — 전체 0.84 > 크롭 0.72)
  ③ 영양 매핑: 분류 결과(class_en)를 40종 영양표(100g 기준)에 조인

왜 이 구조인가:
  - 단일요리는 음식이 화면을 채워 크롭하면 맥락(접시·상차림)이 사라져 손해 → 전체 이미지 분류.
  - DINO는 '음식 없음'을 못 하므로(무조건 40종 중 하나) exp16b가 음식 유무 게이트를 담당.
  - 분류는 우리가 학습한 YOLO(wild 0.60)보다 강한 DINOv3 사전학습+실데이터 프로브(wild 0.84) 사용.

사용:
    from food_classifier import FoodClassifier
    fc = FoodClassifier()                         # 모델·프로브·영양표 로드
    r = fc.analyze(Image.open("photo.jpg"))
    if r is None:
        print("음식이 없어요. 다시 찍어주세요.")
    else:
        print(r["name_ko"], r["conf"], r["nutrition"]["kcal_100g"])
"""

from __future__ import annotations

import csv
import importlib.util
import logging
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel
from ultralytics import YOLO

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
FOOD_BACKEND_ROOT = HERE.parents[2]
DEFAULT_EXP16B = FOOD_BACKEND_ROOT / "best.pt"
DEFAULT_PROBE = HERE / "probe_head.pt"
DEFAULT_NUTRITION = HERE / "nutrition" / "food_nutrition_40class.csv"

# 영문 클래스 → 한글 표시명 (지원 40종)
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
    "dim-sum": "딤섬",
    "doenjang-jjigae": "된장찌개",
    "fish-cake": "어묵",
    "fried-chicken": "후라이드치킨",
    "fried-food-platter": "튀김(모둠)",
    "grilled-fish": "생선구이",
    "grilled-pork-belly": "삼겹살",
    "hamburger": "햄버거",
    "japanese-ramen": "일본라멘",
    "jjigae-red": "빨간찌개",
    "kalguksu": "칼국수",
    "korean-blood-sausage": "순대",
    "korean-ramyeon-red": "라면",
    "mixed-rice-bowl": "비빔밥",
    "pasta": "파스타",
    "pizza": "피자",
    "pork-cutlet-dry": "돈가스",
    "raw-fish": "회",
    "rice-noodle-soup": "쌀국수",
    "rice-porridge": "죽",
    "rice-soup": "국밥",
    "salad": "샐러드",
    "sandwich": "샌드위치",
    "savory-pancake": "전/부침개",
    "seaweed-rice-roll": "김밥",
    "spicy-mixed-noodles": "비빔국수",
    "sushi": "초밥",
    "takoyaki": "타코야키",
    "tteokbokki-red": "떡볶이",
    "udon": "우동",
    "western-cream-soup": "양식수프",
}


def kr(name: str) -> str:
    """영문 클래스명을 한글 표시명으로 변환한다 (없으면 원문)."""
    return KR_NAME.get(name, name)


def _load_clip_food_filter_class():
    """Load ``CLIPFoodFilter`` from the sibling ``food_filter.py``.

    ``food_classifier.py`` is imported via a file-location spec, so its directory is not
    on ``sys.path``; load the sibling module explicitly by path.
    """
    ff_path = HERE / "food_filter.py"
    spec = importlib.util.spec_from_file_location("lemon_food_filter", ff_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"food_filter.py를 불러올 수 없습니다: {ff_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CLIPFoodFilter


def _crop_box(im: Image.Image, box: list[float]) -> Image.Image | None:
    """Return a bounds-clamped crop for a ``[x1, y1, x2, y2]`` box, or None if degenerate."""
    width, height = im.size
    x1, y1, x2, y2 = (round(float(v)) for v in box)
    x1 = max(0, min(x1, width))
    y1 = max(0, min(y1, height))
    x2 = max(0, min(x2, width))
    y2 = max(0, min(y2, height))
    if x2 <= x1 or y2 <= y1:
        return None  # degenerate / out-of-order box → skip the filter (fail-open)
    return im.crop((x1, y1, x2, y2))


def _is_nonfood_crop(food_filter, im: Image.Image, box: list[float], threshold: float) -> bool:
    """Return True when CLIP judges the YOLO box crop to be non-food.

    Fail-open: any crop/inference error returns False (treat as food) so the optional
    filter can never block an otherwise-valid food classification.
    """
    try:
        crop = _crop_box(im, box)
        if crop is None:
            return False
        return not food_filter.is_food(crop, threshold=threshold)
    except Exception:  # best-effort: an optional filter must never block classification
        logger.warning("CLIP food filter inference failed; skipping non-food check.", exc_info=True)
        return False


class FoodClassifier:
    """단일요리 음식 분류기 (exp16b 게이트 + DINOv3 분류 + 영양).

    Attributes:
        det: 음식 유무·위치 게이트 (YOLO exp16b).
        dino: DINOv3 백본(특징 추출, 동결).
        lin: 40종 선형 분류기.
        classes: 클래스명 리스트.
        nutrition: class_en → 영양 dict(100g 기준).
    """

    def __init__(
        self,
        exp16b_path: str | Path = DEFAULT_EXP16B,
        probe_path: str | Path = DEFAULT_PROBE,
        nutrition_csv: str | Path = DEFAULT_NUTRITION,
        det_conf: float = 0.10,
        max_px: int = 896,
        enable_food_filter: bool = False,
        food_filter_threshold: float = 0.5,
        food_filter_model_id: str = "openai/clip-vit-base-patch16",
    ) -> None:
        """모델·프로브·영양표를 로드한다.

        Args:
            exp16b_path: 음식 유무 게이트용 YOLO exp16b 가중치 (git 외부, 파일공유로 받음).
            probe_path: 학습된 DINOv3 선형 프로브 (probe_head.pt, 이 폴더 동봉).
            nutrition_csv: 40종 영양표(100g 기준) CSV.
            det_conf: 음식 유무 신뢰도 임계값(미만이면 "음식 없음").
            max_px: 분류 전 축소 상한(DINOv3 내부 224라 무손실).
            enable_food_filter: True면 YOLO 게이트와 DINOv3 분류 사이에 CLIP 비음식
                필터를 적용한다(YOLO 오탐 컷오프). 기본 False(기존 동작 유지).
            food_filter_threshold: CLIP 음식 확률 임계값(미만이면 비음식으로 컷).
            food_filter_model_id: CLIP zero-shot 필터 모델 ID.

        Raises:
            FileNotFoundError: exp16b 또는 프로브 파일이 없는 경우.
        """
        if not Path(exp16b_path).exists():
            raise FileNotFoundError(
                f"exp16b 없음: {exp16b_path} — 파일공유로 받아 해당 경로에 두세요."
            )
        if not Path(probe_path).exists():
            raise FileNotFoundError(f"프로브 없음: {probe_path}")
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.det = YOLO(str(exp16b_path))
        self.det_conf = det_conf
        self.max_px = max_px
        ckpt = torch.load(probe_path, map_location=self.dev, weights_only=False)
        self.classes: list[str] = ckpt["classes"]
        self.proc = AutoImageProcessor.from_pretrained(ckpt["dino_id"])
        self.dino = AutoModel.from_pretrained(ckpt["dino_id"]).to(self.dev).eval()
        self.lin = torch.nn.Linear(ckpt["feat_dim"], len(self.classes)).to(self.dev)
        self.lin.load_state_dict(ckpt["state_dict"])
        self.lin.eval()
        self.nutrition = self._load_nutrition(nutrition_csv)
        self.enable_food_filter = enable_food_filter
        self.food_filter_threshold = food_filter_threshold
        self.food_filter_model_id = food_filter_model_id
        # Lazy CLIP filter, tri-state: None=not loaded, False=load failed (no retry), instance=ready.
        self._food_filter: object | None = None

    @staticmethod
    def _load_nutrition(path: str | Path) -> dict[str, dict[str, str]]:
        """40종 영양표(100g 기준)를 class_en 키 dict로 로드한다 (없으면 빈 dict)."""
        if not Path(path).exists():
            return {}
        with Path(path).open(encoding="utf-8-sig") as f:
            return {r["class_en"]: r for r in csv.DictReader(f)}

    def _detect_food(self, im: Image.Image) -> list[float] | None:
        """exp16b로 음식 유무·위치를 판단한다. 최고신뢰 박스 [x1,y1,x2,y2] 또는 None(음식 없음)."""
        r = self.det.predict(im, conf=self.det_conf, verbose=False)[0]
        if not len(r.boxes):
            return None
        bi = int(r.boxes.conf.argmax())
        return [float(v) for v in r.boxes.xyxy[bi]]

    @torch.no_grad()
    def _classify(self, im: Image.Image) -> tuple[str, float]:
        """사진 '전체'를 DINOv3+프로브로 분류한다 → (영문클래스, 신뢰도). (크롭 안 함)"""
        x = im.copy()
        x.thumbnail((self.max_px, self.max_px))
        inp = self.proc(images=x, return_tensors="pt").to(self.dev)
        o = self.dino(**inp)
        f = getattr(o, "pooler_output", None)
        if f is None:
            f = o.last_hidden_state[:, 0]
        f = f / f.norm(dim=-1, keepdim=True)
        prob = self.lin(f).softmax(-1)[0]
        i = int(prob.argmax())
        return self.classes[i], float(prob[i])

    def _get_food_filter(self):
        """Lazily build the CLIP non-food filter; return None if disabled/unavailable."""
        if not self.enable_food_filter:
            return None
        if self._food_filter is None:
            try:
                clip_filter_cls = _load_clip_food_filter_class()
                self._food_filter = clip_filter_cls(model_id=self.food_filter_model_id)
                logger.info(
                    "CLIP non-food filter enabled (threshold=%.2f).", self.food_filter_threshold
                )
            except Exception:  # optional filter; degrade to no filtering on any load error
                logger.warning(
                    "CLIP food filter could not load; non-food check disabled.", exc_info=True
                )
                self._food_filter = False
        return self._food_filter or None

    def analyze(self, im: Image.Image) -> dict | None:
        """단일요리 사진을 분석한다.

        Args:
            im: PIL 이미지.

        Returns:
            {name_en, name_ko, conf, box, nutrition} 또는 음식이 없으면 None.
            nutrition은 100g 기준 영양 dict(없으면 None).
        """
        im = im.convert("RGB")
        box = self._detect_food(im)
        if box is None:
            return None  # 음식 미탐지 → "다시 찍어주세요"
        food_filter = self._get_food_filter()
        if food_filter is not None and _is_nonfood_crop(
            food_filter, im, box, self.food_filter_threshold
        ):
            return None  # YOLO 게이트는 통과했으나 CLIP 비음식 판정 → "다시 찍어주세요"
        name, conf = self._classify(im)  # 전체 이미지 분류 (크롭 X)
        return {
            "name_en": name,
            "name_ko": kr(name),
            "conf": conf,
            "box": box,
            "nutrition": self.nutrition.get(name),
        }
