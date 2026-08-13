# Profile Action Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 profile 中的动作契约约束业务事实晋升、候选执行顺序与 Minimal Semantic PDDL，使结账探索按正常业务流程进行。

**Architecture:** 在现有 `SemanticExperimentProfile` 中增加通用、可选的动作契约配置。Explorer、location candidate selector 和 semantic projection 读取同一配置；通用代码不出现站点 URL、selector 或购物动作分支。保持现有 Stagehand Agent、Visual Delta、图结构和 resume/replay 实现不变。

**Tech Stack:** Python 3.11、dataclasses、现有 Web-KOBE graph / Minimal Semantic PDDL pipeline。

## Global Constraints

- 这是小修改：不新增运行时模块，不做无关重构，不删除旧结构。
- 按用户要求不新增测试文件或测试用例；只运行现有相关测试和静态检查。
- 无 profile、没有动作契约、未知动作时保持原行为。
- profile 配置是当前阶段明确保留的配置型硬编码，通用执行代码不得识别购物领域名词。
- 实验输出必须区分 `profile_contract` 与 `observed_evidence` 来源。

---

### Task 1: 声明并传播动作契约

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/exploration_semantics.py`
- Modify only if public export is required: `src/ai_web_explorer/grounded_web/__init__.py`

**Interfaces:**
- Produce an immutable `ActionContract` with `required_facts`, `added_facts`, and `removed_facts` tuples.
- Add optional `action_contracts: Mapping[str, ActionContract]` to `SemanticExperimentProfile`.
- Add normalized lookup and JSON prompt/artifact serialization so consumers do not parse action-specific conditionals.

- [ ] **Step 1: Add the minimal contract data type and profile lookup**

Normalize action and fact IDs through the existing `normalize_semantic_id`. Reject or filter contract facts outside `business_fact_ids` when the profile is constructed/serialized; do not silently introduce new PDDL facts.

- [ ] **Step 2: Configure `practice_shopping_feasibility`**

Use exactly these contracts:

```text
add_to_cart: adds cart_has_items
view_cart: requires cart_has_items
complete_checkout_information: adds checkout_info_complete
complete_payment_information: adds payment_info_complete
place_order: requires cart_has_items, checkout_info_complete, payment_info_complete; adds order_submitted
```

- [ ] **Step 3: Ensure prompt/artifact context carries contracts**

`to_prompt_context()` must serialize contracts deterministically. Keep existing location, fact vocabulary and action-role fields intact. The already configured `allowed_locations` must remain available so Visual Delta can classify the successful submit surface as `confirmation` even before that location has appeared in the graph.

### Task 2: Apply contracts during exploration

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/location_exploration.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `src/ai_web_explorer/grounded_web/planning_fact_verifier.py`

**Interfaces:**
- Candidate selection consumes the current node's verified active business facts plus the optional profile contract.
- Fact verification consumes the executed canonical action ID plus its optional contract.

- [ ] **Step 1: Gate candidates without retiring them**

When a candidate has a contract whose `required_facts` are not all active and verified at the current node, skip it for this selection pass. Do not mark it stale, failed, attempted or terminal. Continue to another eligible candidate. Once preceding actions add the missing facts, the candidate becomes eligible automatically.

- [ ] **Step 2: Restrict business fact promotion per executed action**

For a contracted action, intersect VLM-proposed added/removed business facts with the contract's allowed added/removed sets before `verify_experiment_planning_delta()` promotes them. Contract facts are not created merely because they are declared: execution must succeed and Visual Delta must still report a matching observable change with nonempty evidence.

This must make `view_cart` retain its location transition and `cart_has_items` state while rejecting `checkout_info_complete` and `payment_info_complete` as new effects.

- [ ] **Step 3: Preserve generic behavior**

When the profile has no contract for the action, keep the current vocabulary/evidence verification behavior. Resume/replay must not synthesize contract effects and must remain graph-neutral.

### Task 3: Compile the same contracts into Minimal Semantic PDDL

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/semantic_planning.py`
- Modify only if needed to preserve the profile context in compact artifacts: `src/ai_web_explorer/safesym_bridge/graph_artifacts.py`

**Interfaces:**
- Semantic projection reads serialized profile contracts from the graph artifact.
- Contract requirements/effects augment only the matching observed semantic action.

- [ ] **Step 1: Add contract requirements to projected actions**

For each included observed action, union the matching contract's `required_facts` into PDDL preconditions. Record their provenance as `profile_contract`. Do not require the facts to have been active on an earlier incorrectly modeled edge; the contract is explicit profile knowledge.

- [ ] **Step 2: Bound projected business effects**

For contracted actions, only observed and verified facts allowed by `added_facts`/`removed_facts` may appear as effects. Do not synthesize an effect when the action did not successfully verify it.

- [ ] **Step 3: Preserve location effects**

Continue using the observed semantic source/target location. Ensure Visual Delta receives the full profile `allowed_locations`, so a successful `place_order` observation can select `confirmation`; do not hardcode that mapping in the compiler.

### Task 4: Verify and commit

**Files:**
- No new files except modifications above.

- [ ] **Step 1: Run existing focused tests without adding tests**

Run the existing tests covering semantic profiles, planning fact verification, location exploration, explorer behavior and semantic PDDL. Use the repository's `.venv` and `PYTHONPATH=src`. Report exact pass/fail counts.

- [ ] **Step 2: Run repository checks**

Run `git diff --check` and inspect the complete diff for site-name/action-name branches outside the profile configuration. Confirm no generated experiment artifacts are staged.

- [ ] **Step 3: Commit the implementation**

Commit only the scoped implementation with a concise message such as:

```text
feat: gate semantic actions with profile contracts
```

- [ ] **Step 4: Handoff for independent review**

Report the commit hash, modified files, focused test output, and any known limitation. Do not run a paid real-site experiment; the parent review session will decide whether to run it.
