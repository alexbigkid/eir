# Convert images to optimized JPEG for real estate listing websites
eic *ARGS:
    uv sync --extra convert
    uv run python scripts/image_converter.py {{ARGS}}
