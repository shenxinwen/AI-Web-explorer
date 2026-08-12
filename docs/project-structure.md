# Project Structure

This file records the active project structure. Keep it synchronized with
`docs/project-structure.zh-CN.md` when pipeline boundaries or module ownership
change.

## Active Direction

The repository is centered on the SafeSym-oriented Web-KOBE mainline:

```text
real browser operation
  -> VLM candidate hypotheses and local action selection
  -> Stagehand execution attempt
  -> after-action observation and local verification
  -> Raw Graph + evidence sidecar + checkpoint
  -> offline planning abstraction and Planning Graph
  -> Phase A PDDL projection
  -> SafeSym smoke / safety validation
```

The active explorer is forward-only: it follows the current route until its
candidate set is exhausted or the step budget/terminal condition is reached.
That is not a claim of site-wide exploration completion. The VLM proposes
hypotheses, Stagehand reports execution attempts, and after-action observation
is the verification evidence. A candidate capability is not a verified
transition until a successful observed edge supports it.

The old upstream `explore` runtime and the old `WebObservedGraph` exploration
stack are not active code paths.

## Layer Map

### Operation Layer

Owns browser execution and low-level interaction.

Main modules:

- `src/ai_web_explorer/grounded_web/automation_backend.py`
- `src/ai_web_explorer/grounded_web/playwright_backend.py`
- `src/ai_web_explorer/grounded_web/stagehand_backend.py`
- `src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py`
- `src/ai_web_explorer/grounded_web/stagehand_prompt.py`

Main responsibilities:

- observe browser state;
- collect low-level interactables as auxiliary input for state summaries,
  embedding matching, or execution evidence;
- execute one selected action;
- capture screenshots;
- preserve low-level execution traces.

Stagehand belongs here as the execution backend. Candidate business-action
generation belongs to the observation/exploration flow; low-level interactables
are not exploration candidates, memory/frontier units, or a selector/locator
fallback. Stagehand should not own graph identity, planning facts, or PDDL
semantics.

Main functions/classes:

- `AutomationBackend.observe_state`
- `AutomationBackend.list_interactables`
- `AutomationBackend.execute`
- `AutomationBackend.capture_screenshot`
- `WebKobePlaywrightAdapter`
- `StagehandAutomationBackend`
- `create_async_stagehand_provider_from_env`
- `build_generic_stagehand_exploration_goal`

### Observation And State Layer

Owns page state extraction, visual comparison, and candidate business facts.

Main modules:

- `src/ai_web_explorer/grounded_web/state_signature.py`
- `src/ai_web_explorer/grounded_web/state_facts.py`
- `src/ai_web_explorer/grounded_web/state_summary.py`
- `src/ai_web_explorer/grounded_web/semantic_assistor.py`
- `src/ai_web_explorer/grounded_web/business_profile.py`
- `src/ai_web_explorer/grounded_web/business_affordance.py`
- `src/ai_web_explorer/grounded_web/visual_delta.py`
- `src/ai_web_explorer/grounded_web/openai_visual_delta.py`
- `src/ai_web_explorer/grounded_web/planning_fact_verifier.py`

Main responsibilities:

- build deterministic state snapshots and signatures;
- summarize current state for review and embeddings;
- ask VLM for current business-action candidates;
- compare before/after screenshots and output only
  `candidate_added_facts` / `candidate_removed_facts`;
- let the local structured verifier produce `PlanningDelta` and evidence;
  historical `BusinessTransition` remains load-compatible;
- provide lightweight structured verification.

The VLM affordance result is a candidate hypothesis. The local verifier and
after-action observation determine whether an edge is a verified transition;
the candidate list alone does not establish a capability.

Profile facts live here as preferred observation targets and candidate PDDL
predicate vocabulary, not as the full set of possible website states. Visual
Delta VLM receives only the selected action and before/after screenshots; it
does not receive profile facts, supporting facts, or planning state. Its
observations remain raw edge-trace evidence and do not enter `PlanningState`.
Only locally confirmed facts enter profile/planning state. Visual affordance
observations may provide an optional technical state label; profiles do not
derive node labels from planning facts.

Main functions/classes:

- `StateSnapshot`
- `DeterministicSemanticAssistor.describe_state`
- `ecommerce_checkout_profile`
- `summarize_visual_affordances`
- `summarize_visual_delta`
- `create_openai_visual_delta_provider_from_env`
- `verify_planning_delta`
- `build_state_summary`

### Graph And Memory Layer

Owns the active semantic graph and state memory.

Main modules:

- `src/ai_web_explorer/grounded_web/graph.py`
- `src/ai_web_explorer/grounded_web/graph_manager.py`
- `src/ai_web_explorer/grounded_web/planning_abstraction.py`
- `src/ai_web_explorer/grounded_web/state_embedding.py`
- `src/ai_web_explorer/grounded_web/embedding_provider.py`
- `src/ai_web_explorer/grounded_web/exploration_index.py`

Main responsibilities:

- define `WebKobeGraph`, `WebKobeNode`, `WebKobeEdge`;
- record `BusinessAffordance`, `PlanningDelta`, `PlanningState`, and
  `PlanningTransition`, while remaining compatible with historical
  `BusinessTransition` data;
- preserve explicit visible changes as distinct raw observations before
  embedding target matching can rewrite them;
- keep the compact Raw Graph independently loadable, with detailed evidence
  in the optional `graph_evidence.json` sidecar;
- conservatively group presentation-equivalent observations offline into a
  Planning Graph and aggregate candidate capabilities with exact observation
  provenance;
- propagate source-aware planning state;
- keep state embedding summaries focused on page/business evidence instead of
  Stagehand policy prompt boilerplate;
- preserve `active_facts`, `profile_fact_ids`, and `generated_fact_ids` in
  `PlanningState`;
- retain Visual Delta observations in
  `execution_trace.metadata.visual_delta_trace`, without using them in
  planning transitions, target-matching planning facts, or Phase A PDDL;
- store state embeddings;
- use embedding similarity together with reliable local revisit evidence for
  matching; embeddings are memory aids, not graph identity or PDDL facts;
- detect revisits and provide memory context; explicit URL/signature/visual
  changes prevent a candidate target from merging back to its source, while
  reliable non-source history may still be reused.

Embeddings help locate similar states and avoid repeated actions. They should
not directly enter PDDL.

Main functions/classes:

- `WebKobeGraph`
- `WebKobeNode`
- `WebKobeEdge`
- `WebKobeGraphManager.identify_or_add_node`
- `WebKobeGraphManager.build_planning_transition`
- `WebKobeGraphManager.apply_planning_transition`
- `WebKobeExplorer._avoid_incompatible_existing_target_state`
- `find_best_state_match`
- `build_exploration_context`

### Exploration Policy Layer

Owns the step loop and action choice.

Main modules:

- `src/ai_web_explorer/grounded_web/explorer.py`
- `src/ai_web_explorer/grounded_web/controller.py`

Main responsibilities:

- run one exploration step;
- choose one business action from observed business affordances;
- apply memory context and repetition avoidance;
- keep a lightweight current-node pointer so the next action starts from the
  latest valid materialized business state;
- protect a source from embedding matches when the action has an explicit URL,
  structure-signature, or visual change; reliable non-source revisit evidence
  may still be reused;
- call the Stagehand operation layer and VLM/DOM observation layers;
- update graph state;
- stop with `current_state_exhausted` when the current node has no candidate;
- stop by budget or an optional controller terminal condition;
- treat candidate exhaustion and the bounded step budget as route-local
  termination, without browser-back recovery or automatic replay;
- expose an optional per-completed-step checkpoint callback. The generic
  controller retains a consecutive-unproductive threshold, while the real
  Stagehand runner disables that threshold.

Low-level DOM interactables may still be used as runtime state summary /
embedding-matching input, but they are no longer emitted in canonical
`graph.json` nodes and are not a graph-memory or exploration-decision unit. The
old LLM action selector path was removed so the system does not fall back to
selector/locator-driven exploration.

`WebKobeExplorer` is currently the largest coordination class. New exploration
features should avoid further enlarging it when a small policy/observer/recorder
component would keep coupling lower.

Main functions/classes:

- `WebKobeExplorer.explore_one_step`
- `WebKobeExplorer._select_action`
- `WebKobeExplorer._select_business_affordance_action`
- `WebKobeExplorer._match_current_state`
- `WebKobeExplorer._resolve_current_source_id`
- `WebKobeExplorer._record_source_business_affordances`
- `WebKobeExplorationController.run`

### PDDL Mapping And SafeSym Bridge

Owns planner-facing projection and validation.

Main modules:

- `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`
- `src/ai_web_explorer/safesym_bridge/web_kobe_safesym_smoke.py`
- `src/ai_web_explorer/safesym_bridge/cli.py`

Main responsibilities:

- load `WebKobeGraph` JSON;
- project Planning Graph locations and eligible observed business transitions
  into Phase A PDDL; use profile facts only as the declared vocabulary for
  concrete planning queries;
- write domain-only artifacts for exploration-stage modeling;
- write domain/problem artifacts when a concrete planning query is specified;
- run PDDL readiness checks;
- run SafeSym parser, safety injection, and planner smoke checks.

This layer should be deterministic. It should consume graph semantics, not call
LLM/VLM directly. The offline planning abstraction produces a Planning Graph
and audit report; Phase A projects canonical locations and eligible
non-self-loop business transitions into `domain.pddl` only. Visual Delta
observations, supporting facts, and raw candidate facts are not Phase A
predicates, preconditions, or effects.

Main functions/classes:

- `load_web_kobe_graph_json`
- `compile_web_kobe_graph_to_domain`
- `compile_web_kobe_graph_to_pddl`
- `write_web_kobe_pddl_smoke`
- `write_web_kobe_safesym_smoke`
- `main`

### Experiment Runtime

Owns CLI-facing experiment setup.

Main modules:

- `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- `src/ai_web_explorer/grounded_web/experiment_plan.py`

Main responsibilities:

- launch Playwright;
- configure Stagehand;
- configure VLM and embedding providers;
- wire benchmark/test context;
- write graph, trace, screenshot, embedding, PDDL, and smoke outputs;
- checkpoint embeddings and Stagehand trace before committing the graph/evidence
  pair after each completed action;
- write the final `graph.meta.exploration_summary` (`requested_steps`,
  `steps_completed`, and `stop_reason`) after normal completion.

`graph.json` is the compact, independently loadable Raw Graph; detailed
execution evidence is resolved through `graph_evidence.json`. The checkpoint
keeps the embedding, trace, graph, and evidence artifacts paired after each
completed action. `raw_graph.json`, `planning_graph.json`, and
`planning_abstraction_report.json` are separate audit/projection artifacts;
the sidecar is not read by Phase A.

Checkpointing overwrites the latest artifacts. `--resume-graph` can explicitly
hydrate a saved graph in a fresh browser, validate the entry state, replay a
stable path to an eligible frontier, and continue with a new-step budget.
Failed/inflight attempts require exact `--resume-retry-action` authorization;
cookies, localStorage, and browser processes are not restored, and unstable
replay targets fail closed. The generic execution-event trace preserves
repeated attempts while the compact graph remains independently loadable.

This layer is practical glue. Keep it from growing into the source of graph or
planning semantics.

Main functions/classes:

- `run_web_kobe_exploration`
- `run_stagehand_exploration`
- `run_ecommerce_stagehand_step`
- `write_web_kobe_graph`
- `ecommerce_checkout_experiment_plan`

## Current Recommended Commands

```text
web-kobe-explore
web-kobe-stagehand-explore
web-kobe-ecommerce-stagehand-smoke
web-kobe-domain-from-graph
web-kobe-pddl-from-graph
web-kobe-pddl-smoke
web-kobe-safesym-smoke
```

Debug helpers:

```text
web-kobe-graph
web-kobe-pddl
```

## Important Data Flow

```text
WebKobeExplorer.explore_one_step
  -> adapter.observe_state
  -> adapter.list_interactables
  -> SemanticAssistor.describe_state
  -> GraphManager.identify_or_add_node
  -> optional embedding source match
  -> optional summarize_visual_affordances
  -> local selection of one VLM-proposed business action
  -> adapter.execute
  -> capture after state/screenshots when execution succeeds or the known
     Stagehand tool_choice error is reported
  -> summarize_visual_delta (raw observation trace only) /
     verify_planning_delta
  -> GraphManager.build_planning_transition
  -> GraphManager.add_edge
  -> Raw Graph/evidence sidecar observation
  -> controller invokes the optional completed-step checkpoint
  -> real runner writes embedding, Stagehand trace, then graph/evidence
  -> normal completion writes `graph.meta.exploration_summary`
  -> planning abstraction groups raw observations and aggregates capabilities
  -> Phase A projector consumes planning graph
```

For `Thinking mode does not support this tool_choice`, the explorer continues
after-state observation. A URL/signature/visual change records a successful
transition; no change records `no_observed_change` while preserving the
original error and `backend_reported_success=false`. Unknown execution errors
remain failed self-loops and skip Visual Delta. New exploration does not
produce VLM `BusinessTransition` judgments; old fields remain load-compatible.

## Documentation Files

```text
docs/current-project-overview.md
docs/current-project-overview.zh-CN.md
  Current project direction and issues.

docs/project-decisions.zh-CN.md
  Project decision record. Update it after meaningful architecture or pipeline
  changes.

docs/project-structure.md
docs/project-structure.zh-CN.md
  Current pipeline, module boundaries, and major functions.

docs/safesym-bridge.md
  SafeSym bridge commands and experiment usage.
```
