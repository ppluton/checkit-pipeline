# checkit-pipeline

ETL pipeline pour un système de détection de fake news. Collecte, nettoie et normalise des articles depuis plusieurs sources (NewsData, Fakeddit, Snopes) pour alimenter un modèle de classification.

## Stack

- **Orchestration** : Apache Airflow
- **Extraction** : requests, feedparser, beautifulsoup4
- **Traitement** : pandas
- **Config** : python-dotenv

## Structure

```
checkit-pipeline/
├── dags/                    # DAGs Airflow
├── src/
│   ├── extraction/          # Un module par source de données
│   │   ├── newsdata.py
│   │   ├── fakeddit.py
│   │   └── snopes.py
│   ├── transformation/      # Pipeline de transformation
│   │   ├── cleaner.py       # Nettoyage des textes
│   │   ├── normalizer.py    # Normalisation du schéma
│   │   └── validator.py     # Validation des données
│   └── utils/
│       ├── logger.py        # Logger centralisé
│       └── config.py        # Chargement .env
├── data/
│   ├── raw/                 # Données brutes par source
│   └── processed/           # Données traitées et unifiées
├── tests/                   # Tests unitaires et d'intégration
├── notebooks/               # Exploration et prototypage
├── .env.example             # Template des variables d'environnement
└── requirements.txt
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Remplir `.env` avec les clés API nécessaires.

## Sources

- **NewsData** : API d'agrégation d'actualités (clé requise)
- **Fakeddit** : Dataset multimodal de fake news Reddit
- **Snopes** : Scraping des vérifications de faits
