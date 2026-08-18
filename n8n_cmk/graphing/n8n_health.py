#!/usr/bin/env python3
"""
Graphing definitions for the n8n health, API status, failed runs, users and
tags services.
"""

from cmk.graphing.v1 import Title
from cmk.graphing.v1.graphs import Graph, MinimalRange
from cmk.graphing.v1.metrics import (
    Color,
    DecimalNotation,
    Metric,
    StrictPrecision,
    TimeNotation,
    Unit,
)

UNIT_COUNT = Unit(DecimalNotation(""), StrictPrecision(0))
UNIT_PERCENT = Unit(DecimalNotation("%"), StrictPrecision(1))
UNIT_TIME = Unit(TimeNotation())

# --- health / readiness probes ------------------------------------------------
metric_n8n_response_time = Metric(
    name="n8n_response_time",
    title=Title("Response Time"),
    unit=UNIT_TIME,
    color=Color.BLUE,
)

# --- API endpoint reachability ------------------------------------------------
metric_n8n_api_endpoints_ok = Metric(
    name="n8n_api_endpoints_ok",
    title=Title("Endpoints Reachable"),
    unit=UNIT_COUNT,
    color=Color.GREEN,
)

metric_n8n_api_endpoints_failed = Metric(
    name="n8n_api_endpoints_failed",
    title=Title("Endpoints Not Reachable"),
    unit=UNIT_COUNT,
    color=Color.RED,
)

# --- failed runs ---------------------------------------------------------------
metric_n8n_failures_24h = Metric(
    name="n8n_failures_24h",
    title=Title("Failures (24h)"),
    unit=UNIT_COUNT,
    color=Color.RED,
)

metric_n8n_failures_8h = Metric(
    name="n8n_failures_8h",
    title=Title("Failures (8h)"),
    unit=UNIT_COUNT,
    color=Color.LIGHT_RED,
)

metric_n8n_global_success_rate_24h = Metric(
    name="n8n_global_success_rate_24h",
    title=Title("Global Success Rate (24h)"),
    unit=UNIT_PERCENT,
    color=Color.ORANGE,
)

metric_n8n_global_success_rate_8h = Metric(
    name="n8n_global_success_rate_8h",
    title=Title("Global Success Rate (8h)"),
    unit=UNIT_PERCENT,
    color=Color.LIGHT_ORANGE,
)

metric_n8n_workflows_with_failures_24h = Metric(
    name="n8n_workflows_with_failures_24h",
    title=Title("Workflows with Failures (24h)"),
    unit=UNIT_COUNT,
    color=Color.DARK_PINK,
)

# --- users ---------------------------------------------------------------------
metric_n8n_users_total = Metric(
    name="n8n_users_total",
    title=Title("Total Users"),
    unit=UNIT_COUNT,
    color=Color.BLUE,
)

metric_n8n_users_active = Metric(
    name="n8n_users_active",
    title=Title("Active Users"),
    unit=UNIT_COUNT,
    color=Color.GREEN,
)

metric_n8n_users_pending = Metric(
    name="n8n_users_pending",
    title=Title("Pending Users"),
    unit=UNIT_COUNT,
    color=Color.ORANGE,
)

metric_n8n_users_disabled = Metric(
    name="n8n_users_disabled",
    title=Title("Disabled Users"),
    unit=UNIT_COUNT,
    color=Color.GRAY,
)

# --- tags ----------------------------------------------------------------------
metric_n8n_tags_total = Metric(
    name="n8n_tags_total",
    title=Title("Total Tags"),
    unit=UNIT_COUNT,
    color=Color.PURPLE,
)

metric_n8n_tags_unused = Metric(
    name="n8n_tags_unused",
    title=Title("Unused Tags"),
    unit=UNIT_COUNT,
    color=Color.GRAY,
)

# --- graphs --------------------------------------------------------------------
graph_n8n_api_endpoints = Graph(
    name="n8n_api_endpoints",
    title=Title("n8n API Endpoints"),
    compound_lines=["n8n_api_endpoints_ok", "n8n_api_endpoints_failed"],
)

graph_n8n_failures = Graph(
    name="n8n_failures",
    title=Title("n8n Failures"),
    simple_lines=[
        "n8n_failures_24h",
        "n8n_failures_8h",
        "n8n_workflows_with_failures_24h",
    ],
)

graph_n8n_global_success_rate = Graph(
    name="n8n_global_success_rate",
    title=Title("n8n Global Success Rate"),
    minimal_range=MinimalRange(0, 100),
    simple_lines=[
        "n8n_global_success_rate_24h",
        "n8n_global_success_rate_8h",
    ],
)

graph_n8n_users = Graph(
    name="n8n_users",
    title=Title("n8n Users"),
    compound_lines=[
        "n8n_users_active",
        "n8n_users_pending",
        "n8n_users_disabled",
    ],
    simple_lines=["n8n_users_total"],
    optional=["n8n_users_disabled"],
)

graph_n8n_tags = Graph(
    name="n8n_tags",
    title=Title("n8n Tags"),
    simple_lines=["n8n_tags_total", "n8n_tags_unused"],
    optional=["n8n_tags_unused"],
)
