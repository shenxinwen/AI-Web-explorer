# E003 / C1 results

Gold labels are the human-confirmed C1 annotations for SauceDemo v1 and
Practice Shopping v4. Knowledge is aggregated across runs by
`site + semantic_location + canonical_action_id`.

## Frozen inputs

- SauceDemo: `outputs/paper/formal/E003_c1_v1/saucedemo/run_01..03`
- Practice Shopping: `outputs/paper/formal/E003_c1_v4/practice_shopping/run_01..03`
- SauceDemo gold: `annotation_package_saucedemo_v2/saucedemo/c1_annotations_codex_initial.csv`
- Practice Shopping gold: `annotation_package_practice_shopping_v4/practice_shopping/c1_annotations_ai_initial.csv`
- Both AI initial-label files were reviewed and confirmed by the human reviewer.
- Confirmed archival copies are stored in `gold/saucedemo.csv` and
  `gold/practice_shopping.csv`.

## Main results

| Method | Admitted | Precision | Supported retention | Admission yield | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Proposal-as-fact | 45 | 73.33% | 100.00% | 100.00% | 84.62% |
| Executor-success-as-fact | 40 | 82.50% | 100.00% | 88.89% | 90.41% |
| Evidence-grounded admission | 33 | 96.97% | 96.97% | 73.33% | 96.97% |

Evidence-grounded admission removes most unsupported knowledge while retaining
32 of 33 human-supported functions. The remaining false negative and false
positive are both in SauceDemo. Practice Shopping has 51/55 evidence-complete
attempts; incomplete attempts remain in the artifacts and are not admitted by
the evidence-grounded rule.

| Site | Candidates | Supported | Attempts | Complete evidence |
| --- | ---: | ---: | ---: | ---: |
| SauceDemo | 26 | 17 | 48 | 48/48 |
| Practice Shopping | 19 | 16 | 55 | 51/55 |
| Total | 45 | 33 | 103 | 99/103 |

## Error analysis

- Evidence-grounded false positive: SauceDemo
  `checkout_information_form + complete_information_fields`. The verifier
  admitted the function although the grouped human evidence did not directly
  show all required fields completed.
- Evidence-grounded false negative: SauceDemo
  `product_catalog + sort_products`. Human review found at least one attempt
  with a visible ordering change, but the system did not admit the aggregated
  function.
- Practice Shopping `view_cart` includes the known narrow-expected-outcome
  case: the site correctly opens checkout directly. Human gold treats the core
  function as successful. Cross-run aggregation still admits the function.
- Practice Shopping `filter_by_price` attempts failed or lacked complete after
  evidence and therefore remain rejected rather than becoming repeated
  knowledge entries.

## Downstream self-check

- All three Practice Shopping runs produced semantic PDDL domains.
- Run 02 and Run 03 produced base and SafeSym plans to
  `place_order_succeeded`.
- Run 01 could plan to `view_cart_succeeded`, but not to
  `place_order_succeeded`, because its only transition into the checkout form
  came from the automatically rejected narrow-expected-outcome attempt.
- No configured SafeSym safety rule matched these projected actions, so this
  check demonstrates parser/injection/planner compatibility, not a substantive
  safety intervention result.

## Reproduction

Run `python scripts/paper/analyze_c1.py` from the repository root. It rebuilds
`c1_metrics.json` from the frozen graphs, evidence artifacts, and confirmed
gold labels. The JSON also records per-method false-positive and false-negative
knowledge keys.
