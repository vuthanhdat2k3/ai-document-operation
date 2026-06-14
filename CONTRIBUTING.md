# Contributing to AI Document Operations Agent

Thank you for your interest in contributing to the AI Document Operations Agent! This document provides guidelines and instructions for contributing to this project.

## Table of Contents

- [Development Setup](#development-setup)
- [Branch Strategy](#branch-strategy)
- [Commit Convention](#commit-convention)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation Requirements](#documentation-requirements)
- [Security Requirements](#security-requirements)
- [Review Checklist](#review-checklist)
- [Issue Templates](#issue-templates)
- [Code of Conduct](#code-of-conduct)

---

## Development Setup

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:

```bash
git clone https://github.com/<your-username>/AI-document-operations-agent.git
cd AI-document-operations-agent
git remote add upstream https://github.com/<original-org>/AI-document-operations-agent.git
```

### Install Dependencies

```bash
# Python dependencies
pip install -e ".[dev]"

# Or using poetry
poetry install --with dev

# Node.js dependencies (if applicable)
npm install
```

### Setup Environment

1. Copy the environment template:

```bash
cp .env.example .env
```

2. Configure required environment variables:
   - `OPENAI_API_KEY` or equivalent LLM provider key
   - `DATABASE_URL` for PostgreSQL connection
   - `REDIS_URL` for caching/session storage
   - `NOTION_API_KEY` if using Notion integration
   - Other service-specific keys as needed

3. Initialize the database:

```bash
python -m alembic upgrade head
```

### Run Services

```bash
# Start the development server
python -m uvicorn app.main:app --reload --port 8000

# Start background workers
celery -A app.celery worker --loglevel=info

# Run with Docker Compose (alternative)
docker-compose up -d
```

---

## Branch Strategy

We follow a structured branching model:

| Branch | Purpose | Description |
|--------|---------|-------------|
| `main` | Production-ready | Stable releases only. All code here is deployable. |
| `develop` | Integration branch | Latest development changes. Feature branches merge here first. |
| `feature/*` | New features | Branch from `develop`. Example: `feature/document-parser-v2` |
| `fix/*` | Bug fixes | Branch from `develop` or `main`. Example: `fix/pdf-rendering-crash` |
| `docs/*` | Documentation | Branch from `develop`. Example: `docs/api-endpoint-guide` |

### Branch Naming Convention

```
<type>/<short-description>
```

Examples:
- `feature/add-ocr-processing`
- `fix/memory-leak-in-parser`
- `docs/update-api-spec`
- `refactor/document-pipeline`

---

## Commit Convention

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation changes only |
| `style` | Code formatting (no logic change) |
| `refactor` | Code refactoring (no feature or fix) |
| `test` | Adding or updating tests |
| `chore` | Maintenance tasks, dependencies |

### Examples

```
feat(parser): add support for DOCX file extraction

fix(queue): resolve race condition in task deduplication

docs(api): update endpoint documentation for /documents

style: apply ruff formatting to service modules

refactor(pipeline): extract document validation into separate module

test(parser): add unit tests for PDF edge cases

chore(deps): bump openai from 1.2.0 to 1.3.0
```

### Breaking Changes

For breaking changes, add `BREAKING CHANGE:` in the footer:

```
feat(api): change document upload response format

BREAKING CHANGE: The /documents/upload endpoint now returns
`document_id` instead of `id` in the response body.
```

---

## Pull Request Process

### Step-by-Step

1. **Create a feature branch** from `develop`:
   ```bash
   git checkout develop
   git pull upstream develop
   git checkout -b feature/your-feature-name
   ```

2. **Write code** following the [Coding Standards](#coding-standards)

3. **Add/update tests** per [Testing Requirements](#testing-requirements)

4. **Update documentation** per [Documentation Requirements](#documentation-requirements)

5. **Run the full test suite**:
   ```bash
   pytest --cov=app --cov-report=term-missing
   mypy app/
   ruff check app/
   ```

6. **Create a Pull Request** against `develop` with:
   - Clear title following commit convention
   - Description of changes and motivation
   - Link to related issues
   - Screenshots/logs if applicable

### PR Template

```markdown
## Summary
Brief description of changes.

## Motivation
Why this change is needed.

## Changes
- List of changes made
- Any breaking changes

## Testing
How the changes were tested.

## Checklist
- [ ] Tests pass locally
- [ ] Code follows project standards
- [ ] Documentation updated
- [ ] No secrets or credentials in code
```

### Merge Requirements

- All CI tests pass
- At least one approving review from a code owner
- No merge conflicts with target branch
- All review comments resolved
- Branch is up to date with target branch

---

## Coding Standards

### Python

- **Formatter**: Ruff (configured in `pyproject.toml`)
- **Type Checking**: MyPy with strict mode
- **Linting**: Ruff with project-specific rules

```bash
# Format code
ruff format app/

# Check types
mypy app/ --strict

# Lint
ruff check app/ --fix
```

### TypeScript (if applicable)

- **Formatter**: Prettier
- **Linting**: ESLint with project config

```bash
npx prettier --write "src/**/*.ts"
npx eslint src/ --fix
```

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Variables | snake_case (Python), camelCase (TS) | `document_id`, `documentId` |
| Functions | snake_case (Python), camelCase (TS) | `parse_document`, `parseDocument` |
| Classes | PascalCase | `DocumentProcessor` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| Private members | Leading underscore (Python) | `_internal_method` |

### Import Ordering

```python
# 1. Standard library
import os
import sys
from datetime import datetime

# 2. Third-party packages
from fastapi import APIRouter, Depends
from pydantic import BaseModel

# 3. Local application imports
from app.models.document import Document
from app.services.parser import DocumentParser
```

### Error Handling Patterns

```python
# Use custom exception classes
class DocumentProcessingError(Exception):
    """Base exception for document processing errors."""
    pass

class InvalidDocumentFormatError(DocumentProcessingError):
    """Raised when document format is not supported."""
    pass

# Always handle specific exceptions
try:
    result = process_document(doc)
except InvalidDocumentFormatError as e:
    logger.warning(f"Invalid format: {e}")
    raise HTTPException(status_code=400, detail=str(e))
except DocumentProcessingError as e:
    logger.error(f"Processing failed: {e}")
    raise HTTPException(status_code=500, detail="Internal processing error")
```

---

## Testing Requirements

### Coverage

- Minimum **80% code coverage** for all new code
- Critical paths require **95%+ coverage**
- Coverage is enforced in CI

### Test Types

| Type | When Required | Location |
|------|--------------|----------|
| Unit tests | All new code | `tests/unit/` |
| Integration tests | New features, API changes | `tests/integration/` |
| E2E tests | Critical user flows | `tests/e2e/` |

### Test Naming Convention

```python
# Format: test_<unit>_<scenario>_<expected_result>
def test_document_parser_valid_pdf_returns_parsed_content():
    ...

def test_document_parser_corrupted_file_raises_error():
    ...

def test_queue_processor_duplicate_task_skips_processing():
    ...
```

### Test Data Management

- Use fixtures for test data setup
- Store test fixtures in `tests/fixtures/`
- Never use production data in tests
- Mock external service calls
- Clean up test data after each test

```python
@pytest.fixture
def sample_pdf_document(tmp_path):
    """Create a sample PDF for testing."""
    pdf_path = tmp_path / "test.pdf"
    create_test_pdf(pdf_path)
    yield pdf_path
    pdf_path.unlink(missing_ok=True)
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_parser.py

# Run tests matching pattern
pytest -k "test_document_parser"
```

---

## Documentation Requirements

### When to Update Documentation

| Change Type | Required Documentation |
|------------|----------------------|
| Architecture changes | Update `AGENT.md` |
| API changes | Update `API_SPEC.md` |
| Database schema changes | Update `DATABASE_SCHEMA.md` |
| Tool/function changes | Update `TOOL_CONTRACTS.md` |
| New environment variables | Update `.env.example` and README |

### Code Documentation

- **All public functions** must have docstrings
- Use Google-style docstrings:

```python
def parse_document(file_path: str, format: str = "auto") -> ParsedDocument:
    """Parse a document and extract its content.

    Args:
        file_path: Path to the document file.
        format: Document format hint. Defaults to 'auto' for detection.

    Returns:
        ParsedDocument containing extracted text and metadata.

    Raises:
        InvalidDocumentFormatError: If the format is unsupported.
        FileNotFoundError: If the file does not exist.

    Example:
        >>> doc = parse_document("/path/to/document.pdf")
        >>> print(doc.text)
    """
```

---

## Security Requirements

### Secrets Management

- **Never** commit secrets, API keys, or credentials to the repository
- Use environment variables for all sensitive configuration
- Add `.env` to `.gitignore`
- Rotate keys if accidentally exposed

### Input Validation

- Validate all external inputs at API boundaries
- Use Pydantic models for request validation
- Sanitize file paths and user-provided strings
- Enforce file size limits for uploads

### Output Sanitization

- Sanitize data before rendering in responses
- Prevent injection attacks in generated content
- Escape special characters in log output

### Dependency Security

```bash
# Check for known vulnerabilities
pip-audit

# Or with safety
safety check
```

- Review dependency updates before merging
- Pin dependency versions in production
- Run automated dependency scanning in CI

---

## Review Checklist

When reviewing pull requests, verify:

### Code Quality
- [ ] Code follows project coding standards
- [ ] No code duplication; DRY principle followed
- [ ] Functions are single-purpose and well-named
- [ ] No commented-out code blocks

### Testing
- [ ] All tests pass
- [ ] New code has adequate test coverage
- [ ] Edge cases are tested
- [ ] Error paths are tested

### Documentation
- [ ] Docstrings present for public APIs
- [ ] Relevant docs updated (AGENT.md, API_SPEC.md, etc.)
- [ ] Changelog updated if user-facing change

### Security
- [ ] No secrets or credentials in code
- [ ] Input validation present
- [ ] Output sanitization present
- [ ] No SQL injection vectors
- [ ] No path traversal vulnerabilities

### Performance
- [ ] No unnecessary database queries
- [ ] Proper use of async/await
- [ ] Memory usage is reasonable
- [ ] No blocking calls in async context

### Error Handling
- [ ] Exceptions are caught specifically (not bare `except`)
- [ ] Errors are logged with context
- [ ] User-facing errors are meaningful
- [ ] Resources are cleaned up (context managers)

---

## Issue Templates

### Bug Report

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened.

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.11.4]
- Project version: [e.g., 1.2.0]

**Logs/Screenshots**
Add relevant logs or screenshots.

**Additional context**
Any other information about the problem.
```

### Feature Request

```markdown
**Is your feature request related to a problem?**
A clear description of the problem. Example: "I'm frustrated when..."

**Describe the solution you'd like**
What you want to happen.

**Describe alternatives you've considered**
Other solutions or features you've considered.

**Additional context**
Any other information, mockups, or examples.
```

### Documentation Request

```markdown
**What documentation is missing or incorrect?**
Describe the gap in documentation.

**Where should it be located?**
Which file or section needs updating.

**Suggested content**
What the documentation should cover.

**Target audience**
Who would benefit from this documentation.
```

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive experience for everyone. We pledge to act and interact in ways that contribute to an open, friendly, diverse, and healthy community.

### Expected Behavior

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Accept constructive criticism gracefully
- Focus on what is best for the community and project
- Show empathy toward other contributors

### Unacceptable Behavior

- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported to the project maintainers. All complaints will be reviewed and investigated fairly. Maintainers are obligated to maintain confidentiality regarding the reporter of an incident.

---

## Getting Help

- Open an issue for bugs or feature requests
- Start a discussion for questions or ideas
- Check existing documentation before asking
- Be patient and respectful when seeking help

Thank you for contributing to AI Document Operations Agent!
