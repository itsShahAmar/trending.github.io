# Contributing to YouTube Shorts Automation

Thank you for your interest in contributing! 🎉  
All contributions — bug fixes, new features, documentation improvements, and ideas — are welcome.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Features](#suggesting-features)
  - [Submitting Pull Requests](#submitting-pull-requests)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Commit Message Guidelines](#commit-message-guidelines)

---

## Code of Conduct

This project and everyone participating in it is governed by the
[Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected
to uphold this code.

---

## Getting Started

1. **Fork** the repository and clone your fork locally.
2. Create a new branch from `main`:
   ```bash
   git checkout -b feat/my-awesome-feature
   ```
3. Make your changes, then push and open a Pull Request.

---

## How to Contribute

### Reporting Bugs

Use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) template when
opening a new issue. Please include:

- A clear and concise description of the bug.
- Steps to reproduce the behavior.
- Expected vs. actual behavior.
- Relevant logs or screenshots.
- Your environment (OS, Python version, etc.).

### Suggesting Features

Use the [Feature Request](.github/ISSUE_TEMPLATE/feature_request.md) template
and describe:

- The problem your feature solves.
- Your proposed solution or idea.
- Any alternatives you considered.

### Submitting Pull Requests

1. Ensure your branch is up to date with `main`.
2. Keep changes focused and minimal — one feature or fix per PR.
3. Write clear commit messages (see [guidelines](#commit-message-guidelines) below).
4. Fill out the [PR template](.github/pull_request_template.md).
5. Ensure all existing checks and tests pass before requesting review.

---

## Development Setup

```bash
# Clone your fork
git clone https://github.com/<your-username>/yt-automation.github.io.git
cd yt-automation.github.io

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install -y ffmpeg imagemagick fonts-liberation
```

To run the pipeline locally, set the required environment variables and then:

```bash
python -m src.pipeline
```

---

## Coding Standards

- Follow **PEP 8** for Python code style.
- Use descriptive variable and function names.
- Add docstrings to all public functions and modules.
- Keep functions small and focused on a single responsibility.
- Avoid introducing new paid API dependencies — keeping the project free is a core goal.

---

## Commit Message Guidelines

Use the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <short description>

[optional body]

[optional footer(s)]
```

Common types:

| Type | Description |
|------|-------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation changes only |
| `refactor` | Code change that is neither a fix nor a feature |
| `chore` | Build process or tooling changes |
| `test` | Adding or updating tests |

**Examples:**

```
feat(tts): add support for Spanish voice (es-ES-ElviraNeural)
fix(uploader): retry on 503 transient errors
docs(readme): update quick-start instructions
```

---

Thank you again for contributing — every bit helps! 🚀
