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
Riot API (ingestion) → SQLite (stockage brut) → pandas (extraction) → Gradient Boosted Trees + SHAP (ML) → LLM (Claude API) → interface
```

## Statut global (2026-09-15)

| Phase | Statut |
|---|---|
| 1. Ingestion Riot API | ✅ Terminée |
| 2. Collecte du dataset (SQLite + snowball sampling) | 🚧 Pipeline construit, industrialisé et testé à petite échelle ; reste la collecte à grande échelle |
| Chantier — Industrialisation en package Python | ✅ Terminée |
| 3. Modèle ML (Gradient Boosted Trees + SHAP) | 🚧 Dataset extrait sur la collecte complète, export + guide Power BI prêts ; exploration visuelle, entraînement + SHAP restants |
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
- **Correctif qualité de données (2026-09-15)** : le crawl snowball n'appliquait aucun filtre de mode de jeu — 4 des 20 premiers matchs collectés se sont révélés être en mode Arena (`gameMode="CHERRY"`, 2v2v2v2, sans rapport avec le 5v5 classique). `crawl_matches` ne sauvegarde désormais que les matchs `gameMode == "CLASSIC"` (il continue à explorer les participants de ces matchs pour le snowball sampling, juste sans les stocker).
- **`crawl_matches` évolué pour la collecte à grande échelle** : accepte maintenant une **liste** de graines (`seed_puuids`, pas juste une seule — nécessaire pour relancer efficacement, la file d'attente n'étant pas persistée entre deux exécutions) et une limite de **durée** (`max_duration_seconds`), en plus du `target_count` — utile pour viser "quelques heures de collecte" plutôt qu'un nombre de matchs qu'on ne sait pas estimer précisément à l'avance.
- **`scripts/collect_dataset.py`** : script (pas un notebook — tâche d'infra longue durée, pas un concept à apprendre) qui trouve tous les `puuid` déjà croisés dans les matchs collectés mais jamais explorés (via `metadata.participants` du JSON brut), et relance `crawl_matches` à partir de ces graines. Usage : `python scripts/collect_dataset.py [heures] [db_path]`. Lancé en arrière-plan avec `python -u` (sortie non bufferisée — sans `-u`, les `print()` restent en tampon et n'apparaissent pas en temps réel dans un fichier de log).
- **Collecte à grande échelle lancée le 2026-09-15**, 8h (jusqu'à minuit), logs dans `data/collection.log` (non versionné).

**Reste à faire :**
- Vérifier le résultat de la collecte à grande échelle une fois terminée, et relancer si besoin pour viser plus de matchs.
- Prévoir le renouvellement de la clé API Riot si une future collecte dépasse 24h (clé de dev expire quotidiennement) — envisager une clé personnelle.

## Chantier transversal — Industrialisation en package Python ✅ Terminée

Le code réutilisable de la phase 2 (auparavant inline dans le notebook, avec des variables globales comme `conn`, `cursor`, `headers`) est maintenant un vrai package Python structuré par responsabilité, importable depuis n'importe quel notebook ou script futur.

**Structure réalisée :**
- `lol_assistant/rate_limiter.py` — la classe `RateLimiter` (fenêtre glissante), sans effet de bord (pas de `print`, contrairement à la version notebook — une bibliothèque interne ne décide pas de ce qui s'affiche).
- `lol_assistant/riot_client.py` — classe `RiotClient` encapsulant clé API, headers, région et rate limiter, avec des méthodes `get_puuid`, `get_match_ids`, `get_match_detail`. Chaque méthode appelle `response.raise_for_status()` : elle lève une exception (`requests.HTTPError`) plutôt que de renvoyer un objet à vérifier manuellement.
- `lol_assistant/database.py` — `get_connection(db_path)` (ouvre la connexion **et** garantit le schéma) + les fonctions CRUD, prenant désormais `conn` en paramètre explicite plutôt que de dépendre d'un `cursor` global partagé (qui aurait pu créer des interférences entre requêtes).
- `lol_assistant/crawler.py` — `crawl_matches(riot_client, conn, seed_puuids, target_count, matches_per_player=10, max_duration_seconds=None)`, orchestre les deux modules ci-dessus. Utilise `try`/`except requests.HTTPError` plutôt que de vérifier `status_code`, en cohérence avec `RiotClient`. `seed_puuids` accepte une liste ou une simple chaîne ; `max_duration_seconds` permet de borner par le temps plutôt que par un nombre de matchs (ajouté pour la collecte à grande échelle, voir phase 2).
- `pyproject.toml` à la racine — packaging minimal (`setuptools`), avec `[tool.setuptools.packages.find] include = ["lol_assistant*"]` explicite (sans ça, `setuptools` refuse de choisir entre `data/`, `notebooks/` et `lol_assistant/` comme package à inclure). Dépendances du package : `requests`, `python-dotenv` (le strict nécessaire au code lui-même — `pandas`/`jupyter` restent dans `requirements.txt`, ce sont des outils d'environnement, pas des dépendances du code).

`notebooks/01_riot_api_basics.ipynb` reste inchangé (artefact pédagogique figé). `notebooks/02_dataset_collection.ipynb` a été mis à jour : les cellules de code sont devenues de simples imports depuis `lol_assistant/`, les explications pédagogiques en markdown sont conservées avec une note pointant vers l'implémentation réelle.

`init.py` (vide, à la racine, jamais utilisé, antérieur au projet actuel) a été supprimé.

**Environnement d'exécution découvert au passage** : les notebooks tournent via un environnement **conda nommé `lol-assistant`** (`~/anaconda3/envs/lol-assistant`), pas un `.venv` classique — c'est là qu'a été fait `pip install -e .`. Utile à savoir pour toute installation/dépannage futur sur cette machine.

Validation effectuée : le package s'importe correctement, tests isolés (base de données, `RiotClient` avec un vrai appel API, `crawl_matches` de bout en bout), puis exécution complète du notebook 2 (`jupyter nbconvert --execute`) sans erreur.

Plan détaillé de ce chantier (contexte de décision, alternatives écartées) : voir `~/.claude/plans/avant-de-poser-plein-vivid-rabin.md` (local à la machine où le projet a été démarré, pas versionné).

## Phase 3 — Modèle ML : Gradient Boosted Trees + SHAP 🚧 En cours

Fichier : [`notebooks/03_model_training.ipynb`](notebooks/03_model_training.ipynb)

### La vision (redéfinie en cours de route)

L'architecture initialement prévue était une Factorization Machine (FM) sur des embeddings de champions (voir *Décision abandonnée* plus bas). En la concevant plus en détail, l'utilisateur a reformulé l'objectif en 3 étapes plus riches, à partir du **déroulé de la partie** plutôt que des picks seuls :
1. Identifier, via le ML, les **faits de jeu** (objectifs, kills, économie, vision...) statistiquement liés à la victoire.
2. Pour **chaque champion**, déterminer lesquels de ces faits comptent le plus **spécifiquement pour lui**.
3. Pour une **composition donnée**, agréger ça en un plan de jeu : quels faits prioriser, lesquels ne changeront pas grand-chose.

### Architecture retenue

**Gradient Boosted Trees (XGBoost/LightGBM) + SHAP**, sur un dataset **au niveau joueur** (une ligne par participant par match, pas par match) :
- SHAP donne l'importance globale des features → étape 1.
- Les valeurs d'interaction SHAP entre `champion` et chaque fait de jeu → étape 2.
- Les contributions SHAP pour une ligne donnée (somme exacte = la prédiction) → étape 3, sans outil d'explicabilité externe supplémentaire.

**Pourquoi pas la Timeline API** : Match-V5 (déjà collecté, aucun nouvel appel nécessaire) contient déjà un champ `challenges` par participant — ~125 statistiques dérivées par Riot (`dragonTakedowns`, `teamBaronKills`, `killParticipation`, `teamDamagePercentage`, `laningPhaseGoldExpAdvantage`, `visionScorePerMinute`...). Ça couvre l'essentiel de ce qu'on serait allé chercher dans la Timeline, sans doubler le budget de rate limiting. La Timeline (`RiotClient.get_match_timeline`, déjà ajouté mais non utilisé) reste une option pour affiner plus tard avec du timing précis.

**Erreur corrigée en cours de route** : une première version sommait les champs individuels (`soloKills`...) en totaux d'équipe avant l'entraînement — ce qui détruit le lien champion↔fait de jeu nécessaire à l'étape 2. Corrigé : le dataset reste à la granularité (match, joueur), jamais agrégé à (match, équipe). Certains champs `challenges` sont en réalité des faits d'équipe dupliqués à l'identique chez les 5 coéquipiers (ex: `teamBaronKills`) plutôt que des faits individuels (ex: `soloKills`) — Riot ne documente pas laquelle des deux catégories s'applique à chaque champ, donc c'est détecté empiriquement sur les données (un champ est "équipe" seulement s'il n'a **jamais** varié entre les 5 joueurs d'une même équipe sur tout le dataset).

### Fait et validé (extraction du dataset)

1. Chargement des matchs bruts depuis SQLite + parsing JSON.
2. Extraction composition/résultat/durée par match, filtrage des remakes (`game_duration < 300s`).
3. **Filtrage des modes de jeu hors-sujet** (ex: Arena/`CHERRY`) — présents dans les tout premiers matchs collectés (voir phase 2, correctif crawler).
4. Classification empirique des champs `challenges` (équipe vs joueur), exclusion des champs Arena/ARAM (`SWARM_*`, `poroExplosions`...).
5. Construction du dataset final : une ligne par (match, joueur), `champion` en vraie feature, faits individuels non sommés, faits d'équipe en contexte partagé.
6. **Rejoué sur la collecte complète (2026-09-16)** après la collecte à grande échelle : **123 460 lignes** (12 346 matchs `CLASSIC` valides × 10 joueurs), **134 colonnes**, 173 champions distincts (minimum 93 occurrences chacun). La classification champ équipe/joueur s'est affinée avec plus de données (19 champs équipe contre 26 sur l'échantillon initial de 20 matchs, plus fiable).
7. **Ajout du `role`** (`teamPosition` Riot : `TOP`/`JUNGLE`/`MIDDLE`/`BOTTOM`/`UTILITY`), oublié dans une première version — indispensable pour distinguer "ce fait compte peu pour ce champion" de "ce fait compte peu pour son rôle en général".
8. **Détection de fuite de donnée** : `maxKillDeficit` (3ᵉ plus forte corrélation dans une première passe) s'est avéré valoir **toujours exactement 0** côté perdant, jamais côté gagnant — un signe de fuite (le champ encode quasiment le résultat) plutôt qu'un vrai fait observable en cours de partie. Détecté systématiquement (tout champ quasi-nul chez les perdants mais présent chez les gagnants) plutôt qu'au cas par cas ; exclu du classement de pertinence et de l'entraînement à venir.
9. **Export CSV pour Power BI** (`data/dataset_for_powerbi.csv`, non versionné) — étape d'exploration visuelle interactive prévue avant l'entraînement (Power BI Desktop ne tourne pas sur cette machine Linux ; le fichier est transféré vers une machine Windows). Export volontairement à plat (une ligne par match/joueur, pas pré-agrégé) : Power BI est fait pour construire les pivots/agrégations interactivement.
10. **Classement de pertinence par corrélation** (`data/feature_relevance.csv`), **le même par rôle** (`data/feature_relevance_by_role.csv`, format long rôle×fait), un **état des lieux des valeurs manquantes** (`data/missing_values.csv`, 26 colonnes concernées, 17 à plus de 50%), et une **table de synthèse par champion** (`data/champion_summary.csv` : parties jouées, taux de victoire, rôle principal) — tous non versionnés. En tête du classement global : `turretTakedowns` (corr. 0.60), `turretPlatesTaken` (0.50), `kda` (0.47).
11. **Guide Power BI pas-à-pas** : [`docs/powerbi_guide.md`](docs/powerbi_guide.md) — import des 5 fichiers, types de colonnes, l'histoire de la fuite `maxKillDeficit`, mesures DAX de base, graphiques (barres, matrice rôle×fait, slicers, cartes), avec le rappel que cette exploration ne remplace pas SHAP.

### Reste à faire

Exploration Power BI par l'utilisateur (suivre le guide), puis entraînement du modèle GBT (`champion` en feature catégorielle, `LEAKAGE_SUSPECT_FIELDS` exclus), analyse SHAP (importance globale, interactions champion×fait, attribution par ligne), évaluation (plafond de précision modeste attendu — le skill et le déroulé de partie dominent le résultat réel, on ne vise pas une prédiction fiable coup par coup).

### Décision abandonnée : Factorization Machine sur embeddings de champions

Idée initiale : `biais global + poids individuel par champion + produit scalaire entre paires d'embeddings` (paires même équipe = synergie, équipes opposées = matchup/contre), embeddings appris de façon supervisée. Abandonnée après avoir identifié un vrai problème mathématique en l'implémentant : un produit scalaire est symétrique (`dot(A,B) = dot(B,A)`), mais quel camp est "bleu" ou "rouge" est arbitraire — un terme de contre symétrique ne peut donc porter **aucun signal prédictif** (il ne change pas de signe quand on inverse les équipes, contrairement au label). Le corriger proprement (embeddings offense/défense séparés, ou matrice bilinéaire antisymétrique apprise) ajoutait une complexité prématurée vu le dataset actuel (~20 matchs, qui overfitterait de toute façon). Combiné à l'envie de raisonner sur le déroulé de partie plutôt que sur les picks seuls, ça a motivé le pivot vers GBT+SHAP.

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
├── requirements.txt                   # requests, python-dotenv, jupyter, pandas, scikit-learn, xgboost, shap
├── .env                                # clé API Riot (jamais versionné)
├── .env.example                        # gabarit sans secret
├── .gitignore                          # exclut .env, .venv/, __pycache__/, .ipynb_checkpoints/, data/, .claude/, *.egg-info/
├── lol_assistant/                     # package industrialisé (phase 2)
│   ├── __init__.py
│   ├── rate_limiter.py                # classe RateLimiter (fenêtre glissante)
│   ├── riot_client.py                 # classe RiotClient (auth, région, appels Riot)
│   ├── database.py                    # get_connection + fonctions CRUD SQLite
│   └── crawler.py                     # crawl_matches (BFS/snowball sampling, filtre gameMode, durée max)
├── scripts/
│   └── collect_dataset.py             # collecte à grande échelle, en arrière-plan, bornée en durée
├── notebooks/
│   ├── 01_riot_api_basics.ipynb       # phase 1 — terminée, figée (artefact pédagogique)
│   ├── 02_dataset_collection.ipynb    # phase 2 — importe lol_assistant/, pipeline prêt
│   └── 03_model_training.ipynb        # phase 3 — extraction + exports Power BI faits, entraînement à venir
├── docs/
│   └── powerbi_guide.md               # guide pas-à-pas d'exploration Power BI
└── data/
    ├── matches.db                     # base SQLite (jamais versionnée, générée par la collecte)
    ├── collection.log                 # logs de la collecte à grande échelle (jamais versionné)
    ├── dataset_for_powerbi.csv        # export plat du dataset (jamais versionné, pour exploration Power BI)
    ├── feature_relevance.csv          # classement de pertinence par corrélation (jamais versionné)
    ├── feature_relevance_by_role.csv  # idem, segmenté par rôle (jamais versionné)
    ├── missing_values.csv             # % de valeurs manquantes par colonne (jamais versionné)
    └── champion_summary.csv           # parties/winrate/rôle principal par champion (jamais versionné)
```
