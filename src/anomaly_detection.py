"""
Pour la détection d'anomalies
Permet de:
- Analyser les métriques et identifier les valeurs anormales en fonction des seuils définis
- Calculer les stats sur toute la fenêtre de logs.

Entrée  : state["input_data_logs"]
Sortie  : state["anomalies"]
          state["aggregates"]
          state["service_status_summary"]
"""

from __future__ import annotations


# Seuils (medium, high)
SEUILS = {
    "cpu_usage": (75, 90),                  # %
    "memory_usage": (75, 90),               # %
    "latency_ms": (200, 400),               # ms
    "disk_usage": (80, 92),                 # %
    "io_wait": (10, 20),                    # %
    "error_rate": (0.03, 0.1),              # ratio
    "temperature_celsius": (75, 85),        # °C
}


# Description des métriques
METRIC_DESCRIPTIONS = {
    "cpu_usage": "Utilisation CPU élevée",
    "memory_usage": "Utilisation mémoire élevée",
    "latency_ms": "Latence réseau/applicative élevée",
    "disk_usage": "Espace disque presque saturé",
    "io_wait": "Attente I/O disque anormalement haute",
    "error_rate": "Taux d'erreur applicatif élevé",
    "temperature_celsius": "Température matérielle élevée",
}

SERVICE_STATUS_LEVEL = {"online": 0, "degraded": 1, "offline": 2}


def _get_anomaly_level(
    value: float,
    medium: float,
    high: float
) -> str | None:
    """Détermine le niveau d'une anomalie."""

    if value >= high:
        return "high"

    if value >= medium:
        return "medium"

    return None


def _detect_metric_anomalies(logs: list[dict]) -> list[dict]:
    """Conserve la valeur la plus critique pour chaque métrique."""

    worst_by_metric: dict[str, dict] = {}

    for entry in logs:
        for metric, (medium, high) in SEUILS.items():

            value = entry.get(metric)

            if value is None:
                continue

            anomaly_level = _get_anomaly_level(
                value,
                medium,
                high
            )

            if anomaly_level is None:
                continue

            current_worst = worst_by_metric.get(metric)

            if current_worst is None or value > current_worst["value"]:
                worst_by_metric[metric] = {
                    "metric": metric,
                    "value": value,
                    "threshold": medium,
                    "severity": anomaly_level,
                    "description": (
                        f"{METRIC_DESCRIPTIONS[metric]} "
                        f"(relevé à {entry['timestamp']})"
                    ),
                }

    return list(worst_by_metric.values())


def _detect_service_anomalies(logs: list[dict]) -> list[dict]:
    """Détecte les anomalies liées aux statuts des services."""

    anomalies = []
    seen = set()

    for entry in logs:

        for service, status in entry.get(
            "service_status", {}
        ).items():

            if (
                status in ("degraded", "offline")
                and (service, status) not in seen
            ):
                seen.add((service, status))

                anomaly_level = (
                    "high"
                    if status == "offline"
                    else "medium"
                )

                anomalies.append({
                    "metric": f"service_status.{service}",
                    "value": SERVICE_STATUS_LEVEL[status],
                    "threshold": SERVICE_STATUS_LEVEL["online"],
                    "severity": anomaly_level,
                    "description": (
                        f"Le service '{service}' est en statut "
                        f"'{status}' "
                        f"(relevé à {entry['timestamp']})"
                    ),
                })

    return anomalies


def _service_status_summary(logs: list[dict]) -> dict:
    """Retourne le statut le plus récent de chaque service."""

    latest_status: dict[str, str] = {}

    for entry in logs:
        for service, status in entry.get(
            "service_status", {}
        ).items():
            latest_status[service] = status

    summary = {
        "online": [],
        "degraded": [],
        "offline": [],
    }

    for service, status in latest_status.items():
        if status in summary:
            summary[status].append(service)

    return summary


def anomaly_detection_node(state: dict) -> dict:
    """
    Nœud pour la détection des anomalies.

    Entrée :
        state["input_data_logs"]

    Sortie :
        state["anomalies"]
        state["aggregates"]
        state["service_status_summary"]
    """

    # Récupération des logs validés par le nœud d'ingestion
    logs = state["input_data_logs"]

    # Détection des anomalies
    metric_anomalies = _detect_metric_anomalies(logs)
    service_anomalies = _detect_service_anomalies(logs)

    anomalies = metric_anomalies + service_anomalies

    # Statistiques globales
    n = len(logs) or 1

    aggregates = {
        "average_latency_ms": round(
            sum(entry["latency_ms"] for entry in logs) / n,
            2
        ),

        "max_cpu_usage": max(
            (entry["cpu_usage"] for entry in logs),
            default=0
        ),

        "max_memory_usage": max(
            (entry["memory_usage"] for entry in logs),
            default=0
        ),

        "error_rate": round(
            sum(entry["error_rate"] for entry in logs) / n,
            4
        ),

        "uptime_seconds": max(
            (entry["uptime_seconds"] for entry in logs),
            default=0
        ),

        "insights": {
            "avg_cpu_usage": round(
                sum(entry["cpu_usage"] for entry in logs) / n,
                2
            ),

            "avg_memory_usage": round(
                sum(entry["memory_usage"] for entry in logs) / n,
                2
            ),

            "avg_disk_usage": round(
                sum(entry["disk_usage"] for entry in logs) / n,
                2
            ),

            "avg_io_wait": round(
                sum(entry["io_wait"] for entry in logs) / n,
                2
            ),

            "max_latency_ms": max(
                (entry["latency_ms"] for entry in logs),
                default=0
            ),

            "max_temperature_celsius": max(
                (
                    entry["temperature_celsius"]
                    for entry in logs
                ),
                default=0
            ),

            "points_analyzed": len(logs),
        },
    }

    # Mise à jour du state
    state["anomalies"] = anomalies
    state["aggregates"] = aggregates
    state["service_status_summary"] = (
        _service_status_summary(logs)
    )

    return state