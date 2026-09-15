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
- **Ce README est tenu exhaustif en permanence** : c'est le seul artefact qui voyage avec le dépôt Git et qui reste lisible sans l'historique de conversation (utile en particulier pour reprendre le projet sur une autre machine — voir plus bas).

## Architecture globale du pipeline

```
Riot API (ingestion) → SQLite (stockage brut) → pandas (extraction) → Factorization Machine (ML) → LLM (Claude API) → interface
```

## Statut global (2026-09-15)

| Phase | Statut |
|---|---|
| 1. Ingestion Riot API | ✅ Terminée |
| 2. Collecte du dataset (SQLite + snowball sampling) | 🚧 Pipeline construit, industrialisé et testé à petite échelle ; reste la collecte à grande échelle |
| Chantier — Industrialisation en package Python | ✅ Terminée |
| 3. Modèle ML (Factorization Machine) | 📋 Architecture décidée, implémentation à venir |
| 4. LLM (plan de jeu textuel) | ⏳ À venir |
| 5. Interface | ⏳ À venir |

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

Ce notebook est un **artefact pédagogique figé** : il ne sera pas refactoré vers le futur package Python (contrairement à la phase 2, voir plus bas), car son but est de documenter l'apprentissage pas-à-pas des concepts API, pas de fournir du code réutilisable.

## Phase 2 — Collecte du dataset 🚧 Pipeline prêt, collecte à grande échelle restante

Fichier : [`notebooks/02_dataset_collection.ipynb`](notebooks/02_dataset_collection.ipynb)

**Décisions prises :**
- **Stockage : SQLite** (`data/matches.db`, jamais versionné). Une table `matches` (JSON brut, `match_id` en clé primaire → dédoublonnage automatique) et une table `explored_players` (`puuid` déjà explorés, pour ne pas re-scanner un joueur). Le JSON brut est gardé tel quel : si on veut extraire de nouvelles features plus tard (items, durée de partie...), pas besoin de re-interroger l'API.
- **Stratégie de collecte : snowball sampling.** Chaque match récupéré contient 10 `puuid` (ses participants) qu'on réutilise comme nouvelles graines à explorer — ça donne de la diversité de joueurs sans appels API dédiés à la découverte, via un parcours en largeur (BFS).
- **Rate limiting proactif** (`RateLimiter`, fenêtre glissante 100 appels/120s) plutôt que seulement réactif (attendre après un `429`) — évite de perdre du temps en pénalités pendant une collecte de plusieurs milliers de matchs.

**Fait et validé :**
- Schéma SQLite + fonctions CRUD (`match_already_collected`, `save_match`, `player_already_explored`, `mark_player_explored`).
- `RateLimiter` (fenêtre glissante) + client Riot combinant attente proactive et retry sur `429`.
- Boucle de crawl `crawl_matches` (BFS/snowball sampling) — testée avec succès sur un petit lot (`target_count=20`), y compris la reprise correcte entre deux sessions différentes (un joueur déjà exploré lors d'une exécution précédente est bien ignoré lors de la suivante, sans appel API gaspillé).
- Visualisation du contenu de la base via `pd.read_sql_query` dans le notebook, et via l'extension VS Code *SQLite Viewer* installée pour parcourir `data/matches.db` visuellement.
- Code entièrement industrialisé dans le package `lol_assistant/` (voir section dédiée ci-dessous) — le notebook n'importe plus que des fonctions/classes, il ne les définit plus.

**Reste à faire :**
- Lancer une vraie collecte à grande échelle (`target_count` de plusieurs milliers) — nécessaire pour que les embeddings de champions (phase 3) voient assez de paires différentes.
- Prévoir le renouvellement de la clé API Riot si la collecte dépasse 24h (clé de dev expire quotidiennement) — envisager une clé personnelle.

## Chantier transversal — Industrialisation en package Python ✅ Terminée

Le code réutilisable de la phase 2 (auparavant inline dans le notebook, avec des variables globales comme `conn`, `cursor`, `headers`) est maintenant un vrai package Python structuré par responsabilité, importable depuis n'importe quel notebook ou script futur.

**Structure réalisée :**
- `lol_assistant/rate_limiter.py` — la classe `RateLimiter` (fenêtre glissante), sans effet de bord (pas de `print`, contrairement à la version notebook — une bibliothèque interne ne décide pas de ce qui s'affiche).
- `lol_assistant/riot_client.py` — classe `RiotClient` encapsulant clé API, headers, région et rate limiter, avec des méthodes `get_puuid`, `get_match_ids`, `get_match_detail`. Chaque méthode appelle `response.raise_for_status()` : elle lève une exception (`requests.HTTPError`) plutôt que de renvoyer un objet à vérifier manuellement.
- `lol_assistant/database.py` — `get_connection(db_path)` (ouvre la connexion **et** garantit le schéma) + les fonctions CRUD, prenant désormais `conn` en paramètre explicite plutôt que de dépendre d'un `cursor` global partagé (qui aurait pu créer des interférences entre requêtes).
- `lol_assistant/crawler.py` — `crawl_matches(riot_client, conn, seed_puuid, target_count, matches_per_player=10)`, orchestre les deux modules ci-dessus. Utilise `try`/`except requests.HTTPError` plutôt que de vérifier `status_code`, en cohérence avec `RiotClient`.
- `pyproject.toml` à la racine — packaging minimal (`setuptools`), avec `[tool.setuptools.packages.find] include = ["lol_assistant*"]` explicite (sans ça, `setuptools` refuse de choisir entre `data/`, `notebooks/` et `lol_assistant/` comme package à inclure). Dépendances du package : `requests`, `python-dotenv` (le strict nécessaire au code lui-même — `pandas`/`jupyter` restent dans `requirements.txt`, ce sont des outils d'environnement, pas des dépendances du code).

`notebooks/01_riot_api_basics.ipynb` reste inchangé (artefact pédagogique figé). `notebooks/02_dataset_collection.ipynb` a été mis à jour : les cellules de code sont devenues de simples imports depuis `lol_assistant/`, les explications pédagogiques en markdown sont conservées avec une note pointant vers l'implémentation réelle.

`init.py` (vide, à la racine, jamais utilisé, antérieur au projet actuel) a été supprimé.

**Environnement d'exécution découvert au passage** : les notebooks tournent via un environnement **conda nommé `lol-assistant`** (`~/anaconda3/envs/lol-assistant`), pas un `.venv` classique — c'est là qu'a été fait `pip install -e .`. Utile à savoir pour toute installation/dépannage futur sur cette machine.

Validation effectuée : le package s'importe correctement, tests isolés (base de données, `RiotClient` avec un vrai appel API, `crawl_matches` de bout en bout), puis exécution complète du notebook 2 (`jupyter nbconvert --execute`) sans erreur.

Plan détaillé de ce chantier (contexte de décision, alternatives écartées) : voir `~/.claude/plans/avant-de-poser-plein-vivid-rabin.md` (local à la machine où le projet a été démarré, pas versionné).

## Phase 3 — Modèle ML (à venir)

**Décision d'architecture prise à l'avance :** une **Factorization Machine (FM)** sur des embeddings de champions, pas des features artisanales (tags Tank/Mage/...) ni des embeddings non-supervisés (style word2vec).

Pourquoi ce choix précis :
- Les embeddings sont appris **directement en optimisant la prédiction victoire/défaite** (supervisé) — contrairement à des embeddings de co-occurrence qui capteraient la popularité du méta plutôt que ce qui fait réellement gagner.
- Le score se décompose en une somme interprétable : `biais global + poids individuel par champion + produit scalaire entre paires d'embeddings`.
  - Paires **dans la même équipe** → terme de **synergie**.
  - Paires **d'équipes opposées** → terme de **matchup/contre**.
- Cette décomposition additive permet une **attribution exacte et gratuite** : pour une composition donnée, on peut calculer la contribution de chaque champion à la victoire/défaite prédite, sans outil d'explicabilité externe (type SHAP). C'était l'objectif explicite exprimé : identifier les champions synergiques et les champions décisifs pour une composition donnée.

À faire : extraction du dataset tabulaire depuis SQLite (pandas, `json.loads` sur `raw_json`), encodage des champions en identifiants catégoriels, implémentation de la FM, entraînement, évaluation (en gardant en tête qu'un modèle basé uniquement sur le draft a un plafond de précision modeste — le skill et le déroulé de partie dominent le résultat réel).

## Phase 4 — LLM (à venir)

Utiliser l'API Claude pour transformer la sortie du modèle ML (probabilité de victoire + attribution par champion : qui est le point fort, qui est le point faible) en un **plan de jeu textuel** exploitable par un joueur. Sujets à couvrir : prompt engineering, structured outputs.

## Phase 5 — Interface (à venir)

Assembler le tout dans une interface utilisable (CLI ou notebook consolidé) — pas encore tranché.

## Dépôt Git / GitHub

- Dépôt distant **privé** : [github.com/mimouniahmed/LOL-assistant](https://github.com/mimouniahmed/LOL-assistant), remote `origin` en SSH.
- Branche principale : `main`.
- Premier commit (`1de9d90`) : snapshot des phases 1 et 2 telles que décrites ci-dessus.

## Reprendre le projet sur une nouvelle machine

Ce qui **suit le dépôt Git** (donc récupéré automatiquement via `git clone`) : le code, le package `lol_assistant/`, `pyproject.toml`, les notebooks, ce README, `.gitignore`, `requirements.txt`.

Ce qui **ne suit pas le dépôt** (volontairement exclu par `.gitignore`) et doit être reconstitué à la main :
1. **`.env`** — la clé API Riot. À recopier depuis la machine d'origine de façon sécurisée (jamais par email/chat en clair), ou à régénérer une nouvelle clé sur le [portail développeur Riot](https://developer.riotgames.com/).
2. **`data/matches.db`** — la base SQLite déjà collectée. À copier manuellement (clé USB, `scp`...) si on veut garder les mêmes données ; sinon, elle se reconstruit en relançant la collecte (phase 2).
3. **La clé SSH pour push/pull sur GitHub** — générer une nouvelle clé sur la nouvelle machine (`ssh-keygen`) et l'ajouter sur [github.com/settings/ssh/new](https://github.com/settings/ssh/new), comme fait pour cette machine.
4. **L'historique de conversation et la mémoire du projet** (décisions prises, préférences pédagogiques) — stockés localement par Claude Code sur la machine d'origine, ne voyagent pas automatiquement. Ce README sert justement de filet de sécurité : une nouvelle session Claude Code qui le lit repart avec l'essentiel du contexte.

Étapes concrètes sur la nouvelle machine (avec `venv` — un environnement conda fonctionne aussi, voir note dans la section "Chantier transversal") :
```bash
git clone git@github.com:mimouniahmed/LOL-assistant.git
cd LOL-assistant
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .   # installe le package lol_assistant/ en mode éditable
cp .env.example .env   # puis remplir avec la vraie clé API
jupyter notebook
```

## Structure du projet

```
LOL-assistant/
├── README.md                          # ce fichier
├── pyproject.toml                     # packaging du package lol_assistant/ (pip install -e .)
├── requirements.txt                   # requests, python-dotenv, jupyter, pandas
├── .env                                # clé API Riot (jamais versionné)
├── .env.example                        # gabarit sans secret
├── .gitignore                          # exclut .env, .venv/, __pycache__/, .ipynb_checkpoints/, data/, .claude/, *.egg-info/
├── lol_assistant/                     # package industrialisé (phase 2)
│   ├── __init__.py
│   ├── rate_limiter.py                # classe RateLimiter (fenêtre glissante)
│   ├── riot_client.py                 # classe RiotClient (auth, région, appels Riot)
│   ├── database.py                    # get_connection + fonctions CRUD SQLite
│   └── crawler.py                     # crawl_matches (BFS/snowball sampling)
├── notebooks/
│   ├── 01_riot_api_basics.ipynb       # phase 1 — terminée, figée (artefact pédagogique)
│   └── 02_dataset_collection.ipynb    # phase 2 — importe lol_assistant/, pipeline prêt
└── data/
    └── matches.db                     # base SQLite (jamais versionnée, générée par la collecte)
```
