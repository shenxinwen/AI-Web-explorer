# Location Candidate Dependency MVP — clean Stage B

## Scope

This branch is a clean offline migration of formal MVP Tasks 1–4 from
main commit 334e1d5ee260dba0e10911901e4014610655384f. It does not run live
Practice Shopping, OpenAI API calls, SafeSym, a browser, checkout, or order
submission. Plan Task 5 (live acceptance) is intentionally not started.

Worktree: D:\GitHUb\ai-web-explorer-main\.worktrees\location-candidate-dependency-mvp
Branch: codex/location-candidate-dependency-mvp

## Commits

1. e8fe8da — feat: parse minimal VLM action dependencies
2. 353df22 — feat: schedule location candidates by dependencies
3. dee8e79 — feat: observe minimal action outcomes
4. 8082e82 — feat: compile verified action dependencies to PDDL
5. 864703a — test: preserve legacy affordance read compatibility
6. b4ca8b8 — fix: keep initial action prompts profile independent
7. 492e360 — docs: report clean location dependency MVP migration
8. 495f938 — docs: list final migration report commit
9. 1280d4f — fix: scope completion predicates by location
10. 66f1388 — fix: fail closed on missing action prerequisites
11. 9d85caa — fix: preserve failed outcome precedence over navigation
12. 98be609 — fix: allow visible workflow prerequisite inference
13. fc9571b — fix: require actions array for initial scans
14. d079311 — test: align legacy scans with initial action contract
15. 16ea52e — test: use actions contract in active scan fixture

Commits 10–13 are the four requested review fixes, each implemented with a
focused RED/GREEN test cycle. Commits 14–15 only update legacy/active test
fixtures to exercise the resulting parser contract; they add no runtime
module or unrelated refactor.

## Implemented behavior

- Initial active scans use flat actions records with only action_id,
  description, target, and requires. Duplicate, self, dangling, and cyclic
  dependencies fail closed.
- requires is persisted in location candidate memory. Candidates are
  scheduled only after every required candidate has a successful status;
  failed terminal requirements recursively block dependents.
- Executed-action observation uses exactly outcome, location_change, and
  evidence. Success is converted locally to a coarse SemanticObservation;
  failed and uncertain outcomes are not projectable.
- The active outcome path uses an initial scan at a newly observed location
  and bypasses targeted/supplement scans. Legacy response reading remains
  only as a low-cost compatibility path.
- Successful dependency actions produce completed_<location>_<action>
  predicates. Dependent actions receive those predicates as required facts,
  and Minimal Semantic PDDL therefore cannot execute a dependent first.
- For a location change, the final semantic location is shared by the edge
  observation, target node hint, current pointer anchor, and candidate pool
  key. If the coarse page hint equals the source, the target node ID is used
  as the stable fallback.
- A dependent edge is fail-closed when any same-location required action lacks
  a projectable successful edge. The projection report records
  missing_successful_required_action and the missing action IDs, so a missing,
  failed, or non-projectable prerequisite cannot create a dependent shortcut.
- When a three-field action outcome exists, failed and uncertain take priority
  over node, URL, or signature changes and remain non-projectable. Only a
  successful outcome with location_change=true can become navigation; a
  successful unchanged-location outcome is still projectable as succeeded.
- Initial dependency prompts allow direct inference from visible required
  fields, disabled controls, labels, and visible workflow structure, including
  clearly shown login or checkout steps. They reject dependencies based on
  undisplayed site capabilities or a complete typical workflow and retain
  requires=[] for independent actions.
- Active initial parsing now requires a top-level actions array. regions and
  business_affordances are not initial fallbacks; their read compatibility is
  limited to non-initial legacy scans.
- OpenAI visual provider default is gpt-4o-mini; environment variables and
  explicit model arguments retain precedence. DeepSeek/Stagehand response
  parsing was not changed.
- Initial action prompts do not include profile context, contracts, workflow
  answers, or site-specific action tokens. A generic hardcoded-token scan of
  added production lines was empty.
- Follow-up causal correction: completion facts are keyed by
  (source_location, action_id), so same-named actions at other locations
  cannot satisfy a dependency. Every projectable successful action now gets
  its own location-qualified completion fact, including independent actions;
  failed, uncertain, and non-projectable edges do not.

## Offline verification

Using the existing D:\GitHUb\ai-web-explorer-main\.venv with PYTHONPATH
pointing at this worktree:

- Focused files: test_business_affordance.py 21 passed; test_semantic_planning.py
  19 passed; the web explorer focused suite is included in the SafeSym total
  below. All focused dependency, outcome, parser, and semantic/PDDL tests
  passed.
- tests/safesym_bridge: 591 passed, 4 skipped, 2 warnings.
- Full pytest -q in the sandbox: 594 passed, 4 skipped, 1 failed.
  The sole failure was the browser fixture launch:
  tests/test_local_shop_fixture.py::test_local_shop_fixture_supports_cart_state_changes
  with Playwright BrowserType.launch: spawn EPERM. The same test was then
  rerun with controlled permission and passed: 1 passed in 3.03s.
- git diff --check main...HEAD: passed.

The correction was TDD-verified: the two new semantic-planning regression
tests failed before the implementation change and passed afterward.

## Diff and files

Implementation diff relative to main (including this report):

    17 files changed, 1821 insertions(+), 137 deletions(-)

Changed files:

- src/ai_web_explorer/grounded_web/action_outcome.py
- src/ai_web_explorer/grounded_web/business_affordance.py
- src/ai_web_explorer/grounded_web/explorer.py
- src/ai_web_explorer/grounded_web/graph.py
- src/ai_web_explorer/grounded_web/graph_manager.py
- src/ai_web_explorer/grounded_web/location_exploration.py
- src/ai_web_explorer/grounded_web/openai_visual_delta.py
- src/ai_web_explorer/grounded_web/semantic_planning.py
- src/ai_web_explorer/safesym_bridge/browser_runner.py
- src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py
- tests/safesym_bridge/test_action_outcome.py
- tests/safesym_bridge/test_business_affordance.py
- tests/safesym_bridge/test_location_exploration.py
- tests/safesym_bridge/test_location_scoped_feasibility_pipeline.py
- tests/safesym_bridge/test_semantic_planning.py
- tests/safesym_bridge/test_web_kobe_explorer.py

Excluded from this clean branch: old v0/v1/v2/v3 reports, frozen screenshot
evaluators, transition-prompt experiments, runtime observations/raw outputs,
and all old experimental commits/files from the prior validation branch.

## Live acceptance matrix

| Acceptance item | Status |
|---|---|
| Initial four-field candidate contract | Offline PASS |
| Dependency persistence and scheduling | Offline PASS |
| Failure propagation | Offline PASS |
| Strict three-field action outcome | Offline PASS |
| Successful coarse semantic projection | Offline PASS |
| Failed/uncertain exclusion | Offline PASS |
| Same-page-type location consistency | Offline PASS |
| Dependency completion predicates and Minimal PDDL | Offline PASS |
| Practice Shopping live/API/browser/SafeSym validation | Not run by design |

No live result, credential, endpoint, or website availability claim is made
from this branch.
