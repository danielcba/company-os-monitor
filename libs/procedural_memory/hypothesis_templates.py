"""Hypothesis Templates - declarative candidate explanations (Reasoning/Predict).

The Hypothesis Template Library is procedural memory (P3): a catalogue of
candidate explanations per domain, expressed as declarative templates, never
reasoning and never ML. Each template pairs an explanation with observable
predicted consequences and a concrete falsification criterion - the framework
pairs explanation with prediction, and a prediction detached from explanation
is not a hypothesis.

Per the framework, the system must maintain multiple competing hypotheses
simultaneously (premature convergence on a single explanation is a cognitive
failure), so each scope exposes at least two templates. Templates never
generate anything by themselves: the generator in ``hypothesis-service``
instantiates them with measured facts and emits ``HypothesisCreate`` records.

``coherence_estimate`` is a declarative prior per candidate explanation
(documented, purpose-dependent). The CALIBRATED coherence (S + C + ECE) is
computed by Confidence (Sprint 8) and is out of scope here - the estimate only
seeds the MVP row and is never claimed as measured.
"""
from dataclasses import dataclass, field

from libs.reasoning.anomaly import ANOMALY_CLASS_POINT, ANOMALY_CLASSES

# Anomaly classes supported by the MVP templates. Only ``point`` has templates
# today; contextual/collective are reserved for later sprints.
HYPOTHESIS_SCOPED_ANOMALY_CLASSES: frozenset[str] = frozenset({ANOMALY_CLASS_POINT})


@dataclass(frozen=True)
class HypothesisTemplate:
    """Declarative definition of one candidate explanation (procedural memory).

    ``template_id`` is versioned (``_v1``/``_v2``): revising a template means
    publishing a NEW version, never mutating a published one. ``scope_anomaly_class``
    restricts which anomaly classes the template applies to; ``scope_mental_models``
    and ``scope_purposes`` (empty frozenset = all purposes) restrict which
    scopes it explains. ``description_template``/``consequence_templates``/
    ``falsification_templates`` carry placeholders for measured facts
    (``{scope}``, ``{anomaly_class}``, ``{deviation_score}``, ``{frequency}``).
    The generated hypothesis is TENTATIVE: description language is hypothetical
    (``podría``/``candidata``), never asserted as fact (the framework's
    Non-example: asserting "because disk is full" without testing is an
    assumption, not a hypothesis).
    """

    template_id: str
    scope_anomaly_class: str = ANOMALY_CLASS_POINT
    scope_mental_models: frozenset[str] = field(default_factory=frozenset)
    scope_purposes: frozenset[str] = field(default_factory=frozenset)
    description_template: str = ""
    consequence_templates: tuple[str, ...] = ()
    falsification_templates: tuple[str, ...] = ()
    coherence_estimate: float = 0.5

    def __post_init__(self) -> None:
        if self.scope_anomaly_class not in ANOMALY_CLASSES:
            raise ValueError(f"unknown anomaly_class: {self.scope_anomaly_class}")  # noqa: TRY003
        if not self.description_template.strip():
            raise ValueError("description_template must not be empty")  # noqa: TRY003
        if not self.consequence_templates:
            raise ValueError("consequence_templates must not be empty")  # noqa: TRY003
        if not self.falsification_templates:
            raise ValueError("falsification_templates must not be empty")  # noqa: TRY003
        if not 0.0 <= self.coherence_estimate <= 1.0:
            raise ValueError("coherence_estimate must be in [0, 1]")  # noqa: TRY003


def _t(  # noqa: PLR0913, PLR0917 - factory for declarative template records
    template_id: str,
    models: tuple[str, ...],
    description: str,
    consequences: tuple[str, ...],
    falsifications: tuple[str, ...],
    coherence: float,
    purposes: frozenset[str] = frozenset(),
) -> HypothesisTemplate:
    return HypothesisTemplate(
        template_id=template_id,
        scope_anomaly_class=ANOMALY_CLASS_POINT,
        scope_mental_models=frozenset(models),
        scope_purposes=purposes,
        description_template=description,
        consequence_templates=consequences,
        falsification_templates=falsifications,
        coherence_estimate=coherence,
    )


HYPOTHESIS_TEMPLATE_LIBRARY: tuple[HypothesisTemplate, ...] = (
    # ------------------------------------------------------------------
    # Disk Saturation (resource_pressure) - H1/H2/H3
    # ------------------------------------------------------------------
    _t(
        "disk_logging_verbosity_v1",
        ("resource_pressure",),
        "Un aumento de la verbosidad de logging podría elevar el uso de CPU/memoria/disco "
        "en el scope {scope} (desviación {deviation_score:.1f}, clase {anomaly_class}).",
        (
            "El patrón de escritura de logs del proceso activo mostrará un incremento "
            "sostenido de líneas por minuto (frecuencia observada {frequency}).",
            "Los niveles de verbosidad configurados habrán cambiado dentro de la ventana "
            "de la desviación.",
        ),
        (
            "Si el nivel de verbosidad de logging se mantiene sin cambios y el volumen "
            "de líneas por minuto no aumentó, la hipótesis queda descartada.",
        ),
        0.5,
    ),
    _t(
        "disk_retention_policy_v1",
        ("resource_pressure",),
        "Un cambio en la política de retención podría haber elevado el volumen de datos "
        "persistidos en el scope {scope} (desviación {deviation_score:.1f}, "
        "clase {anomaly_class}).",
        (
            "El volumen de datos retenidos por los jobs de retención mostrará un incremento "
            "acorde a la nueva política (frecuencia observada {frequency}).",
            "Las políticas de retención configuradas habrán cambiado dentro de la ventana "
            "de la desviación.",
        ),
        (
            "Si la política de retención no cambió y el volumen retenido por los jobs "
            "permanece constante, la hipótesis queda descartada.",
        ),
        0.4,
    ),
    _t(
        "disk_auto_growth_v1",
        ("resource_pressure",),
        "Una configuración de auto-growth mal ajustada podría haber agotado el espacio "
        "disponible en el scope {scope} (desviación {deviation_score:.1f}, "
        "clase {anomaly_class}).",
        (
            "Los archivos de datos con auto-growth habrán crecido hasta el límite "
            "configurado (frecuencia observada {frequency}).",
            "Los eventos de auto-growth en el registro del motor habrán aumentado dentro "
            "de la ventana de la desviación.",
        ),
        (
            "Si las configuraciones de auto-growth se encuentran en valores normales y no "
            "se registraron eventos de crecimiento en la ventana, la hipótesis queda "
            "descartada.",
        ),
        0.5,
    ),
    # ------------------------------------------------------------------
    # Backup Failure (capacity_risk) - H1/H2/H3
    # ------------------------------------------------------------------
    _t(
        "backup_maintenance_schedule_v1",
        ("capacity_risk",),
        "Un cambio en el horario del job de mantenimiento podría explicar la desviación "
        "en el scope {scope} (desviación {deviation_score:.1f}, clase {anomaly_class}).",
        (
            "El job de mantenimiento aparecerá programado en un horario distinto al "
            "registrado previamente (frecuencia observada {frequency}).",
            "La ventana de ejecución del mantenimiento habrá cambiado dentro de la ventana "
            "de la desviación.",
        ),
        (
            "Si el horario del job de mantenimiento no cambió, la hipótesis queda "
            "descartada.",
        ),
        0.5,
    ),
    _t(
        "backup_target_capacity_v1",
        ("capacity_risk",),
        "El destino de backup podría haber alcanzado su capacidad durante la ventana "
        "del scope {scope} (desviación {deviation_score:.1f}, clase {anomaly_class}).",
        (
            "El espacio libre del destino de backup habrá descendido por debajo del umbral "
            "documentado (frecuencia observada {frequency}).",
            "Los intentos de escritura del backup habrán fallado por falta de espacio "
            "dentro de la ventana.",
        ),
        (
            "Si el espacio libre del destino permanece por encima del umbral, la hipótesis "
            "queda descartada.",
        ),
        0.6,
    ),
    _t(
        "backup_antivirus_conflict_v1",
        ("capacity_risk",),
        "Un análisis antivirus nuevo podría interferir con la ventana de backup "
        "en el scope {scope} (desviación {deviation_score:.1f}, clase {anomaly_class}).",
        (
            "Se registrará un análisis antivirus solapado con la ventana de backup "
            "(frecuencia observada {frequency}).",
            "El horario del análisis antivirus habrá cambiado dentro de la ventana "
            "de la desviación.",
        ),
        (
            "Si no hay análisis antivirus configurado en la ventana de backup o su horario "
            "no cambió, la hipótesis queda descartada.",
        ),
        0.4,
    ),
    # ------------------------------------------------------------------
    # Auth Burst (auth_compromise) - H1/H2/H3
    # ------------------------------------------------------------------
    _t(
        "auth_compromised_account_v1",
        ("auth_compromise",),
        "Una cuenta comprometida podría estar siendo sondeada por un actor externo "
        "en el scope {scope} (desviación {deviation_score:.1f}, clase {anomaly_class}).",
        (
            "Los intentos de autenticación fallidos provendrán de un conjunto acotado de "
            "orígenes (frecuencia observada {frequency}).",
            "Se observará un patrón de credenciales probadas sobre la misma cuenta dentro "
            "de la ventana.",
        ),
        (
            "Si los intentos fallidos provienen de un único origen o no se concentran en "
            "una cuenta, la hipótesis queda descartada.",
        ),
        0.6,
    ),
    _t(
        "auth_retry_loop_v1",
        ("auth_compromise",),
        "Una aplicación mal configurada podría estar reintentando autenticaciones en un "
        "bucle en el scope {scope} (desviación {deviation_score:.1f}, "
        "clase {anomaly_class}).",
        (
            "Los logs de la aplicación mostrarán reintentos periódicos y regulares de "
            "autenticación (frecuencia observada {frequency}).",
            "El origen de los reintentos será consistente con un único cliente "
            "de aplicación.",
        ),
        (
            "Si los logs de la aplicación no muestran reintentos periódicos, la hipótesis "
            "queda descartada.",
        ),
        0.5,
    ),
    _t(
        "auth_external_monitoring_v1",
        ("auth_compromise",),
        "Una herramienta de monitoreo externa podría estar probando credenciales "
        "en el scope {scope} (desviación {deviation_score:.1f}, clase {anomaly_class}).",
        (
            "Se identificará una herramienta de monitoreo configurada que realiza pruebas "
            "de autenticación (frecuencia observada {frequency}).",
            "El patrón de los intentos coincidirá con la cadencia documentada de dicha "
            "herramienta.",
        ),
        (
            "Si no existe una herramienta de monitoreo configurada que pruebe credenciales, "
            "la hipótesis queda descartada.",
        ),
        0.4,
    ),
)

HYPOTHESIS_TEMPLATES: dict[str, HypothesisTemplate] = {
    definition.template_id: definition for definition in HYPOTHESIS_TEMPLATE_LIBRARY
}
