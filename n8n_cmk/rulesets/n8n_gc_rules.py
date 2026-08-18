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
    LevelDirection,
    SimpleLevels,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, HostCondition, Topic


def _parameter_form_gc() -> Dictionary:
    """Define Levels for n8n GC metrics"""
    return Dictionary(
        elements={
            "gc_duration_seconds": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Float(),
                    prefill_fixed_levels=DefaultValue(value=(1.0, 5.0)),
                    title=Title("GC Duration (seconds) Levels"),
                ),
                required=False,
            ),
        }
    )


rule_spec_n8n_gc = CheckParameters(
    name="n8n_gc",
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_gc,
    title=Title("n8n Garbage Collection Monitoring"),
    condition=HostCondition(),
)


