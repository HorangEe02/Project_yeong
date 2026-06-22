"""API v1 라우터 집계."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.v1 import (
    activity,
    ai_agent,
    analysis_results,
    dashboard,
    food_records,
    health,
    meals,
    medical_records,
    notifications,
    nutrition,
    predictions,
    privacy,
    regulated_inputs,
    supplements,
    user_medications,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(activity.router)
api_router.include_router(ai_agent.router)
api_router.include_router(predictions.router)
api_router.include_router(nutrition.router)
api_router.include_router(analysis_results.router)
api_router.include_router(privacy.router)
api_router.include_router(regulated_inputs.router)
api_router.include_router(supplements.router)
api_router.include_router(meals.router)
api_router.include_router(health.router)
api_router.include_router(medical_records.router)
api_router.include_router(dashboard.router)
api_router.include_router(notifications.router)
api_router.include_router(food_records.router)
api_router.include_router(user_medications.router)
