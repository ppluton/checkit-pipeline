# Rapport KPI de l'ETL — CheckIt.AI

> Généré par `src/monitoring/kpi.py`. Relancer met les chiffres à jour.

## Volumétrie et taux de rejet par source

| Source | Brut | Valides | Rejetés | Taux de rejet |
| --- | --- | --- | --- | --- |
| fakeddit | 5 | 5 | 0 | 0% |
| guardian | 45 | 45 | 0 | 0% |
| snopes | 20 | 13 | 7 | 35% |
| liar | 100 | 100 | 0 | 0% |

## Dataset unifié

- Total : **163** records
- Labels : fake 35, real 66, null 62
- Couverture image réelle : **36%** (58/163)

## Découpage et intégrité

- Tailles : train 114 · validation 24 · test 25
- Fuites de contenu inter-split : **0** (cible : 0)
