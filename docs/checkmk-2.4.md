# The Checkmk 2.4 build (1.0.1)

The `main` branch targets **Checkmk 2.5** and will not load on 2.4: it is
built against `cmk.graphing.v1` and the 2.5 rulesets API. The last release
that ran on 2.4 is **1.0.1**, packaged with and declaring
`version.min_required = 2.4.0p15`.

This page records what that build does, what it does not do, and what to
expect when moving off it. It is documentation only — the 1.0.1 sources are
not in this branch.

## What 1.0.1 contains

20 files, against 25 on `main`. It discovers eight services:

| Service | Notes |
| --- | --- |
| `n8n Workflows` | Totals, active/inactive split, complexity |
| `n8n Workflow <name>` | One per workflow |
| `n8n Heap` | Heap used, fill ratio, old/new space |
| `n8n GC` | Collection counts and durations |
| `n8n Runtime` | File descriptors, event loop lag, handles, resources |
| `n8n System Info` | Platform and agent version |
| `n8n Projects`, `n8n Variables` | 403 on the Community edition |

## Known problems in 1.0.1

These are the reasons the 2.5 line exists, not regressions introduced by it.
Anyone still on 2.4 should know about them.

* **Graphing does not work.** The four graphing files import
  `cmk.gui.plugins.metrics`, an API removed before 2.4. Nothing is rendered
  and no metric definitions are registered.
* **Six agent sections have no check.** The agent emits `n8n_healthz`,
  `n8n_readiness`, `n8n_api_status`, `n8n_failed_runs`, `n8n_users` and
  `n8n_tags`, but no plugin consumes them, so health, readiness, endpoint
  status, failure analysis, users and tags are collected and discarded.
* **`check_healthz()` and `check_readiness()` are never called.** They are
  defined but unreachable, so `n8n_api_status` always reports `healthz;FAIL`
  even against a healthy instance.
* **`results['executions']` is never populated**, so the executions endpoint
  is reported as failed and `n8n_executions` is never emitted.
* **`SimpleLevels` parameters crash the check.** The ruleset hands the check
  `("fixed", (warn, crit))`, which the code unpacks directly as a pair of
  numbers. Any configured level raises
  `TypeError: '<' not supported between instances of 'float' and 'tuple'`.
  It only triggers on the active-workflow branch, so it can stay hidden until
  a workflow is activated.
* **`failed_executions_24h` is used before assignment**, raising
  `UnboundLocalError` when the 24h rule is configured.
* **`response_time` stores an absolute timestamp** instead of the elapsed
  time.
* **The ruleset exposes only four collection toggles** (`metrics`,
  `workflows`, `variables`, `projects`). The agent supports `healthz`,
  `readiness`, `executions`, `users`, `tags`, `failed_runs` and
  `workflow_executions` as well, but they cannot be reached from the GUI.
* **The agent CLI uses single-dash long options** (`-url`, `-api-key`).

## Moving from 1.0.1 to the 2.5 line

Both packages are named `n8n`, so the site holds one at a time.

```bash
mkp disable n8n 1.0.1 && mkp remove n8n 1.0.1
mkp add n8n-2.0.1.mkp && mkp enable n8n 2.0.1
cmk -II <host> && cmk -R
```

Points to check afterwards:

* **Six new services appear** (`n8n Health`, `n8n Readiness`,
  `n8n API Endpoints`, `n8n Failed Runs`, `n8n Users`, `n8n Tags`), so a
  rediscovery is required rather than optional.
* **Existing rules survive.** The ruleset names are unchanged, and the 2.5
  build normalizes the `SimpleLevels` shapes that used to crash, so rules
  written for 1.0.1 start working rather than breaking.
* **`n8n Failed Runs` alerts out of the box** on the 2.5 line — 10/50
  failures in 24h and a 95/80% success rate — where 1.0.1 had no such
  service at all.
* **Graphs start from zero.** 1.0.1 registered no metrics, so there is no
  RRD history to carry over.

## Maintaining 1.0.1

There is no branch for it in this repository. If a fix is ever needed for a
site that cannot move to 2.5, restore the sources from the packaged MKP:

```bash
tar xzf n8n-1.0.1.mkp cmk_addons_plugins.tar
tar xf cmk_addons_plugins.tar
```

Bear in mind that the graphing files would have to be rewritten against
`cmk.graphing.v1` for the graphs to work at all — which is most of what
separates 1.0.1 from the current line.
