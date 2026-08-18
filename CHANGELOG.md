# Changelog

## 2.1.2 — 2026-08-18

Correctness pass over the checks and the agent. No new services.

### Fixed

* **Hardcoded service states.** The workflow item check raised WARN for any
  historical failure and CRIT for any error execution, and the summary check
  derived WARN/CRIT from the share of active workflows — all of it independent
  of the configured levels, so the rulesets barely affected the service state.
  Both now use `check_levels`; the status line is informational and every
  WARN/CRIT comes from a level. `total_executions_24h` was read from the
  params but never evaluated; it is now.
* **Fabricated data while n8n is unreachable.** The failed-runs and
  workflow-executions analyses returned `available: True` with zeroed counters
  and a 100% success rate when the executions endpoint could not be read, so a
  dead n8n looked like "no failures". They now distinguish a failed fetch from
  a genuinely empty result, report the endpoints as FAIL, and omit the
  sections so the services go stale instead.
* **Perfdata carried no thresholds.** Levels are now attached to the metrics,
  so the graphs show where warn/crit sit.
* **Doubled metric prefix.** Prometheus names already start with `n8n_`, and
  the checks prefixed them again, producing `n8n_n8n_nodejs_gc_duration_...`.
  Fixed in the checks and in the graphing definitions. **This renames metrics:
  the RRD history of the old `n8n_n8n_*` names is not carried over.**
* **`heap_percent` alerted constantly.** It is the fill ratio of the heap V8
  has currently allocated, which V8 keeps high by design; the 80/90 defaults
  fired on a healthy instance. It now ships without levels — the absolute
  `heap_used` is the default alerting signal — and the output says "% of
  allocated heap" so it is not read as headroom.
* **Inconsistent success rate for workflows with no executions.** The lifetime
  rate defaulted to 0 while the 24h and 8h rates defaulted to 100. All are 100
  now, and the check skips the success-rate levels when nothing has run.
* **Workflow names reported as `unknown`.** The executions endpoint is queried
  with `includeData=false` and carries no `workflowData.name`. The agent now
  keeps an id-to-name map from the workflows endpoint and resolves through it.
* **`n8n Failed Runs` could never alert.** It had empty default parameters, so
  it stayed OK until someone wrote a rule. The defaults now mirror the
  ruleset's prefills (10/50 failures, 95/80% success rate).
* **Meaningless service item in WATO.** `n8n_gc`, `n8n_heap_usage`,
  `n8n_runtime` and `n8n_workflows` are itemless checks whose rulesets used
  `HostAndItemCondition`, so the rule editor asked for an item and showed
  `'None'`. They use `HostCondition` now. `n8n_workflow_item` keeps its item,
  retitled "Workflow name".
* **Non-standard CLI options.** The agent took `-url`, `-api-key`,
  `-user` and `-api-password` with a single dash. Double-dash spellings are
  now the primary form; the old ones remain as aliases.

### Also changed

* Organisational hints (low tag coverage, more inactive than active
  workflows, high average node count) are notices instead of WARNs.

## 2.1.1

Migration to Checkmk 2.5 and repair of the pre-existing plugin. See the
package history for details:

* `SimpleLevels` parameters (`("fixed", (w, c))`) were unpacked directly by the
  checks, raising `TypeError` for active workflows.
* `failed_executions_24h` was used before assignment.
* The graphing definitions still imported `cmk.gui.plugins.metrics`, removed
  before 2.4; rewritten against `cmk.graphing.v1`.
* `check_healthz()` / `check_readiness()` were defined but never called, and
  `results['executions']` was never populated, so those sections were never
  emitted and the endpoints always reported FAIL.
* `response_time` recorded an absolute timestamp instead of the elapsed time.
* The special agent ruleset gained the `healthz`, `readiness`, `executions`,
  `users`, `tags`, `failed_runs` and `workflow_executions` toggles, and checks
  were added for the sections that had none.
