import difflib
import os
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Sonnet 5 par défaut : tâche de rédaction assez "gabarisée" (données structurées -> texte),
# pas besoin du modèle le plus capable. Passer model="claude-opus-5" pour la meilleure qualité.
DEFAULT_MODEL = "claude-sonnet-5"

# "champion" et "role" apparaissent dans les CSV exportés (oubli du filtre dans le notebook
# d'entraînement) mais ce ne sont pas des faits de jeu actionnables — à exclure du classement.
NON_FACT_COLUMNS = {"champion", "role"}


def load_ranking_artifacts(data_dir=DATA_DIR):
    """Charge les deux artefacts nécessaires à composition_fact_ranking, produits par
    notebooks/03_model_training.ipynb (étapes 1 et 2 de l'analyse SHAP)."""
    global_importance = (
        pd.read_csv(data_dir / "global_shap_importance.csv")
        .set_index("feature")["mean_abs_shap"]
    )
    interactions = pd.read_csv(data_dir / "champion_feature_interactions.csv")
    return global_importance, interactions


def _validate_team(champions, known_champions):
    if len(champions) != 5:
        raise ValueError(f"Une équipe doit avoir exactement 5 champions, reçu {len(champions)} : {champions}")

    unknown = [c for c in champions if c not in known_champions]
    if unknown:
        details = []
        for c in unknown:
            close = difflib.get_close_matches(c, known_champions, n=1)
            details.append(f"'{c}'" + (f" (vouliez-vous dire '{close[0]}' ?)" if close else " (inconnu)"))
        raise ValueError("Champion(s) non reconnu(s) : " + ", ".join(details))


def composition_fact_ranking(champions, global_importance, interactions):
    """champions : liste de 5 noms de champions (une équipe). Renvoie un classement des faits
    de jeu par importance estimée pour cette équipe précise (global + le champion le plus
    concerné, pas une somme — voir notebooks/03_model_training.ipynb, Concept 19).

    Lève une ValueError si la liste n'a pas exactement 5 noms, ou si un nom de champion
    n'est pas reconnu (avec une suggestion si un nom proche existe)."""
    _validate_team(champions, set(interactions["champion"].unique()))

    features = [f for f in global_importance.index if f not in NON_FACT_COLUMNS]

    rows = []
    for feat in features:
        base = global_importance.get(feat, 0.0)
        key_champion = None
        key_boost = 0.0

        subset = interactions[
            interactions["champion"].isin(champions) & (interactions["feature"] == feat)
        ]
        for row in subset.itertuples():
            if row.mean_abs_interaction > key_boost:
                key_boost = row.mean_abs_interaction
                key_champion = row.champion

        rows.append({
            "feature": feat,
            "global_importance": base,
            "key_champion": key_champion,
            "key_champion_boost": key_boost,
            "team_importance": base + key_boost,
        })

    return pd.DataFrame(rows).sort_values("team_importance", ascending=False).reset_index(drop=True)


def _format_ranking(ranking, top_n):
    lines = []
    for row in ranking.head(top_n).itertuples():
        champ_note = f" (surtout via {row.key_champion})" if row.key_champion else ""
        lines.append(f"- {row.feature}{champ_note}")
    return "\n".join(lines)


def build_game_plan_prompt(your_team, enemy_team, your_ranking, enemy_ranking, top_n=6):
    """Construit le prompt envoyé au LLM à partir des deux classements déjà calculés."""
    return f"""Voici une composition League of Legends à analyser.

Notre équipe : {", ".join(your_team)}
Équipe adverse : {", ".join(enemy_team)}

D'après un modèle entraîné sur des dizaines de milliers de vraies parties, voici les faits de jeu \
(objectifs, avance en lane, etc.) qui comptent le plus pour NOTRE équipe, avec le champion à qui \
chaque fait profite le plus (élément statistique, pas une garantie) :
{_format_ranking(your_ranking, top_n)}

Et voici les mêmes faits de jeu, mais pour l'équipe ADVERSE — donc ce sur quoi elle va probablement \
s'appuyer, et qu'on devrait chercher à empêcher ou retarder :
{_format_ranking(enemy_ranking, top_n)}

Rédige un plan de jeu court et concret pour NOTRE équipe, en français :
1. Explique en langage clair et actionnable (pas de jargon de noms de champs bruts) ce sur quoi se \
concentrer en priorité et pourquoi, en mentionnant le champion clé quand c'est pertinent.
2. Explique ce que l'équipe adverse va probablement essayer de faire, et comment le contrer ou le \
retarder.
3. Reste concis (200-300 mots), pas de liste à puces interminable — un ton de coach qui donne un vrai \
plan, pas un rapport de données."""


def generate_game_plan(your_team, enemy_team, client=None, model=DEFAULT_MODEL, data_dir=DATA_DIR):
    """Pipeline complet : classement des faits pour les deux équipes (aucun appel modèle/SHAP,
    juste une lecture des artefacts déjà calculés) + narration par un LLM Claude."""
    global_importance, interactions = load_ranking_artifacts(data_dir)
    your_ranking = composition_fact_ranking(your_team, global_importance, interactions)
    enemy_ranking = composition_fact_ranking(enemy_team, global_importance, interactions)

    prompt = build_game_plan_prompt(your_team, enemy_team, your_ranking, enemy_ranking)

    if client is None:
        load_dotenv()
        client = anthropic.Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    game_plan_text = "".join(block.text for block in response.content if block.type == "text")

    return game_plan_text, your_ranking, enemy_ranking
