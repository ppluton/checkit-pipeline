# Fiche dataset — CheckIt.AI (généré le 2026-06-26)

> Document généré automatiquement par `src/transformation/dataset.py`.
> Ne pas éditer à la main : relancer la génération met les chiffres à jour.

## Vue d'ensemble

- **Total de records** : 163
- **Langues** : en (163)
- **Groupes de contenu dupliqué** : 0

## Répartition par source

| Source | Records |
| --- | --- |
| fakeddit | 5 |
| guardian | 44 |
| liar | 100 |
| snopes | 14 |

## Répartition des labels

| Label | Records |
| --- | --- |
| fake | 32 |
| real | 68 |
| null | 63 |

Le label `null` n'est pas une absence d'information : il marque les verdicts
*nuancés* (Mixture, half-true…) pour lesquels on refuse de forcer un binaire
trompeur. La nuance d'origine est conservée dans `label_detail`.

## Couverture image (multimodal)

- Avec image : 63
- Sans image (texte seul) : 100

## Longueur de contenu (caractères)

- min 24 · médiane 124 · moyenne 1275.0 · max 16176

## Découpage train / validation / test

| Split | fakeddit | guardian | liar | snopes | Total |
| --- | --- | --- | --- | --- | --- |
| train | 3 | 31 | 70 | 10 | 114 |
| validation | 0 | 7 | 15 | 2 | 24 |
| test | 2 | 6 | 15 | 2 | 25 |

**Méthodologie.** Split déterministe (seed fixe), stratifié par
`(source × label)` pour que chaque partition garde le même mélange de sources
et de classes. Il est *leakage-safe* : les records au contenu identique sont
regroupés et placés dans le même split, donc un même texte ne peut jamais
apparaître à la fois en entraînement et en test.

## Limites connues

- **Multimodal partiel** : on stocke des adresses d'images, pas encore les
  images elles-mêmes (elles peuvent expirer).
- **Hétérogénéité des sources** : statements politiques (LIAR), posts Reddit
  (Fakeddit), claims (Snopes) et articles de presse (Guardian) ont des styles
  très différents. Le split stratifié atténue le risque que le modèle apprenne
  la *source* plutôt que la véracité, mais une évaluation out-of-distribution
  resterait plus exigeante.
- **Taille** : le volume actuel est modeste ; Fakeddit n'est pas encore passé
  à l'échelle.
