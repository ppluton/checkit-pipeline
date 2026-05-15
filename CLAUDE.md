# CLAUDE.md — checkit-pipeline

## Contexte projet

**CheckIt.AI** — Pipeline ETL pour la détection de **fake news multimodales** (texte + image). Collecte, normalise et valide des articles depuis 6 sources hétérogènes pour alimenter un modèle de classification.

Doc de cadrage : `Module_03_Etape1_Sources_Exploration.md`.

## Stack

- **Langage** : Python 3.11+
- **Gestion des deps** : **uv** (pas pip, pas poetry). Manifeste : `pyproject.toml`, lockfile : `uv.lock` (commité).
- **Orchestration** : Apache Airflow
- **Extraction** : `requests`, `feedparser`, `beautifulsoup4`, `praw` (Reddit), `datasets` (HuggingFace)
- **Traitement** : `pandas`
- **Validation** : `pydantic>=2`
- **Config** : `python-dotenv`
- **Tests** : `pytest`
- **Lint/format** : `ruff` (configuré dans `pyproject.toml`)

> Les préférences globales (bun, Biome, bun:test) **ne s'appliquent pas ici** : projet Python pur.

### Workflow uv

- Ajouter une dépendance : `uv add <pkg>`
- Ajouter une dep de dev : `uv add --dev <pkg>`
- Lancer un script dans l'env : `uv run python -m src.extraction.fakeddit`
- Sync de l'env depuis le lockfile : `uv sync`
- Ne **jamais** committer `requirements.txt` ni utiliser `pip install` directement.

## Sources

| Source | Modalités | Méthode | Priorité |
|---|---|---|---|
| FAKEDDIT | Texte + Image | TSV + Reddit API | 🟢 Étape 2 |
| The Guardian | Texte + Thumbnail | API REST (clé gratuite) | 🟢 Étape 2 |
| Snopes | Texte + Image | RSS + scraping HTML | 🟡 |
| FakeNewsNet | Texte + Image URLs | Clone GitHub + scraping | 🟡 |
| NewsCLIPpings | Texte + Image | GitHub + VisualNews | 🔵 Vision |
| LIAR | Texte seul | HuggingFace `datasets` | 🔵 NLP |

## Schéma de sortie unifié (JSON Lines)

Toute source doit être normalisée vers :

```json
{
  "id": "uuid-v4",
  "source": "fakeddit | newsdata | snopes | ...",
  "title": "...",
  "content": "...",
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

**Stockage** : `data/raw/<source>/*.jsonl` (brut par source) puis `data/processed/*.jsonl` (unifié).

## Règles de code

- **Pas de over-engineering** : stubs minimaux d'abord, on étoffe selon le besoin.
- **Pas de commentaires** sauf logique non-évidente (ex: contournement d'un bug d'API).
- **Typage** : annotations Python sur tout signature publique.
- **Logger** : utiliser `src.utils.logger.get_logger(__name__)`, jamais `print`.
- **Config** : passer par `src.utils.config`, jamais `os.getenv` direct dans le code métier.
- **Préserver les nuances de labels** : ne pas réduire `Mixture`/`Unproven` à un binaire — utiliser `label_detail`.

## Règles ETL spécifiques

1. **Extraction → `data/raw/<source>/`** : format brut de la source, peu transformé.
2. **Transformation** : `cleaner` (HTML/Unicode) → `normalizer` (schéma cible) → `validator` (champs requis, association texte-image).
3. **Rate limiting** : `time.sleep(1)` minimum entre requêtes scraping. Vérifier `robots.txt` pour Snopes.
4. **Idempotence** : les DAGs doivent pouvoir être rejoués sans dupliquer (clé : `(source, id)`).
5. **Pas de secrets en clair** : tout passe par `.env` (ignoré dans git).

## Workflow

- Projet de **portfolio** : tout livrable (code, commits, PRs, docs) doit être **professionnel** et écrit comme par un développeur humain.
- Commits atomiques, conventionnels (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).
- Messages de commit en **anglais**, à l'impératif court (50 char max pour le sujet), corps optionnel en wrap 72 char expliquant le *pourquoi*.
- **Ne jamais inclure** : `Co-Authored-By: Claude*`, `🤖 Generated with Claude Code`, ni aucune mention d'assistant IA dans commits, PRs, code, docs ou commentaires.
- **Ne pas signer** les commits avec une trailer co-author IA. Le commit est attribué à Pierre Pluton uniquement.
- Pas d'emojis dans les commits, PRs ou docs publics (README, CLAUDE.md interne ok).
- Code en anglais (noms de variables, fonctions, commentaires). Docs projet en français acceptées.
- Ne pas commit sans demande explicite. Ne pas push sans confirmation.
- Branche principale : `main`.

## Ton & style des livrables

- README, commits, PRs : ton **factuel et technique**, pas marketing, pas conversationnel.
- Pas de formulations type "I've created...", "Let me know if...", "Hope this helps".
- Préférer la voix passive ou impersonnelle dans les descriptions techniques.
- Pas de mention du processus de création (ex: "généré avec X", "écrit avec l'aide de Y").

## Commandes utiles

```bash
# Setup initial
uv sync
cp .env.example .env

# Airflow standalone (dev)
export AIRFLOW_HOME=$(pwd)/.airflow
uv run airflow standalone

# Lancer une extraction isolée
uv run python -m src.extraction.fakeddit
uv run python -m src.extraction.guardian

# Tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format .
```

## Pièges connus

- **FakeNewsNet** : URLs d'articles expirent → scraper les images dès la collecte initiale.
- **The Guardian** : 5000 req/jour avec clé developer gratuite, rate limit 1 req/s respecté côté code (`RATE_LIMIT_SLEEP`).
- **Snopes** : robots.txt à vérifier avant tout scraping automatisé.
- **FAKEDDIT** : ~1M de posts → ne pas tout charger en mémoire, streamer.
