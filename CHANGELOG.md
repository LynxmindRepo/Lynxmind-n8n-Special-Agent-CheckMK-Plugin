# Changelog

## 2.0.1 — 2026-08-21

* **Executions were silently capped at ~250.** `/api/v1/executions` returns
  newest-first and n8n caps `limit` at 250 server-side no matter what is
  requested. A single unpaginated request was all every section derived from
  executions ever saw, so any instance running more than ~250 executions
  since the agent was first activated had its 24h/8h stats, failure counts
  and "recent failures" list silently frozen at whatever fit on that one
  page. Reported by a user running 10-12 workflows at 1-5 minute intervals
  (3,000+ executions/day).

  Fixed with a shared paginating fetch that follows n8n's `nextCursor` until
  it runs out, or until a page's oldest execution predates the agent's
  activation timestamp - whichever comes first, so a fresh install doesn't
  page needlessly. A 50-page (~12,500 execution) safety cap prevents runaway
  API calls; past that the run logs a warning and reports on what it did
  fetch rather than hang. That cap is a known, deliberate ceiling, not a
  full fix: because "since activation" stats are recomputed from a full
  re-fetch every run rather than an incrementally persisted counter, an
  instance old enough to have accumulated more than ~12,500 executions since
  its agent was first activated will still see truncated lifetime totals.
  24h/8h stats are unaffected at any age, since they only need a shallow
  page of recent history.

## 2.0.0 — 2026-08-18

Correctness pass over the checks and the agent. No new services.

> The package was renumbered at this release: the work described below
> was previously published as 2.1.2. Entries under it keep their original
> numbers, so this heading sorts below them.

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

Migration to Checkmk 2.5 and repair of the pre-existing plugin — the first
release that does not run on 2.4. Everything below is what 1.0.1 got wrong;
see [docs/checkmk-2.4.md](docs/checkmk-2.4.md) for the 2.4 build itself.

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
