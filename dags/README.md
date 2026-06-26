# DAGs

Orchestration Airflow du pipeline ETL.

## `checkit_pipeline_dag.py`

DAG `checkit_pipeline` : enchaîne extraction, transformation, assemblage
du dataset, acquisition d'images et restitution des KPI.

### Graphe

```
[extract_guardian]
[extract_fakeddit] ─► [transform] ─► [build_dataset] ─► [acquire_images]
[extract_snopes]                                            │
[extract_liar]                       [load_to_postgres] ◄───┘ ─► [report_kpis]
```

### Tâches

| Tâche | Appelle | Rôle |
| --- | --- | --- |
| `extract_guardian` | `guardian.fetch` | Brut Guardian |
| `extract_fakeddit` | `fakeddit.fetch` | Brut Fakeddit |
| `extract_snopes` | `snopes.fetch` | Brut Snopes |
| `extract_liar` | `liar.fetch` | Brut LIAR |
| `transform` | `pipeline.transform` | Dataset unifié validé |
| `build_dataset` | `dataset.build_dataset` | Split + data card |
| `acquire_images` | `images.acquire_all` | Téléchargement des images |
| `load_to_postgres` | `load.load_splits` | Chargement Postgres (full refresh) |
| `report_kpis` | `dashboard.main` | KPI + dashboard |

### Décisions d'architecture

- **Fan-in parallèle des extractions** : les quatre sources n'ont aucun
  état partagé (chacune écrit dans son propre `data/raw/<source>/`), donc
  elles s'exécutent en parallèle. Le temps total est borné par la source
  la plus lente (Snopes, ~30 s avec le délai de politesse).
- **Une tâche par source** (plutôt qu'un dynamic mapping) : chaque source
  a ses spécificités (clé d'API, rate limit, structure) et son profil de
  retry. Le découpage donne aux opérateurs un redémarrage et une
  observabilité précis.
- **`build_dataset` séparé de `transform`** : le split et les statistiques
  opèrent sur le dataset unifié *complet*, donc une fois après
  normalisation de toutes les sources. Tâche distincte = rejouable
  (ex. re-shuffle avec une nouvelle seed) sans refaire l'extraction.
- **`acquire_images` en avant-dernier** : étape la plus lente et la plus
  faillible (une requête HTTP par record). La placer après le split
  garantit qu'un échec n'empêche jamais la production du dataset unifié et
  du split ; elle réécrit les fichiers de split en place en corrigeant
  `has_image`.
- **`report_kpis` en clôture** : recalcule les KPI et régénère le
  dashboard, pour que chaque run laisse une vue auditable et à jour
  (volumétrie, taux de rejet, couverture image, intégrité du split).

### Configuration

- `schedule="@daily"` : adapté à la fraîcheur des sources (Snopes ~20
  fact-checks/semaine, Guardian quelques centaines/jour, Fakeddit
  statique) sans épuiser le quota Guardian.
- `retries=1`, `retry_delay=5 min`, `catchup=False`.
- Imports faits **dans** les callables (pas au niveau module) pour ne pas
  charger `src` au parsing du DAG par le scheduler.

### Lancement local

```bash
docker compose up -d   # Postgres : backend Airflow + cible du load
export AIRFLOW_HOME=$(pwd)/.airflow
export AIRFLOW__CORE__DAGS_FOLDER=$(pwd)/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTOR=LocalExecutor
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@localhost:5433/airflow
uv run airflow standalone
```
