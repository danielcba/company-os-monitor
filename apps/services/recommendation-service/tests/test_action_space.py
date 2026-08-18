"""Unit tests for the Action Space Library (Procedural Memory, declarative)."""
from dataclasses import FrozenInstanceError

import pytest
from libs.procedural_memory.action_space import (
    ACTION_SPACE_LIBRARY,
    ACTION_SPACES,
    DOMAINS,
    ActionSpaceEntry,
    filter_action_space,
)

# Catalogue per docs/04-informes-seguridad.md (FASE 6, Action Space by Domain).
EXPECTED_ACTIONS = {
    "storage": {
        "expand_volume",
        "add_disk",
        "move_data",
        "compress",
        "purge_old",
        "change_retention",
        "enable_dedup",
    },
    "compute": {
        "scale_up",
        "scale_out",
        "restart_service",
        "migrate_vm",
        "adjust_limits",
        "tune_kernel",
    },
    "security": {
        "reset_credentials",
        "revoke_sessions",
        "enable_mfa",
        "block_ip",
        "isolate_host",
        "rotate_keys",
    },
    "backup": {
        "retry_job",
        "change_schedule",
        "change_target",
        "verify_integrity",
        "test_restore",
    },
    "network": {
        "block_port",
        "modify_acl",
        "reroute_traffic",
        "enable_ddos_protection",
    },
    "observability": {
        "increase_log_level",
        "add_metric",
        "create_alert_rule",
        "adjust_threshold",
    },
}


def test_catalog_covers_all_domains_with_explicit_actions():
    assert {entry.domain for entry in ACTION_SPACE_LIBRARY} == DOMAINS
    for entry in ACTION_SPACE_LIBRARY:
        assert entry.allowed_actions == EXPECTED_ACTIONS[entry.domain]
        assert entry.action_id.endswith("_v1")  # versioned, immutable contract
        assert entry.purposes  # every space declares which purposes it applies to


def test_entries_are_frozen_and_unique():
    assert len(ACTION_SPACE_LIBRARY) == len(ACTION_SPACES)
    for entry in ACTION_SPACE_LIBRARY:
        assert isinstance(entry, ActionSpaceEntry)
        with pytest.raises(FrozenInstanceError):
            entry.allowed_actions = frozenset({"something_else"})


def test_entry_validates_domain_and_nonempty_space():
    with pytest.raises(ValueError):
        ActionSpaceEntry(
            action_id="bogus_v1",
            domain="not_a_domain",
            allowed_actions=frozenset({"x"}),
        )
    with pytest.raises(ValueError):
        ActionSpaceEntry(
            action_id="empty_v1",
            domain="storage",
            allowed_actions=frozenset(),
        )
    with pytest.raises(ValueError):
        ActionSpaceEntry(
            action_id="",
            domain="storage",
            allowed_actions=frozenset({"expand_volume"}),
        )


def test_filter_action_space_by_enabled_domains():
    only_security = filter_action_space(
        ACTION_SPACE_LIBRARY, enabled_domains=frozenset({"security"})
    )
    assert len(only_security) == 1
    assert only_security[0].domain == "security"

    empty = filter_action_space(ACTION_SPACE_LIBRARY, enabled_domains=frozenset())
    assert empty == ACTION_SPACE_LIBRARY

    with pytest.raises(ValueError):
        filter_action_space(
            ACTION_SPACE_LIBRARY, enabled_domains=frozenset({"storage", "bogus"})
        )


def test_every_domain_has_more_than_one_permitted_action():
    # The Formulator needs at least one alternative per offer.
    for entry in ACTION_SPACE_LIBRARY:
        assert len(entry.allowed_actions) >= 2