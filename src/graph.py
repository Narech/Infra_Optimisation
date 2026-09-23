
"""
Orchestration du pipeline : Ingestion -> Detection d'anomalies -> Recommandation.

Implémentation avec la librairie LangGraph (StateGraph). 
Chaque étape reste
une fonction pure state -> state (dict).

Requirement : pip install langgraph
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import TypedDict, Any

from langgraph.graph import StateGraph, END

from .data_ingestion_processing import data_ingestion_node
from .anomaly_detection import anomaly_detection_node
from .generate_recommendation import generate_recommendation_node


class PipelineState(TypedDict, total=False):

    data_file: str
    input_data_logs: list
    ingestion_logs: dict
    anomalies: list
    aggregates: dict
    service_status_summary: dict
    recommendations: list


def build_graph():
    """ Construit et compile le graphe LangGraph :
    ingestion -> analyse -> recommandation -> END
    """
    graph = StateGraph(PipelineState)

    graph.add_node("ingestion", data_ingestion_node)
    graph.add_node("anomaly_detection", anomaly_detection_node)
    graph.add_node("generate_recommendation", generate_recommendation_node)

    graph.set_entry_point("ingestion")
    graph.add_edge("ingestion", "anomaly_detection")
    graph.add_edge("anomaly_detection", "generate_recommendation")
    graph.add_edge("generate_recommendation", END)

    return graph.compile()


def run_pipeline(data_file: str) -> dict:
    """Exécute le graphe LangGraph et construit le rapport final."""
    compiled_graph = build_graph()
    state: PipelineState = compiled_graph.invoke({"data_file": data_file})

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "insights": state["aggregates"]["insights"],
        "average_latency_ms": state["aggregates"]["average_latency_ms"],
        "max_cpu_usage": state["aggregates"]["max_cpu_usage"],
        "max_memory_usage": state["aggregates"]["max_memory_usage"],
        "error_rate": state["aggregates"]["error_rate"],
        "uptime_seconds": state["aggregates"]["uptime_seconds"],
        "anomalies": state["anomalies"],
        "recommendations": state["recommendations"],
        "service_status_summary": state["service_status_summary"],
    }
    return report