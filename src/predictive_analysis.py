from __future__ import annotations

import json
import urllib.request
import urllib.error


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"
OLLAMA_TIMEOUT_S = 250
OLLAMA_MAX_TOKENS = 800


def _build_prompt(history: list[dict]) -> str:

    return (
        "Tu es un expert en analyse prédictive et infrastructure IT "
        "pour une PME française.\n\n"

        "Voici l'historique des données d'infrastructure :\n\n"
        f"{json.dumps(history, ensure_ascii=False)}\n\n"

        "Analyse l'ensemble de cet historique afin de :\n"
        "- identifier les tendances émergentes ;\n"
        "- anticiper les défaillances potentielles ;\n"
        "- anticiper les risques de surcharge ;\n"
        "- proposer des actions permettant d'optimiser "
        "la planification des ressources.\n\n"

        "Base ton analyse uniquement sur les données fournies.\n"
        "Ne considère pas chaque mesure indépendamment : "
        "analyse leur évolution dans l'historique.\n\n"

        "Réponds STRICTEMENT avec un objet JSON valide "
        "ayant exactement cette structure :\n"

        "{"
        '"trends": [], '
        '"potential_failures": [], '
        '"potential_overloads": [], '
        '"resource_planning": []'
        "}\n\n"

        "Chaque élément doit être court, précis et basé "
        "sur les données observées.\n"
        "Réponds uniquement en français.\n"
        "Aucun texte avant ou après le JSON."
    )


def _call_llm(history: list[dict]) -> dict | None:

    prompt = _build_prompt(history)

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "num_predict": OLLAMA_MAX_TOKENS
        },
    }).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={
            "Content-Type": "application/json"
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=OLLAMA_TIMEOUT_S
        ) as response:

            result = json.loads(response.read())

        analysis = json.loads(result["response"])

    except (
        urllib.error.URLError,
        TimeoutError,
        KeyError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:

        print(
            f"[predictive-analysis] "
            f"Appel Mistral impossible : {exc}"
        )

        return None

    required_keys = {
        "trends",
        "potential_failures",
        "potential_overloads",
        "resource_planning",
    }

    if not required_keys.issubset(analysis.keys()):

        print(
            "[predictive-analysis] "
            "Réponse Mistral incomplète."
        )

        return None

    return analysis


def predictive_analysis_node(state: dict) -> dict:

    history = state["input_data_logs"]

    if not history:
        state["predictive_analysis"] = {
            "trends": [],
            "potential_failures": [],
            "potential_overloads": [],
            "resource_planning": [],
        }

        return state

    analysis = _call_llm(history)

    if analysis is None:
        analysis = {
            "trends": [],
            "potential_failures": [],
            "potential_overloads": [],
            "resource_planning": [],
        }

    state["predictive_analysis"] = analysis

    return state