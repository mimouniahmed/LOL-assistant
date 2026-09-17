import json
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CHAMPION_MAP_CACHE = DATA_DIR / "champion_id_map.json"


def get_champion_id_to_name(cache_path=CHAMPION_MAP_CACHE):
    """Associe chaque championId numérique (tel que renvoyé par Spectator-V5) au nom du
    champion (le même format que partout ailleurs dans le projet : dataset, SHAP, game_plan.py).
    Source : Data Dragon, le CDN statique et non authentifié de Riot pour les données de jeu
    (pas besoin de clé API). Mis en cache localement pour ne pas re-télécharger à chaque appel."""
    if cache_path.exists():
        with open(cache_path) as f:
            return json.load(f)

    versions = requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()
    latest = versions[0]
    champions = requests.get(
        f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion.json"
    ).json()["data"]

    id_to_name = {entry["key"]: entry["id"] for entry in champions.values()}

    with open(cache_path, "w") as f:
        json.dump(id_to_name, f)

    return id_to_name


def get_composition_from_active_game(riot_client, game_name, tag_line):
    """Raccourci de saisie : au lieu de taper 10 noms de champions à la main, on les récupère
    depuis la partie en cours d'un joueur (Spectator-V5). Une fois les deux équipes extraites,
    la partie en cours elle-même n'est plus utilisée — ni son état (kills, or, timers) ni son
    résultat, seuls les 10 noms de champions comptent, exactement comme pour une composition
    saisie à la main. Ça ne change pas le contrat du produit (composition hypothétique en
    entrée), ça change juste comment on la saisit.

    Lève une ValueError si le joueur n'est pas en partie actuellement."""
    puuid = riot_client.get_puuid(game_name, tag_line)
    game = riot_client.get_active_game(puuid)
    if game is None:
        raise ValueError(f"{game_name}#{tag_line} n'est pas en partie actuellement.")

    id_to_name = get_champion_id_to_name()

    me = next(p for p in game["participants"] if p["puuid"] == puuid)
    my_team_id = me["teamId"]

    your_team = []
    enemy_team = []
    for p in game["participants"]:
        champion_name = id_to_name[str(p["championId"])]
        if p["teamId"] == my_team_id:
            your_team.append(champion_name)
        else:
            enemy_team.append(champion_name)

    return your_team, enemy_team
