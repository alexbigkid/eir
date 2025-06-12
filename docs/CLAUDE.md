← [Back to Main Documentation](../README.md)

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Eir is a Python application for EXIF-based image renaming and RAW format conversion. It processes image directories, extracts EXIF metadata, organizes files by camera make/model, and converts RAW images to DNG format using a modern async/reactive architecture.

## Development Commands

- Install dependencies: `uv sync`
- Run the CLI: `uv run eir` or `eir` (after installation)
- Build the package: `uv build`
- Run tests: `pytest` (test files need to be implemented)
- Format/lint: `ruff check` and `ruff format`

## Architecture

### Entry Points and Flow
- **Main CLI entry:** `src/eir/cli.py:main()` (configured in pyproject.toml)
- **Command-line parsing:** `src/eir/clo.py` handles all CLI options and validation
- **Processing engines:** Two implementations exist - modern reactive (`processor.py`) and legacy comprehensive (`epr.py`)

### Core Components
- **processor.py:** Modern async/RxPY reactive pipeline (currently placeholder implementations)
- **epr.py:** Legacy but fully-featured EXIF processing engine with complete functionality
- **logger_manager.py:** Singleton pattern for centralized logging with YAML configuration
- **constants.py:** Dynamic constants loaded from pyproject.toml metadata

### Key Processing Features
- Supports 15+ RAW formats (CR2, CR3, NEF, ARW, etc.) and standard image/video formats
- EXIF extraction using PyExifTool with fallback handling for missing metadata
- File organization: `YYYYMMDD_project_name/make_model_extension/YYYYMMDD-HHMM_project_name_###.ext`
- RAW to DNG conversion via pydngconverter

### Configuration
- **Logging:** Uses `logging.yaml` with console and rotating file handlers
- **Code quality:** Ruff with 98-char line length, Google docstrings, comprehensive rulesets
- **Dependencies:** Modern stack with UV package management, RxPY reactive programming

## Architecture Highlights
- **Unified implementation:** Modern async RxPY architecture with complete EXIF functionality
- **Reactive pipeline:** Uses RxPY observables for concurrent file processing
- **Complete functionality:** Full EXIF extraction, file organization, and RAW to DNG conversion
- **Performance optimized:** Async/await throughout with concurrent operations

## Development Notes
- Uses Python >=3.13 with UV for package management and Hatchling for builds
- Async/await throughout with RxPY for reactive programming patterns
- Comprehensive EXIF metadata support for multiple camera manufacturers
- Performance tracing available via `@function_trace` decorator and PerformanceTimer context manager
