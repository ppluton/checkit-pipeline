# Extraction

Première étape de l'ETL : collecte du brut depuis chaque source et
persistance sans interprétation dans `data/raw/<source>/*.jsonl`.

## Contrat

- Les extracteurs **filtrent** mais ne **transforment** pas. Le mapping
  vers le schéma unifié et la politique de labels appartiennent au
  `normalizer`, pas ici.
- Chaque module expose une fonction `fetch(...) -> Path` retournant le
  chemin du JSONL écrit, et un bloc `__main__` lançant une extraction
  réduite (`uv run python -m src.extraction.<source>`).
- L'écriture passe par `src.utils.io.write_jsonl` (streaming, fichier
  horodaté par défaut pour ne pas écraser les runs précédents).
- Erreurs traitées par enregistrement : loggées et comptées (`skipped`),
  jamais fatales pour le batch.

## Modules

| Fichier | Source | Méthode | Sortie |
| --- | --- | --- | --- |
| `fakeddit.py` | FAKEDDIT | TSV en streaming | `data/raw/fakeddit/` |
| `guardian.py` | The Guardian | API REST Open Platform | `data/raw/guardian/` |
| `snopes.py` | Snopes | RSS + ClaimReview JSON-LD + BS4 | `data/raw/snopes/` |
| `liar.py` | LIAR | Archive UCSB (TSV) | `data/raw/liar/` |

### `fakeddit.py`

Source d'entraînement principale (~1M posts Reddit multimodaux, labels
2 classes et 6 classes).

- **Streaming** via `pd.read_csv(chunksize=10_000, sep="\t")` : le
  fichier ne tient pas en mémoire, traitement par chunks dans un
  générateur.
- `dtype=str` et `on_bad_lines="skip"` pour un parsing robuste.
- Filtre les lignes sans `image_url` (contrat multimodal).
- `LABEL_6WAY` / `LABEL_2WAY` exposés comme constantes, réutilisés par le
  `normalizer`.
- `FAKEDDIT_TSV_PATH` accepte un chemin local ou une URL.

### `guardian.py`

Baseline « real » haute crédibilité.

- **Pas de paramètre de recherche `q`** : choix anti-fuite de label. Une
  recherche thématique (« fake news ») ramènerait des articles *parlant*
  de désinformation mais labellisés `real`, apprenant au modèle le
  vocabulaire du sujet plutôt que la véracité. Échantillonnage de
  sections neutres (`world|science|technology|business|environment`).
- Conserve uniquement `type == "article"`.
- Pagination bornée par `max_pages` (maîtrise du quota 5000 req/jour).
- `RATE_LIMIT_SLEEP = 1.0 s` entre pages.
- `require_image=True` par défaut ; les articles sans thumbnail sont
  comptés et loggés.

### `snopes.py`

Fact-checker de référence ; scraping RSS puis page article.

- **Double stratégie**, dans l'ordre :
  1. **ClaimReview JSON-LD** (préféré) : données structurées schema.org,
     stables face aux refontes HTML, verdict et claim verbatim.
  2. **Fallback CSS (BeautifulSoup)** : sélecteurs sur les classes
     `rating`/`claim` quand le JSON-LD manque. `verdict = None` accepté
     pour les articles narratifs (le `normalizer` les écarte).
- **`protego`** au lieu de `urllib.robotparser` : le `robots.txt` de
  Snopes débute par une directive non standard `Content-Signal:` qui fait
  échouer la stdlib (refus global). `protego` la gère ; résultat mis en
  cache (`lru_cache`).
- Rate limit 1.5 s, `User-Agent` explicite.
- `extraction_method` enregistré par record pour la traçabilité.

### `liar.py`

Source auxiliaire texte seul (déclarations politiques, labels PolitiFact
6 niveaux).

- Contourne `load_dataset("liar")` (loader-script cassé dans
  `datasets>=3`) et la branche `refs/convert/parquet` de HuggingFace
  (supprimée) en lisant l'archive ZIP canonique d'UCSB (fichiers TSV).
- Concatène les trois splits, conserve l'origine dans une colonne
  `split`.
- Aucun filtrage : les labels ambigus (`half-true`) sont gardés, le
  `normalizer` décide.
- `image_url` toujours nul (schéma nullable).
