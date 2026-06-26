# Transformation

Deuxième étape de l'ETL : transformation du brut
(`data/raw/<source>/*.jsonl`) vers le dataset unifié et validé
(`data/processed/*.jsonl`), puis assemblage du dataset entraînable
(splits, statistiques, images).

## Chaîne de traitement

Pour chaque source, dans l'ordre :

```
clean (cleaner) -> normalize (normalizer) -> validate (validator)
```

puis, sur le dataset unifié :

```
build_dataset (dataset) -> acquire_all (images) -> load_splits (load)
```

Le cœur métier est séparé des IO : `transform_source` est pur et testé
directement ; `transform` ajoute les lectures/écritures de fichiers.

## Modules

### `schema.py`

Contrat de sortie unifié en **Pydantic v2** (`Article`,
`ArticleMetadata`).

- `Literal` sur `label`, `label_method`, `source_credibility` :
  vocabulaire fermé, pas de dérive silencieuse du dataset.
- `extra="forbid"` : rejette tout champ inconnu (attrape les typos).
- `label` et `label_detail` nullables : sources sans verdict ou verdicts
  nuancés.
- `id` généré ici (`default_factory=uuid4`), pas à l'extraction.
- `to_jsonl()` produit la ligne JSON canonique via `model_dump_json`.

### `cleaner.py`

Sanitation structurelle.

- `clean(df, source)` : suppression des clés nulles et des doublons sur
  la **clé naturelle** par source (`NATURAL_KEY` : `url` pour Snopes, `id`
  ailleurs) — garantit l'idempotence si des runs se chevauchent.
- `sanitize_text` : `html.unescape` -> retrait HTML (BeautifulSoup) ->
  normalisation Unicode NFKC -> collapse des espaces.
- `sanitize_text` est défini ici (logique « HTML/Unicode ») mais appliqué
  par le `normalizer`, seul à connaître le champ texte de chaque source.

### `normalizer.py`

Mappe chaque schéma source vers `Article` (une fonction par source,
dispatch via `_MAPPERS`).

Politique de labels :

- **Fakeddit** : `2_way_label` -> `real`/`fake` ; `6_way_label` ->
  `label_detail`. `credibility=medium`, `label_method=community`.
- **Guardian** : pas de verdict mais baseline crédible -> `label=real`,
  `label_method=human_expert`, `label_detail=None`.
- **Snopes / LIAR** : verdict conservé verbatim dans `label_detail` ;
  seuls les extrêmes non ambigus sont mappés vers le binaire. Les
  verdicts nuancés (`Mixture`, `half-true`) donnent `label=None`.

Principe directeur : ne jamais réduire une nuance à un binaire trompeur.

### `validator.py`

Garde-fou unique avant `data/processed/`.

- Vérifie : `title` et `content` non vides, `image_url` syntaxiquement
  valide (`urlparse`, http/https + netloc), conformité au modèle `Article`.
- Chaque rejet est loggé avec sa raison précise (observabilité).
- Retourne des objets `Article` typés : frontière entre les lignes
  DataFrame faiblement typées et le domaine fortement typé.

### `pipeline.py`

Orchestration de la chaîne.

- `transform_source(df, source, collected_at)` : cœur pur sans IO.
- `transform()` : lit le dernier brut par source (`latest_raw_file`),
  applique le cœur, agrège, écrit le fichier processed.
- `collected_at` : timestamp de run unique passé à toutes les sources (le
  brut n'a pas de date de collecte uniforme).

### `dataset.py`

Assemblage du dataset entraînable.

- `compute_stats` : résumé JSON (tailles, distributions label/source,
  couverture image, longueur de contenu, doublons).
- `assign_splits` : split **déterministe** (`seed=42`), **stratifié par
  `(source, label)`**, et **leakage-safe** — les records au contenu
  identique (clé SHA-256 du contenu) sont regroupés dans le même split,
  donc un texte ne peut être à la fois en train et en test.
- `render_data_card` / `refresh_data_card` : génèrent `docs/data_card.md`
  en relisant les fichiers de split (reflète l'état post-split et
  post-images).
- `build_dataset` : lit le dernier `checkit_*.jsonl`, écrit
  `train/validation/test.jsonl`, régénère la carte.

### `images.py`

Acquisition des images (rend le dataset réellement multimodal ; tourne
après `build_dataset`).

- Télécharge chaque `image_url` vers `data/images/<id>.<ext>` (chemin
  reconstructible depuis l'`id`, sans champ schéma supplémentaire).
- **Politique d'échec** : image non récupérable -> record gardé en texte
  seul, `metadata.has_image=False`, aucun texte perdu.
- Extension déduite du `Content-Type`, validation du corps comme image.
- **Injection de dépendance** : la fonction réseau (`fetch`) est passée en
  paramètre -> `acquire_images` testable sans HTTP. `_http_fetch` est
  l'adaptateur réel (`requests.Session` + rate limit 1 s).

### `load.py`

Chargement du dataset en **PostgreSQL** (le « L » de l'ETL ; tourne après
`acquire_images`, voir `docker-compose.yml`).

- `load_splits` : *full refresh* transactionnel de `checkit.articles`
  (`TRUNCATE` + `INSERT` des splits). Idempotent par construction —
  rejouer laisse la table identique au dataset — sans clé naturelle stable
  (les UUID sont régénérés à chaque run).
- `_to_row` : aplatit un record unifié (avec `metadata` imbriqué) en ligne
  de table ; fonction pure, testée sans base.
- Connexion via le rôle **à privilèges minimaux** `checkit_app`
  (propriétaire du seul schéma `checkit`, aucun droit sur la base Airflow).
- URL SQLAlchemy configurable (`CHECKIT_DB_URL`) -> bascule vers un Postgres
  managé (Neon) sans changement de code.
