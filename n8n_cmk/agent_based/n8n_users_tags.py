#!/usr/bin/env python3
"""
n8n Users and Tags plugins for CheckMK

Both sections were already produced by the special agent but had no parser,
so the data never reached a service.

<<<n8n_users>>>
  total;<n> / active;<n> / pending;<n>
  user;<id>;<email>;<first>;<last>;<disabled>;<role>;<created_at>

<<<n8n_tags>>>
  total;<n>
  tag;<id>;<name>;<usage_count>
"""

from typing import Dict, List, Optional

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    Result,
    Service,
    State,
    StringTable,
)


def _to_int(raw: str, default: int = 0) -> int:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------
def parse_n8n_users(string_table: StringTable) -> Optional[Dict]:
    if not string_table:
        return None

    data: Dict = {"total": 0, "active": 0, "pending": 0, "users": []}

    for line in string_table:
        parts = " ".join(line).split(";")
        if len(parts) < 2:
            continue
        key = parts[0]

        if key in ("total", "active", "pending"):
            data[key] = _to_int(parts[1])
        elif key == "user" and len(parts) >= 8:
            data["users"].append({
                "id": parts[1],
                "email": parts[2],
                "first_name": parts[3],
                "last_name": parts[4],
                "disabled": parts[5].strip().lower() == "true",
                "role": parts[6],
                "created_at": parts[7],
            })

    return data


def discover_n8n_users(section: Optional[Dict]) -> DiscoveryResult:
    if section is not None:
        yield Service()


def check_n8n_users(section: Optional[Dict]) -> CheckResult:
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No users data available")
        return

    total = section["total"]
    active = section["active"]
    pending = section["pending"]
    users: List[Dict] = section["users"]

    yield Result(
        state=State.OK,
        summary=f"{total} users ({active} active, {pending} pending)",
    )

    disabled = [u for u in users if u["disabled"]]
    if disabled:
        yield Result(
            state=State.OK,
            summary=f"{len(disabled)} disabled",
        )

    owners = [u for u in users if "owner" in u["role"].lower()]
    if owners:
        yield Result(
            state=State.OK,
            notice="Owners: " + ", ".join(u["email"] for u in owners),
        )

    for user in users[:10]:
        name = f"{user['first_name']} {user['last_name']}".strip() or user["email"]
        flags = " (disabled)" if user["disabled"] else ""
        yield Result(
            state=State.OK,
            notice=f"{name} <{user['email']}> - {user['role']}{flags}",
        )

    yield Metric("n8n_users_total", total)
    yield Metric("n8n_users_active", active)
    yield Metric("n8n_users_pending", pending)
    yield Metric("n8n_users_disabled", len(disabled))


agent_section_n8n_users = AgentSection(
    name="n8n_users",
    parse_function=parse_n8n_users,
)

check_plugin_n8n_users = CheckPlugin(
    name="n8n_users",
    sections=["n8n_users"],
    service_name="n8n Users",
    discovery_function=discover_n8n_users,
    check_function=check_n8n_users,
)


# --------------------------------------------------------------------------
# Tags
# --------------------------------------------------------------------------
def parse_n8n_tags(string_table: StringTable) -> Optional[Dict]:
    if not string_table:
        return None

    data: Dict = {"total": 0, "tags": []}

    for line in string_table:
        parts = " ".join(line).split(";")
        if len(parts) < 2:
            continue
        if parts[0] == "total":
            data["total"] = _to_int(parts[1])
        elif parts[0] == "tag" and len(parts) >= 3:
            data["tags"].append({
                "id": parts[1],
                "name": parts[2],
                "usage_count": _to_int(parts[3]) if len(parts) > 3 else 0,
            })

    return data


def discover_n8n_tags(section: Optional[Dict]) -> DiscoveryResult:
    if section is not None:
        yield Service()


def check_n8n_tags(section: Optional[Dict]) -> CheckResult:
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No tags data available")
        return

    total = section["total"]
    tags: List[Dict] = section["tags"]

    yield Result(state=State.OK, summary=f"{total} tags defined")

    if tags:
        most_used = sorted(tags, key=lambda t: t["usage_count"], reverse=True)[:5]
        for tag in most_used:
            yield Result(
                state=State.OK,
                notice=f"{tag['name']}: used by {tag['usage_count']} workflow(s)",
            )

        unused = [t for t in tags if t["usage_count"] == 0]
        if unused:
            yield Result(
                state=State.OK,
                summary=f"{len(unused)} unused",
            )
        yield Metric("n8n_tags_unused", len(unused))

    yield Metric("n8n_tags_total", total)


agent_section_n8n_tags = AgentSection(
    name="n8n_tags",
    parse_function=parse_n8n_tags,
)

check_plugin_n8n_tags = CheckPlugin(
    name="n8n_tags",
    sections=["n8n_tags"],
    service_name="n8n Tags",
    discovery_function=discover_n8n_tags,
    check_function=check_n8n_tags,
)
