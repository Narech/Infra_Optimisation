"""
Pour lancer le pipeline et écrire output.json.

[--input data/rapport.json] [--output output.json]
"""
import argparse
import json

from src.graph import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Pipeline d'optimisation d'infrastructure")
    parser.add_argument("--input", default="data/rapport.json", help="Fichier de logs JSON en entrée")
    parser.add_argument("--output", default="output.json", help="Fichier de rapport JSON en sortie")
    args = parser.parse_args()

    report = run_pipeline(args.input)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Rapport généré : {args.output}")
    print(f"  - {len(report['anomalies'])} anomalie(s) détectée(s)")
    print(f"  - {len(report['recommendations'])} recommandation(s) générée(s)")


if __name__ == "__main__":
    main()
