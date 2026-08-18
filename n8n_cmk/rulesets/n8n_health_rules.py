#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# (c) Elicarlos Ferreira <elicarlos.dias@lynxmind.com>
# License: GNU General Public License v2
"""Rulesets for the n8n API status and failed runs services."""

from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    Float,
    Integer,
    LevelDirection,
    ServiceState,
    SimpleLevels,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, HostCondition, Topic


def _parameter_form_api_status() -> Dictionary:
    return Dictionary(
        elements={
            "failed_endpoints_state": DictElement(
                parameter_form=ServiceState(
                    title=Title("State when endpoints are not reachable"),
                    help_text=Help(
                        "An endpoint also reports as not reachable when its "
                        "collection is simply not enabled in the special agent "
                        "rule, so this defaults to OK. Raise it if every "
                        "endpoint you enabled must always answer."
                    ),
                    prefill=DefaultValue(ServiceState.OK),
                ),
                required=False,
            ),
        }
    )


def _parameter_form_failed_runs() -> Dictionary:
    return Dictionary(
        elements={
            "failures_24h": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(10, 50)),
                    title=Title("Total failures in 24h"),
                ),
                required=False,
            ),
            "global_success_rate_24h": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.LOWER,
                    form_spec_template=Float(),
                    prefill_fixed_levels=DefaultValue(value=(95.0, 80.0)),
                    title=Title("Global success rate % (24h)"),
                ),
                required=False,
            ),
        }
    )


rule_spec_n8n_api_status = CheckParameters(
    name="n8n_api_status",
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_api_status,
    title=Title("n8n API Endpoints"),
    condition=HostCondition(),
)

rule_spec_n8n_failed_runs = CheckParameters(
    name="n8n_failed_runs",
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_failed_runs,
    title=Title("n8n Failed Runs"),
    condition=HostCondition(),
)
