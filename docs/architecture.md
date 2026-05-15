# Architecture & décisions techniques

Document de référence pour comprendre *pourquoi* le projet est structuré comme il l'est. Le code dit ce qu'il fait ; ce fichier dit pourquoi.

## 1. Vue d'ensemble

```
External sources                     Local storage              Output
────────────────                     ─────────────              ──────
The Guardian API ─┐
                  │
Fakeddit TSV     ─┼─► EXTRACT ──► data/raw/<source>/*.jsonl
                  │   (parallel)
Snopes RSS+HTML ─┘
                                                                   │
                                                                   ▼
                                  data/raw/*.jsonl ─► TRANSFORM ─► data/processed/*.jsonl
                                                      cleaner →
                                                      normalizer →
                                                      validator
                                                                   │
                                                                   ▼
                                                              LOAD (PostgreSQL — Étape 4)
                                                                   │
                                                                   ▼
                                                              MODEL TRAINING (hors scope)
```

Chaque flèche correspond à une responsabilité unique. Aucun étage ne fait le travail du suivant : l'extraction ne normalise pas, la normalisation ne valide pas, etc. C'est ce qui permet de rejouer une étape sans recommencer tout le pipeline.

## 2. Choix de stack

### 2.1 `uv` au lieu de `pip` / `poetry`

| Critère | `pip + requirements.txt` | `poetry` | `uv` |
|---|---|---|---|
| Vitesse install | Lente | Lente | ~10× plus rapide |
| Lockfile reproductible | Non (sauf `pip-tools`) | Oui | Oui (`uv.lock`) |
| Python managé | Non | Non | Oui (`uv python install`) |
| Adoption industrielle | Standard | Niche | Croissante (Astral) |

`uv` couvre l'ensemble du cycle (résolution, install, exécution, gestion des versions Python) avec une UX cohérente. Le lockfile `uv.lock` est commit pour garantir des builds reproductibles entre machines et CI.

### 2.2 `Pydantic v2` pour le schéma

Le pipeline ingère 3 sources de structures très différentes vers un schéma unifié (`Article`). Sans validation runtime, une dérive silencieuse (ex. nouveau champ ajouté par l'API Guardian) ne serait détectée qu'au moment de l'entraînement du modèle, beaucoup trop tard.

Choix précis :
- `Literal["high", "medium", "low"]` plutôt que `str` — vocabulaire fermé, typos impossibles
- `ConfigDict(extra="forbid")` — un champ inconnu lève une erreur, pas un warning
- `model_dump_json(exclude_none=False)` — sérialisation JSONL canonique, les `null` sont explicites

### 2.3 `protego` au lieu de `urllib.robotparser`

`urllib.robotparser` de la stdlib échoue silencieusement quand un `robots.txt` contient des directives non standard. Snopes utilise `Content-Signal: search=yes,ai-train=no` (extension Cloudflare/IETF récente) et la stdlib retourne `False` pour *tous* les user-agents, y compris `Googlebot`.

`protego` est le parseur utilisé par Scrapy. Il gère correctement :
- les directives non standard (ignorées au lieu de tout invalider)
- la précédence `Allow` vs `Disallow` (RFC 9309)
- les wildcards et patterns

C'est une dépendance de 200 ko qui évite une faille de fond dans le scraping.

### 2.4 `pandas` pour Fakeddit, `requests` pour Guardian/Snopes

`pandas.read_csv(chunksize=...)` est plus ergonomique que `csv` pour streamer un TSV de 1 M de lignes avec parsing typé. Pour les API REST et le scraping, `requests` reste l'outil standard de fait et son interface est familière à tout développeur Python.

## 3. Structure du pipeline d'extraction

Chaque module `src/extraction/<source>.py` expose une fonction `fetch(...)` unique, idempotente côté disque (un fichier de sortie par run, timestamp dans le nom).

Pattern commun :

```python
def fetch(...) -> Path:
    out_dir = RAW_DIR / "<source>"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"<source>_{timestamp}.jsonl"
    with out_path.open("w") as f:
        for record in _iter_records(...):
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return out_path
```

- **Sortie séparée par source** : `data/raw/guardian/`, `data/raw/fakeddit/`, `data/raw/snopes/`. La transformation peut traiter chaque source avec une logique différente sans se mélanger les pinceaux.
- **JSONL** plutôt que JSON tabular : un objet par ligne permet de streamer en lecture, d'append-only, et de paralléliser le traitement par split de fichier.
- **Pas de normalisation à l'extraction** : on conserve les champs sources tels quels (`webPublicationDate`, `2_way_label`, `og:image`...). Le `normalizer` traduit vers le schéma unifié plus tard.

### 3.1 The Guardian — différence avec le spec

Le spec original mentionne NewsData.io. Nous avons substitué The Guardian Open Platform pour rester sur une stack entièrement gratuite : NewsData propose 200 req/jour gratuit puis devient payant, alors que The Guardian Developer Tier offre 5 000 req/jour sans condition commerciale. Le rôle dans le pipeline est identique : source d'articles frais à haute crédibilité, sans labels, servant de baseline "real".

### 3.2 Fakeddit — choix du streaming

Le TSV multimodal Fakeddit fait ~1 M de lignes. Charger l'ensemble en RAM (`pd.read_csv(...)` sans `chunksize`) consomme 2-3 GB et bloque sur un laptop standard. La version par chunks (10 000 lignes) tient en mémoire constante et peut s'arrêter via `limit=` pour les smoke tests sans charger plus que nécessaire.

### 3.3 Snopes — double stratégie d'extraction

Le module tente d'abord d'extraire les données via le bloc JSON-LD `ClaimReview` (schema.org) embarqué par Snopes pour le SEO. C'est la source la plus stable : elle ne change pas quand Snopes redessine son site, et elle est standardisée par schema.org.

Si JSON-LD est absent (cas des `/news/` qui sont des articles narratifs, pas des fact-checks), on retombe sur des sélecteurs CSS BeautifulSoup, en acceptant que le `verdict` puisse être `None`. Le `normalizer` filtrera ces rows.

Le champ `extraction_method` (`claim_review_jsonld` vs `css_fallback`) est conservé dans la sortie brute : utile pour debug et pour mesurer le taux de couverture JSON-LD.

## 4. Schéma unifié — pourquoi ce design

```json
{
  "id": "<uuid>",
  "source": "fakeddit | guardian | snopes | ...",
  "title": "...",
  "content": "...",
  "image_url": "https://...",
  "label": "fake | real | null",
  "label_detail": "Mixture | Mostly True | satire | ...",
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

Points de design :

- **`label` nullable** : Guardian fournit des articles non labellisés. Plutôt que de forger un label arbitraire à l'extraction, on laisse `null` et on s'appuie sur `metadata.source_credibility = "high"` pour signaler "présomption de real" au modèle.
- **`label_detail` libre** : préserve les nuances Snopes (`Mixture`, `Originated as Satire`...) qui sont l'information la plus précieuse de la source. Reduce to binary = perte d'information irréversible.
- **`metadata.label_method`** : un label "human_expert" (Snopes, FakeNewsNet) n'a pas le même poids qu'un label "community" (Fakeddit, basé sur le subreddit d'origine). Ce champ permet au modèle d'apprendre cette pondération.
- **`metadata.has_image`** : redondant avec `image_url != null`, mais explicite. Permet de filtrer rapidement en SQL sans parser l'URL.

## 5. Idempotence et reprise

- **Extraction** : chaque run produit un fichier timestampé distinct. Pas de modification de fichiers existants → idempotent par construction.
- **Transformation** : à concevoir (Étape 3) pour traiter `data/raw/<source>/*.jsonl` → `data/processed/<batch>.jsonl` avec déduplication sur la clé naturelle (`url` pour Guardian/Snopes, `id` Reddit pour Fakeddit).
- **Load** : à concevoir (Étape 4) avec `INSERT ... ON CONFLICT (source, natural_key) DO UPDATE` pour ne pas dupliquer en cas de rejeu.

## 6. Observabilité

- **Logs structurés** : `src/utils/logger.py` centralise le format (`timestamp | module | level | message`). Compatible avec un parsing CloudWatch / GCP Logging.
- **Métriques applicatives** (Étape 5) : `valid_rate`, `image_coverage`, `extract_duration`, `label_balance`. À exposer via Statsd ou Prometheus, ou simplement loggées en sortie de DAG.

## 7. Sécurité

- `.env` est en `.gitignore` et n'a jamais été commité.
- `.env.example` documente toutes les variables sans aucune valeur sensible.
- Les clés API ne sont jamais loggées (`logger.info("Querying GDELT: %r", query)` n'inclut pas la clé, qui est dans l'URL).
- Le `User-Agent` envoyé est identifiable (`checkit-pipeline/0.1 (+github_url)`), permettant aux administrateurs des sites scrapés de nous joindre en cas de souci.

## 8. Divergences assumées vs le spec d'origine

| Spec | Implémentation actuelle | Raison |
|---|---|---|
| `requirements.txt` | `pyproject.toml` + `uv.lock` | Stack moderne, builds reproductibles |
| `newsdata_extractor.py` | `guardian.py` | API gratuite illimitée vs NewsData payante |
| Naming `*_extractor.py` | `<source>.py` | Le dossier `src/extraction/` rend le suffixe redondant |
| `urllib.robotparser` (implicite) | `protego` | Bug stdlib sur les directives non standard |
| `praw` (Reddit pour Fakeddit images) | Direct TSV streaming | Le TSV multimodal Fakeddit contient déjà les URLs d'image, PRAW est superflu |

Toutes ces divergences sont des améliorations qualité ou des contournements de limites techniques, jamais des raccourcis fonctionnels. Le contrat de sortie (schéma unifié, JSON Lines, séparation extract/transform/load) reste strictement celui du spec.
