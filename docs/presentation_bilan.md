# CheckIt.AI — Présentation de bilan

> Support de soutenance — pipeline d'extraction, transformation et
> orchestration de données multimodales pour entraîner un détecteur de
> fake news.
>
> Mission : *Concevoir une stratégie d'extraction de données multimodales
> pour entraîner un détecteur de fake news.*

---

## 1. Le besoin de l'entreprise

CheckIt.AI veut entraîner un modèle capable de détecter les fausses
informations **multimodales** : un contenu associe un *texte* (titre, article,
déclaration) et une *image*. Un modèle ne s'entraîne pas sur le web brut : il
lui faut un **jeu de données propre, étiqueté, équilibré et reproductible**.

Le besoin se traduit en trois exigences concrètes :

1. **Couvrir plusieurs sources hétérogènes** pour obtenir à la fois du contenu
   fiable et du contenu douteux, étiquetés.
2. **Tout ramener à un format unique** exploitable par l'entraînement.
3. **Rendre le processus rejouable et observable** (orchestration, qualité,
   monitoring), parce qu'un dataset se reconstruit régulièrement.

Ce projet répond aux trois.

---

## 2. La stratégie d'extraction multimodale

Quatre sources complémentaires ont été retenues après exploration (voir le
*rapport d'exploration*, `docs/rapport_sources.md`) :

| Source | Modalités | Rôle dans le dataset | Méthode |
|---|---|---|---|
| **Fakeddit** | Texte + Image | Source d'entraînement principale, labels fins | TSV en flux |
| **The Guardian** | Texte + Image | Baseline « real » haute crédibilité | API REST |
| **Snopes** | Texte + Image | Vérifications expertes, verdicts nuancés | RSS + ClaimReview + scraping |
| **LIAR** | Texte seul | Source NLP auxiliaire, labels fins PolitiFact | Parquet HuggingFace |

**Principe directeur :** chaque source est extraite *telle quelle* dans
`data/raw/<source>/` (filtrée, jamais interprétée). L'interprétation est
repoussée à la transformation. C'est ce qui permet de rejouer une étape sans
recommencer tout le pipeline.

---

## 3. L'architecture ETL de bout en bout

```mermaid
flowchart LR
    G["The Guardian<br/>API REST"] --> RAW
    F["Fakeddit<br/>TSV en flux"] --> RAW
    S["Snopes<br/>RSS + scraping"] --> RAW
    L["LIAR<br/>Parquet HF"] --> RAW

    RAW[("data/raw/&lt;source&gt;/*.jsonl")] --> C

    subgraph T[Transformation]
      direction LR
      C["cleaner<br/>nettoyage"] --> N["normalizer<br/>traduction"] --> V["validator<br/>contrôle qualité"]
    end

    V --> U[("data/processed/<br/>checkit_*.jsonl")]
    U --> D["build_dataset<br/>split + stats + fiche"]
    D --> SP[("train / validation / test")]
    D --> CARD[("docs/data_card.md")]
    SP --> IMG["acquire_images<br/>téléchargement"]
    IMG --> STORE[("data/images/&lt;id&gt;")]
```

Le tout est orchestré par **Apache Airflow** (`dags/checkit_pipeline_dag.py`) :

```
[extract_guardian]
[extract_fakeddit]  ─►  [transform] ─► [build_dataset] ─► [acquire_images]
[extract_snopes]
[extract_liar]
```

- Les 4 extractions tournent **en parallèle** (aucun état partagé).
- `acquire_images` est volontairement **en dernier** : c'est l'étape la plus
  lente et la plus faillible ; un échec réseau n'y bloque jamais la production
  du dataset.

---

## 4. Le schéma de données unifié

Toute source converge vers un modèle unique, validé par **Pydantic v2**
(`src/transformation/schema.py`). Vocabulaire fermé sur les labels,
champs inconnus interdits.

```mermaid
classDiagram
    class Article {
        +UUID id
        +string source
        +string title
        +string content
        +string image_url
        +string label
        +string label_detail
        +string language
        +string domain
        +datetime collected_at
        +ArticleMetadata metadata
    }
    class ArticleMetadata {
        +string source_credibility
        +bool has_image
        +string label_method
    }
    Article "1" --> "1" ArticleMetadata : metadata
    note for Article "label vaut fake, real ou null ; label_detail garde le verdict brut (Mixture, half-true, satire)"
```

Champs nullables : `image_url`, `label`, `label_detail`, `domain`.
Vocabulaires fermés : `label` (fake/real), `source_credibility`
(high/medium/low), `label_method` (human_expert/community/automated).

| Champ | Type | Rôle |
|---|---|---|
| `id` | UUID v4 | identifiant unique, sert aussi de nom de fichier image |
| `source` | str | provenance (`fakeddit`, `guardian`, `snopes`, `liar`) |
| `title` / `content` | str | texte, nettoyé (HTML, Unicode, espaces) |
| `image_url` | str / null | adresse de l'image (null = texte seul) |
| `label` | `fake` / `real` / null | label binaire, **uniquement pour les cas nets** |
| `label_detail` | str / null | verdict d'origine conservé (nuance préservée) |
| `metadata.source_credibility` | high / medium / low | crédibilité de la source |
| `metadata.has_image` | bool | image réellement disponible (corrigé après acquisition) |
| `metadata.label_method` | human_expert / community / automated | mode d'étiquetage |

---

## 5. Trois décisions techniques qui font la qualité du dataset

**a. Préserver les nuances de labels.** Snopes et LIAR distinguent *Mixture*,
*half-true*, *Originated as Satire*… Réduire ça à `fake`/`real` détruirait de
l'information. Choix : le verdict d'origine est **toujours** conservé dans
`label_detail`, et le label binaire reste `null` pour les cas ambigus.

**b. Éliminer une fuite de label silencieuse (Guardian).** La requête initiale
cherchait des articles *sur* la désinformation, étiquetés `real` — un modèle y
aurait appris le vocabulaire du sujet, pas la véracité. Corrigé : actualité
neutre sur des rubriques factuelles, filtrée aux vrais articles. Le label `real`
redevient honnête.

**c. Un découpage train/val/test étanche.** Split 70/15/15 **déterministe**,
stratifié par `(source × label)`, et *leakage-safe* : les contenus identiques
sont forcés dans le même paquet, donc aucun texte ne fuit du train vers le test.

> Détail pédagogique de ces points : `docs/etape3_transformation.md`.

---

## 6. Qualité et reproductibilité

- **Tests** : 76 tests (`uv run pytest`), TDD systématique sur toute la logique
  métier (nettoyage, mapping, validation, split, acquisition).
- **Lint / format** : `ruff` (zéro avertissement).
- **Reproductibilité** : dépendances figées par `uv.lock` ; split déterministe
  (graine fixe) ; extractions horodatées et idempotentes.
- **Fiche dataset** générée automatiquement (`docs/data_card.md`), donc jamais
  périmée.

---

## 7. Correspondance avec les livrables attendus

| Livrable attendu | Réalisation | État |
|---|---|---|
| Rapport d'exploration de données | `docs/rapport_sources.md` | Fait |
| Scripts d'extraction automatisée | `src/extraction/{fakeddit,guardian,snopes,liar}.py` | Fait |
| Pipeline de transformation reproductible | `src/transformation/{cleaner,normalizer,validator,pipeline,dataset,images}.py` | Fait |
| Schéma de données finalisé (Mermaid) | Section 4 ci-dessus + `src/transformation/schema.py` | Fait |
| Flux ETL (Airflow) | `dags/checkit_pipeline_dag.py` | Fait |
| Tableau de bord KPI de l'ETL | `src/monitoring/` + `docs/etl_dashboard.png` + `docs/etl_kpi_report.md` | Fait |
| Plan de monitoring | `docs/monitoring.md` | Fait |

---

## 8. Plan de démonstration (session de bilan)

Objectif : montrer en direct que le pipeline extrait, transforme et orchestre
des données multimodales prêtes à entraîner un détecteur de fake news.

**Étape 0 — Le projet est sain (30 s)**
```bash
uv run pytest -q        # 76 tests verts
uv run ruff check .     # lint propre
```

**Étape 1 — Extraction en direct depuis une vraie source (1 min)**
```bash
uv run python -m src.extraction.guardian
# montrer data/raw/guardian/guardian_*.jsonl fraîchement créé
```
Commentaire : actualité neutre, filtrée aux articles avec image — pas de fuite
de label.

**Étape 2 — Transformation vers le schéma unifié (1 min)**
```bash
uv run python -m src.transformation.pipeline
# 4 sources -> data/processed/checkit_*.jsonl (163 records)
```
Montrer une ligne Snopes : `label = null`, `label_detail = "Originated as
Satire"` — la nuance est préservée.

**Étape 3 — Découpage et fiche dataset (1 min)**
```bash
uv run python -m src.transformation.dataset
# train/validation/test.jsonl + docs/data_card.md régénérée
```
Ouvrir `docs/data_card.md` : distributions, découpage 114/24/25, méthodologie.

**Étape 4 — Multimodal : téléchargement réel des images (1 min)**
```bash
uv run python -m src.transformation.images
# 58 images téléchargées, 5 basculées en texte seul (liens morts)
ls data/images | head
```
Commentaire : le dataset ne dépend plus d'URLs qui expirent.

**Étape 5 — Tableau de bord KPI (1 min)**
```bash
uv run python -m src.monitoring.dashboard
# régénère docs/etl_dashboard.png + docs/etl_kpi_report.md
```
Ouvrir le dashboard : volumétrie brut/valides par source, taux de rejet,
couverture image réelle (36 %), découpage et fuites (0). Enchaîner sur le plan
de monitoring (`docs/monitoring.md`) : seuils d'alerte, dérive de schéma,
gestion des échecs et reprise.

**Étape 6 — Orchestration Airflow (2 min)**
```bash
export AIRFLOW_HOME=$(pwd)/.airflow
uv run airflow standalone
```
Montrer le DAG `checkit_pipeline` : graphe `extract ×4 → transform →
build_dataset → acquire_images → report_kpis`, déclenchement, logs,
parallélisme des extractions, relances automatiques.

---

## 9. Indicateurs clés à mettre en avant (KPI)

Mesurables dès aujourd'hui sur le dataset produit :

| KPI | Valeur actuelle | Lecture |
|---|---|---|
| Volume unifié | 163 records | sortie de la transformation |
| Taux de validation Snopes | 13/20 (65 %) | rejets attendus (articles sans verdict) |
| Couverture image réelle | 58 / 163 (36 %) | multimodal effectif après téléchargement |
| Équilibre des labels | real 66 / fake 35 / null 62 | nuance préservée |
| Étanchéité du split | 0 fuite inter-split | vérifié |
| Couverture de tests | 76 tests verts | qualité du code |

Ces indicateurs constituent la base du **tableau de bord KPI** à formaliser.

---

## 10. Limites assumées et backlog

- **Fakeddit à l'échelle** : l'échantillon actuel (5 lignes) est factice ; le
  pipeline sait déjà streamer le vrai fichier (~1 M lignes), reste à régler la
  dépendance de données (`FAKEDDIT_TSV_PATH`). Non bloquant : le reste du
  pipeline est agnostique au volume.
- **FakeNewsNet / NewsCLIPpings** : sources d'extension restées au backlog
  d'exploration.

L'ensemble des 7 livrables attendus est produit. Le seul chantier ouvert
(Fakeddit à l'échelle) est une dépendance de données, pas un manque de code :
la fondation (extraction, transformation, orchestration, KPI, monitoring,
qualité) est complète et testée.
