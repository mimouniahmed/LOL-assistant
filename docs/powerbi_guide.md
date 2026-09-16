# Guide Power BI — explorer le dataset avant l'entraînement

Deux objectifs en un : apprendre les bases de Power BI en le pratiquant, et repérer visuellement quels faits de jeu comptent le plus pour la victoire, avant de se lancer dans le modèle Gradient Boosted Trees + SHAP.

Six fichiers à importer (générés par `notebooks/03_model_training.ipynb`, à transférer depuis la machine Linux vers Windows — non versionnés dans Git) :
- **`dataset_for_powerbi.csv`** — la table plate, une ligne par (match, joueur), 123 460 lignes × 134 colonnes. Contient `role` (`TOP`/`JUNGLE`/`MIDDLE`/`BOTTOM`/`UTILITY`).
- **`feature_relevance.csv`** — classement de ~128 faits de jeu par corrélation avec la victoire (Concept 7), fuites de données déjà exclues.
- **`feature_relevance_early_game.csv`** — le même classement, mais restreint aux **29 faits précoces/causaux** (Concept 11) — celui qui compte vraiment pour la suite, voir section 2bis.
- **`feature_relevance_by_role.csv`** — la corrélation globale (Concept 7), calculée **séparément pour chaque rôle** (format long : une ligne par rôle × fait, Concept 9).
- **`missing_values.csv`** — pourcentage de valeurs manquantes par colonne (Concept 8).
- **`champion_summary.csv`** — par champion : parties jouées, taux de victoire, rôle principal (Concept 10).

## 0. Import

`Accueil > Obtenir les données > Texte/CSV` — importe les cinq fichiers, un par un. Power BI les charge chacun comme une **table** séparée (visibles dans le volet "Données" à droite).

**Vérifie les types de colonnes** (icône ABC/123/calendrier à gauche de chaque nom de colonne, dans l'onglet Power Query "Transformer les données") : `team_win` vient de Python comme le texte `"True"`/`"False"` — Power BI ne le convertit pas toujours automatiquement en booléen/nombre. S'il reste en texte, les agrégations (moyenne, etc.) ne fonctionneront pas dessus. Corrige-le en `Nombre entier` (True→1, False→0) via clic droit sur la colonne > `Type` — c'est ce qui permettra de calculer un "taux de victoire" comme une simple moyenne.

**Pas besoin de relation entre les tables** — aucune ne partage de clé commune au sens strict (`feature_relevance` a une ligne par *colonne* de `dataset_for_powerbi`, pas par match). On les utilise dans des visuels séparés, sur des pages séparées si besoin.

## 1. Premier visuel : le classement de pertinence (apprendre : graphique en barres, tri)

À partir de `feature_relevance` :
- Glisse `feature` dans **Axe**, `abs_correlation` dans **Valeurs**, choisis un graphique à **barres horizontales**.
- Trie par valeur décroissante (menu `...` du visuel > `Trier par` > `abs_correlation`).
- Ajoute un **filtre de niveau visuel** (`Top N`, ex: 20) sur `feature` par `abs_correlation` — sinon la centaine de barres devient illisible.
- Glisse `correlation_with_win`, `mean_when_win`, `mean_when_loss` dans **Info-bulles** pour les voir au survol.

En tête sur les données actuelles : `turretTakedowns`, `turretPlatesTaken`, `kda`, `teamBaronKills`.

## 2. Une histoire de fuite de donnée : `maxKillDeficit`

Ce champ n'apparaît **volontairement pas** dans `feature_relevance.csv`, alors qu'il était la 3ᵉ corrélation la plus forte dans une première passe. En creusant (voir Concept 6bis du notebook), il s'est avéré valoir **toujours exactement 0** chez les équipes perdantes, jamais chez les gagnantes — un signe de fuite de donnée : un champ qui encode quasiment le résultat lui-même plutôt qu'un fait observable en cours de partie. Un tel champ ferait paraître un modèle ML artificiellement excellent, sans être exploitable pour un vrai plan de jeu (on ne peut pas "faire du `maxKillDeficit`" pendant une partie).

Si tu veux le vérifier toi-même dans Power BI : importe temporairement `dataset_for_powerbi`, graphique à colonnes groupées avec `team_win` en axe et `Moyenne de maxKillDeficit` en valeur — la barre côté défaite sera à zéro. Bon réflexe à garder pour la suite : toujours se demander si un fait très corrélé est **causal/observable pendant la partie**, ou juste une reformulation du résultat.

## 2bis. Causes vs conséquences : se restreindre à l'early game

`turretTakedowns`, `teamBaronKills`, `kda`... sont en tête du classement global, mais ce sont des **cumuls sur toute la partie**. Une équipe qui écrase déjà l'autre accumule ce genre de stats tout au long du match simplement parce qu'elle gagne déjà — ce n'est pas ce qui l'a fait gagner, c'est la **conséquence** d'être déjà en train de gagner. Un fait précoce (avant ~20 min), lui, reflète plus une vraie décision stratégique : le snowball n'a pas encore eu le temps de tout expliquer.

`feature_relevance_early_game.csv` ne garde que les faits bornés dans le temps (Héraut, Voidgrubs, plusieurs champs "Before10Minutes"/"Laning"/"Early"...) ou des horodatages. Résultat frappant : le classement change complètement de forme. `maxLevelLeadLaneOpponent` (corrélation 0.37) prend la tête — nettement plus faible que le 0.60 de `turretTakedowns`, ce qui est normal et honnête : on a retiré le bruit de "être déjà en train de gagner", il reste un signal plus modeste mais plus actionnable.

**Un détour instructif, à refaire toi-même si tu veux pratiquer une recherche web** : `turretPlatesTaken` semblait être un candidat évident pour cette catégorie (les plaques de tourelle "disparaissent à 14 minutes", une règle du jeu connue) — mais une recherche a révélé que le **patch 26.01** (sorti en janvier 2026, donc actif pendant toute notre collecte) a supprimé cette expiration. Vérifié aussi dans les données : `turretPlatesTaken` atteint 41 chez nous, un score impossible sous l'ancien plafond de 14 minutes. Bonne leçon : les mécaniques d'un jeu vivant changent, une hypothèse doit se vérifier, pas se supposer — surtout dans un projet dont les données sont plus récentes que tes propres connaissances.

Visuel suggéré : reprends le graphique en barres de la section 1, mais sur `feature_relevance_early_game` — la hiérarchie est vraiment différente, ça vaut le coup de comparer les deux côte à côte (deux visuels sur la même page).

## 3. Taux de victoire par champion (apprendre : mesures DAX)

À partir de `dataset_for_powerbi` :
- Nouvelle mesure (`Modélisation > Nouvelle mesure`) :
  ```dax
  Taux de victoire = AVERAGE(dataset_for_powerbi[team_win])
  ```
  DAX (le langage de formules de Power BI) ressemble à des formules Excel, mais opère sur des colonnes/tables entières. `AVERAGE` sur une colonne 0/1 donne directement une proportion — c'est le taux de victoire.
- Ajoute une deuxième mesure pour le nombre de parties, indispensable pour juger la fiabilité du taux ci-dessus :
  ```dax
  Nombre de parties = COUNTROWS(dataset_for_powerbi)
  ```
- Graphique à barres : `champion` en axe, `Taux de victoire` en valeur. **Filtre** sur `Nombre de parties >= 50` (filtre de niveau visuel) — un champion avec 5 parties peut afficher 100% ou 0% de winrate par pur hasard, pas un vrai signal.
- **Vérification croisée** : importe aussi `champion_summary` (déjà pré-calculé en Python) et compare ses colonnes `games_played`/`win_rate` à ce que ta mesure DAX affiche pour les mêmes champions — si ça ne correspond pas exactement, il y a un bug quelque part (dans la mesure ou dans l'extraction Python). Une bonne habitude à prendre : un calcul refait dans un second outil sert de garde-fou.

## 4. Comparer un fait de jeu entre victoires et défaites (apprendre : filtres, légendes)

Reprends un des faits en tête du classement (ex: `turretTakedowns`) :
- Graphique à colonnes groupées : `team_win` en axe, `Moyenne de turretTakedowns` en valeur (glisser la colonne, puis changer l'agrégation par défaut de "Somme" à "Moyenne" via le menu du champ).
- Ajoute `champion` ou `role` en **légende** ou en **slicer** (étape 6) pour voir si l'écart victoire/défaite est stable selon les champions/rôles, ou très différent pour certains.

## 5. Pertinence par rôle (apprendre : matrice, segments multiples)

À partir de `feature_relevance_by_role` :
- Visuel **Matrice** : `role` en lignes, `feature` en colonnes (filtré aux ~10-15 faits les plus pertinents globalement via `feature_relevance`), `correlation_with_win` en valeurs — un coup d'œil direct sur "ce fait compte-t-il pareil pour tous les rôles, ou surtout pour un seul".
- **Ignore le rôle `UNKNOWN`** (4 lignes sur 123 460 dans la table complète — un artefact ponctuel de l'API Riot, pas un vrai signal ; ses corrélations à `1.00` sont un pur effet d'échantillon minuscule). Ajoute un filtre `role ≠ UNKNOWN` au niveau de la page.
- Alternative plus simple : un graphique à barres avec `feature` en axe, `abs_correlation` en valeur, et un **slicer** sur `role` pour basculer entre rôles.

## 6. Slicer interactif (apprendre : interactivité)

Ajoute un visuel **Segment** (slicer) sur `champion`, `role`, ou `team`. Sélectionner une valeur dans le slicer filtre alors **tous** les autres visuels de la page en même temps — la vraie force de Power BI par rapport à des graphiques statiques.

## 7. Qualité des données (apprendre : graphique en barres simple, contexte)

À partir de `missing_values` : graphique à barres, `feature` en axe, `missing_pct` en valeur, trié décroissant. 17 colonnes ont plus de 50% de valeurs manquantes (ex: `hadAfkTeammate` à ~99% — logique, ce champ n'existe que s'il y a eu un coéquipier AFK). Utile à savoir avant d'aller plus loin : une colonne très creuse peut donner une fausse impression de pertinence si on ne la croise pas avec son taux de remplissage.

## 8. Vue d'ensemble rapide (apprendre : cartes/KPI)

Deux visuels **Carte** : un avec `COUNTROWS(dataset_for_powerbi)` (nombre total de lignes), un avec `AVERAGE(dataset_for_powerbi[game_duration])` (durée moyenne de partie) — pour un coup d'œil global en haut de la page.

## Limite importante à garder en tête

Cette exploration (corrélations Python + visuels Power BI) ne capture que des relations **simples** : "ce fait bouge-t-il globalement (ou par rôle) avec la victoire". Elle ne peut pas détecter qu'un fait compte **beaucoup pour un champion précis et pas du tout pour un autre au sein du même rôle** (une interaction fine) — c'est exactement ce que les valeurs d'interaction SHAP, calculées après l'entraînement du modèle Gradient Boosted Trees, apporteront en plus. Cette étape Power BI sert à se familiariser avec les données, repérer les pistes évidentes et les problèmes de qualité (fuites, valeurs manquantes) avant d'attaquer le modèle — pas à le remplacer.

Même la restriction "early game" (section 2bis) reste de la **corrélation**, pas une preuve de causalité au sens strict — elle réduit la contamination par le résultat final, elle ne l'élimine pas complètement (une équipe légèrement meilleure peut aussi gagner sa lane tôt *et* le reste du match, sans lien de cause à effet direct entre les deux). À garder en tête en lisant les chiffres.
