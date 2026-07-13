# Project Structure

This repository keeps source code, tests, examples, and documentation in separate folders.

```text
src/ai_web_explorer/
  Core Python package for the web explorer.

src/ai_web_explorer/safesym_bridge/
  SauceDemo -> SafeSym graph/PDDL bridge MVP.

tests/
  Automated tests.

tests/safesym_bridge/
  Tests for the SafeSym bridge.

docs/
  Human-facing documentation.

docs/images/
  Images used by README and docs.

docs/notes/
  Project notes and design-direction documents.

docs/superpowers/
  Design specs and implementation plans created during guided development.

examples/
  Committed example artifacts.

examples/safesym/
  Historical SafeSym FSM JSON example files.

outputs/
  Local generated outputs. This directory is ignored by git.

data/
  Local exploration data and tracked sample fixtures.

resources/
  Prompt templates and other runtime resources.
```

Root-level files are kept for project configuration and entry-point documentation:

- `README.md`
- `pyproject.toml`
- `.gitignore`
- `.python-version`
- lock files
