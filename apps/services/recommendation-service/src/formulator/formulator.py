"""Recommendation Formulator - Action/Propose capability (pure, no I/O).

Implements the Recommendation concept's Cognitive Contract for the MVP:
Input = Active Context + leading Hypothesis + calibrated Confidence + explicit
Action Space; Transform = derive the course of action that best serves the
current purpose under the constraints of the current context; Output = a
Recommendation with its traceable rationale, its observable expected
consequences, its (already calibrated) confidence and the alternatives
considered. All functions here are pure and deterministic: same inputs always
produce the same offer (the deterministic recommendation_id then makes
re-formulation idempotent).

A Recommendation is an OFFER, not a commitment (P6): this module never executes
anything and never triggers alerts. The chosen action is always drawn from the
EXPLICIT Action Space of the resolved domain/purpose (the framework: "The action
space must be explicit so that the system knows what it is choosing among.").
The selection scheme is documented declaratively (domain -> preferred action);
alternatives are the remaining permitted actions, each with its rationale and
the reason it was not chosen. ``confidence_score`` is the CALIBRATED score of
the leading Hypothesis (Sprint 8) - the Formulator never recalibrates (R4).

Anti-order: ``action_description`` and ``rationale`` are proposals with
rationale, never unqualified commands ("run now" is a Non-example of the
concept). Language stays advisory and reversible.
"""
from collections.abc import Sequence

from libs.action.recommendation import (
    STATUS_PROPOSED,
    RecommendationCreate,
)
from libs.learning.confidence import Confidence
from libs.perception.context import Context
from libs.procedural_memory.action_space import ActionSpaceEntry
from libs.reasoning.anomaly import Anomaly
from libs.reasoning.hypothesis import Hypothesis

# Target type the Formulator consumes: the calibrated Confidence of the leading
# Hypothesis (Recommendation/Decision targets are calibrated by future Action
# Layer phases through the same ConfidenceStore API).
TARGET_TYPE_HYPOTHESIS = "hypothesis"

# Declarative mapping mental_model_id -> domain. Each mental model of the
# Context catalog (libs/perception/context.py) is bound to the Action Space
# domain that serves its purpose (procedural memory, never reasoning).
MENTAL_MODEL_DOMAINS: dict[str, str] = {
    "resource_pressure": "storage",
    "service_failure": "compute",
    "auth_compromise": "security",
    "capacity_risk": "backup",
    "connectivity_degradation": "network",
}

# Declarative fallback purpose -> domain (used when no mental model mapping
# applies; the canonical purposes of the Context Activator).
PURPOSE_DOMAINS: dict[str, str] = {
    "security_posture": "security",
    "capacity_management": "storage",
    "infrastructure_health": "observability",
}

# Preferred (leading) action per domain: the offer the Formulator derives for
# that domain, drawn from the explicit space. Declarative and auditable.
LEADING_ACTION_BY_DOMAIN: dict[str, str] = {
    "storage": "expand_volume",
    "compute": "restart_service",
    "security": "reset_credentials",
    "backup": "change_target",
    "network": "modify_acl",
    "observability": "adjust_threshold",
}

# Advisory (non-imperative) description of each permitted action - WHAT to do
# as an offer, never an unqualified order.
ACTION_DESCRIPTION_TEMPLATES: dict[str, str] = {
    "expand_volume": (
        "Expandir el volumen objetivo del almacenamiento antes del umbral "
        "proyectado, o mover los datos a un destino con espacio disponible."
    ),
    "add_disk": "Añadir un disco adicional al volumen objetivo antes del umbral proyectado.",
    "move_data": "Mover los datos del volumen objetivo a un destino con espacio disponible.",
    "compress": "Comprimir los datos más antiguos del volumen objetivo para liberar espacio.",
    "purge_old": (
        "Purgar los datos fuera del periodo de retención documentado del volumen objetivo."
    ),
    "change_retention": "Ajustar el periodo de retención del volumen objetivo al espacio disponible.",
    "enable_dedup": "Habilitar la deduplicación en el volumen objetivo para reducir el consumo.",
    "scale_up": "Aumentar la capacidad de cómputo del servicio afectado dentro del límite autorizado.",
    "scale_out": "Añadir una instancia adicional del servicio afectado dentro del límite autorizado.",
    "restart_service": (
        "Reiniciar el servicio afectado para restablecer su estado activo dentro de la ventana de mantenimiento."
    ),
    "migrate_vm": "Migrar la VM afectada a un host con capacidad disponible.",
    "adjust_limits": "Ajustar los límites de recursos del servicio afectado a su patrón observado.",
    "tune_kernel": "Ajustar los parámetros de kernel del host afectado al patrón observado.",
    "reset_credentials": (
        "Resetear las credenciales de la cuenta afectada y monitorizar el acceso durante 7 días."
    ),
    "revoke_sessions": "Revocar las sesiones activas de la cuenta afectada.",
    "enable_mfa": "Habilitar un segundo factor de autenticación en la cuenta afectada.",
    "block_ip": "Bloquear el origen de los intentos de autenticación concentrados.",
    "isolate_host": (
        "Aislar el host afectado de la red productiva hasta confirmar el alcance del incidente."
    ),
    "rotate_keys": "Rotar las claves del servicio afectado e invalidar las anteriores.",
    "retry_job": "Reintentar el job de backup fallido dentro de la ventana de ejecución.",
    "change_schedule": "Cambiar el horario del job de backup a la ventana documentada.",
    "change_target": (
        "Cambiar el destino de backup al arreglo alternativo con espacio disponible."
    ),
    "verify_integrity": "Verificar la integridad de los backups del objetivo.",
    "test_restore": "Ejecutar una restauración de prueba sobre los backups del objetivo.",
    "block_port": "Bloquear el puerto afectado en los hosts del alcance.",
    "modify_acl": "Modificar las reglas de acceso del alcance para restringir el tráfico.",
    "reroute_traffic": "Reenrutar el tráfico del alcance por la ruta alterna.",
    "enable_ddos_protection": "Habilitar la protección DDoS en el servicio afectado.",
    "increase_log_level": "Aumentar el nivel de registro del servicio afectado para observabilidad.",
    "add_metric": "Añadir la métrica faltante al seguimiento del servicio afectado.",
    "create_alert_rule": "Crear una regla de alerta sobre la métrica afectada.",
    "adjust_threshold": "Ajustar el umbral de alerta de la métrica afectada al nuevo patrón.",
}

# Observable, verifiable expected consequences per action (WHAT is expected to
# happen, in concrete measurable terms).
CONSEQUENCE_TEMPLATES: dict[str, tuple[str, ...]] = {
    "expand_volume": (
        (
            "El espacio libre del volumen objetivo permanecerá por encima del umbral "
            "documentado durante los próximos 90 días."
        ),
        "No habrá fallos de escritura por capacidad en el volumen objetivo en los próximos 90 días.",
    ),
    "add_disk": (
        (
            "El espacio libre del volumen objetivo permanecerá por encima del umbral "
            "documentado tras añadir el disco."
        ),
    ),
    "move_data": (
        "El volumen objetivo quedará con espacio libre por encima del umbral documentado.",
    ),
    "compress": (
        "El volumen de datos persistidos del objetivo se reducirá tras la compresión.",
    ),
    "purge_old": (
        (
            "La purga liberará espacio en el volumen objetivo sin eliminar datos dentro "
            "del periodo de retención documentado."
        ),
    ),
    "change_retention": (
        "El crecimiento persistido se mantendrá dentro del espacio disponible del objetivo.",
    ),
    "enable_dedup": (
        "El consumo de almacenamiento del objetivo se reducirá tras habilitar la deduplicación.",
    ),
    "scale_up": (
        "La capacidad de cómputo del servicio aumentará sin interrupción del servicio.",
    ),
    "scale_out": (
        "La capacidad de cómputo del servicio aumentará con una instancia adicional.",
    ),
    "restart_service": (
        "El servicio volverá al estado activo y dejará de registrar el error observado.",
    ),
    "migrate_vm": (
        "La VM afectada quedará ejecutándose en un host con capacidad disponible.",
    ),
    "adjust_limits": (
        "El consumo de recursos del servicio se mantendrá dentro de los nuevos límites.",
    ),
    "tune_kernel": (
        "El comportamiento del host afectado convergerá al patrón documentado.",
    ),
    "reset_credentials": (
        (
            "La cuenta afectada dejará de presentar autenticaciones fallidas concentradas "
            "durante los próximos 7 días."
        ),
    ),
    "revoke_sessions": (
        "Las sesiones activas de la cuenta afectada quedarán revocadas.",
    ),
    "enable_mfa": (
        "Los intentos de autenticación de la cuenta requerirán un segundo factor.",
    ),
    "block_ip": (
        "El tráfico del origen acotado dejará de alcanzar el servicio afectado.",
    ),
    "isolate_host": (
        "El host afectado quedará aislado de la red productiva.",
    ),
    "rotate_keys": (
        "Las credenciales rotadas invalidarán el uso de las anteriores.",
    ),
    "retry_job": (
        "El job de backup completará la siguiente ejecución dentro de la ventana.",
    ),
    "change_schedule": (
        "El job de backup se ejecutará dentro de la nueva ventana programada.",
    ),
    "change_target": (
        (
            "El destino alternativo mantendrá espacio libre por encima del umbral "
            "documentado durante los próximos 90 días."
        ),
        "No habrá fallos de backup por capacidad en el nuevo destino en los próximos 90 días.",
    ),
    "verify_integrity": (
        "La integridad de los backups del objetivo quedará verificada sin restaurar datos.",
    ),
    "test_restore": (
        "Una restauración de prueba sobre los backups del objetivo completará sin errores.",
    ),
    "block_port": (
        "El tráfico hacia el puerto afectado quedará bloqueado en los hosts del alcance.",
    ),
    "modify_acl": (
        "Las reglas de acceso actualizadas restringirán el tráfico al rango documentado.",
    ),
    "reroute_traffic": (
        "El tráfico del alcance circulará por la ruta alterna documentada.",
    ),
    "enable_ddos_protection": (
        "El servicio afectado quedará cubierto por la protección DDoS configurada.",
    ),
    "increase_log_level": (
        "El registro del servicio afectado capturará el nivel de detalle requerido.",
    ),
    "add_metric": (
        "La nueva métrica quedará disponible para su seguimiento continuo.",
    ),
    "create_alert_rule": (
        "Las alertas se dispararán cuando la métrica afectada supere el umbral configurado.",
    ),
    "adjust_threshold": (
        "Las alertas de la métrica afectada quedarán calibradas al nuevo umbral.",
    ),
}

# Why each alternative was considered (declarative, per action).
CONSIDERATION_RATIONALE: dict[str, str] = {
    "expand_volume": "Amplía la capacidad del objetivo existente sin cambiar el destino.",
    "add_disk": "Añade capacidad física al objetivo sin migrar datos.",
    "move_data": "Libera el objetivo moviendo datos a un destino con espacio.",
    "compress": "Reduce el volumen persistido con un coste inmediato bajo.",
    "purge_old": "Libera espacio eliminando datos fuera del periodo de retención.",
    "change_retention": "Ajusta el periodo de retención al espacio disponible.",
    "enable_dedup": "Reduce el consumo de almacenamiento del objetivo.",
    "scale_up": "Aumenta la capacidad del servicio existente.",
    "scale_out": "Distribuye la carga añadiendo instancias.",
    "restart_service": "Restablece el servicio afectado de forma inmediata.",
    "migrate_vm": "Traslada la VM a un host con capacidad.",
    "adjust_limits": "Ajusta los límites del servicio al patrón observado.",
    "tune_kernel": "Ajusta los parámetros del host al patrón observado.",
    "reset_credentials": "Elimina el valor de las credenciales afectadas.",
    "revoke_sessions": "Invalida las sesiones activas de la cuenta afectada.",
    "enable_mfa": "Refuerza la autenticación de la cuenta afectada.",
    "block_ip": "Corta el tráfico del origen acotado.",
    "isolate_host": "Contiene el alcance del incidente aislándolo de la red productiva.",
    "rotate_keys": "Invalidan las claves potencialmente expuestas.",
    "retry_job": "Reintenta el job fallido en la misma ventana.",
    "change_schedule": "Mueve el job a la ventana documentada.",
    "change_target": "Dirige el backup a un destino con espacio disponible.",
    "verify_integrity": "Confirma la integridad de los backups sin restaurar.",
    "test_restore": "Valida la recuperación real de los backups.",
    "block_port": "Restringe el tráfico hacia el puerto afectado.",
    "modify_acl": "Ajusta el acceso del alcance al rango documentado.",
    "reroute_traffic": "Desvía el tráfico por una ruta alterna.",
    "enable_ddos_protection": "Activa la protección DDoS sobre el servicio afectado.",
    "increase_log_level": "Aumenta el detalle de registro para diagnóstico.",
    "add_metric": "Expone la métrica faltante para seguimiento.",
    "create_alert_rule": "Notifica cuando la métrica supere el umbral.",
    "adjust_threshold": "Calibra el umbral de alerta al patrón observado.",
}

# Declarative reason each alternative was NOT chosen (advisory, auditable).
REJECTION_REASONS: dict[str, str] = {
    "expand_volume": "Requiere coordinación con el equipo de almacenamiento antes de ejecutarse.",
    "add_disk": "Depende de hardware disponible y de una ventana de mantenimiento mayor.",
    "move_data": "El movimiento de datos puede tardar más que el alivio inmediato del objetivo.",
    "compress": "Puede no acompañar el ritmo de crecimiento y demora el alivio inmediato.",
    "purge_old": "Riesgo de eliminar datos próximos al límite del periodo de retención documentado.",
    "change_retention": "Riesgo de incumplir la política de retención documentada.",
    "enable_dedup": "El beneficio depende del contenido y no es inmediato.",
    "scale_up": "Incrementa coste y no resuelve el desequilibrio subyacente.",
    "scale_out": "Mayor complejidad operativa y no aborda el estado del servicio.",
    "restart_service": "Provoca una interrupción del servicio dentro de la ventana productiva.",
    "migrate_vm": "Implica un movimiento de mayor alcance y requiere ventana.",
    "adjust_limits": "Ajusta el síntoma sin abordar la causa de la presión.",
    "tune_kernel": "Cambio a nivel de host con mayor superficie de riesgo.",
    "reset_credentials": "Requiere coordinación con el propietario de la cuenta antes de ejecutarse.",
    "revoke_sessions": "Puede interrumpir sesiones legítimas en curso.",
    "enable_mfa": "Despliegue de mayor alcance y no es inmediato.",
    "block_ip": "Puede afectar tráfico legítimo proveniente del mismo origen.",
    "isolate_host": "Impacto operativo mayor; solo se justifica si el compromiso se confirma.",
    "rotate_keys": "Requiere rotación coordinada con los sistemas dependientes.",
    "retry_job": "Reintentar sin corregir la causa puede repetir el fallo.",
    "change_schedule": "No libera capacidad si la causa es el destino.",
    "change_target": "Depende de que el arreglo alternativo esté en línea.",
    "verify_integrity": "Verifica pero no previene el fallo de capacidad.",
    "test_restore": "Valida recuperación pero no resuelve la causa inmediata.",
    "block_port": "Puede cortar tráfico legítimo hacia el puerto.",
    "modify_acl": "Cambia el plano de acceso y requiere revisión de autorización.",
    "reroute_traffic": "La ruta alterna debe verificarse antes de desviar tráfico.",
    "enable_ddos_protection": "Mitigación preventiva, no resuelve el incidente activo.",
    "increase_log_level": "Observa más, no resuelve la causa.",
    "add_metric": "Expone más datos, no resuelve la causa.",
    "create_alert_rule": "Notifica el problema, no lo mitiga.",
    "adjust_threshold": "Ajusta la señal de alerta sin abordar la causa.",
}


def resolve_domain(context: Context) -> str | None:
    """Resolve the Action Space domain for a Context (declarative mapping).

    Uses the Context's mental model binding first; falls back to the purpose.
    Returns None when no declarative binding applies: no recommendation is
    formed for scopes without an explicit Action Space (the system never
    invents an action space).
    """
    domain = MENTAL_MODEL_DOMAINS.get(context.mental_model_id)
    if domain is None:
        domain = PURPOSE_DOMAINS.get(context.purpose)
    return domain


def select_action_space(
    action_spaces: Sequence[ActionSpaceEntry],
    domain: str | None,
    purpose: str,
) -> ActionSpaceEntry | None:
    """The explicit Action Space of a domain that applies to a purpose.

    Only spaces declared in the catalogue qualify; the Formulator may never
    choose outside the explicit space (framework: the action space must be
    explicit so the system knows what it is choosing among).
    """
    if domain is None:
        return None
    for entry in action_spaces:
        if entry.domain == domain and (
            not entry.purposes or purpose in entry.purposes
        ):
            return entry
    return None


def resolve_active_context(
    hypothesis: Hypothesis,
    anomalies: Sequence[Anomaly],
    contexts: Sequence[Context],
) -> Context | None:
    """The Active Context a Hypothesis accounts for (read-only, P1).

    Follows the traceability chain hypothesis -> anomaly (``anomaly_ids``) ->
    context (``anomaly.context_id``) and prefers the currently active activation
    (``is_active = true``); otherwise None (no Active Context -> no
    recommendation). Pure: reads the pre-loaded P1 immutable objects.
    """
    anomaly_ids = set(hypothesis.anomaly_ids)
    ctx_ids = {a.context_id for a in anomalies if a.id in anomaly_ids}
    for ctx in contexts:
        if ctx.id in ctx_ids and ctx.is_active:
            return ctx
    return None


def _validate(
    hypothesis: Hypothesis, confidence: Confidence, context: Context
) -> None:
    """Guard traceability invariants before formulating (fail loudly, not silently)."""
    if confidence.target_type != TARGET_TYPE_HYPOTHESIS:
        raise ValueError(
            f"confidence target_type must be {TARGET_TYPE_HYPOTHESIS!r}, "
            f"got {confidence.target_type!r}"
        )
    if confidence.target_id != hypothesis.id:
        raise ValueError(
            "confidence must calibrate the leading hypothesis (target_id mismatch)"
        )
    if confidence.tenant_id != hypothesis.tenant_id or (
        context.tenant_id != hypothesis.tenant_id
    ):
        raise ValueError("tenant mismatch across hypothesis/confidence/context")


def _alternative_records(
    alternatives: list[str], confidence: Confidence
) -> list[dict[str, object]]:
    """One record per alternative: rationale + rejected reason + confidence.

    The alternative's confidence is the CALIBRATED confidence of the shared
    understanding (the leading Hypothesis) - in the MVP the offer and its
    alternatives arise from the same understanding, so they carry the same
    calibrated score. Per-alternative calibration (each option as its own
    target) is a future phase documented in the journal.
    """
    records: list[dict[str, object]] = []
    for action in alternatives:
        records.append(
            {
                "action": action,
                "rationale": CONSIDERATION_RATIONALE.get(
                    action, "Opción considerada dentro del action space explícito."
                ),
                "rejected_reason": REJECTION_REASONS.get(
                    action,
                    "No elegida como acción principal en esta formulación.",
                ),
                "confidence": round(confidence.confidence_score, 4),
            }
        )
    return records


def _rationale(
    hypothesis: Hypothesis,
    confidence: Confidence,
    context: Context,
    entry: ActionSpaceEntry,
    leading: str,
) -> str:
    """Traceable, first-class rationale (evidence/hypothesis/confidence facts).

    Cites only facts that exist in the P1 immutable artifacts - the Context
    binding, the Hypothesis description/consequences/falsification and the
    calibrated Confidence score and its justification - and declares the chosen
    action inside the explicit Action Space. No unbacked causal language.
    """
    consequences = "; ".join(hypothesis.predicted_consequences) or "ninguna"
    return (
        f"Recomendación para el contexto activo {context.mental_model_id!r} "
        f"(propósito {context.purpose!r}, coherencia de activación "
        f"{context.coherence_score:.4f}). "
        f"Derivada de la hipótesis candidata {hypothesis.id} - "
        f"{hypothesis.description!r} - con consecuencias observables declaradas "
        f"({consequences}) y criterio de falsificación {hypothesis.falsification_criterion!r}. "
        f"Confidence calibrada {confidence.confidence_score:.4f} (id {confidence.id}): "
        f"{confidence.calibration_justification} "
        f"Acción propuesta {leading!r}, elegida dentro del action space explícito "
        f"{entry.action_id!r} del dominio {entry.domain!r}. La propuesta es advisory "
        f"y reversible: no se ejecuta nada (P6); el compromiso y la autoridad "
        f"residen en la Decision (Sprint 10)."
    )


def formulate(
    hypothesis: Hypothesis,
    confidence: Confidence,
    context: Context,
    action_space: ActionSpaceEntry,
) -> RecommendationCreate | None:
    """Derive the best course of action for the current purpose (pure, no I/O).

    Returns a ``RecommendationCreate`` (advisory, ``status='proposed'``) or
    None when the Context's domain does not match the given Action Space (the
    service then counts the hypothesis as ``without_action_space``). The chosen
    action is the declared leading action of the domain when present in the
    explicit space, otherwise the first permitted action in canonical order.
    ``confidence_score`` is the calibrated score of the leading Hypothesis
    (never recalibrated). Deterministic: same inputs -> same offer.
    """
    _validate(hypothesis, confidence, context)
    domain = resolve_domain(context)
    if domain is None or domain != action_space.domain:
        return None
    if action_space.purposes and context.purpose not in action_space.purposes:
        return None

    allowed = sorted(action_space.allowed_actions)
    leading = LEADING_ACTION_BY_DOMAIN.get(domain)
    if leading is None or leading not in action_space.allowed_actions:
        leading = allowed[0]

    alternatives = [action for action in allowed if action != leading]
    return RecommendationCreate(
        tenant_id=hypothesis.tenant_id,
        hypothesis_id=hypothesis.id,
        insight_id=None,
        confidence_id=confidence.id,
        action_description=ACTION_DESCRIPTION_TEMPLATES.get(leading, leading),
        rationale=_rationale(hypothesis, confidence, context, action_space, leading),
        expected_consequences=list(CONSEQUENCE_TEMPLATES.get(leading, ())),
        alternatives_considered=_alternative_records(alternatives, confidence),
        confidence_score=confidence.confidence_score,
        status=STATUS_PROPOSED,
    )