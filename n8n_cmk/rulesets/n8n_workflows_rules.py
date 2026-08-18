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
from cmk.rulesets.v1.rule_specs import CheckParameters, HostAndItemCondition, HostCondition, Topic


def _parameter_form_workflows() -> Dictionary:
    """Define Levels for n8n Workflows (overall statistics)"""
    return Dictionary(
        elements={
            "total_workflows": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(100, 200)),
                    title=Title("Total Workflows Levels"),
                ),
                required=False,
            ),
            "inactive_workflows": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(10, 20)),
                    title=Title("Inactive Workflows Levels"),
                ),
                required=False,
            ),
        }
    )


def _parameter_form_workflow_item() -> Dictionary:
    """Define Levels for individual n8n Workflow"""
    return Dictionary(
        elements={
            "success_rate": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.LOWER,
                    form_spec_template=Float(),
                    prefill_fixed_levels=DefaultValue(value=(90.0, 70.0)),
                    title=Title("Success Rate % Levels"),
                ),
                required=True,
            ),
            "failed_executions": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(10, 50)),
                    title=Title("Failed Executions Levels"),
                ),
                required=False,
            ),
            "total_executions_24h": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(1000, 5000)),
                    title=Title("Total Executions (24h) Levels"),
                ),
                required=False,
            ),
            "failed_executions_24h": DictElement(
                parameter_form=SimpleLevels(
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(),
                    prefill_fixed_levels=DefaultValue(value=(50, 200)),
                    title=Title("Failed Executions (24h) Levels"),
                ),
                required=False,
            ),
        }
    )


# Rules for overall workflows statistics
rule_spec_n8n_workflows = CheckParameters(
    name="n8n_workflows",
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_workflows,
    title=Title("n8n Workflows Monitoring"),
    condition=HostCondition(),
)

# Rules for individual workflow items
rule_spec_n8n_workflow_item = CheckParameters(
    name="n8n_workflow_item",
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_workflow_item,
    title=Title("n8n Workflow Item Monitoring"),
    condition=HostAndItemCondition(item_title=Title("Workflow name")),
)


