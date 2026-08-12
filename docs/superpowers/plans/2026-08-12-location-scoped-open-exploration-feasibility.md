# Location-Scoped Open Exploration Feasibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a resumable, location-scoped open-exploration loop that inherits candidates within one semantic location, performs targeted candidate discovery after verified business-fact changes, completes the PracticeAutomatedTesting checkout with generated data, and emits SafeSym-solvable Minimal Semantic PDDL.

**Architecture:** Keep `WebKobeExplorer`, Raw Graph persistence, frontier replay, Semantic Planning Graph, Minimal Semantic PDDL, and SafeSym smoke as the main pipeline. Add a small experiment-semantic profile module and a location-level candidate-memory/coordinator module; the existing Explorer delegates candidate discovery and outcome bookkeeping to those units instead of accumulating more policy code. Extend the existing visual affordance/delta contracts rather than adding a second VLM stack, and keep site-specific vocabulary in the selected experiment profile and experiment harness only.

**Tech Stack:** Python 3.9+, dataclasses, asyncio, pytest, Playwright, Stagehand Python SDK, OpenAI-compatible vision provider, existing Web-KOBE graph JSON, PDDL, SafeSym.

## Global Constraints

- The real target is `https://practiceautomatedtesting.com/shopping`; this is a controlled test site and final `place_order` is allowed with generated fictional data only.
- Exploration remains open-ended. No SafeSym goal, expected plan, or fixed checkout sequence may influence candidate generation or ranking.
- PDDL contains only one active location, cumulative capability-completion facts, and necessary business facts; candidate/scan/replay/budget state never becomes a PDDL predicate.
- Candidate exploration identity is `(semantic_location, canonical_action)`; replay is recovery only and never creates graph nodes, graph edges, planning facts, or candidate-attempt records.
- Prompt/profile hard-coding may define the feasibility vocabulary and examples, but generic selector/compiler code must not branch on the site URL, product name, CSS/XPath, or fixed action order.
- Default budgets are exact: exploration attempts `20`, consecutive no-progress `3`, action attempts per candidate `2`, replay failures per frontier `2`, total replays `4`, VLM scan attempts `2`, candidates per location `8`.
- Every formal Stagehand action attempt consumes the 20-step budget; candidate preflight, VLM scans, and replay do not.
- A stable observed page change is sufficient for action success, including when Stagehand reports the known `tool_choice` model error; facts still require matching visible evidence.
- VLM/Stagehand waits must use explicit, generous configurable timeouts. Do not terminate merely because a response is slow.
- Preserve Location/Surface/Trace projection compatibility. Remove code only after `rg` proves it is unused by runtime, tests, and the public API; do not perform an unrelated large refactor.

---

## Planned File Structure

### New focused modules

- `src/ai_web_explorer/grounded_web/exploration_semantics.py`: experiment semantic vocabulary, evidence rules, generated checkout data, and profile resolution.
- `src/ai_web_explorer/grounded_web/location_exploration.py`: location candidate pools, scan bookkeeping, action outcomes, serialization, and selector-facing policy.
- `tests/safesym_bridge/test_exploration_semantics.py`: semantic profile and generated-data tests.
- `tests/safesym_bridge/test_location_exploration.py`: location-memory, scan deduplication, retry, and persistence tests.
- `tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py`: deterministic end-to-end pipeline test.
- `scripts/run_practice_shopping_feasibility.ps1`: reproducible real-site exploration, semantic projection, and SafeSym smoke harness.

### Existing modules to modify

- `src/ai_web_explorer/grounded_web/business_affordance.py`: reuse the existing candidate VLM parser/provider for `initial`, `supplement`, and `targeted` scan modes.
- `src/ai_web_explorer/grounded_web/visual_delta.py`: carry the experiment vocabulary and explicit observable/business-fact fields through the existing before/after VLM call.
- `src/ai_web_explorer/grounded_web/planning_fact_verifier.py`: conservatively promote allow-listed, evidenced experiment facts.
- `src/ai_web_explorer/grounded_web/explorer.py`: delegate candidate lifecycle to `LocationExplorationCoordinator`; keep browser observation/execution and edge creation here.
- `src/ai_web_explorer/grounded_web/frontier_replay.py`: select remaining actions by semantic location memory while preserving node fallback.
- `src/ai_web_explorer/grounded_web/controller.py`: consume parameterized limits, semantic progress, and replay budgets.
- `src/ai_web_explorer/grounded_web/openai_visual_delta.py`: expose a configurable request timeout for both candidate and delta VLM calls.
- `src/ai_web_explorer/grounded_web/stagehand_prompt.py`: reuse `BenchmarkTaskContext` in generic selected-action exploration without milestone guidance.
- `src/ai_web_explorer/safesym_bridge/browser_runner.py`: wire profile, coordinator, budgets, generated data, timeouts, checkpoints, and summaries.
- `src/ai_web_explorer/safesym_bridge/cli.py`: expose the exact runtime parameters without changing legacy defaults silently.
- `src/ai_web_explorer/safesym_bridge/graph_artifacts.py`: prove location exploration metadata survives compact checkpoint round trips.
- Existing tests under `tests/safesym_bridge/`: extend the nearest focused files; do not append all cases to the 2,000-line Explorer test file when a new module test is clearer.

---

### Task 1: Add the feasibility semantic profile and generated test data

**Files:**
- Create: `src/ai_web_explorer/grounded_web/exploration_semantics.py`
- Create: `tests/safesym_bridge/test_exploration_semantics.py`
- Modify: `src/ai_web_explorer/grounded_web/__init__.py`

**Interfaces:**
- Produces: `SemanticExperimentProfile`, `FactEvidenceRule`, `GeneratedCheckoutData`, `practice_shopping_feasibility_profile()`, `resolve_semantic_experiment_profile(name)`, and `generate_checkout_test_data(seed)`.
- Consumed by: Tasks 2, 3, 4, 7, and 8.

- [ ] **Step 1: Write failing tests for the exact vocabulary and safe generated data**

```python
from ai_web_explorer.grounded_web.exploration_semantics import (
    generate_checkout_test_data,
    practice_shopping_feasibility_profile,
    resolve_semantic_experiment_profile,
)


def test_practice_profile_separates_locations_capabilities_and_business_facts():
    profile = practice_shopping_feasibility_profile()
    assert profile.allowed_locations == (
        "shopping", "product_detail", "checkout", "confirmation"
    )
    assert profile.completion_fact_ids == {
        "products_sorted", "products_filtered", "products_found",
        "products_paginated", "product_details_viewed",
    }
    assert profile.business_fact_ids == {
        "cart_has_items", "checkout_info_complete",
        "payment_info_complete", "order_submitted",
    }
    assert {
        "sort_products", "filter_products", "search_products",
        "add_to_cart", "open_checkout", "complete_checkout_information",
        "complete_payment_information", "place_order",
    }.issubset(set(profile.canonical_action_examples))
    assert resolve_semantic_experiment_profile(profile.profile_id) == profile


def test_generated_checkout_data_is_deterministic_and_fictional():
    first = generate_checkout_test_data("practice-v1")
    second = generate_checkout_test_data("practice-v1")
    assert first == second
    assert first.email.endswith("@example.test")
    assert first.card_number == "4111111111111111"
    assert first.to_benchmark_context().test_credentials == {}
```

- [ ] **Step 2: Run the tests and verify the module is missing**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_exploration_semantics.py -q
```

Expected: collection fails with `ModuleNotFoundError: ai_web_explorer.grounded_web.exploration_semantics`.

- [ ] **Step 3: Implement immutable profile and evidence-rule types**

```python
@dataclass(frozen=True)
class FactEvidenceRule:
    fact_id: str
    descriptions: tuple[str, ...]


@dataclass(frozen=True)
class SemanticExperimentProfile:
    profile_id: str
    allowed_locations: tuple[str, ...]
    completion_facts: tuple[FactEvidenceRule, ...]
    business_facts: tuple[FactEvidenceRule, ...]
    action_role_examples: Mapping[str, str]
    canonical_action_examples: tuple[str, ...]

    @property
    def completion_fact_ids(self) -> frozenset[str]:
        return frozenset(rule.fact_id for rule in self.completion_facts)

    @property
    def business_fact_ids(self) -> frozenset[str]:
        return frozenset(rule.fact_id for rule in self.business_facts)

    def to_prompt_context(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "allowed_locations": list(self.allowed_locations),
            "completion_facts": {
                rule.fact_id: list(rule.descriptions)
                for rule in self.completion_facts
            },
            "business_facts": {
                rule.fact_id: list(rule.descriptions)
                for rule in self.business_facts
            },
            "action_role_examples": dict(self.action_role_examples),
            "canonical_action_examples": list(self.canonical_action_examples),
        }

    def to_business_flow_profile(self) -> BusinessFlowProfile:
        return BusinessFlowProfile(
            site_type=self.profile_id,
            stages=[],
            planning_facts=[
                PlanningFactSpec(
                    fact_id=rule.fact_id,
                    meaning=" ".join(rule.descriptions),
                )
                for rule in self.business_facts
            ],
        )
```

The Practice profile must contain only the vocabulary approved in the design. It may include role examples such as `sort_products -> presentation_capability` and `open_checkout -> guarded_navigation`; it must not contain a URL, selector, product, execution order, or SafeSym goal.

- [ ] **Step 4: Implement generated fictional checkout data**

```python
@dataclass(frozen=True)
class GeneratedCheckoutData:
    first_name: str
    last_name: str
    email: str
    phone: str
    address: str
    city: str
    postal_code: str
    country: str
    cardholder: str
    card_number: str
    expiry: str
    cvv: str

    def to_benchmark_context(self) -> BenchmarkTaskContext:
        return BenchmarkTaskContext(
            site_label="PracticeAutomatedTesting controlled test site",
            checkout_data=dataclasses.asdict(self),
            notes=("Use fictional data only; final test order is allowed.",),
        )


def generate_checkout_test_data(seed: str) -> GeneratedCheckoutData:
    suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    return GeneratedCheckoutData(
        first_name="Test", last_name=f"User{suffix}",
        email=f"shop-{suffix}@example.test", phone="555-0100",
        address="123 Test Street", city="Testville", postal_code="12345",
        country="Netherlands", cardholder=f"Test User {suffix}",
        card_number="4111111111111111", expiry="12/30", cvv="123",
    )
```

- [ ] **Step 5: Run focused tests and public API tests**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_exploration_semantics.py tests/test_grounded_web_public_api.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add src/ai_web_explorer/grounded_web/exploration_semantics.py src/ai_web_explorer/grounded_web/__init__.py tests/safesym_bridge/test_exploration_semantics.py
git commit -m "feat: add exploration semantic profiles"
```

---

### Task 2: Add persisted location-level candidate memory

**Files:**
- Create: `src/ai_web_explorer/grounded_web/location_exploration.py`
- Create: `tests/safesym_bridge/test_location_exploration.py`
- Modify: `src/ai_web_explorer/safesym_bridge/graph_artifacts.py`
- Modify: `tests/safesym_bridge/test_graph_artifacts.py`

**Interfaces:**
- Consumes: `SemanticExperimentProfile` from Task 1 and existing `BusinessAffordance`.
- Produces: `ExplorationLimits`, `CandidateAttemptOutcome`, `LocationCandidateRecord`, `LocationCandidatePool`, `LocationExplorationMemory`, `TargetedScanKey`, and `LOCATION_EXPLORATION_META_KEY`.
- Later callers use `memory.pool_for`, `memory.merge_scan`, `memory.next_candidate`, `memory.record_attempt`, `memory.should_run_targeted_scan`, `memory.to_dict`, and `LocationExplorationMemory.from_dict`.

- [ ] **Step 1: Write failing tests for location-scoped deduplication and retries**

```python
def test_same_action_is_deduped_within_location_but_not_across_locations():
    memory = LocationExplorationMemory()
    memory.merge_scan("shopping", [_affordance("add_to_cart")], kind="initial")
    memory.merge_scan("product_detail", [_affordance("add_to_cart")], kind="initial")
    memory.record_attempt("shopping", "add_to_cart", observable_change=True)
    assert memory.next_candidate("shopping") is None
    assert memory.next_candidate("product_detail").action_name == "add_to_cart"


def test_second_no_change_attempt_closes_candidate():
    memory = LocationExplorationMemory(
        limits=ExplorationLimits(max_action_attempts_per_candidate=2)
    )
    memory.merge_scan("shopping", [_affordance("sort_products")], kind="initial")
    memory.record_attempt("shopping", "sort_products", observable_change=False)
    assert memory.next_candidate("shopping").action_name == "sort_products"
    memory.record_attempt("shopping", "sort_products", observable_change=False)
    assert memory.next_candidate("shopping") is None
```

- [ ] **Step 2: Write failing tests for scan identity and checkpoint round trip**

```python
def test_targeted_scan_key_is_order_independent_and_runs_once():
    memory = LocationExplorationMemory()
    assert memory.should_run_targeted_scan(
        "shopping", added=["cart_has_items"], removed=[]
    )
    memory.mark_targeted_scan_complete(
        "shopping", added=["cart_has_items"], removed=[]
    )
    assert not memory.should_run_targeted_scan(
        "shopping", added=["cart_has_items"], removed=[]
    )


def test_location_memory_survives_compact_graph_round_trip(tmp_path):
    graph = _graph(meta={LOCATION_EXPLORATION_META_KEY: _memory().to_dict()})
    write_web_kobe_graph(graph, tmp_path / "graph.json")
    restored = load_web_kobe_graph_json(tmp_path / "graph.json")
    assert restored.meta[LOCATION_EXPLORATION_META_KEY] == _memory().to_dict()
```

- [ ] **Step 3: Run focused tests and verify failures**

Run:

```powershell
python -m pytest tests/safesym_bridge/test_location_exploration.py tests/safesym_bridge/test_graph_artifacts.py -q
```

Expected: failures for missing memory types and metadata round-trip behavior.

- [ ] **Step 4: Implement the memory types and deterministic serialization**

```python
@dataclass(frozen=True)
class ExplorationLimits:
    max_exploration_steps: int = 20
    max_consecutive_no_progress: int = 3
    max_action_attempts_per_candidate: int = 2
    max_replay_attempts_per_frontier: int = 2
    max_total_replays: int = 4
    max_vlm_scan_attempts: int = 2
    max_candidates_per_location: int = 8


@dataclass(frozen=True, order=True)
class TargetedScanKey:
    location_id: str
    added_business_facts: tuple[str, ...]
    removed_business_facts: tuple[str, ...]


class LocationExplorationMemory:
    def next_candidate(self, location_id: str) -> BusinessAffordance | None:
        pool = self.pool_for(location_id)
        eligible = [
            record for record in pool.candidates.values()
            if record.status in {"pending", "retryable_no_change", "retryable_failure"}
            and record.attempts < self.limits.max_action_attempts_per_candidate
        ]
        if not eligible:
            return None
        relevance = {"core": 0, "supporting": 1, "low_value": 2, "unknown": 3}
        return min(
            eligible,
            key=lambda item: (
                relevance.get(item.affordance.relevance_hint, 3),
                -(item.affordance.confidence or 0.0),
                item.discovery_order,
                item.action_id,
            ),
        ).affordance

    def should_run_targeted_scan(self, location_id: str, *, added, removed) -> bool:
        key = TargetedScanKey(
            normalize_semantic_id(location_id),
            tuple(sorted(set(map(normalize_semantic_id, added)))),
            tuple(sorted(set(map(normalize_semantic_id, removed)))),
        )
        return bool(key.added_business_facts or key.removed_business_facts) and (
            key not in self.completed_targeted_scans
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": "location-exploration-v1",
            "locations": {
                key: self.locations[key].to_dict()
                for key in sorted(self.locations)
            },
            "completed_targeted_scans": [
                key.to_dict() for key in sorted(self.completed_targeted_scans)
            ],
        }
```

Implement `merge_scan` as a canonical-action keyed merge: apply replacements first, mark explicit disabled IDs, ignore already terminal actions, and add only novel candidates. Implement `record_attempt` so visible change closes the candidate as `success`; the first no-change/failure remains retryable and the second closes as `no_observable_change`/`failed_retry_exhausted`. `from_dict` must normalize and sort the same fields emitted by `to_dict` and reject unknown schema versions.

Serialize locations, candidates, facts, and scan keys in sorted order. Preserve unknown future metadata keys when compacting the graph; do not move candidate state to the evidence sidecar because resume reads the compact graph.

- [ ] **Step 5: Run focused tests**

```powershell
python -m pytest tests/safesym_bridge/test_location_exploration.py tests/safesym_bridge/test_graph_artifacts.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add src/ai_web_explorer/grounded_web/location_exploration.py src/ai_web_explorer/safesym_bridge/graph_artifacts.py tests/safesym_bridge/test_location_exploration.py tests/safesym_bridge/test_graph_artifacts.py
git commit -m "feat: persist location candidate memory"
```

---

### Task 3: Extend the existing VLM contracts for scan modes and experiment facts

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/business_affordance.py`
- Modify: `src/ai_web_explorer/grounded_web/visual_delta.py`
- Modify: `src/ai_web_explorer/grounded_web/planning_fact_verifier.py`
- Modify: `tests/safesym_bridge/test_business_affordance.py`
- Modify: `tests/safesym_bridge/test_visual_delta_summarizer.py`
- Modify: `tests/safesym_bridge/test_planning_fact_verifier.py`

**Interfaces:**
- Consumes: `SemanticExperimentProfile.to_prompt_context()` from Task 1.
- Produces: expanded `VisualAffordanceRequest` (`scan_kind`, location/current pools/business delta/profile context), expanded `VisualAffordanceResult` (`location_id`, `replacements`, `disabled_action_ids`), expanded `VisualDeltaResult.observable_change`, and `verify_experiment_planning_delta`.
- Maintains: existing initial-scan and legacy-response compatibility.

- [ ] **Step 1: Write failing tests for initial, supplement, and targeted scan prompts**

```python
def test_targeted_scan_requests_only_business_delta_changes():
    request = VisualAffordanceRequest(
        goal="Explore useful website functionality.",
        current_screenshot_path="after.png",
        max_actions=8,
        scan_kind="targeted",
        semantic_location="shopping",
        existing_action_ids=["open_empty_cart", "add_to_cart"],
        completed_action_ids=["add_to_cart"],
        added_business_facts=["cart_has_items"],
        removed_business_facts=[],
        semantic_profile_context=_profile().to_prompt_context(),
    )
    result = summarize_visual_affordances(request, provider=_capture_provider())
    prompt = json.loads(result.trace.prompt)
    assert prompt["scan_kind"] == "targeted"
    assert prompt["business_delta"]["added"] == ["cart_has_items"]
    assert "SafeSym" not in prompt["instruction"]


def test_targeted_scan_parses_semantic_replacement():
    result = summarize_visual_affordances(
        _targeted_request(),
        provider=lambda *_args, **_kwargs: json.dumps({
            "location_id": "shopping",
            "newly_enabled": [{
                "intent": "open_checkout", "label": "Cart",
                "target": "cart button", "confidence": 0.9,
                "supporting_facts": ["cart_has_items"],
            }],
            "semantically_changed": [{
                "old_action": "open_empty_cart",
                "new_action": "open_checkout",
            }],
            "disabled": ["open_empty_cart"],
        }),
    )
    assert [item.action_name for item in result.business_affordances] == ["open_checkout"]
    assert result.replacements == [("open_empty_cart", "open_checkout")]
```

- [ ] **Step 2: Write failing tests for observable change and fact allow-listing**

```python
def test_experiment_verifier_promotes_only_evidenced_allowed_business_fact():
    result = verify_experiment_planning_delta(
        profile=_profile(),
        observable_change=True,
        candidate_added_facts=["cart_has_items", "invented_fact"],
        candidate_removed_facts=[],
        evidence=["The cart count changed from 0 to 1."],
        structured_delta=PlanningDelta(),
    )
    assert result.verified_added_facts == ["cart_has_items"]
    assert "invented_fact" not in result.profile_fact_ids


def test_action_change_without_fact_evidence_does_not_promote_business_fact():
    result = verify_experiment_planning_delta(
        profile=_profile(), observable_change=True,
        candidate_added_facts=["cart_has_items"], candidate_removed_facts=[],
        evidence=[], structured_delta=PlanningDelta(),
    )
    assert result.verified_added_facts == []
```

- [ ] **Step 3: Run focused tests and verify failures**

```powershell
python -m pytest tests/safesym_bridge/test_business_affordance.py tests/safesym_bridge/test_visual_delta_summarizer.py tests/safesym_bridge/test_planning_fact_verifier.py -q
```

Expected: failures for the new request/result fields and verifier.

- [ ] **Step 4: Extend one candidate provider instead of creating a duplicate stack**

Add scan-specific fields with backward-compatible defaults:

```python
@dataclass(frozen=True)
class VisualAffordanceRequest:
    goal: str
    current_screenshot_path: str
    current_signature: dict[str, Any] | None = None
    max_actions: int = 5
    scan_kind: str = "initial"
    semantic_location: str | None = None
    existing_action_ids: list[str] = field(default_factory=list)
    completed_action_ids: list[str] = field(default_factory=list)
    added_business_facts: list[str] = field(default_factory=list)
    removed_business_facts: list[str] = field(default_factory=list)
    semantic_profile_context: dict[str, Any] | None = None
```

For `initial`, retain the existing `regions` schema. For `supplement`, request only novel canonical actions. For `targeted`, request only `newly_enabled`, `semantically_changed`, and `disabled`; explicitly permit empty arrays and forbid re-emitting completed actions.

- [ ] **Step 5: Extend the visual delta contract conservatively**

Add these JSON fields:

```text
observable_change
business_facts_added
business_facts_removed
```

Pass the allow-listed profile context to the prompt. If `visual_change_kind` is not `surface` or `mixed`, force `target_location` to the confirmed source anchor. Treat malformed evidence (for example a string instead of a list) as no evidence, not as verified evidence.

Compute the final `observable_change` as a deterministic OR of URL-path change, structured signature change, observed DOM/state delta, accepted VLM visual-change kind, and VLM `observable_change`. A failed/malformed VLM response must not erase a change already proven by browser observation.

- [ ] **Step 6: Implement experiment fact verification before PDDL projection**

Merge structured verification first, then allow VLM-derived business facts only when all are true: observable change, fact is in `profile.business_fact_ids`, and at least one non-empty evidence string exists. Never add site/action-name branches to `semantic_planning.py` or `minimal_semantic_pddl.py`.

- [ ] **Step 7: Run focused tests**

```powershell
python -m pytest tests/safesym_bridge/test_business_affordance.py tests/safesym_bridge/test_visual_delta_summarizer.py tests/safesym_bridge/test_planning_fact_verifier.py tests/safesym_bridge/test_semantic_planning.py tests/safesym_bridge/test_minimal_semantic_pddl.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit Task 3**

```powershell
git add src/ai_web_explorer/grounded_web/business_affordance.py src/ai_web_explorer/grounded_web/visual_delta.py src/ai_web_explorer/grounded_web/planning_fact_verifier.py tests/safesym_bridge/test_business_affordance.py tests/safesym_bridge/test_visual_delta_summarizer.py tests/safesym_bridge/test_planning_fact_verifier.py
git commit -m "feat: add semantic candidate scan contracts"
```

---

### Task 4: Integrate location pools into Explorer and frontier selection

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/location_exploration.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/grounded_web/frontier_replay.py`
- Modify: `tests/safesym_bridge/test_location_exploration.py`
- Modify: `tests/safesym_bridge/test_web_kobe_explorer.py`
- Modify: `tests/safesym_bridge/test_frontier_replay.py`

**Interfaces:**
- Consumes: Task 2 memory and Task 3 scan/delta contracts.
- Produces: `LocationExplorationCoordinator`, which owns scan retry, pool merge, candidate selection/preflight, attempt outcome, semantic progress, and graph-meta synchronization.
- Explorer calls only coordinator methods; it remains responsible for browser observation, Stagehand execution, Raw Edge creation, and semantic observation attachment.

- [ ] **Step 1: Write failing tests for candidate inheritance across Raw Nodes**

```python
@pytest.mark.asyncio
async def test_same_location_inherits_pool_without_second_full_scan():
    scanner = SequencedScanner(initial=[_aff("sort_products"), _aff("filter_products")])
    explorer = _explorer(scanner=scanner, deltas=[_sorted_delta(), _filtered_delta()])
    await explorer.explore_one_step()
    graph = await explorer.explore_one_step()
    assert scanner.calls_by_kind == {"initial": 1}
    memory = LocationExplorationMemory.from_graph(graph)
    assert memory.completed_action_ids("shopping") == {
        "sort_products", "filter_products"
    }
```

- [ ] **Step 2: Write failing tests for business targeted scan and new-location scan**

```python
@pytest.mark.asyncio
async def test_business_fact_change_runs_one_targeted_scan():
    scanner = SequencedScanner(
        initial=[_aff("add_to_cart")],
        targeted=[_aff("open_checkout")],
    )
    explorer = _explorer(scanner=scanner, deltas=[_cart_added_delta()])
    graph = await explorer.explore_one_step()
    assert scanner.calls_by_kind == {"initial": 1, "targeted": 1}
    assert _pool_actions(graph, "shopping") == {"add_to_cart", "open_checkout"}


@pytest.mark.asyncio
async def test_surface_change_scans_new_location_once():
    scanner = SequencedScanner(
        initial_by_location={
            "shopping": [_aff("open_product")],
            "product_detail": [_aff("close_product_detail")],
        }
    )
    explorer = _explorer(scanner=scanner, deltas=[_product_detail_delta()])
    await explorer.explore_one_step()
    await explorer.explore_one_step()
    assert scanner.initial_locations == ["shopping", "product_detail"]
```

- [ ] **Step 3: Write failing tests for frontier selection by location, not node**

```python
def test_frontier_does_not_repeat_completed_location_action_on_sibling_raw_node():
    graph = _same_location_graph(
        location="shopping",
        nodes=("before_sort", "after_sort"),
        completed=("sort_products",),
        remaining=("filter_products",),
    )
    frontier = select_frontier(graph, include_start=True)
    assert frontier.untried_action_ids == ("filter_products",)
```

- [ ] **Step 4: Run focused tests and verify failures**

```powershell
python -m pytest tests/safesym_bridge/test_location_exploration.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_frontier_replay.py -q
```

- [ ] **Step 5: Implement `LocationExplorationCoordinator` and move policy out of Explorer**

```python
class LocationExplorationCoordinator:
    def record_action_outcome(
        self, *, location_before: str, location_after: str, action_id: str,
        observable_change: bool, completion_facts: list[str],
        business_added: list[str], business_removed: list[str], failed: bool,
    ) -> OutcomeUpdate:
        attempt = self.memory.record_attempt(
            location_before, action_id,
            observable_change=observable_change, failed=failed,
        )
        new_location = normalize_semantic_id(location_after) != normalize_semantic_id(location_before)
        targeted = self.memory.should_run_targeted_scan(
            location_before, added=business_added, removed=business_removed,
        )
        return OutcomeUpdate(
            attempt=attempt,
            new_location=new_location,
            targeted_scan_required=targeted,
            has_progress=bool(
                new_location or completion_facts or business_added or business_removed
            ),
        )

    def sync_graph_meta(self, manager: WebKobeGraphManager) -> None:
        manager.meta[LOCATION_EXPLORATION_META_KEY] = self.memory.to_dict()
```

`ensure_candidates` must: resolve the reliable node anchor; run one initial scan when absent; use the scan-returned allowed location to anchor the first node; run one supplement only after an exhausted pool; and merge every trace into the pool audit log. `select_candidate` must run the light DOM preflight, mark only definite absence as stale, and return unknown availability for Stagehand execution. The Explorer calls `record_action_outcome`, performs a targeted scan when requested, and folds whether that scan found a novel action into `has_progress` before checkpointing.

Initial scans return the location ID for first-node anchoring. Candidate preflight returns `available`, `stale`, or `unknown`; execute `unknown`, and mark stale only on clear DOM/target absence or explicit VLM disablement. Retry VLM scans up to `limits.max_vlm_scan_attempts`, persisting every trace.

- [ ] **Step 6: Replace node-local scan/selection in Explorer with coordinator calls**

Remove `_visual_affordance_observed_node_ids` and the node-only guard in `_record_source_business_affordances` after all references move to the coordinator. Do not delete Raw Node `business_affordances`; populate it from the location pool as a compatibility/readability snapshot.

After the edge is observed and verified, set:

```python
manager.meta["last_step_semantic_progress"] = outcome.has_progress
manager.meta["last_step_kind"] = outcome.step_kind
```

`has_progress` means new location, new completion fact, verified business add/remove, or a scan discovering a novel canonical action. A visually changed edge with none of those is successful but not semantic progress.

- [ ] **Step 7: Update frontier selection with a fail-closed fallback**

When `semantic_location_hint` is reliable and location memory exists, use the location pool and its completed/disabled state. When the anchor is missing or conflicted, retain current node-local behavior. Replay path edges remain Raw Graph edges; only the frontier candidate lookup changes.

- [ ] **Step 8: Run focused and regression tests**

```powershell
python -m pytest tests/safesym_bridge/test_location_exploration.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_frontier_replay.py tests/safesym_bridge/test_resume.py -q
```

Expected: all pass.

- [ ] **Step 9: Commit Task 4**

```powershell
git add src/ai_web_explorer/grounded_web/location_exploration.py src/ai_web_explorer/grounded_web/explorer.py src/ai_web_explorer/grounded_web/frontier_replay.py tests/safesym_bridge/test_location_exploration.py tests/safesym_bridge/test_web_kobe_explorer.py tests/safesym_bridge/test_frontier_replay.py
git commit -m "feat: explore candidates by semantic location"
```

---

### Task 5: Parameterize termination and replay budgets

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/controller.py`
- Modify: `src/ai_web_explorer/grounded_web/resume.py`
- Modify: `tests/safesym_bridge/test_web_kobe_controller.py`
- Modify: `tests/safesym_bridge/test_resume.py`

**Interfaces:**
- Consumes: `ExplorationLimits` and `last_step_semantic_progress`.
- Produces: exact stop reasons, persisted budget counters, `frontier_replay_attempts`, and normal `frontier_exhausted` detection.

- [ ] **Step 1: Write failing tests for the 20-step and three-no-progress limits**

```python
@pytest.mark.asyncio
async def test_formal_attempt_budget_stops_at_configured_twenty():
    explorer = CountingExplorer(progress=True)
    controller = WebKobeExplorationController(
        explorer, limits=ExplorationLimits(max_exploration_steps=20)
    )
    result = await controller.run()
    assert result.summary.steps_completed == 20
    assert result.summary.stop_reason == "max_exploration_steps_reached"


@pytest.mark.asyncio
async def test_three_semantically_unproductive_attempts_stop_run():
    explorer = CountingExplorer(progress=False)
    controller = WebKobeExplorationController(
        explorer, limits=ExplorationLimits(max_consecutive_no_progress=3)
    )
    result = await controller.run()
    assert result.summary.steps_completed == 3
    assert result.summary.stop_reason == "consecutive_no_progress_limit_reached"
```

- [ ] **Step 2: Write failing replay-budget tests**

```python
@pytest.mark.asyncio
async def test_replay_blocks_frontier_after_two_failures_and_stops_globally_at_four():
    runner = ReplayRunner(always_fails=True)
    result = await _controller_with_two_frontiers(runner).run()
    assert result.graph.meta["replay_attempt_count"] == 4
    assert result.graph.meta["frontier_replay_attempts"] == {
        "frontier_a": 2, "frontier_b": 2,
    }
    assert result.summary.stop_reason == "total_replay_limit_reached"
```

- [ ] **Step 3: Run controller/resume tests and verify failures**

```powershell
python -m pytest tests/safesym_bridge/test_web_kobe_controller.py tests/safesym_bridge/test_resume.py -q
```

- [ ] **Step 4: Make limits one constructor object and keep legacy call compatibility**

```python
class WebKobeExplorationController:
    def __init__(self, explorer, *, limits: ExplorationLimits | None = None,
                 terminal_condition=None, step_checkpoint=None,
                 frontier_replay_runner=None, start_url=None):
        self.limits = limits or ExplorationLimits()

    async def run(self, *, max_steps: int | None = None):
        step_limit = max_steps if max_steps is not None else self.limits.max_exploration_steps
        for _attempt_index in range(step_limit):
            graph = await self.explorer.explore_one_step()
            if graph.meta.get("last_step_semantic_progress") is True:
                consecutive_no_progress = 0
            else:
                consecutive_no_progress += 1
            if consecutive_no_progress >= self.limits.max_consecutive_no_progress:
                stop_reason = "consecutive_no_progress_limit_reached"
                break
```

Keep explicit `max_steps` as a compatibility override for existing tests/callers. Use `last_step_semantic_progress`, not `last_step_graph_changed`, for the new no-progress limit.

- [ ] **Step 5: Implement exact normal and protective stop reasons**

Use:

```text
frontier_exhausted
max_exploration_steps_reached
consecutive_no_progress_limit_reached
total_replay_limit_reached
no_recoverable_frontier
```

Persist counters before every checkpoint. A replay attempt increments the global budget when it starts, whether it succeeds or fails. Block one frontier only after its second failure, not its first. Replay validation must still require target location plus required business facts.

- [ ] **Step 6: Run focused tests**

```powershell
python -m pytest tests/safesym_bridge/test_web_kobe_controller.py tests/safesym_bridge/test_resume.py tests/safesym_bridge/test_frontier_replay.py -q
```

- [ ] **Step 7: Commit Task 5**

```powershell
git add src/ai_web_explorer/grounded_web/controller.py src/ai_web_explorer/grounded_web/resume.py tests/safesym_bridge/test_web_kobe_controller.py tests/safesym_bridge/test_resume.py
git commit -m "feat: bound exploration and replay budgets"
```

---

### Task 6: Wire CLI, timeouts, generated checkout context, and checkpoints

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/openai_visual_delta.py`
- Modify: `src/ai_web_explorer/grounded_web/stagehand_backend.py`
- Modify: `src/ai_web_explorer/grounded_web/stagehand_prompt.py`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_openai_visual_delta.py`
- Modify: `tests/safesym_bridge/test_stagehand_backend.py`
- Modify: `tests/safesym_bridge/test_stagehand_prompt.py`
- Modify: `tests/safesym_bridge/test_browser_runner.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Consumes: profile, generated data, coordinator, and limits from Tasks 1-5.
- Produces: CLI flags, provider timeouts, open-exploration final-order authorization, persistent summaries, and resume-compatible configuration.

- [ ] **Step 1: Write failing CLI parser tests for all exact defaults**

```python
def test_stagehand_explore_accepts_location_feasibility_parameters(monkeypatch, tmp_path):
    captured = _capture_stagehand_runner(monkeypatch)
    main([
        "web-kobe-stagehand-explore",
        "--url", "https://practiceautomatedtesting.com/shopping",
        "--output", str(tmp_path / "graph.json"),
        "--semantic-experiment-profile", "practice_shopping_feasibility",
        "--max-exploration-steps", "20",
        "--max-consecutive-no-progress", "3",
        "--max-action-attempts-per-candidate", "2",
        "--max-replay-attempts-per-frontier", "2",
        "--max-total-replays", "4",
        "--max-vlm-scan-attempts", "2",
        "--max-candidates", "8",
        "--vlm-request-timeout-seconds", "180",
        "--stagehand-action-timeout-seconds", "240",
        "--allow-test-site-final-order",
        "--test-data-seed", "practice-v1",
    ])
    assert captured["limits"] == ExplorationLimits()
    assert captured["allow_test_site_final_order"] is True
```

- [ ] **Step 2: Write failing provider and Stagehand-context tests**

```python
def test_openai_factory_passes_configured_timeout():
    calls = {}
    create_openai_visual_delta_provider_from_env(
        request_timeout_seconds=180,
        openai_factory=lambda **kwargs: calls.update(kwargs) or FakeClient(),
        environ={"OPENAI_API_KEY": "test"}, load_dotenv=lambda: None,
    )
    assert calls["timeout"] == 180


def test_generic_selected_action_goal_can_include_generated_checkout_data():
    goal = build_generic_stagehand_exploration_goal(
        site_purpose="controlled shopping test",
        benchmark_context=generate_checkout_test_data("practice-v1").to_benchmark_context(),
        allow_final_order=True,
    )
    assert "@example.test" in goal
    assert "final confirmation is allowed" in goal
    assert "Advance the checkout task" not in goal
```

- [ ] **Step 3: Run focused tests and verify failures**

```powershell
python -m pytest tests/safesym_bridge/test_openai_visual_delta.py tests/safesym_bridge/test_stagehand_backend.py tests/safesym_bridge/test_stagehand_prompt.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py -q
```

- [ ] **Step 4: Add provider and action timeouts**

Pass `timeout=request_timeout_seconds` to the OpenAI-compatible client factory. Add `action_timeout_seconds` to `StagehandAutomationBackend` and wrap its provider execution with `asyncio.wait_for`; on timeout set `last_execution_error="stagehand_action_timeout"`, preserve an execution attempt, and apply the normal retry budget instead of terminating the run.

- [ ] **Step 5: Reuse `BenchmarkTaskContext` without task-driving milestone prompts**

Extend `build_generic_stagehand_exploration_goal` with optional `benchmark_context` and `allow_final_order`. Include generated data and the explicit controlled-test permission, but retain `GENERIC_EXPLORATION_ACTION_POLICY`; do not call `build_ecommerce_checkout_stagehand_goal` or inject configured milestones.

- [ ] **Step 6: Wire parameters and checkpoint metadata**

Add exact CLI options from the test. Parse both `--steps` and `--max-exploration-steps` with default `None`: reject both together; resolve to `20` for the selected feasibility profile and retain legacy `8` when no experiment profile is selected. On resume, load `LOCATION_EXPLORATION_META_KEY` and budget counters before selecting a frontier.

Apply the same `max_total_replays` and `max_replay_attempts_per_frontier` counters to the browser runner's pre-controller resume bootstrap loop; it must not have a separate unbounded recovery path.

Write `exploration_summary` with:

```json
{
  "stop_reason": "frontier_exhausted",
  "formal_action_attempts": 0,
  "semantic_progress_count": 0,
  "consecutive_no_progress": 0,
  "replay_attempt_count": 0,
  "limits": {}
}
```

Populate real values deterministically; checkpoint after each formal attempt and before every return.

- [ ] **Step 7: Run focused tests**

```powershell
python -m pytest tests/safesym_bridge/test_openai_visual_delta.py tests/safesym_bridge/test_stagehand_backend.py tests/safesym_bridge/test_stagehand_prompt.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py -q
```

- [ ] **Step 8: Commit Task 6**

```powershell
git add src/ai_web_explorer/grounded_web/openai_visual_delta.py src/ai_web_explorer/grounded_web/stagehand_backend.py src/ai_web_explorer/grounded_web/stagehand_prompt.py src/ai_web_explorer/safesym_bridge/browser_runner.py src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_openai_visual_delta.py tests/safesym_bridge/test_stagehand_backend.py tests/safesym_bridge/test_stagehand_prompt.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py
git commit -m "feat: expose feasibility exploration controls"
```

---

### Task 7: Prove the full semantic graph and PDDL pipeline deterministically

**Files:**
- Create: `tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py`
- Modify: `src/ai_web_explorer/grounded_web/semantic_planning.py` only if the failing test exposes a generic projection defect.
- Modify: `src/ai_web_explorer/safesym_bridge/minimal_semantic_pddl.py` only if the failing test exposes a generic compiler defect.

**Interfaces:**
- Consumes: completed exploration pipeline.
- Produces: deterministic offline proof that ordinary capabilities do not become checkout prerequisites and the full confirmation goal is reachable.

- [ ] **Step 1: Write a deterministic fake-browser end-to-end test**

```python
@pytest.mark.asyncio
async def test_location_scoped_pipeline_reaches_confirmation_without_ordinary_dependencies():
    explorer = build_feasibility_fixture(
        actions=[
            observed("sort_products", "shopping", "shopping", completion=["products_sorted"]),
            observed("filter_products", "shopping", "shopping", completion=["products_filtered"]),
            observed("add_to_cart", "shopping", "shopping", business_add=["cart_has_items"]),
            observed("open_checkout", "shopping", "checkout", required=["cart_has_items"]),
            observed("complete_checkout_information", "checkout", "checkout", business_add=["checkout_info_complete"]),
            observed("complete_payment_information", "checkout", "checkout", business_add=["payment_info_complete"]),
            observed("place_order", "checkout", "confirmation",
                     required=["cart_has_items", "checkout_info_complete", "payment_info_complete"],
                     business_add=["order_submitted"]),
        ]
    )
    graph = (await WebKobeExplorationController(explorer).run()).graph
    semantic, report = build_semantic_planning_graph(graph)
    domain = compile_minimal_semantic_domain(semantic).domain
    problem = compile_minimal_semantic_problem(
        semantic, goal_location="confirmation", goal_facts=["order_submitted"]
    ).problem
    assert "(products_sorted)" in domain
    checkout = _action(domain, "open_checkout")
    assert "cart_has_items" in checkout.split(":precondition", 1)[1].split(":effect", 1)[0]
    assert "products_sorted" not in checkout.split(":precondition", 1)[1].split(":effect", 1)[0]
    assert "(at_confirmation)" in problem
    assert "(order_submitted)" in problem
    assert report.excluded_edges == []
```

- [ ] **Step 2: Add assertions for scan counts, deduplication, and replay neutrality**

The fixture must assert one initial scan per location, no full scan after ordinary facts, exactly one targeted scan for `cart_has_items`, no repeated `(location, action)` exploration, and unchanged graph node/edge counts when a replay-only recovery is invoked.

- [ ] **Step 3: Run the new test and fix only generic defects it exposes**

```powershell
python -m pytest tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py -q
```

Do not add a Practice-site branch to `semantic_planning.py` or `minimal_semantic_pddl.py`. If projection already passes, leave those files unchanged.

- [ ] **Step 4: Run the complete non-browser test suite**

```powershell
python -m pytest tests -q --ignore=tests/safesym_bridge/test_web_kobe_playwright_integration.py --ignore=tests/test_local_shop_fixture.py
```

Expected: all pass.

- [ ] **Step 5: Audit and remove only replaced dead code**

Run:

```powershell
rg -n "_visual_affordance_observed_node_ids|_record_source_business_affordances|current_state_exhausted|max_consecutive_unproductive_steps" src tests
```

Remove a legacy helper or field only if all production callers have moved to the coordinator and no public import/test relies on it. Do not delete Location/Surface/Trace PDDL, `run_ecommerce_stagehand_step`, or benchmark milestone code merely because this feasibility path does not use them.

- [ ] **Step 6: Commit Task 7**

```powershell
git add tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py src/ai_web_explorer/grounded_web src/ai_web_explorer/safesym_bridge
git commit -m "test: prove location scoped semantic pipeline"
```

---

### Task 8: Add the reproducible real-site harness and run acceptance

**Files:**
- Create: `scripts/run_practice_shopping_feasibility.ps1`
- Create after the run: `docs/experiments/practice-shopping-location-scoped-feasibility-v1.md`
- Modify: `docs/current-project-overview.zh-CN.md`

**Interfaces:**
- Consumes: `web-kobe-stagehand-explore`, `web-kobe-phase-a --projection semantic`, and `web-kobe-safesym-smoke`.
- Produces: the complete artifact directory and an evidence-backed experiment report.

- [ ] **Step 1: Write the harness with explicit parameters and no secrets**

```powershell
param(
  [string]$OutputRoot = "outputs/experiments/practice_automated_testing/location_scoped_v1",
  [string]$SafeSymRoot = "C:\Users\moon\Desktop\Projects\SafeSym",
  [string]$FastDownward = "C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py",
  [switch]$Clean
)

$ErrorActionPreference = "Stop"
$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputRoot))
$allowedOutputRoot = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) "outputs/experiments"))
if (-not $resolvedOutput.StartsWith($allowedOutputRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "OutputRoot must remain below outputs/experiments"
}
if ($Clean -and (Test-Path -LiteralPath $resolvedOutput)) {
  Remove-Item -LiteralPath $resolvedOutput -Recurse -Force
}
New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null

python -m ai_web_explorer.safesym_bridge.cli web-kobe-stagehand-explore `
  --url "https://practiceautomatedtesting.com/shopping" `
  --app-name practice_shopping `
  --output "$OutputRoot/graph.json" `
  --stagehand-trace "$OutputRoot/stagehand_trace.json" `
  --screenshot-dir "$OutputRoot/screenshots" `
  --semantic-experiment-profile practice_shopping_feasibility `
  --openai-visual-delta `
  --visual-delta-model gpt-4o-mini `
  --max-exploration-steps 20 `
  --max-consecutive-no-progress 3 `
  --max-action-attempts-per-candidate 2 `
  --max-replay-attempts-per-frontier 2 `
  --max-total-replays 4 `
  --max-vlm-scan-attempts 2 `
  --max-candidates 8 `
  --vlm-request-timeout-seconds 180 `
  --stagehand-action-timeout-seconds 240 `
  --allow-test-site-final-order `
  --test-data-seed practice-v1 `
  --frontier-replay

python -m ai_web_explorer.safesym_bridge.cli web-kobe-phase-a `
  --graph "$OutputRoot/graph.json" `
  --output "$OutputRoot/semantic_projection" `
  --projection semantic `
  --goal-location confirmation `
  --goal-fact order_submitted

python -m ai_web_explorer.safesym_bridge.cli web-kobe-safesym-smoke `
  --task-dir "$OutputRoot/semantic_projection" `
  --safesym-root $SafeSymRoot `
  --rules "$SafeSymRoot/configs/constraint_rules.json" `
  --fast-downward $FastDownward
```

The script must stop on a non-zero command, preserve an existing resumable graph unless `-Clean` is explicitly passed, and never print environment secrets.

- [ ] **Step 2: Verify script syntax and CLI help before the paid run**

```powershell
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
  (Resolve-Path scripts/run_practice_shopping_feasibility.ps1),
  [ref]$null,
  [ref]$errors
) | Out-Null
if ($errors.Count -gt 0) { throw ($errors | Out-String) }
python -m ai_web_explorer.safesym_bridge.cli web-kobe-stagehand-explore --help
```

Expected: no PowerShell parse errors and all new flags appear.

- [ ] **Step 3: Run the real experiment and wait for slow providers**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_practice_shopping_feasibility.ps1
```

Allow the configured 180/240-second waits. Do not terminate on the known Stagehand `tool_choice` message when the after-observation changed.

- [ ] **Step 4: Inspect artifacts programmatically**

```powershell
python -m json.tool outputs/experiments/practice_automated_testing/location_scoped_v1/graph.json | Out-Null
python -m json.tool outputs/experiments/practice_automated_testing/location_scoped_v1/semantic_projection/semantic_planning_graph.json | Out-Null
python -m json.tool outputs/experiments/practice_automated_testing/location_scoped_v1/semantic_projection/semantic_projection_report.json | Out-Null
python -m json.tool outputs/experiments/practice_automated_testing/location_scoped_v1/semantic_projection/safesym_smoke_report.json | Out-Null
```

Then inspect `domain.pddl`, `problem.pddl`, the SafeSym plan files, scan traces, screenshots, `stop_reason`, budgets, candidate attempts, and fact provenance. Verify the eleven minimum acceptance conditions in the design specification one by one.

- [ ] **Step 5: Write an evidence-backed experiment report**

Record exact commit, command, models, timings, stop reason, attempts, replay counts, location pools, scan counts, facts, PDDL actions, SafeSym result, artifact paths, and every unmet acceptance condition. Do not call a protected stop a natural exhaustion, and do not claim full success if SafeSym only parsed but did not solve.

- [ ] **Step 6: Run final verification**

```powershell
python -m pytest tests -q --ignore=tests/safesym_bridge/test_web_kobe_playwright_integration.py --ignore=tests/test_local_shop_fixture.py
git diff --check
git status --short
```

Expected: tests pass; `git diff --check` is clean; only intentional experiment documentation/code changes are present. Browser-gated tests may be run separately when Chromium is available.

- [ ] **Step 7: Commit Task 8**

```powershell
git add scripts/run_practice_shopping_feasibility.ps1 docs/experiments/practice-shopping-location-scoped-feasibility-v1.md docs/current-project-overview.zh-CN.md
git commit -m "docs: record location scoped shopping experiment"
```

---

## Reviewer Gates

After every task, the execution session must report the commit and focused test output. Review must reject:

- node-scoped candidate retry masquerading as location-scoped memory;
- any `can_*`/`action_tried` PDDL predicate;
- site/action-name branches in selector, semantic projection, or PDDL compiler;
- business facts promoted without allow-list membership and evidence;
- ordinary facts copied into checkout prerequisites;
- replay that creates or mutates planning edges;
- no-progress based only on Raw Graph novelty;
- scan/replay counters lost on compact checkpoint/resume;
- a fixed checkout sequence injected into open-exploration ranking;
- final-order execution outside the selected controlled test profile;
- tests that prove only mocked PDDL without the real-site artifact review in Task 8.
