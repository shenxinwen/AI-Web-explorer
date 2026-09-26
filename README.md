# VERA

Core implementation of **VERA: Verification and Environmental Risk Awareness for Functional Model Induction through Open-Ended Web Exploration**.

VERA explores web interfaces, verifies functional hypotheses against observed outcomes, and links admitted knowledge to execution evidence and contextual risk annotations.

This repository contains a partial code release. We plan to release the full code after publication.

## Structure

```text
src/vera/
  grounded_web/   Exploration, hypothesis memory, replay, verification, and risk assessment
  runtime/        Browser execution, graph persistence, and command-line interface
  admission.py    Evidence-based knowledge admission
configs/          Example exploration configuration
```

## Quick start

Requires Python 3.11+.

```bash
pip install -e .
python -m playwright install chromium
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, then run on your test application:

```bash
vera explore --url http://localhost:8000 --app-name demo \
  --config configs/exploration.json --output outputs/demo
```

The configuration controls models, exploration budgets, and recovery. Add `--headed` to display the browser or `--resume` to continue an existing run.

Build the admitted-knowledge view from the recorded evidence:

```bash
vera admit --graph outputs/demo/graph.json \
  --artifact-root . --output outputs/demo/admitted_knowledge.json
```

Run artifacts are saved under the output directory, including the functional graph, evidence records, screenshots, and admitted knowledge.
