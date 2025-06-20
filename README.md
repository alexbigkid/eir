# EXIF Picture Renamer [!Tests](https://github.com/alexbigkid/eir/actions/workflows/pipeline.yml/badge.svg) [![codecov](https://codecov.io/gh/alexbigkid/eir/branch/main/graph/badge.svg)](https://codecov.io/gh/alexbigkid/eir)
Renames all image files in the folder according to image file exif metadata for easy ordering and archiving

[TOC]


## Prerequisites

| tool | description                                        |
| :--- | :------------------------------------------------- |
| uv   | python package manager                             |

- The project should work on MacOS and Linux and any other unix like system
- I haven't tried Windows, since I don't own a windows machine
- Stay tuned ... I am currently working on the single executable binary for MacOS, Linux and Windows


## Instructions for developers

On you terminal command line
- if you haven't installed <b>Homebrew</b> yet (password probably required):
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
- install <b>uv</b> - Python version and Python package manager tool with:
```bash
brew install uv
```
- clone <b>eir</b> repository:
```bash
git clone https://github.com/alexbigkid/eir
cd eir
```
- install Python dependencies
```bash
uv sync
```
- and run:
```bash
uv run eir
```



### App runs on:
- [x] MacOS Sequoia (local machine) / Python 3.13.3
- [ ] Linux Ubuntu 20.04  / Python 3.12.x
- [ ] Windows 10 / Python 3.12.x


### Pipeline Unit Tests ran on:
- [x] Linux latest / Python 3.12.x, 3.13.x
- [x] MacOS latest / Python 3.12.x, 3.131.x
- [x] Windows latest / Python 3.12.x, 3.13.x

## Documentation

- [📦 Packaging Guide](docs/PACKAGING.md) - How packages are built for different platforms
- [🏗️ Architecture Support](docs/ARCHITECTURE.md) - Supported CPU architectures and platforms
- [🚀 Distribution Guide](docs/DISTRIBUTION.md) - How to distribute packages to package managers
- [🔑 GitHub Secrets Setup](docs/GITHUB_SECRETS_SETUP.md) - CI/CD automation configuration
- [🤖 Claude Instructions](docs/CLAUDE.md) - AI assistant development guidance

:checkered_flag:
