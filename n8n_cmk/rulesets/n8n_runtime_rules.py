#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# (c) Elicarlos Ferreira <elicarlos.dias@lynxmind.com> | <dias.elicarlos@gmail.com>
# License: GNU General Public License v2

from cmk.rulesets.v1 import Title
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    Float,
    Integer,
    LevelDirection,
    SimpleLevels,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, HostCondition, Topic


def _parameter_form_runtime() -> Dictionary:
    """Define Levels for the 4 most important n8n Runtime metrics"""
    return Dictionary(
        elements={
            "fds": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(400, 700)),
                    title=Title("File Descriptors Levels"),
                ),
                required=False,
            ),
            "eventloop_lag_ms": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Float(),
                    prefill_fixed_levels=DefaultValue(value=(10.0, 50.0)),
                    title=Title("Event Loop Lag (ms) Levels"),
                ),
                required=False,
            ),
            "active_handles": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(50, 100)),
                    title=Title("Active Handles Levels"),
                ),
                required=False,
            ),
            "active_resources": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(100, 200)),
                    title=Title("Active Resources Levels"),
                ),
                required=False,
            ),
        }
    )


rule_spec_n8n_runtime = CheckParameters(
    name="n8n_runtime",
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_runtime,
    title=Title("n8n Runtime Monitoring"),
    condition=HostCondition(),
)


