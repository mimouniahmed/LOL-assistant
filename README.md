# LOL Assistant — plan de jeu à partir d'une composition

Projet éducatif : construire, étape par étape, un assistant qui aide un joueur de League of Legends à établir un **plan de jeu** à partir d'une **composition d'équipe** (10 champions, 2 équipes). L'objectif premier est d'apprendre — l'API Riot Games, le ML, et l'intégration d'un LLM — pas de livrer un produit fini rapidement.

## Ce que l'assistant final fera (et ne fera pas)

- **Entrée** : une composition **choisie librement par l'utilisateur** (les 10 champions des deux équipes), hypothétique — pas une partie en cours.
- **Sortie** : un plan de jeu textuel expliquant les forces/faiblesses de la composition et les champions décisifs, pas juste un pourcentage de victoire brut.
- **Ce que ce n'est pas** : l'assistant ne va *pas* chercher la partie en cours d'un joueur précis. Aucun pseudo n'est nécessaire pour l'utiliser. Les pseudos utilisés pendant le développement (voir phase 1 et 2) ne servent qu'en coulisses, pour collecter des données d'entraînement.

## Méthode de travail

- Tout est développé en **notebooks Jupyter**, un concept par cellule, exécuté et observé avant de passer au suivant.
- Chaque bout de code est expliqué dans la conversation avant/au moment de l'écrire (pas seulement en commentaire) — l'utilisateur veut comprendre chaque brique, pas se faire livrer du code.
- Le projet avance par phases, chacune validée avant de passer à la suivante.

## Architecture globale du pipeline

```
Riot API (ingestion) → SQLite (stockage brut) → pandas (extraction) → Factorization Machine (ML) → LLM (Claude API) → interface
```

## Phase 1 — Bases de l'API Riot ✅ Terminée

Fichier : [`notebooks/01_riot_api_basics.ipynb`](notebooks/01_riot_api_basics.ipynb)

Ce qu'on y a appris et implémenté, concept par concept :
1. Anatomie d'une requête HTTP (méthode, URL, headers) — appel sans clé API pour observer le `401`.
2. Authentification via le header `X-Riot-Token`, clé chargée depuis `.env` (jamais en dur dans le code).
3. Régions (`europe`, `americas`...) vs plateformes (`euw1`, `na1`...) — deux systèmes de routage différents selon les endpoints.
4. **Account-V1** : résoudre un Riot ID (`pseudo#tag`) en `puuid`, avec encodage d'URL (`urllib.parse.quote`).
5. **Match-V5** : lister les IDs de matchs récents d'un `puuid`, puis récupérer le détail complet d'un match.
6. **Rate limiting** : lecture des headers `X-Rate-Limit-*`, gestion du `429` avec une fonction `riot_get` qui attend et réessaie automatiquement (`Retry-After`).
7. **Extraction d'une composition** : à partir du détail d'un match, isoler pour chacun des 10 participants `champion`, `team` (bleue/rouge), `role`, `win`.

Résultat concret validé : récupération du `puuid` de l'utilisateur, de ses matchs récents, et extraction complète d'une composition à 10 lignes.

## Phase 2 — Collecte du dataset (en cours 🚧)

Fichier : [`notebooks/02_dataset_collection.ipynb`](notebooks/02_dataset_collection.ipynb)

**Décisions prises :**
- **Stockage : SQLite** (pas de fichiers plats JSON/CSV). Une table `matches` (JSON brut, `match_id` en clé primaire → dédoublonnage automatique) et une table `explored_players` (`puuid` déjà explorés, pour ne pas re-scanner un joueur). Le JSON brut est gardé tel quel : si on veut extraire de nouvelles features plus tard (items, durée de partie...), pas besoin de re-interroger l'API.
- **Stratégie de collecte : snowball sampling.** Chaque match récupéré contient 10 `puuid` (ses participants) qu'on réutilise comme nouvelles graines à explorer — ça donne de la diversité de joueurs sans appels API dédiés à la découverte.
- Nécessité identifiée d'un **rate limiting proactif** (espacer les appels avant de se faire limiter), pas seulement réactif (attendre après un `429`), pour une collecte efficace de plusieurs milliers de matchs.
- Fait : schéma SQLite + fonctions `match_already_collected`, `save_match`, `player_already_explored`, `mark_player_explored`, testées avec des données factices.

**Reste à faire pour clore la phase 2 :**
- Rate limiter proactif (respecter les ~50 req/min sans attendre le `429`).
- Boucle de crawl snowball sampling complète (file d'attente de `puuid`, dédoublonnage via SQLite, sauvegarde incrémentale).
- Lancer une vraie collecte (objectif : plusieurs milliers de matchs, nécessaire pour que les embeddings de champions voient assez de paires différentes).
- Point d'attention pratique : la clé de dev Riot expire toutes les 24h — envisager une clé personnelle (ne pas expirer quotidiennement) si la collecte s'étale sur plusieurs jours.

## Phase 3 — Modèle ML (à venir)

**Décision d'architecture prise à l'avance :** une **Factorization Machine (FM)** sur des embeddings de champions, pas des features artisanales (tags Tank/Mage/...) ni des embeddings non-supervisés (style word2vec).

Pourquoi ce choix précis :
- Les embeddings sont appris **directement en optimisant la prédiction victoire/défaite** (supervisé) — contrairement à des embeddings de co-occurrence qui capteraient la popularité du méta plutôt que ce qui fait réellement gagner.
- Le score se décompose en une somme interprétable : `biais global + poids individuel par champion + produit scalaire entre paires d'embeddings`.
  - Paires **dans la même équipe** → terme de **synergie**.
  - Paires **d'équipes opposées** → terme de **matchup/contre**.
- Cette décomposition additive permet une **attribution exacte et gratuite** : pour une composition donnée, on peut calculer la contribution de chaque champion à la victoire/défaite prédite, sans outil d'explicabilité externe (type SHAP). C'était l'objectif explicite exprimé : identifier les champions synergiques et les champions décisifs pour une composition donnée.

À faire : extraction du dataset tabulaire depuis SQLite (pandas), encodage des champions en identifiants catégoriels, implémentation de la FM, entraînement, évaluation (en gardant en tête qu'un modèle basé uniquement sur le draft a un plafond de précision modeste — le skill et le déroulé de partie dominent le résultat réel).

## Phase 4 — LLM (à venir)

Utiliser l'API Claude pour transformer la sortie du modèle ML (probabilité de victoire + attribution par champion : qui est le point fort, qui est le point faible) en un **plan de jeu textuel** exploitable par un joueur. Sujets à couvrir : prompt engineering, structured outputs.

## Phase 5 — Interface (à venir)

Assembler le tout dans une interface utilisable (CLI ou notebook consolidé) — pas encore tranché.

## Structure du projet

```
LOL-assistant/
├── README.md                          # ce fichier
├── requirements.txt                   # requests, python-dotenv, jupyter, pandas
├── .env                                # clé API Riot (jamais versionné)
├── .env.example                        # gabarit sans secret
├── .gitignore
├── notebooks/
│   ├── 01_riot_api_basics.ipynb       # phase 1 — terminée
│   └── 02_dataset_collection.ipynb    # phase 2 — en cours
├── data/
│   └── matches.db                     # base SQLite (jamais versionnée, générée par la collecte)
└── init.py                             # vide, pas encore utilisé — à clarifier/supprimer
```
