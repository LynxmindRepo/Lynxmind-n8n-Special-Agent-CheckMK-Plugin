# Checkmk n8n Special Agent

Checkmk extension package (MKP) that monitors an [n8n](https://n8n.io) instance
through its public REST API and its Prometheus `/metrics` endpoint.

* **Package name:** `n8n`
* **Version:** 2.0.0
* **Requires:** Checkmk 2.5.0 or newer
* **License:** GPL-2.0

## What it monitors

The special agent emits eleven agent sections, from which the following
services are discovered:

| Service | What it reports |
| --- | --- |
| `n8n Health` | `/healthz` reachability and response time |
| `n8n Readiness` | `/healthz/readiness` reachability and response time |
| `n8n API Endpoints` | How many of the 13 collected endpoints answered |
| `n8n System Info` | Platform, agent version, collection timestamp |
| `n8n Heap` | Heap used, heap fill ratio, old/new space sizes |
| `n8n GC` | Garbage collection counts and durations by kind |
| `n8n Runtime` | File descriptors, event loop lag, active handles/resources |
| `n8n Workflows` | Totals, active/inactive split, average complexity |
| `n8n Workflow <name>` | One service per workflow: executions, success rate, failures, complexity |
| `n8n Failed Runs` | Failure counts and global success rate over 24h/8h |
| `n8n Users` | Total, active and pending users |
| `n8n Tags` | Number of tags defined |
| `n8n Projects`, `n8n Variables` | Only on n8n editions that expose these endpoints |

74 metrics, 22 graphs and one perfometer are defined.

## Installation

Upload `n8n-2.0.0.mkp` under *Setup → Extension packages*, or from the command
line as the site user:

```bash
mkp add n8n-2.0.0.mkp && mkp enable n8n 2.0.0
```

Then create the host and the rule:

1. Add a host for the n8n instance with the agent tag set to
   **API integrations, no Checkmk agent**.
2. *Setup → Agents → Other integrations → Applications → **n8n Monitor via API***
   (ruleset `special_agents:agent_n8n_monitor`). Set the base URL and an n8n
   API key, and tick the collections you want.
3. Run a service discovery and activate the changes.

### Creating the n8n API key

In n8n: *Settings → n8n API → Create an API key*. The key is sent as the
`X-N8N-API-KEY` header.

## Configuration rulesets

| Ruleset | Service |
| --- | --- |
| `n8n Monitor via API` (special agent) | Which endpoints to collect, URL, credentials, timeout, TLS |
| `n8n Workflows Monitoring` | Total and inactive workflow levels |
| `n8n Workflow Item Monitoring` | Per workflow: success rate, failed executions, 24h levels |
| `n8n Failed Runs` | Failures in 24h, global success rate |
| `n8n API Endpoints` | State to report when an endpoint is unreachable |
| `n8n Heap Monitoring` | Heap used, heap fill ratio, old/new space |
| `n8n Garbage Collection Monitoring` | GC duration levels |
| `n8n Runtime Monitoring` | File descriptors, event loop lag, handles, resources |

Only `n8n Workflow Item Monitoring` takes a service item (the workflow name);
every other ruleset applies per host.

## Notes and known limits

* **Community edition returns 403** for `variables`, `projects`, `credentials`
  and `webhooks`. The FAIL that `n8n API Endpoints` reports for these is
  legitimate, not a bug — untick them in the rule if the noise bothers you.
* **`heap_percent` ships without levels.** It is `heap_used / heap_size_total`,
  that is, how full the heap V8 has *currently allocated* is — not how close
  the process is to its heap limit. V8 keeps that ratio high on purpose, so a
  healthy n8n sits at 80–95% and any default level fires constantly.
  prom-client does not export `nodejs_heap_size_limit_bytes`, so the ratio
  cannot be rebased onto the real ceiling. The absolute `heap_used` is what
  alerts by default.
* **The API key is passed on the command line.** The agent has no password
  store support, so `Secret.unsafe()` is used. The key is therefore visible in
  the process table of the monitoring site.
* **Execution history is filtered by an activation timestamp** stored under the
  site's `var` directory, so statistics start at the moment the plugin was
  first run rather than including pre-existing history.

## Repository layout

```
n8n_cmk/
  agent_based/        check plugins and section parsers
  graphing/           metric, graph and perfometer definitions
  libexec/            agent entry point invoked by the server side call
  rulesets/           WATO rulesets (special agent + check parameters)
  server_side_calls/  special agent command construction
  special_agents/     the agent itself
packaging/manifest.template   MKP manifest, version substituted at build time
scripts/build.sh              deploy sources into a site and build the MKP
```

## Building

Run as the site user on a Checkmk 2.5 site:

```bash
./scripts/build.sh
```

It copies the sources into `local/lib/python3/cmk_addons/plugins/`, byte
compiles them, and calls `mkp package` with the version from `VERSION`. The
resulting file lands in `var/check_mk/packages_local/`.

After installing a new version, remove the previous one and restart the core —
the CMC helper processes keep the old Python modules in memory until then:

```bash
mkp disable n8n <old> && mkp remove n8n <old>
cmk -II <host> && cmk -R
```
