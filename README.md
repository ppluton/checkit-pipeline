# checkit-pipeline

> **CheckIt.AI · Data Engineering**
> Pipeline ETL automatisé pour extraire, transformer et charger des données multimodales (texte + image) destinées à entraîner un modèle de détection de fake news.

CheckIt.AI développe des outils d'intelligence artificielle pour lutter contre la désinformation. Ce projet couvre l'intégralité du cycle data engineering : ingestion multi-sources, normalisation vers un schéma unifié, validation, orchestration Airflow et monitoring.

## Mission

Construire un pipeline qui ingère des publications **texte + image** depuis des sources hétérogènes (datasets académiques, API d'actualité, fact-checkers via scraping), les unifie dans un format prêt-à-modèle, et tourne quotidiennement de manière fiable et observable.

```
 Sources externes ──► EXTRACT ──► data/raw/*.jsonl ──► TRANSFORM ──► data/processed/*.jsonl ──► LOAD ──► PostgreSQL
                                                       (cleaner · normalizer · validator)
```

Voir [`docs/architecture.md`](docs/architecture.md) pour les choix techniques détaillés.

## Stack

| Couche | Outil | Raison |
|---|---|---|
| Orchestration | Apache Airflow | Standard ETL, DAGs versionnés, retry/scheduling natif |
| Gestion deps | [uv](https://github.com/astral-sh/uv) | Reproductible (`uv.lock`), ~10× plus rapide que pip |
| Extraction HTTP | `requests`, `feedparser`, `beautifulsoup4`, `protego` | Stack scraping mature |
| Validation | `pydantic>=2` | Contrats stricts au niveau des frontières IO |
| Traitement | `pandas` | Streaming TSV via `chunksize`, idiomatique pour ETL |
| Config | `python-dotenv` | `.env` requis par le spec |
| Tests / lint | `pytest`, `ruff` | Tooling Astral cohérent avec uv |

## Sources de données

| Source | Modalités | Volume | Labels | Méthode | Statut |
|---|---|---|---|---|---|
| [FAKEDDIT](https://github.com/entitize/Fakeddit) | Texte + Image | ~1M | 2 et 6 classes | TSV streaming | ✅ Implémenté |
| [The Guardian](https://open-platform.theguardian.com) | Texte + Thumbnail | 5 000 req/jour | ❌ (baseline real) | API REST | ✅ Implémenté |
| [Snopes](https://www.snopes.com/feed/) | Texte + Image | ~20/sem | Nuancés (`True`, `False`, `Mixture`, `Mostly True`, ...) | RSS + ClaimReview JSON-LD + BS4 | ✅ Implémenté |
| [LIAR](https://huggingface.co/datasets/ucsbnlp/liar) | Texte seul ⚠️ | ~12K | 6 niveaux (`pants-fire` → `true`) | HuggingFace parquet | ✅ Implémenté (NLP-only) |
| [FakeNewsNet](https://github.com/KaiDMML/FakeNewsNet) | Texte + Image URLs | ~23K | Binaire (PolitiFact) | GitHub + scraping | 🔲 Backlog |
| [NewsCLIPpings](https://github.com/g-luo/news_clippings) | Texte + Image | ~71K | Binaire (hors-contexte) | GitHub + VisualNews | 🔲 Backlog (vision) |

Le rapport d'exploration détaillé (Étape 1) est dans [`docs/rapport_sources.md`](docs/rapport_sources.md).

> **Note sur la substitution NewsData.io → The Guardian** : le spec d'origine prévoyait NewsData.io, dont l'usage devient payant au-delà du plan gratuit (200 req/jour). Le Guardian Open Platform offre 5 000 req/jour gratuit avec une qualité éditoriale supérieure. La justification complète est dans [`docs/architecture.md §3.1`](docs/architecture.md#31-the-guardian--différence-avec-le-spec).

> **Note sur LIAR (texte-seul)** : LIAR brise volontairement le contrat strict "multimodal" pour servir de **source NLP auxiliaire**. Le futur classifieur multimodal a une branche texte qui peut s'entraîner sur l'ensemble des sources (LIAR inclus), tandis que la branche vision reste limitée aux sources avec image. Notre schéma le supporte nativement (`image_url` nullable, `metadata.has_image = false`). Détails dans [`docs/architecture.md §3.4`](docs/architecture.md#34-liar--source-nlp-only-auxiliaire).

## Schéma de sortie unifié

Toutes les sources sont normalisées vers le format JSON Lines suivant (validé par Pydantic dans [`src/transformation/schema.py`](src/transformation/schema.py)) :

```json
{
  "id": "<uuid-v4>",
  "source": "fakeddit | guardian | snopes | ...",
  "title": "Article or post title",
  "content": "Full text content",
  "image_url": "https://...",
  "label": "fake | real | null",
  "label_detail": "Mixture | Mostly True | satire | manipulated_content | ...",
  "language": "en",
  "domain": "snopes.com",
  "collected_at": "2026-05-15T00:00:00Z",
  "metadata": {
    "source_credibility": "high | medium | low",
    "has_image": true,
    "label_method": "human_expert | community | automated"
  }
}
```

Décisions clés :

- `label` est **nullable** : sources non labellisées (Guardian) restent utilisables via `source_credibility`.
- `label_detail` est **libre** : préserve les nuances fact-checker (`Mixture`, `Originated as Satire`...) que le binaire détruirait.
- `metadata.label_method` distingue les labels experts (Snopes) des labels communautaires (Fakeddit) — utile en feature engineering.

## Structure du projet

```
checkit-pipeline/
├── dags/
│   └── checkit_pipeline_dag.py       # DAG principal : 3 extracts parallèles → transform
├── src/
│   ├── extraction/
│   │   ├── fakeddit.py               # Streaming TSV multimodal
│   │   ├── guardian.py               # Content API + pagination
│   │   ├── liar.py                   # HuggingFace parquet (NLP-only)
│   │   └── snopes.py                 # RSS + ClaimReview JSON-LD + BS4
│   ├── transformation/
│   │   ├── schema.py                 # Modèles Pydantic (Article, ArticleMetadata)
│   │   ├── cleaner.py                # [Étape 3] dédup, drop nulls, sanitise text
│   │   ├── normalizer.py             # [Étape 3] mapping raw → Article par source
│   │   └── validator.py              # [Étape 3] enforce invariants, log rejets
│   └── utils/
│       ├── logger.py                 # Logger stdout formaté (idempotent)
│       └── config.py                 # Chargement .env, chemins data/
├── data/
│   ├── raw/                          # Données brutes par source (gitignored)
│   └── processed/                    # Dataset unifié (gitignored)
├── docs/
│   ├── rapport_sources.md            # Étape 1 — exploration des sources
│   └── architecture.md               # Décisions techniques détaillées
├── tests/                            # pytest
├── notebooks/                        # Exploration / prototypage
├── pyproject.toml                    # Manifeste deps
├── uv.lock                           # Lockfile reproductible
├── .env.example                      # Template variables d'env
├── CLAUDE.md                         # Conventions internes (commit, code, style)
└── README.md
```

## Installation

Prérequis : [uv](https://github.com/astral-sh/uv) (`brew install uv` ou `curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
uv sync
cp .env.example .env
```

Compléter `.env` :
- `GUARDIAN_API_KEY` — clé developer gratuite via https://open-platform.theguardian.com/access/
- `FAKEDDIT_TSV_PATH` — chemin local ou URL du TSV multimodal Fakeddit (voir `docs/rapport_sources.md`)

## Utilisation

### Extraction isolée par source

```bash
uv run python -m src.extraction.fakeddit
uv run python -m src.extraction.guardian
uv run python -m src.extraction.snopes
uv run python -m src.extraction.liar
```

Chaque commande écrit un fichier `data/raw/<source>/<source>_<timestamp>.jsonl`.

### Pipeline complet via Airflow

```bash
docker compose up -d   # Postgres : backend Airflow + cible du load
export AIRFLOW_HOME=$(pwd)/.airflow
export AIRFLOW__CORE__DAGS_FOLDER=$(pwd)/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTOR=LocalExecutor
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@localhost:5433/airflow
uv run airflow standalone
```

Interface : http://localhost:8080 — le DAG `checkit_pipeline` apparaît dans la liste.
Le backend Postgres évite la contention SQLite sous les extractions parallèles.

> [!NOTE]
> **Exécution du DAG : `dags test` vs `standalone`.**
> Deux façons de lancer le pipeline, avec un comportement différent selon l'environnement :
>
> - **`uv run airflow dags test checkit_pipeline`** exécute tout le DAG dans un seul
>   processus, séquentiellement. C'est le mode **fiable** : il termine vert sur les
>   9 tâches (logs à l'appui) et constitue la preuve d'exécution recommandée.
> - **`uv run airflow standalone`** lance l'ordonnanceur complet + l'interface web +
>   l'executor (un sous-processus par tâche). C'est le mode qui fournit le **graphe
>   visuel**.
>
> **Limite connue d'Airflow 3.x en mode standalone** : sur certaines machines, la
> couche d'exécution (task-SDK + serveur d'API) peut laisser des **tâches très
> rapides** (ex. `extract_fakeddit`, qui lit un échantillon de 5 lignes) bloquées en
> état `running` alors qu'elles ont fini — la complétion n'est pas remontée à
> l'ordonnanceur. Le passage à Postgres a supprimé la contention de verrou SQLite
> (`database is locked`), mais ce point relève de l'infrastructure d'orchestration,
> **pas du pipeline** : le code passe vert à chaque `dags test`.
>
> **Recommandation** : utiliser `dags test` comme preuve d'exécution, et l'UI
> standalone pour visualiser et présenter le graphe des tâches.

### Tests & lint

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Roadmap & livrables (5 étapes)

| Étape | Livrable | Statut | Détail |
|---|---|---|---|
| 1 | Exploration des sources | ✅ | [`docs/rapport_sources.md`](docs/rapport_sources.md) — 6 sources évaluées, critères qualité/volume/droits |
| 2 | Scripts d'extraction | ✅ (4/6 sources) | `src/extraction/{fakeddit,guardian,snopes,liar}.py`, exécution sans intervention, logs + gestion d'erreurs |
| 3 | Transformation + schéma | ✅ | `cleaner` → `normalizer` → `validator` → `dataset` → `images` ; schéma Pydantic v2 + Mermaid |
| 4 | DAG Airflow (ETL) | ✅ | `dags/checkit_pipeline_dag.py` — extract ×4 → transform → split → images → **load Postgres** → KPI, exécuté vert de bout en bout ; backend Airflow + base applicative en Postgres (Docker) |
| 5 | KPIs & monitoring | ✅ | `src/monitoring/` — rapport MD, figure PNG, app Streamlit interactive ; plan `docs/monitoring.md` |

## Décisions techniques marquantes

Synthèse rapide (détails dans [`docs/architecture.md`](docs/architecture.md)) :

- **uv au lieu de pip** — builds reproductibles, lockfile commité, install ~10× plus rapide
- **Pydantic v2 strict** — `extra="forbid"` empêche la dérive silencieuse du schéma
- **protego au lieu de `urllib.robotparser`** — la stdlib refuse Snopes à cause d'une directive non-standard (`Content-Signal:`), protego (Scrapy) gère ça correctement
- **ClaimReview JSON-LD prioritaire** — extraction Snopes via schema.org plutôt que CSS, stable across redesigns
- **Streaming TSV par chunks de 10k** — Fakeddit fait ~1M de lignes, le chargement complet sature un laptop standard
- **Une tâche d'extraction par source dans le DAG** — restartabilité fine, observabilité par source

## Points de vigilance

- `.env` **jamais commité** — vérifié dans `.gitignore`, contient les clés API.
- `data/raw/` et `data/processed/` **non versionnés** — datasets gros, recréables.
- **Droits d'usage** : Fakeddit, LIAR, FakeNewsNet en recherche académique uniquement. The Guardian developer tier en non-commercial avec attribution.
- **Scraping respectueux** : `User-Agent` identifiable, `time.sleep(1.5)` entre requêtes Snopes, `robots.txt` vérifié via protego.
- **Nuances de labels préservées** : ne pas réduire `Mixture` ou `Unproven` à un binaire `fake/real` — utiliser `label_detail`.

## Ressources

- [Apache Airflow Docs](https://airflow.apache.org/docs/)
- [The Guardian Open Platform](https://open-platform.theguardian.com/documentation/)
- [Fakeddit Paper (Nakamura et al., 2020)](https://arxiv.org/abs/1911.03854)
- [schema.org/ClaimReview](https://schema.org/ClaimReview)
- [Protego (robots.txt parser de Scrapy)](https://github.com/scrapy/protego)
- [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/)

---

*CheckIt.AI · Data Engineering · pipeline ETL · Python · Airflow · PostgreSQL*
