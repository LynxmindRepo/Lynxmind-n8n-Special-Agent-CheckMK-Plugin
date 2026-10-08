#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# (c) Elicarlos Ferreira <elicarlos.dias@lynxmind.com> | <dias.elicarlos@gmail.com>
# License: GNU General Public License v2

from cmk.rulesets.v1 import Help, Title
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
            "gc_time_percent": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Float(unit_symbol="%"),
                    prefill_fixed_levels=DefaultValue(value=(5.0, 10.0)),
                    title=Title("Time spent in garbage collection"),
                    help_text=Help(
                        "Share of wall-clock time n8n spent in garbage collection "
                        "since the previous check, summed over minor, major and "
                        "incremental collections. A collection pauses the "
                        "JavaScript thread, so this is time in which the n8n "
                        "process could not do any other work."
                    ),
                ),
                required=False,
            ),
        },
        # Levels on the lifetime GC duration. They were compared against a
        # counter that only grows, so they cannot be converted into a rate.
        # Kept here so that rules saved with them still load.
        ignored_elements=("gc_duration_seconds",),
    )


rule_spec_n8n_gc = CheckParameters(
    name="n8n_gc",
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_gc,
    title=Title("n8n Garbage Collection Monitoring"),
    condition=HostCondition(),
)


