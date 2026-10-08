"""Self-check for the n8n GC check: it alerts on the GC rate, not the lifetime sum.

``n8n_nodejs_gc_duration_seconds_sum`` is a Prometheus counter. It holds the
GC time accumulated since the n8n process started and can only grow, so it
says nothing about the current load until two samples are compared.

The check is exercised against the real ``cmk.agent_based.v2`` API, so this
needs the Python environment of a Checkmk 2.5 site. Run as the site user:

    python3 tests/test_gc_rate.py

No framework: asserts raise on failure.
"""
import sys
from pathlib import Path

try:
    from cmk.agent_based.v2 import IgnoreResultsError, Metric, Result, State
except ImportError:
    print("SKIPPED: cmk.agent_based.v2 is not importable - run as the site user of a Checkmk 2.5 site")
    sys.exit(0)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from n8n_cmk.agent_based import n8n_gc  # noqa: E402
from n8n_cmk.agent_based.n8n_metrics import parse_n8n_metrics  # noqa: E402

T0 = 1_791_480_000.0
MINUTE = 60.0


def _section(minor, major, incremental=None, collections=4438):
    """Build the section the way Checkmk does: agent lines through the parser."""
    lines = [
        ["version;v2.1.0"],
        ["memory_mb;455.07"],
        ["heap_percent;90.09"],
        ["eventloop_lag_ms;2.31"],
        [f"gc_total;{collections}"],
        ["active_resources;12.0"],
        [f"n8n_nodejs_gc_duration_seconds_sum_kind_minor;{minor}"],
        [f"n8n_nodejs_gc_duration_seconds_sum_kind_major;{major}"],
    ]
    if incremental is not None:
        lines.append([f"n8n_nodejs_gc_duration_seconds_sum_kind_incremental;{incremental}"])
    return parse_n8n_metrics(lines)


def _default_params():
    return dict(n8n_gc.check_plugin_n8n_gc.check_default_parameters)


def _check(store, now, params=None, **sums):
    params = _default_params() if params is None else params
    return list(n8n_gc.check_n8n_gc_testable(params, _section(**sums), store, now))


def _prime(store, now, **sums):
    """Record a first sample. Whether it yields a verdict is tested separately."""
    try:
        _check(store, now, **sums)
    except IgnoreResultsError:
        pass


def _state(results):
    return State.worst(*(r.state for r in results if isinstance(r, Result)))


def _metric(results, name):
    found = [m for m in results if isinstance(m, Metric) and m.name == name]
    assert len(found) == 1, f"expected exactly one metric {name!r}, got {found!r} in {results!r}"
    return found[0]


def _close(actual, expected):
    return abs(actual - expected) < 1e-6


def test_healthy_long_running_process_is_ok():
    # Ten hours of uptime: 8.5 s of minor and 6.4 s of major GC in total.
    # In the last minute GC took 26 ms, i.e. 0.04 % of the time.
    store = {}
    _prime(store, T0, minor=8.530, major=6.447, incremental=0.399)
    results = _check(store, T0 + MINUTE, minor=8.545, major=6.458, incremental=0.399)
    assert _state(results) is State.OK, results


def test_reports_share_of_wall_clock_time():
    # +0.6 s minor and +0.3 s major within 60 s: 1.0 % + 0.5 % = 1.5 %.
    store = {}
    _prime(store, T0, minor=8.0, major=6.0, incremental=0.4)
    results = _check(store, T0 + MINUTE, minor=8.6, major=6.3, incremental=0.4)
    assert _close(_metric(results, "n8n_gc_time_percent").value, 1.5), results
    assert _close(_metric(results, "n8n_gc_time_percent_minor").value, 1.0), results
    assert _close(_metric(results, "n8n_gc_time_percent_major").value, 0.5), results
    assert _close(_metric(results, "n8n_gc_time_percent_incremental").value, 0.0), results


def test_default_levels_warn_between_five_and_ten_percent():
    # A young process, lifetime sums still well below one second.
    # +0.4 s minor and +0.3 s major within 10 s: 7 %.
    store = {}
    _prime(store, T0, minor=0.1, major=0.1)
    results = _check(store, T0 + 10, minor=0.5, major=0.4)
    assert _state(results) is State.WARN, results


def test_default_levels_crit_above_ten_percent():
    # A young process, lifetime sums still below one second.
    # +0.8 s minor and +0.7 s major within 10 s: 15 %.
    store = {}
    _prime(store, T0, minor=0.1, major=0.1)
    results = _check(store, T0 + 10, minor=0.9, major=0.8)
    assert _state(results) is State.CRIT, results


def test_first_sample_gives_no_verdict():
    # A single sample of a counter carries no rate. The service must stay
    # pending instead of reporting a state it cannot know.
    try:
        results = _check({}, T0, minor=8.530, major=6.447, incremental=0.399)
    except IgnoreResultsError:
        return
    raise AssertionError(f"expected IgnoreResultsError, got {results!r}")


def test_restart_does_not_turn_into_a_rate():
    # n8n restarts, the counters start again near zero. That drop must not be
    # read as a (negative) rate, and the sample after it must work normally.
    store = {}
    _prime(store, T0, minor=8.530, major=6.447)
    try:
        results = _check(store, T0 + MINUTE, minor=0.020, major=0.050)
    except IgnoreResultsError:
        pass
    else:
        raise AssertionError(f"expected IgnoreResultsError after a counter reset, got {results!r}")

    # +0.3 s minor and +0.3 s major within 60 s: 1 %.
    results = _check(store, T0 + 2 * MINUTE, minor=0.320, major=0.350)
    assert _close(_metric(results, "n8n_gc_time_percent").value, 1.0), results
    assert _state(results) is State.OK, results


def test_kind_seen_for_the_first_time_is_left_out_once():
    # "incremental" only shows up after the first incremental collection.
    # Its first value is a lifetime sum, not something that happened in this
    # interval, so it must not be divided by the interval - and it must not
    # block the verdict for the other kinds either.
    store = {}
    _prime(store, T0, minor=8.0, major=6.0)
    results = _check(store, T0 + MINUTE, minor=8.6, major=6.3, incremental=30.0)
    assert _close(_metric(results, "n8n_gc_time_percent").value, 1.5), results
    assert _state(results) is State.OK, results


def test_collection_count_without_durations_still_reports():
    # Without any duration counter there is no rate to wait for. The service
    # must not stay pending forever.
    section = parse_n8n_metrics([["memory_mb;455.07"], ["gc_total;4438"]])
    for now in (T0, T0 + MINUTE):
        results = list(n8n_gc.check_n8n_gc_testable(_default_params(), section, {}, now))
        assert _close(_metric(results, "n8n_gc_total").value, 4438.0), results
        assert _state(results) is State.OK, results


def test_configured_levels_are_applied():
    # 1.5 % against levels of 1 % / 2 %.
    store = {}
    params = {"gc_time_percent": ("fixed", (1.0, 2.0))}
    _prime(store, T0, minor=8.0, major=6.0)
    results = _check(store, T0 + MINUTE, params=params, minor=8.6, major=6.3)
    assert _state(results) is State.WARN, results


def test_levels_can_be_switched_off():
    # 15 % with "No levels" selected in the rule.
    store = {}
    params = {"gc_time_percent": ("no_levels", None)}
    _prime(store, T0, minor=8.0, major=6.0)
    results = _check(store, T0 + MINUTE, params=params, minor=14.0, major=9.0)
    assert _state(results) is State.OK, results


def test_rule_written_for_the_lifetime_sum_is_ignored():
    # Rules saved before this change still carry "gc_duration_seconds".
    # Those numbers were set against the lifetime sum and mean nothing for a
    # rate; they must neither crash the check nor decide its state.
    store = {}
    params = {**_default_params(), "gc_duration_seconds": ("fixed", (1.0, 5.0))}
    _prime(store, T0, minor=8.530, major=6.447, incremental=0.399)
    results = _check(store, T0 + MINUTE, params=params, minor=8.545, major=6.458, incremental=0.399)
    assert _state(results) is State.OK, results


def test_lifetime_sums_are_graphed_without_levels():
    # The sums stay available as metrics, but a warn/crit line on a counter
    # that only grows is exactly the bug.
    store = {}
    _prime(store, T0, minor=8.530, major=6.447, incremental=0.399)
    results = _check(store, T0 + MINUTE, minor=8.545, major=6.458, incremental=0.399)
    for kind, expected in (("minor", 8.545), ("major", 6.458), ("incremental", 0.399)):
        metric = _metric(results, f"n8n_nodejs_gc_duration_seconds_sum_kind_{kind}")
        assert _close(metric.value, expected), metric
        assert metric.levels == (None, None), metric
    assert _close(_metric(results, "n8n_gc_total").value, 4438.0), results


def test_every_emitted_metric_has_a_graphing_definition():
    # A metric without a definition gets an auto-generated graph with no
    # title and no unit.
    from cmk.graphing.v1 import metrics as graphing_metrics

    from n8n_cmk.graphing import n8n_gc as n8n_gc_graphing

    defined = {
        obj.name for obj in vars(n8n_gc_graphing).values() if isinstance(obj, graphing_metrics.Metric)
    }
    store = {}
    _prime(store, T0, minor=8.0, major=6.0, incremental=0.4)
    results = _check(store, T0 + MINUTE, minor=8.6, major=6.3, incremental=0.4)
    emitted = {m.name for m in results if isinstance(m, Metric)}
    assert emitted and emitted <= defined, f"metrics without a definition: {sorted(emitted - defined)}"


def main():
    tests = [(name, func) for name, func in sorted(globals().items()) if name.startswith("test_")]
    failed = 0
    for name, func in tests:
        try:
            func()
        except Exception as exc:  # noqa: BLE001 - report every failing check, then exit non-zero
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok   {name}")
    if failed:
        print(f"{failed} of {len(tests)} GC checks failed")
        sys.exit(1)
    print(f"all {len(tests)} GC checks passed")


if __name__ == "__main__":
    main()
