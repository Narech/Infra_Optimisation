"""
Pour l'ingestion et l'analyse des données 
Permet de:
 - Lire le fichier de logs JSON
 - Vérifier que chaque entrée est bien constituée et respecte le format attendu
 - Rejeter les entrées non conformes et le notifier dans les logs 

Input: fichier JSON
Output: state["input_data_logs"]  -> liste des entrées conforme à la structure des données
        state["ingestion_logs"] -> rapport sur l'ingestion des données
"""
from __future__ import annotations
import json
from pathlib import Path

DATA_STRUCTURE= {
    "timestamp": str,
    "cpu_usage": (int, float),
    "memory_usage": (int, float),
    "latency_ms": (int, float),
    "disk_usage": (int, float),
    "network_in_kbps": (int, float),
    "network_out_kbps": (int, float),
    "io_wait": (int, float),
    "thread_count": (int, float),
    "active_connections": (int, float),
    "error_rate": (int, float),
    "uptime_seconds": (int, float),
    "temperature_celsius": (int, float),
    "power_consumption_watts": (int, float),
    "service_status": dict,
}


def _validate_data(entry: dict) -> list[str]:
    """ Vérifie une entrée et retourne les erreurs """
    errors = []
    for key, expected_type in DATA_STRUCTURE.items():
        if key not in entry:
            errors.append(f"champ manquant: {key}")
            continue
        if not isinstance(entry[key], expected_type):
            errors.append(f"type invalide pour {key}: {type(entry[key]).__name__}")
    return errors


def data_ingestion_node(state: dict) -> dict:
    """ Noeud pour l'ingestion des données 
        Entrée: state['data_file'] 
        Sorie:  state['input_data_logs']
    """
    data_file = Path(state["data_file"])
    with open(data_file, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        raw = [raw]  

    valid_keys = []
    rejected = []
    for i, key in enumerate(raw):
        errors = _validate_data(key)
        if errors:
            rejected.append({"index": i, "errors": errors})
        else:
            valid_keys.append(key)

    state["input_data_logs"] = valid_keys
    state["ingestion_logs"] = {
     "total": len(raw),
     "valid": len(valid_keys),
     "invalid": len(rejected),
     "invalid_details": rejected,
    }
    return state
