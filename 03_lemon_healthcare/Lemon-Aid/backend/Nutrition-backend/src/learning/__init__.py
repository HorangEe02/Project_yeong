"""Consent-gated learning data pipeline package."""

from src.learning.consent_gate import ImageLearningGateDecision, evaluate_image_learning_gate

__all__ = ["ImageLearningGateDecision", "evaluate_image_learning_gate"]
