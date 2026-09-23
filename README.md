# Infra Optimisation

Pipeline d'analyse d'infrastructure technique pour une PME française : ingestion
de logs, détection d'anomalies par seuils métier, et génération de
recommandations d'optimisation orchestré avec **LangGraph**.

## Architecture

Le pipeline est un graphe LangGraph séquentiel à 3 nœuds :

data/rapport.json
1- Ingestion (Lecture et validation)
2- Détection d'anomalies
3- Génération de recommendations ( Avec un LLM local, Mistral vis Ollama et des recommendations statiques en support)

## Fichiers

- `src/data_ingestion_processing.py` lit `data/rapport.json`, valide chaque enregistrement contre le schéma attendu (`DATA_STRUCTURE`), rejette et journalise les entrées non conformes. 

- `src/anomaly_detection.py` calcule les statistiques globaux (latence moyenne, pics CPU/mémoire, taux d'erreur, uptime, insights) et détecte les anomalies par comparaison à des seuils métier (`SEUILS`), ainsi que le statut de chaque service (`service_status_summary`)

- `src/generate_recommendation.py`, pour chaque anomalie détectée, génère une recommandation d'action via un LLM local Mistral (via Ollama), avec renvoi automatique sur des recommendations statiques en cas d'échec

- `src/graph.py`  Construit et compile le graphe LangGraph (`StateGraph`), définit l'état partagé (`PipelineState`) et assemble le rapport final. 

- `src/main.py` Point d'entrée CLI : exécute le pipeline et écrit `output.json` 

## Choix techniques

- **Orchestration LangGraph** : chaque étape est un nœud (`state -> state`) relié par `add_edge`, avec un état typé (`TypedDict`) déclarant les clés que chaque nœud lit et écrit (nécessaire pour que LangGraph propage correctement les données d'un nœud à l'autre)

- **Recommandations par LLM local Mistral (via Ollama)**, plutôt qu'une API payante, Ollama est gratuit, opensource, sans clé API, fonctionne hors-ligne une fois le modèle téléchargé (`ollama pull mistral`). 
Avec le prompt j'ai demandé une réponse JSON, en français, avec 4 champs (`action`, `target`, `parameters`, `advantage`)

- **Recommendations statiques en cas d'échec de Ollama** : si Ollama n'est pas lancé, si l'appel expire (timeout), ou si la réponse du modèle est incomplète ou mal formée, le pipeline retombe automatiquement sur `RECOMMENDATION_RULES`, des recommendations statiques couvrant chaque métrique. Le pipeline ne plante donc jamais à cause d'une indisponibilité du LLM.

- **Seuils d'anomalie** (`SEUILS` dans `anomaly_detection.py`) calibrés par métrique, avec un niveau `medium`/`high` selon la valeur observée.

## Format de sortie (`output.json`)

```json
{
  "timestamp": "2026-09-23T11:38:54Z",
  "insights": {
    "avg_cpu_usage": 60.67,
    "avg_memory_usage": 67.63,
    "avg_disk_usage": 63.91,
    "avg_io_wait": 4.01,
    "max_latency_ms": 384,
    "max_temperature_celsius": 89,
    "points_analyzed": 500
  },
  "average_latency_ms": 0,
  "max_cpu_usage": 0,
  "max_memory_usage": 0,
  "error_rate": 0,
  "uptime_seconds": 0,
  "anomalies": [
    {
      "metric": "cpu_usage",
      "value": 99,
      "seuil": 75,
      "anomaly_level": "high",
      "description": "Utilisation CPU élevée (relevé à 2023-10-02T13:00:00Z)"
    }
  ],
  "recommendations": [
    {
      "id": "rec-001",
      "action": "Mettre à l'échelle le serveur ou réduire la charge de travail",
      "target": "compute",
      "parameters": { "strategy": "..." },
      "advantage": "Réduction de 20% de la consommation de ressources CPU..."
    }
  ],
  "service_status_summary": {
    "online": ["database", "api_gateway", "cache"],
    "degraded": [],
    "offline": []
  }
}
```

## Installation

```bash
python3 -m venv .env_infra_optimisation
source .env_infra_optimisation/bin/activate
pip install -r requirements.txt
```

### Prérequis pour obtenir les recommandations par LLM

1. Installer [Ollama](https://ollama.com/download)
brew install ollama
2. Télécharger le modèle : `ollama pull mistral` 
3. Lancer le serveur Ollama en arrière-plan : `ollama serve`


## Exécution

```bash
python3 -m src.main
```

Le terminal affiche le nombre d'enregistrements analysés, le nombre
d'anomalies détectées et le nombre de recommandations générées.

## Configuration du modèle LLM

Dans `src/generate_recommendation.py` :

- `OLLAMA_MODEL`: Modèle Ollama utilisé (`mistral`)
- `OLLAMA_TIMEOUT_S`: Délai maximum par appel avant renvoi à la recommendation statique 
- `OLLAMA_MAX_TOKENS`: Longueur maximale de la réponse générée pour éviter un JSON tronqué

