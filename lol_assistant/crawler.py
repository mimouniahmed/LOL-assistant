from collections import deque

import requests

from . import database


def crawl_matches(riot_client, conn, seed_puuid, target_count, matches_per_player=10):
    queue = deque([seed_puuid])
    collected = 0

    while queue and collected < target_count:
        puuid = queue.popleft()

        if database.player_already_explored(conn, puuid):
            continue
        database.mark_player_explored(conn, puuid)

        try:
            match_ids = riot_client.get_match_ids(puuid, count=matches_per_player)
        except requests.HTTPError as exc:
            print(f"Erreur pour le joueur {puuid} ({exc}), on passe.")
            continue

        for match_id in match_ids:
            if collected >= target_count:
                break
            if database.match_already_collected(conn, match_id):
                continue

            try:
                match_data = riot_client.get_match_detail(match_id)
            except requests.HTTPError as exc:
                print(f"Erreur pour le match {match_id} ({exc}), on passe.")
                continue

            database.save_match(conn, match_id, riot_client.region, match_data)
            collected += 1

            # snowball : les 10 participants de ce match deviennent de nouvelles graines
            for participant_puuid in match_data["metadata"]["participants"]:
                if not database.player_already_explored(conn, participant_puuid):
                    queue.append(participant_puuid)

            if collected % 10 == 0:
                print(f"{collected}/{target_count} matchs collectés...")

    print(f"Terminé : {collected} matchs collectés, {len(queue)} joueurs encore en attente dans la file.")
