# Monitoring

Observabilité de l'ETL : indicateurs de santé du pipeline et restitution
sous trois formes — rapport Markdown, figure PNG reproductible, et
tableau de bord **interactif** Streamlit.

Les trois consomment la **même** source (`kpi.compute_kpis`), donc les
chiffres ne peuvent jamais diverger.

## Modules

### `kpi.py`

Calcul des indicateurs.

- Helpers purs, testables sans IO :
  - `rejection_rate(raw, valid)` : taux de rejet.
  - `per_source_rejection(...)` : brut / valides / rejetés / taux par
    source.
  - `leakage_count(splits)` : nombre de clés de contenu présentes dans
    plus d'un split (cible : 0).
- `compute_kpis()` : assemble tous les KPI depuis les artefacts disque
  (dernier brut par source, fichiers de split). Lecture depuis les splits
  (avec `has_image` corrigé) pour rester cohérent avec la data card ;
  fallback sur le batch unifié si les splits n'existent pas encore.
- `image_coverage_rate` : images réellement téléchargées / total.
- `render_report(kpis)` : produit `docs/etl_kpi_report.md`.

### `dashboard.py`

Tableau de bord visuel.

- `matplotlib.use("Agg")` appelé **avant** l'import de pyplot : backend
  non interactif, rendu PNG sans écran (compatible CI / Airflow).
- `build_figure` : quatre panneaux — volumétrie brut vs valides, balance
  des labels, couverture image, tailles de splits et nombre de fuites.
- Sortie statique reproductible : `docs/etl_dashboard.png`.
- `main()` calcule les KPI, écrit le PNG et le rapport Markdown.

### `streamlit_app.py`

Tableau de bord **interactif** (outil recommandé par la mission).

- `build_frames(kpis)` : fonction pure (testée) qui prépare les frames
  affichées, pour garder la couche de rendu mince.
- Vue interactive : métriques clés, filtre par source, graphes survolables
  et tables triables, plus un volet sur les nuances de labels
  (`label_detail`).
- Lisible par un public non technique : libellés explicites, indicateurs
  en haut, pas de jargon.

## Lancement

```bash
# Rapport Markdown + figure PNG (artefact reproductible)
uv run python -m src.monitoring.dashboard

# Tableau de bord interactif
uv run streamlit run src/monitoring/streamlit_app.py
```
