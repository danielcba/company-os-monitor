"""Action Space Library - declarative permitted actions (Procedural Memory).

The Recommendation design implication governs this module: "The action space
must be explicit so that the system knows what it is choosing among." The
Action Space is procedural memory (P3): a declarative catalogue of the actions
the system is ALLOWED to propose, per domain and per purpose. It NEVER reasons
by itself - it only declares the space; the Recommendation Formulator (Action/
Propose) derives the course of action within this explicit space.

``ActionSpaceEntry`` is frozen and versioned: revising the space means
publishing a NEW ``action_id`` (``*_v1``/``*_v2``), never mutating a published
one. ``allowed_actions`` is a frozenset of action identifiers; ``purposes``
declares which purposes (context.purpose) the entry applies to (empty frozenset
= all purposes). The initial catalogue mirrors docs/04-informes-seguridad.md
(FASE 6: Action Space Definition, Table by Domain).
"""
from dataclasses import dataclass, field

# Canonical domains of the Action Space (docs/04, FASE 6).
DOMAIN_STORAGE = "storage"
DOMAIN_COMPUTE = "compute"
DOMAIN_SECURITY = "security"
DOMAIN_BACKUP = "backup"
DOMAIN_NETWORK = "network"
DOMAIN_OBSERVABILITY = "observability"
DOMAINS: frozenset[str] = frozenset(
    {
        DOMAIN_STORAGE,
        DOMAIN_COMPUTE,
        DOMAIN_SECURITY,
        DOMAIN_BACKUP,
        DOMAIN_NETWORK,
        DOMAIN_OBSERVABILITY,
    }
)

# Canonical purposes (shared with the Context Activator, libs/perception/context.py).
PURPOSE_INFRASTRUCTURE_HEALTH = "infrastructure_health"
PURPOSE_SECURITY_POSTURE = "security_posture"
PURPOSE_CAPACITY_MANAGEMENT = "capacity_management"


@dataclass(frozen=True)
class ActionSpaceEntry:
    """Declarative definition of one explicit Action Space (procedural memory).

    ``action_id`` is versioned (``*_v1``/``*_v2``): revising the space means
    publishing a NEW version, never mutating a published one. ``domain`` is one
    of DOMAINS; ``allowed_actions`` is the explicit set of permitted action
    identifiers the Formulator may choose among; ``purposes`` (empty frozenset
    = all purposes) declares which purposes the space applies to; ``description``
    documents the space factually. Declarative only - never reasoning.
    """

    action_id: str
    domain: str
    allowed_actions: frozenset[str] = field(default_factory=frozenset)
    purposes: frozenset[str] = field(default_factory=frozenset)
    description: str = ""

    def __post_init__(self) -> None:
        if self.domain not in DOMAINS:
            raise ValueError(f"unknown domain: {self.domain}")  # noqa: TRY003
        if not self.action_id.strip():
            raise ValueError("action_id must not be empty")  # noqa: TRY003
        if not self.allowed_actions:
            raise ValueError("allowed_actions must not be empty")  # noqa: TRY003


def _entry(  # noqa: PLR0913, PLR0917 - declarative factory for the catalogue
    action_id: str,
    domain: str,
    actions: tuple[str, ...],
    purposes: frozenset[str] | None = None,
    description: str = "",
) -> ActionSpaceEntry:
    return ActionSpaceEntry(
        action_id=action_id,
        domain=domain,
        allowed_actions=frozenset(actions),
        purposes=purposes if purposes is not None else frozenset(),
        description=description,
    )


# Initial explicit Action Space catalogue (docs/04-informes-seguridad.md, FASE 6).
ACTION_SPACE_LIBRARY: tuple[ActionSpaceEntry, ...] = (
    _entry(
        "storage_actions_v1",
        DOMAIN_STORAGE,
        (
            "expand_volume",
            "add_disk",
            "move_data",
            "compress",
            "purge_old",
            "change_retention",
            "enable_dedup",
        ),
        frozenset({PURPOSE_INFRASTRUCTURE_HEALTH, PURPOSE_CAPACITY_MANAGEMENT}),
        "Acciones permitidas sobre almacenamiento (volúmenes, discos, retención).",
    ),
    _entry(
        "compute_actions_v1",
        DOMAIN_COMPUTE,
        (
            "scale_up",
            "scale_out",
            "restart_service",
            "migrate_vm",
            "adjust_limits",
            "tune_kernel",
        ),
        frozenset({PURPOSE_INFRASTRUCTURE_HEALTH}),
        "Acciones permitidas sobre cómputo (capacidad, servicios, VMs).",
    ),
    _entry(
        "security_actions_v1",
        DOMAIN_SECURITY,
        (
            "reset_credentials",
            "revoke_sessions",
            "enable_mfa",
            "block_ip",
            "isolate_host",
            "rotate_keys",
        ),
        frozenset({PURPOSE_SECURITY_POSTURE}),
        "Acciones permitidas sobre postura de seguridad (credenciales, sesiones, acceso).",
    ),
    _entry(
        "backup_actions_v1",
        DOMAIN_BACKUP,
        (
            "retry_job",
            "change_schedule",
            "change_target",
            "verify_integrity",
            "test_restore",
        ),
        frozenset({PURPOSE_INFRASTRUCTURE_HEALTH, PURPOSE_CAPACITY_MANAGEMENT}),
        "Acciones permitidas sobre backup (jobs, horarios, destinos, integridad).",
    ),
    _entry(
        "network_actions_v1",
        DOMAIN_NETWORK,
        (
            "block_port",
            "modify_acl",
            "reroute_traffic",
            "enable_ddos_protection",
        ),
        frozenset({PURPOSE_INFRASTRUCTURE_HEALTH}),
        "Acciones permitidas sobre red (puertos, ACLs, rutas, protección DDoS).",
    ),
    _entry(
        "observability_actions_v1",
        DOMAIN_OBSERVABILITY,
        (
            "increase_log_level",
            "add_metric",
            "create_alert_rule",
            "adjust_threshold",
        ),
        frozenset({PURPOSE_INFRASTRUCTURE_HEALTH, PURPOSE_SECURITY_POSTURE}),
        "Acciones permitidas de observabilidad (registro, métricas, alertas).",
    ),
)

ACTION_SPACES: dict[str, ActionSpaceEntry] = {
    entry.action_id: entry for entry in ACTION_SPACE_LIBRARY
}


def filter_action_space(
    library: tuple[ActionSpaceEntry, ...] = ACTION_SPACE_LIBRARY,
    enabled_domains: frozenset[str] = frozenset(),
) -> tuple[ActionSpaceEntry, ...]:
    """Restrict the catalogue to the enabled domains (empty = all enabled).

    Per-deployment flag (``ACTION_SPACE_DOMAINS`` in env): the Formulator may
    only choose within the spaces that remain in the filtered catalogue.
    """
    if not enabled_domains:
        return library
    unknown = enabled_domains - DOMAINS
    if unknown:
        raise ValueError(f"unknown enabled domains: {sorted(unknown)}")  # noqa: TRY003
    return tuple(entry for entry in library if entry.domain in enabled_domains)