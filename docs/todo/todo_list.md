# Image Converter - Implementation Checklist

- [x] Add `pillow` and `pillow-heif` to `pyproject.toml`, run `uv sync`
- [x] Implement and test `collect_convertible_files()`
- [x] Implement and test `extract_and_sort_by_date()`
- [x] Implement and test `generate_output_name()`
- [x] Implement and test `open_any_image()` (mock pydngconverter/pillow-heif)
- [x] Implement and test `resize_preserve_aspect()`
- [x] Implement and test `convert_single()`
- [x] Implement and test `convert_all()` RxPY pipeline
- [x] Wire up CLI subcommand
- [x] Ruff lint and format
