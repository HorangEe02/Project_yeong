r"""CLIP 기반 음식/비음식 zero-shot 필터 (프로덕션 어댑터용).

이미지 박스가 진짜 음식인지 학습 없이 판별. 사람·화분·소품·빈 식기 등 즉시 거름.
HuggingFace CLIP-ViT-B/16 사용. ``food_classifier.py`` 의 단일요리 파이프라인에서
exp16b YOLO 게이트와 DINOv3 분류 사이의 비음식 컷오프로 호출된다.

원본: 팀 연구 모듈 ``food_image_analysis/food_filter.py`` 를 프로덕션용으로 이식
(import 가드의 ``sys.exit`` 제거, ``print`` -> 로깅). 모델 로드는 호출자가 지연 수행한다.

사용 예:
    from food_filter import CLIPFoodFilter
    flt = CLIPFoodFilter()
    scores = flt.score_batch([crop1, crop2, ...])   # [0.95, 0.12, ...] 음식 확률
    keep_mask, scores = flt.filter(crops, threshold=0.5)
"""

from __future__ import annotations

import logging

import torch
from transformers import CLIPModel, CLIPProcessor

logger = logging.getLogger(__name__)


# 다국어 + Korean food 친화 프롬프트
FOOD_PROMPTS = [
    "a photo of food on a plate",
    "a photo of a meal",
    "a photo of Korean food",
    "a photo of a cooked dish",
    "a close-up photograph of food",
    "rice, noodles, or soup in a bowl",
    "side dishes on a table",
    "a bowl of stew or soup",
    "kimchi and other Korean side dishes",
    # 음료도 food 로 — Classifier 가 음료 클래스 미보유 시 별도 UX 처리
    "a beverage in a cup or glass",
    "coffee, tea, or juice",
    "a drink with ice or foam",
    # 한국 카페 음료 (CLIP 가중치 도움용)
    "Korean cafe drink with ice",
    "iced americano coffee",
    "cafe latte in a clear glass",
    "Korean traditional tea or sikhye",
    "bubble tea with tapioca pearls",
    "fruit smoothie in a tall glass",
]

NOT_FOOD_PROMPTS = [
    "a photo of a person",
    "a photo of a human face",
    "a photo of hands or fingers",
    "a photo of a plant in a pot",
    "a photo of flowers in a vase",
    "an empty plate or bowl",
    "an empty cup or glass",
    "utensils only without food",
    "a phone, remote, or electronic device",
    "a tissue, napkin, or receipt",
    "decorative table objects",
    "salt and pepper shakers",
    "an empty wooden or marble table surface",
    # 식기 본체 (음식 없이 그릇/항아리만) — 음식이 보이지 않는 경우만
    "a decorative ceramic jar with a closed lid",
    "a Korean traditional onggi jar without food",
    "an empty teapot or kettle",
    "a closed container with no food visible inside",
    # 양념·소스 종지 (영양 분석 대상 아님)
    "a small dish of dipping sauce",
    "a small bowl of soy sauce for dipping",
    "a small saucer with dark sauce",
    "a tiny sauce cup next to the main food",
    "a side dish of seasoning sauce",
    # 종이컵 / 음료수 컵 (영양 분석 제외)
    "an empty paper coffee cup",
    "a disposable paper cup with brand logo",
    "a takeout paper cup on the table",
    "a plain water cup or glass",
]


class CLIPFoodFilter:
    """CLIP 으로 음식/비음식 zero-shot 판별."""

    def __init__(
        self,
        model_id: str = "openai/clip-vit-base-patch16",
        device: str = "auto",
        food_prompts: list[str] | None = None,
        not_food_prompts: list[str] | None = None,
    ) -> None:
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        logger.info("CLIP food filter loading: %s (%s)", model_id, device)
        self.model = CLIPModel.from_pretrained(model_id).to(device).eval()
        self.processor = CLIPProcessor.from_pretrained(model_id)

        self.food_prompts = food_prompts or FOOD_PROMPTS
        self.not_food_prompts = not_food_prompts or NOT_FOOD_PROMPTS

        # 텍스트 임베딩 미리 계산 (한 번만)
        with torch.no_grad():
            all_texts = self.food_prompts + self.not_food_prompts
            inputs = self.processor(text=all_texts, return_tensors="pt", padding=True).to(device)
            txt_emb = self.model.get_text_features(**inputs)
            txt_emb = txt_emb / txt_emb.norm(dim=-1, keepdim=True)
            self.text_embed = txt_emb
        self.n_food = len(self.food_prompts)
        self.n_total = len(all_texts)
        logger.info(
            "CLIP food filter ready (%d food / %d non-food prompts)",
            self.n_food,
            len(self.not_food_prompts),
        )

    @torch.inference_mode()
    def score_batch(self, images) -> list[float]:
        """이미지(PIL) 리스트 → 음식 확률(0~1) 리스트."""
        if not images:
            return []
        inputs = self.processor(images=list(images), return_tensors="pt", padding=True).to(
            self.device
        )
        img_emb = self.model.get_image_features(**inputs)
        img_emb = img_emb / img_emb.norm(dim=-1, keepdim=True)

        # 코사인 유사도 [B, n_total]
        sims = img_emb @ self.text_embed.T

        # 음식 그룹 vs 비음식 그룹 각각 max
        food_max = sims[:, : self.n_food].max(dim=1).values
        nonfood_max = sims[:, self.n_food :].max(dim=1).values

        # softmax 로 음식 확률 변환 (temperature 100 = CLIP 표준)
        stacked = torch.stack([food_max, nonfood_max], dim=1)
        probs = (stacked * 100).softmax(dim=1)
        return probs[:, 0].cpu().numpy().tolist()

    def filter(self, images, threshold: float = 0.5):
        """이미지 리스트 → (keep_mask: bool 리스트, scores: float 리스트).
        threshold 이상이면 음식 = keep."""
        scores = self.score_batch(images)
        mask = [s >= threshold for s in scores]
        return mask, scores

    def is_food(self, image, threshold: float = 0.5) -> bool:
        """단일 이미지가 음식이면 True (score >= threshold)."""
        scores = self.score_batch([image])
        return bool(scores and scores[0] >= threshold)
