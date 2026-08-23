# Project Structure

This file records the active project structure. Keep it synchronized with
`docs/project-structure.zh-CN.md` when pipeline boundaries or module ownership
change.

## Active Direction

The repository is centered on SafeSym-oriented, location-scoped open exploration:

```text
browser observation + VLM initial scan
  -> LocationExplorationMemory stores actions and same-location requires
  -> local selection of an unfinished action whose requirements succeeded
  -> Stagehand executes one action
  -> screenshot outcome / location_change / evidence observation
  -> record a location-scoped completion fact and optional location transition
  -> initial scan after first reaching a new location
  -> reset + stored-action replay when another frontier must be restored
  -> checkpoint graph, location memory, and cumulative budgets
  -> SemanticPlanningGraph
  -> Minimal Semantic domain.pddl + problem.pddl
  -> SafeSym parse / solve
```

Browser execution remains forward along the current path, but the controller no
longer treats current-path exhaustion as the end of all exploration. It can select
another recoverable frontier and replay stored actions to restore that breakpoint.
Replay is restoration only: it must not modify graph content, candidate pools,
planning facts, scan state, or candidate attempt counts.

VLM output is a candidate hypothesis, Stagehand reports an execution attempt, and
after-action observation supplies verification evidence. A successful action is
deduplicated within its semantic location and unlocks explicitly dependent actions.
The active minimal path preserves the pool on the same page, scans each new location
once, and does not invoke targeted or supplement scans. Those mechanisms remain as
legacy compatibility code.

The planner-facing acceptance path is now `SemanticPlanningGraph -> Minimal
Semantic PDDL`, producing both `domain.pddl` and `problem.pddl`. Older Planning
Graph / Phase A, Location PDDL, and other projectors remain as compatibility or
historical paths rather than the current semantic acceptance standard.

The framework is not completely free of hardcoding. Cart structured-fact
shortcuts, the optional `ecommerce_checkout` BusinessFlowProfile, and the
controlled final-order URL remain explicit domain/experiment configuration. The
PDDL compiler, candidate memory, replay, and controller do not branch on
shopping-specific action or location names.

Semantic experiment profiles and action contracts are no longer runtime paths.
Candidate discovery uses a profile-free action-dependency response; the optional
BusinessFlowProfile is consumed locally for structured verification and planning
projection rather than injected into VLM prompts.

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
- `src/ai_web_explorer/grounded_web/exploration_semantics.py`
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

The optional BusinessFlowProfile defines structured fact predicates for local
verification and planner-facing projection. It is not a closed VLM vocabulary and
is not injected into Visual Affordance or Visual Delta. Raw visual responses remain
in the edge trace, while only locally verified structured facts enter the planning
state. A technical state label does not define graph identity or PDDL facts.

The active location-scoped boundary is that Visual
Affordance discovers concrete actions and same-location `requires` links without
concrete profile facts, action examples, contracts, expected flow, or the PDDL
goal. After-action observation returns only `outcome`, `location_change`, and
short visible evidence. The local runtime generates stable completion predicates
for successful actions. The new path bypasses targeted and supplement scans and
does not ask the VLM to emit planner-facing facts.

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
- `src/ai_web_explorer/grounded_web/location_exploration.py`

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
- retain raw Visual Delta responses and validation traces in
  `execution_trace.metadata.visual_delta_trace`; only accepted semantic
  observations and verified planning facts enter the active semantic projection;
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
- `src/ai_web_explorer/grounded_web/frontier_replay.py`
- `src/ai_web_explorer/grounded_web/location_exploration.py`

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
- maintain a fixed candidate pool per semantic location and track success,
  retry, stale, and no-change by `(location, action)`;
- run one initial action/dependency scan for a new location and bypass targeted
  and supplement scans on the active minimal path;
- select another recoverable frontier when the current pool is exhausted and
  restore it through reset plus stored-action replay;
- validate only the final semantic location and required business facts during
  replay, without exact per-raw-node gates or graph mutation;
- stop under formal-action, consecutive-no-progress, candidate-retry,
  per-frontier replay, and total-replay limits;
- checkpoint graph, location memory, cumulative budgets, and replay metrics so
  `--resume-graph` can continue in a fresh browser.

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
- `LocationExplorationMemory`
- `LocationExplorationCoordinator`
- `FrontierReplayRunner.replay`
- `select_frontier`

### PDDL Mapping And SafeSym Bridge

Owns planner-facing projection and validation.

Main modules:

- `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`
- `src/ai_web_explorer/safesym_bridge/web_kobe_safesym_smoke.py`
- `src/ai_web_explorer/grounded_web/semantic_planning.py`
- `src/ai_web_explorer/safesym_bridge/minimal_semantic_pddl.py`
- `src/ai_web_explorer/safesym_bridge/cli.py`

Main responsibilities:

- load `WebKobeGraph` JSON;
- build a `SemanticPlanningGraph` that separates location, capability, and
  business facts from successful raw edges;
- generate Minimal Semantic `domain.pddl` and `problem.pddl`;
- retain older Phase A / Location PDDL as compatibility and fallback paths;
- run PDDL readiness checks;
- run SafeSym parser, safety injection, and planner smoke checks.

This layer is deterministic and does not call LLM/VLM. The active minimal path
emits a location-scoped completion fact for each successful action; only an
explicit same-location `requires` link promotes the referenced completion fact
to another action's precondition. Unrelated completion facts are not promoted.
The optional BusinessFlowProfile may supply verified structured facts locally;
semantic experiment profiles and action contracts are not runtime dependencies.
Failed, conflicting, or semantically unusable edges are excluded with
projection-report reasons.

Main functions/classes:

- `load_web_kobe_graph_json`
- `compile_web_kobe_graph_to_domain`
- `compile_web_kobe_graph_to_pddl`
- `write_web_kobe_pddl_smoke`
- `write_web_kobe_safesym_smoke`
- `build_semantic_planning_graph`
- `compile_minimal_semantic_domain`
- `compile_minimal_semantic_problem`
- `main`

### Experiment Runtime

Owns CLI-facing experiment setup.

Main modules:

- `src/ai_web_explorer/safesym_bridge/browser_runner.py`

Main responsibilities:

- launch Playwright;
- configure Stagehand;
- configure VLM and embedding providers;
- wire optional business-profile/test context;
- write graph, trace, screenshot, embedding, PDDL, and smoke outputs;
- checkpoint embeddings and Stagehand trace before committing the graph/evidence
  pair after each completed action;
- write the final `graph.meta.exploration_summary` (`requested_steps`,
  `steps_completed`, and `stop_reason`) after normal completion.

`graph.json` is the compact, independently loadable Raw Graph; detailed execution
evidence is resolved through `graph_evidence.json`. The checkpoint keeps the
embedding, trace, graph, and evidence artifacts paired after each completed
action. Active SemanticPlanningGraph and Minimal Semantic PDDL consume verified
semantics from the graph rather than inventing facts from the sidecar.
`raw_graph.json`, the older `planning_graph.json`, and
`planning_abstraction_report.json` remain compatible audit artifacts.

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
- `write_web_kobe_graph`

## Current Recommended Commands

```text
web-kobe-stagehand-explore      # active VLM/Stagehand open exploration
web-kobe-explore                # deterministic Playwright graph smoke
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

The active minimal dependency path is:

```text
WebKobeExplorer.explore_one_step
  -> adapter.observe_state
  -> adapter.list_interactables
  -> SemanticAssistor.describe_state
  -> GraphManager.identify_or_add_node
  -> optional embedding source match
  -> one initial summarize_visual_affordances scan per new location
  -> LocationExplorationMemory stores actions and same-location requires
  -> local selection of one unfinished action whose requirements succeeded
  -> adapter.execute
  -> capture after state/screenshots when execution succeeds or the known
     Stagehand tool_choice error is reported
  -> minimal outcome/location_change/evidence observation
  -> GraphManager.build_planning_transition
  -> GraphManager.add_edge
  -> LocationExplorationCoordinator records outcome and completion state
  -> select_frontier + FrontierReplayRunner when the current path is exhausted
  -> Raw Graph/evidence sidecar observation
  -> controller invokes the optional completed-step checkpoint
  -> real runner writes embedding, Stagehand trace, then graph/evidence
  -> normal completion writes `graph.meta.exploration_summary`
  -> build_semantic_planning_graph
  -> compile_minimal_semantic_domain / compile_minimal_semantic_problem
  -> SafeSym parse / solve
```

The legacy compatibility path may still merge targeted/supplement candidates
and call Visual Delta plus the structured planning-fact verifier. It is not the
active minimal dependency flow above.

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
