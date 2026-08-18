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


def _parameter_form_heap_usage() -> Dictionary:
    """Define Levels for n8n Heap metrics (usage + spaces)"""
    return Dictionary(
        elements={
            "heap_percent": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Float(),
                    prefill_fixed_levels=DefaultValue(value=(80.0, 90.0)),
                    title=Title("Heap Usage (%) Levels"),
                ),
                required=False,
            ),
            "heap_used": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(419430400, 524288000)),  # 400MB, 500MB
                    title=Title("Heap Used (bytes) Levels"),
                ),
                required=False,
            ),
            "old_space": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(314572800, 419430400)),  # 300MB, 400MB
                    title=Title("Old Space (bytes) Levels"),
                ),
                required=False,
            ),
            "new_space": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(67108864, 134217728)),  # 64MB, 128MB
                    title=Title("New Space (bytes) Levels"),
                ),
                required=False,
            ),
        }
    )


rule_spec_n8n_heap_usage = CheckParameters(
    name="n8n_heap_usage",
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_heap_usage,
    title=Title("n8n Heap Monitoring"),
    condition=HostCondition(),
)


