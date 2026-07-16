# LLM Action Selector Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. This project defaults to single-agent inline execution.

**Goal:** Add a minimal, traceable LLM-guided action selection experiment for Web-KOBE without letting the LLM directly operate the browser.

**Architecture:** Introduce a small selector interface that consumes goal, current state, and already-grounded candidate actions, then returns one existing action id plus diagnostics. Keep browser execution inside existing grounded_web code. Persist per-step trace data so failures can be attributed to selection, parsing, invalid action, execution, or observation.

**Tech Stack:** Python dataclasses/protocols, existing Web-KOBE models, pytest, optional environment-backed LLM provider later.

## Global Constraints

- Do not let the LLM generate selectors or arbitrary browser commands.
- Do not replace the deterministic ranker by default.
- The LLM may only select from candidate action ids already produced by grounded_web.
- Every selector decision must be traceable.
- Real LLM/network use must remain optional; unit tests use fake selectors/providers.

---

## Tasks

### Task 1: Selector Core

- Add `src/ai_web_explorer/grounded_web/llm_action_selector.py`.
- Add tests covering valid selections, invalid action ids, malformed JSON, and trace output.

### Task 2: Web-KOBE Integration Hook

- Add an optional selector dependency to `WebKobeExplorer`.
- Preserve deterministic behavior when no selector is supplied.
- Add tests proving the selector can choose `product_add_to_cart` over deterministic ranking.

### Task 3: Smoke Trace Runner

- Add a small smoke helper that runs one or more Web-KOBE steps with selector traces.
- Keep real LLM provider optional.
- Update docs/current-project-overview after validation.
