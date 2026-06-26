# Plan de monitoring de l'ETL — CheckIt.AI

> Comment on surveille le pipeline une fois en production, ce qu'on mesure,
> les seuils d'alerte et la conduite à tenir en cas de problème.

Un pipeline ETL n'est pas un script qu'on lance une fois : il tourne de façon
récurrente (`@daily`) et alimente l'entraînement d'un modèle. Si sa qualité
dérive sans qu'on le voie, c'est le modèle qui en pâtit. Le monitoring répond à
une question simple : **« le dataset produit aujourd'hui est-il aussi bon que
celui d'hier ? »**

## 1. Ce qu'on surveille, par étage

| Étage | Signal surveillé | Pourquoi |
|---|---|---|
| Extraction | Succès/échec de chaque source, volume collecté | Une API en panne ou un quota épuisé fait chuter le volume |
| Extraction | Respect du rate limit et du `robots.txt` | Rester bon citoyen, éviter les bannissements |
| Transformation | Taux de rejet du validator par source | Un pic de rejet signale un changement de format source |
| Acquisition images | Taux d'échec de téléchargement | Des URLs qui expirent en masse = perte de multimodal |
| Découpage | Fuite de contenu inter-split | Doit rester à 0, sinon évaluation faussée |
| Global | Fraîcheur (âge du dernier run réussi) | Détecter un pipeline silencieusement arrêté |

## 2. Indicateurs et seuils d'alerte

Les valeurs sont issues du tableau de bord KPI (`docs/etl_kpi_report.md`,
`src/monitoring/`). Seuils proposés, à affiner avec l'historique :

| Indicateur | Cible | Avertissement | Critique |
|---|---|---|---|
| Volume collecté / source | ≈ baseline | −30 % vs moyenne 7 j | −60 % ou 0 |
| Taux de rejet validator | < 15 % | 15–30 % | > 30 % |
| Taux d'échec image | < 10 % | 10–25 % | > 25 % |
| Fuites inter-split | 0 | — | ≥ 1 |
| Fraîcheur (dernier succès) | < 24 h | 24–48 h | > 48 h |
| Tests CI | 100 % verts | — | tout échec |

Note : le taux de rejet Snopes est structurellement élevé (~35 %) car les
articles narratifs sans verdict sont écartés volontairement. Le seuil doit donc
être évalué **par source**, pas globalement.

## 3. Comment on observe

- **Logs structurés** : tous les modules passent par `src.utils.logger`
  (format homogène, niveau INFO/WARNING). Chaque rejet et chaque échec
  d'image est tracé avec sa raison — jamais d'échec silencieux.
- **Interface Airflow** : statut des tâches, durées, logs par exécution,
  historique des succès/échecs, relances.
- **Tableau de bord KPI** : figure PNG + rapport Markdown régénérés à chaque run
  par la tâche `report_kpis` (`docs/etl_dashboard.png` + `docs/etl_kpi_report.md`),
  et application **Streamlit interactive** (`src/monitoring/streamlit_app.py`)
  pour l'exploration en direct.
- **Fiche dataset** : `docs/data_card.md`, régénérée à chaque run, pour suivre
  la dérive des distributions dans le temps.

## 4. Gestion des incidents et reprise

- **Échecs transitoires** (HTTP 5xx, timeouts) : Airflow rejoue automatiquement
  la tâche (`retries=1`, `retry_delay=5 min`). Les erreurs réseau sur un article
  isolé sont loggées sans interrompre le lot (extraction tolérante aux pannes).
- **Idempotence** : les extractions écrivent des fichiers horodatés et la
  transformation ne lit que le plus récent ; un rejeu ne duplique pas le
  dataset final. Une tâche peut être relancée seule sans tout reprendre.
- **Isolation des pannes** : l'acquisition d'images, étape la plus faillible,
  est en fin de chaîne — une panne de téléchargement ne bloque jamais la
  production du dataset unifié et du découpage.
- **Échec d'une source** : les 4 extractions étant indépendantes, l'échec de
  l'une n'empêche pas les autres ; le dataset est produit avec les sources
  disponibles, et le KPI de volume signale le manque.

## 5. Dérive de schéma (point de vigilance principal)

Le risque le plus sournois est qu'une source change silencieusement son format
(clé d'API renommée, structure HTML modifiée). Le `validator` (Pydantic,
`extra="forbid"`, vocabulaire fermé) est le filet de sécurité : un changement de
contrat fait grimper le taux de rejet, ce qui déclenche l'alerte décrite en
section 2 plutôt que de laisser passer des données corrompues.

## 6. Cadence et responsabilités

| Quoi | Fréquence | Déclencheur |
|---|---|---|
| Exécution du pipeline | Quotidienne (`@daily`) | Airflow scheduler |
| Régénération KPI + fiche | À chaque run | Tâche `report_kpis` |
| Revue des seuils d'alerte | Mensuelle | Manuel, à partir de l'historique |
| Audit qualité du dataset | Avant chaque entraînement | Manuel, via la fiche dataset |
