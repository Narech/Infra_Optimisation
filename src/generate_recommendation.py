"""
Pour la génération de recommendations
Permet de:
- Proposer une action (recommandations métiers, bonnes pratiques infra) pour
  chaque anomalie détectée, en s'appuyant sur un LLM (Mistral via Ollama en local)

Entrée  : state["anomalies"]
Sortie  : state["recommendations"]
"""

from __future__ import annotations
import json
import urllib.request
import urllib.error

from .anomaly_detection import SERVICE_STATUS_LEVEL

STATUS_BY_LEVEL = {level: name for name, level in SERVICE_STATUS_LEVEL.items()}

# Configuration de l'appel au LLM local (Ollama)
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"         
OLLAMA_TIMEOUT_S = 90            
OLLAMA_MAX_TOKENS = 250          

# Proposition de recommendations statiques en cas d'insponibilité du LLM
RECOMMENDATION_RULES = {
    "cpu_usage": {
        "action": "Ajouter des instances (scaling horizontal) ou augmenter la capacité CPU",
        "target": "compute",
        "parameters": {"strategy": "autoscaling", "cpu_target_percent": 65},
        "benefit_estimate": "Réduction estimée de 20-30% du taux d'utilisation CPU moyen",
    },
    "memory_usage": {
        "action": "Augmenter la RAM allouée ou identifier les fuites mémoire applicatives",
        "target": "compute",
        "parameters": {"strategy": "vertical_scaling_or_profiling"},
        "benefit_estimate": "Réduction du risque d'OOM et de swap disque",
    },
    "latency_ms": {
        "action": "Mettre en place un cache applicatif et/ou un load balancer",
        "target": "network",
        "parameters": {"strategy": "caching_and_load_balancing", "cache_ttl_s": 60},
        "benefit_estimate": "Réduction estimée de 30-50% de la latence moyenne",
    },
    "disk_usage": {
        "action": "Nettoyer les données obsolètes ou étendre le volume de stockage",
        "target": "storage",
        "parameters": {"strategy": "cleanup_or_resize"},
        "benefit_estimate": "Évite la saturation disque et les incidents en cascade",
    },
    "io_wait": {
        "action": "Migrer vers un stockage plus rapide (SSD/NVMe) ou répartir la charge I/O",
        "target": "storage",
        "parameters": {"strategy": "storage_upgrade_or_io_balancing"},
        "benefit_estimate": "Réduction du temps d'attente I/O et des files d'attente disque",
    },
    "error_rate": {
        "action": "Analyser les logs applicatifs et envisager un rollback ou un correctif",
        "target": "application",
        "parameters": {"strategy": "log_analysis_and_rollback"},
        "benefit_estimate": "Réduction du taux d'erreur et amélioration de la fiabilité",
    },
    "temperature_celsius": {
        "action": "Vérifier le refroidissement matériel et la charge des équipements",
        "target": "hardware",
        "parameters": {"strategy": "cooling_check"},
        "benefit_estimate": "Réduit le risque de throttling ou de panne matérielle",
    },
}


def _service_fallback(anomaly: dict) -> dict:
    service = anomaly["metric"].split(".", 1)[1]
    status = STATUS_BY_LEVEL.get(anomaly["value"], "inconnu")
    return {
        "action": f"Investiguer et redémarrer/basculer le service '{service}' (statut: {status})",
        "target": f"service:{service}",
        "parameters": {"strategy": "restart_or_failover"},
        "benefit_estimate": "Rétablissement du service et réduction du risque d'indisponibilité",
    }




def _build_prompt(anomaly: dict) -> str:
    return (
        "Tu es un expert en infrastructure IT qui conseille une PME française.\n"
        "IMPORTANT : réponds uniquement en français, y compris dans le JSON "
        "(tous les textes doivent être en français, pas en anglais).\n\n"
        f"Une anomalie a été détectée : métrique='{anomaly['metric']}', "
        f"valeur={anomaly['value']}, seuil={anomaly.get('threshold')}, "
        f"sévérité={anomaly.get('severity')}.\n"
        f"Détail : {anomaly.get('description')}\n\n"
        "Propose UNE recommandation concrète pour y remédier.\n"
        "Sois très concis : les champs 'action' et 'benefit_estimate' doivent "
        "faire chacun moins de 15 mots.\n"
        "Réponds STRICTEMENT avec un objet JSON valide contenant EXACTEMENT "
        "ces 4 clés, sans aucun texte avant ou après :\n"
        '{"action": "...", "target": "compute|network|storage|application|hardware|service:<nom>", '
        '"parameters": {"strategy": "..."}, "benefit_estimate": "..."}\n\n'
        "- action : phrase courte décrivant l'action à mener, EN FRANÇAIS\n"
        "- benefit_estimate : OBLIGATOIRE, le bénéfice attendu, chiffré si pertinent, "
        "EN FRANÇAIS (ex: \"Réduction de 20% de la latence\")\n"
        "- parameters : objet libre avec les paramètres techniques indicatifs\n\n"
        "N'oublie surtout pas le champ 'benefit_estimate', il est indispensable. "
        "Rappel : tout le texte doit être en français."
    )

def _call_llm(anomaly: dict) -> dict | None:
    """Appelle le LLM local via Ollama et retourne un dict de recommandation,
    ou None si l'appel échoue ou que la réponse n'est pas exploitable."""
    prompt = _build_prompt(anomaly)
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",  
        "options": {"num_predict": OLLAMA_MAX_TOKENS},
    }).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_S) as response:
            result = json.loads(response.read())
        parsed = json.loads(result["response"])
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, ValueError) as exc:
        print(f"[llm] Appel LLM impossible ({exc}), bascule sur la règle statique.")
        return None

   
    if len(parsed) == 1 and isinstance(next(iter(parsed.values())), dict):
        parsed = next(iter(parsed.values()))


    ADVANTAGE_ALIASES = ["advantage", "benefit", "avantage", "benefice",
                         "bénéfice", "impact", "gain", "result", "résultat"]
    if "benefit_estimate" not in parsed:
        for alias in ADVANTAGE_ALIASES:
            if alias in parsed:
                parsed["benefit_estimate"] = parsed[alias]
                break

    required_keys = {"action", "target", "parameters", "benefit_estimate"}
    if not required_keys.issubset(parsed.keys()):
        print(
            f"[llm] Réponse LLM incomplète (clés reçues: {list(parsed.keys())}), "
            "bascule sur la règle statique."
        )
        return None

    return {
        "action": parsed["action"],
        "target": parsed["target"],
        "parameters": parsed["parameters"],
        "benefit_estimate": parsed["benefit_estimate"],
    }

def _recommend_for_anomaly(anomaly: dict) -> dict | None:
    """ Lance la fonction pour obtenir la réponse du LLM si pas fonctionnelle,
      utilise la recommendation statique correspondante """
    metric = anomaly["metric"]

    llm_result = _call_llm(anomaly)
    if llm_result is not None:
        return llm_result

    if metric.startswith("service_status."):
        return _service_fallback(anomaly)

    return RECOMMENDATION_RULES.get(metric)


def generate_recommendation_node(state: dict) -> dict:
    """ Nœud pour la génération de recommandation
        Entrée: state['anomalies']
        Pour chaque anomalie, Lance une génération via LLM local (Ollama),
        avec renvoi sur une recommendation statique en cas d'échec.
    """
    anomalies = state["anomalies"]
    recommendations = []

    for idx, anomaly in enumerate(anomalies, start=1):
        rule = _recommend_for_anomaly(anomaly)
        if rule is None:
            continue

        recommendations.append({
            "id": f"rec-{idx:03d}",
            "action": rule["action"],
            "target": rule["target"],
            "parameters": rule["parameters"],
            "benefit_estimate": rule["benefit_estimate"],
        })

    state["recommendations"] = recommendations
    return state