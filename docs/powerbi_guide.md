# Guide Power BI — explorer le dataset avant l'entraînement

Deux objectifs en un : apprendre les bases de Power BI en le pratiquant, et repérer visuellement quels faits de jeu comptent le plus pour la victoire, avant de se lancer dans le modèle Gradient Boosted Trees + SHAP.

Deux fichiers à importer (générés par `notebooks/03_model_training.ipynb`, à transférer depuis la machine Linux vers Windows — non versionnés dans Git) :
- **`dataset_for_powerbi.csv`** — la table plate, une ligne par (match, joueur), 123 460 lignes × 133 colonnes.
- **`feature_relevance.csv`** — un classement de 129 faits de jeu par corrélation avec la victoire, calculé en Python (voir Concept 7 du notebook).

## 0. Import

`Accueil > Obtenir les données > Texte/CSV` — importe les deux fichiers, un par un. Power BI les charge chacun comme une **table** séparée (visibles dans le volet "Données" à droite).

**Vérifie les types de colonnes** (icône ABC/123/calendrier à gauche de chaque nom de colonne, dans l'onglet Power Query "Transformer les données") : `team_win` vient de Python comme le texte `"True"`/`"False"` — Power BI ne le convertit pas toujours automatiquement en booléen/nombre. S'il reste en texte, les agrégations (moyenne, etc.) ne fonctionneront pas dessus. Corrige-le en `Nombre entier` (True→1, False→0) via clic droit sur la colonne > `Type` — c'est ce qui permettra de calculer un "taux de victoire" comme une simple moyenne.

**Pas besoin de relation entre les deux tables** — elles ne partagent pas de clé commune (`feature_relevance` a une ligne par *colonne* de l'autre table, pas par match). On les utilise dans des visuels séparés.

## 1. Premier visuel : le classement de pertinence (apprendre : graphique en barres, tri)

À partir de `feature_relevance` :
- Glisse `feature` dans **Axe**, `abs_correlation` dans **Valeurs**, choisis un graphique à **barres horizontales**.
- Trie par valeur décroissante (menu `...` du visuel > `Trier par` > `abs_correlation`).
- Ajoute un **filtre de niveau visuel** (`Top N`, ex: 20) sur `feature` par `abs_correlation` — sinon les 129 barres deviennent illisibles.
- Glisse `correlation_with_win`, `mean_when_win`, `mean_when_loss` dans **Info-bulles** pour les voir au survol.

C'est la version interactive de ce qu'on a déjà vu dans le notebook (`turretTakedowns`, `turretPlatesTaken`, `maxKillDeficit` en tête) — mais explorable visuellement, sans revenir à Python.

## 2. Taux de victoire par champion (apprendre : mesures DAX)

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

## 3. Comparer un fait de jeu entre victoires et défaites (apprendre : filtres, légendes)

Reprends un des faits en tête du classement (ex: `turretTakedowns`) :
- Graphique à colonnes groupées : `team_win` en axe, `Moyenne de turretTakedowns` en valeur (glisser la colonne, puis changer l'agrégation par défaut de "Somme" à "Moyenne" via le menu du champ).
- Ajoute `champion` en **légende** ou en **slicer** (filtre visuel, étape 4) pour voir si l'écart victoire/défaite est stable selon les champions, ou très différent pour certains — un premier aperçu (informel) de ce que l'étape 2 de ta vision (SHAP par champion) formalisera plus tard.

## 4. Slicer interactif (apprendre : interactivité)

Ajoute un visuel **Segment** (slicer) sur `champion` (ou `team`). Sélectionner un champion dans le slicer filtre alors **tous** les autres visuels de la page en même temps — la vraie force de Power BI par rapport à des graphiques statiques.

## 5. Vue d'ensemble rapide (apprendre : cartes/KPI)

Deux visuels **Carte** : un avec `COUNTROWS(dataset_for_powerbi)` (nombre total de lignes), un avec `AVERAGE(dataset_for_powerbi[game_duration])` (durée moyenne de partie) — pour un coup d'œil global en haut de la page.

## Limite importante à garder en tête

Cette exploration (corrélations Python + visuels Power BI) ne capture que des relations **simples** : "ce fait bouge-t-il globalement avec la victoire". Elle ne peut pas détecter qu'un fait compte **beaucoup pour un champion précis et pas du tout pour un autre** (une interaction) — c'est exactement ce que les valeurs d'interaction SHAP, calculées après l'entraînement du modèle Gradient Boosted Trees, apporteront en plus. Cette étape Power BI sert à se familiariser avec les données et à repérer les pistes évidentes avant d'attaquer le modèle — pas à le remplacer.
