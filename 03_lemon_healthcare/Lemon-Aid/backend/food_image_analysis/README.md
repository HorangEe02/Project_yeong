# Food Image Analysis Backend

This directory owns the food image analysis backend feature.

## Scope

- Keep feature code under `src/food_image_analysis/`.
- Keep unit and integration tests under `tests/`.
- Call external OCR, vision, or multimodal providers only through adapter interfaces.
- Keep feature flags off by default until consent and provider settings are ready.

## Structure

```text
backend/food_image_analysis/
├── src/
│   └── food_image_analysis/
│       └── __init__.py
├── tests/
│   └── __init__.py
└── README.md
```

## Development Rules

- Use English names for packages, modules, functions, and variables.
- Add full type hints and Google-style docstrings for public Python APIs.
- Add tests together with new functions and classes.
- Use Korean for user-facing messages.
- Avoid regulated medical wording; describe outputs as analysis, evaluation, or support information.
