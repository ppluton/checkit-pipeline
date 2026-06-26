# Rapport KPI de l'ETL — CheckIt.AI

> Généré par `src/monitoring/kpi.py`. Relancer met les chiffres à jour.

## Volumétrie et taux de rejet par source

| Source | Brut | Valides | Rejetés | Taux de rejet |
| --- | --- | --- | --- | --- |
| fakeddit | 5 | 5 | 0 | 0% |
| guardian | 44 | 44 | 0 | 0% |
| snopes | 20 | 14 | 6 | 30% |
| liar | 100 | 100 | 0 | 0% |

## Dataset unifié

- Total : **163** records
- Labels : fake 32, real 68, null 63
- Couverture image réelle : **39%** (63/163)

## Découpage et intégrité

- Tailles : train 114 · validation 24 · test 25
- Fuites de contenu inter-split : **0** (cible : 0)
