# checkit-pipeline

**Pipeline ETL pour la détection de fake news multimodales** (texte + image).
Projet CheckIt.AI — Data Engineering.

Collecte, nettoie et normalise des articles depuis 6 sources hétérogènes (Reddit, fact-checkers, datasets académiques, API d'actualité) vers un schéma unifié JSON Lines prêt à l'entraînement d'un modèle de classification.

## Stack

- **Orchestration** : Apache Airflow
- **Extraction** : `requests`, `feedparser`, `beautifulsoup4`
- **Traitement** : `pandas`
- **Config** : `python-dotenv`

## Sources de données

| Source | Modalités | Volume | Labels | Méthode |
|---|---|---|---|---|
| **FAKEDDIT** | Texte + Image | ~1M | 2 et 6 classes | TSV + Reddit API |
| **NewsData.io** | Texte + URL image | ~200/j | ❌ | API REST |
| **Snopes** | Texte + Image | ~20/sem | Nuancés (5+) | RSS + scraping |
| **FakeNewsNet** | Texte + Image URLs | ~23K | Binaire (PolitiFact) | GitHub + scraping |
| **NewsCLIPpings** | Texte + Image | ~71K | Binaire (hors-contexte) | GitHub + VisualNews |
| **LIAR** | Texte seul | ~12K | 6 niveaux | HuggingFace |

Voir `Module_03_Etape1_Sources_Exploration.md` pour le détail.

## Structure

```
checkit-pipeline/
├── dags/                          # DAGs Airflow
│   └── checkit_pipeline_dag.py    # Pipeline principal : extract → transform
├── src/
│   ├── extraction/                # Un module par source
│   │   ├── newsdata.py            # API REST temps réel
│   │   ├── fakeddit.py            # Dataset Reddit (TSV + PRAW)
│   │   └── snopes.py              # RSS + scraping HTML
│   ├── transformation/
│   │   ├── cleaner.py             # Nettoyage HTML / Unicode
│   │   ├── normalizer.py          # Vers schéma unifié
│   │   └── validator.py           # Vérification champs requis
│   └── utils/
│       ├── logger.py              # Logger stdout formaté
│       └── config.py              # Chargement .env + chemins
├── data/
│   ├── raw/                       # Données brutes par source (JSONL)
│   └── processed/                 # Dataset unifié (JSONL)
├── tests/                         # pytest
├── notebooks/                     # Exploration / prototypage
├── .env.example                   # Template variables d'env
├── requirements.txt
├── CLAUDE.md                      # Instructions pour assistant IA
└── README.md
```

## Schéma de sortie unifié

Toutes les sources sont normalisées vers ce schéma JSON Lines :

```json
{
  "id": "uuid-v4",
  "source": "fakeddit | newsdata | snopes | ...",
  "title": "Article or post title",
  "content": "Full text content",
  "image_url": "https://...",
  "label": "fake | real",
  "label_detail": "false | misleading | satire | mixture | ...",
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

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Éditer .env et renseigner NEWSDATA_API_KEY
```

## Utilisation

### Lancer Airflow en local (dev)

```bash
export AIRFLOW_HOME=$(pwd)/.airflow
airflow standalone
```

Interface : http://localhost:8080 — le DAG `checkit_pipeline` apparaît dans la liste.

### Exécuter une extraction isolée

```bash
python -m src.extraction.newsdata
python -m src.extraction.fakeddit
python -m src.extraction.snopes
```

## Pipeline

```
┌──────────────────────────────────────────┐
│           Extraction (parallèle)          │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  │
│  │newsdata │  │ fakeddit │  │ snopes  │  │
│  └────┬────┘  └────┬─────┘  └────┬────┘  │
└───────┼────────────┼─────────────┼───────┘
        │            │             │
        └────────────┼─────────────┘
                     ▼
          ┌──────────────────────┐
          │   data/raw/*.jsonl   │
          └──────────┬───────────┘
                     ▼
          ┌──────────────────────┐
          │     Transformation   │
          │  cleaner → normalizer│
          │       → validator    │
          └──────────┬───────────┘
                     ▼
          ┌──────────────────────┐
          │ data/processed/*.jsonl│
          └──────────────────────┘
```

## Points de vigilance

- **Droits d'usage** : LIAR et FakeNewsNet en recherche uniquement. Vérifier les CGU de NewsData.io.
- **Rate limiting** : respecter `robots.txt` (Snopes) et `time.sleep(1)` entre requêtes scraping.
- **Idempotence** : les DAGs doivent être rejouables — clé unique `(source, id)`.
- **Nuances de labels** : ne pas réduire `Mixture` ou `Unproven` à un binaire `fake/real` — utiliser `label_detail`.

## Roadmap

- [x] **Étape 1** — Exploration des sources
- [ ] **Étape 2** — Scripts d'extraction FAKEDDIT + NewsData.io
- [ ] **Étape 3** — Pipeline de transformation (cleaner / normalizer / validator)
- [ ] **Étape 4** — DAG Airflow complet + scheduling
- [ ] **Étape 5** — Tests + monitoring + documentation finale
