# De la collecte au dataset multimodal, expliqué simplement

> Note de projet — 29 mai 2026
>
> Ce document raconte, de manière accessible, ce qui a été construit après la
> collecte : la *transformation* des données brutes, leur *découpage* en jeux
> d'entraînement, et l'*acquisition des images* — et **pourquoi** chaque choix
> a été fait. Il s'adresse autant à un relecteur technique qu'à quelqu'un qui
> découvre le projet. Le code dit *comment* ; ce texte dit *pourquoi* et
> *pour quoi faire*.

## 1. Le problème qu'on cherche à résoudre

Le projet CheckIt.AI collecte des articles depuis quatre sources très
différentes pour entraîner un modèle de détection de fausses informations :

- **Fakeddit** : des posts Reddit (titre + image) avec un label vrai/faux,
- **The Guardian** : des articles de presse fiables (texte + photo),
- **Snopes** : des vérifications de faits par des experts humains,
- **LIAR** : des déclarations politiques annotées (texte seul).

Le souci : **chaque source parle sa propre langue**. Fakeddit appelle le label
`2_way_label` et range les images dans `image_url` ; Snopes parle de `verdict`
(« True », « Mixture »…) ; LIAR utilise un entier de 0 à 5. Un modèle de
machine learning, lui, a besoin de recevoir des données **toutes au même
format**, sinon il ne sait pas quoi en faire.

L'étape 3 est donc une étape de **traduction** : prendre ces quatre dialectes
et tout réécrire dans une seule langue commune — notre schéma unifié `Article`.

> **Analogie.** Imaginez quatre personnes qui remplissent le même formulaire,
> mais chacune dans sa propre écriture, avec ses abréviations et parfois des
> taches d'encre. La transformation, c'est le travail de recopier les quatre
> formulaires au propre, dans un format identique, en jetant ceux qui sont
> illisibles.

## 2. Les trois étages de la transformation

On a découpé ce travail en trois étapes successives, chacune avec **une seule
responsabilité**. C'est volontaire : si quelque chose casse, on sait
immédiatement lequel des trois est en cause.

```
data/raw/<source>/*.jsonl                         data/processed/*.jsonl
        │                                                   ▲
        ▼                                                   │
   [ cleaner ]  ──►  [ normalizer ]  ──►  [ validator ] ────┘
   nettoie          traduit              vérifie
```

### 2.1 Le `cleaner` — le ménage

Son rôle est purement « structurel » : il ne comprend pas le sens des données,
il fait le ménage.

- **Supprimer les doublons.** Quand on relance une collecte, on peut récupérer
  deux fois le même article. Le cleaner les repère grâce à une *clé naturelle*
  propre à chaque source (l'URL pour Snopes, l'identifiant du post pour
  Fakeddit) et n'en garde qu'un.
- **Nettoyer le texte.** Il fournit l'outil `sanitize_text`, qui transforme un
  texte « sale » en texte propre. Exemple concret :

  ```
  Avant : "<p>Some <b>HTML</b> body</p>"
  Après : "Some HTML body"
  ```

  Il enlève les balises HTML, décode les caractères encodés (`&amp;` redevient
  `&`), normalise les accents (le « é » de Mbappé s'affiche correctement) et
  écrase les espaces en trop.

> **Subtilité importante.** Le cleaner *possède* l'outil de nettoyage de texte,
> mais ce n'est pas lui qui décide *quelle* colonne nettoyer — parce que le
> texte ne se trouve pas au même endroit selon la source. C'est l'étage
> suivant (le normalizer), qui sait où vit le texte, qui applique l'outil. On
> évite ainsi de dupliquer la connaissance des formats dans deux fichiers.

### 2.2 Le `normalizer` — le traducteur

C'est le cœur de l'étape. Il prend les données nettoyées et les réécrit dans
le format unique. Une fonction de traduction par source. Quelques exemples :

| Source | Donnée brute | Donnée traduite |
|---|---|---|
| Fakeddit | `2_way_label = "1"` | `label = "fake"` |
| Fakeddit | `6_way_label = "1"` | `label_detail = "satire"` |
| Snopes | `verdict = "False"` | `label = "fake"`, `label_detail = "False"` |
| LIAR | `label_text = "pants-fire"` | `label = "fake"`, `label_detail = "pants-fire"` |

### 2.3 Le `validator` — le contrôle qualité

Dernier rempart avant que la donnée ne soit écrite. Il reconstruit chaque
article selon un modèle strict (Pydantic) et **rejette** tout ce qui ne respecte
pas les règles : titre ou contenu vide, adresse d'image invalide, label en
dehors du vocabulaire autorisé. Surtout, **chaque rejet est tracé dans les
logs** : on ne perd jamais une donnée en silence, on sait toujours pourquoi
elle a été écartée. C'est une exigence d'ingénierie data : une erreur doit être
*observable*, pas cachée.

## 3. La règle d'or : préserver les nuances

Un piège classique en détection de fake news serait de tout réduire à
« vrai » ou « faux ». Mais la réalité est plus subtile. Snopes utilise des
verdicts comme *« Mixture »* (partiellement vrai), *« Originated as Satire »*
(c'était de l'humour), *« Unproven »* (impossible à vérifier). LIAR distingue
*« half-true »* de *« mostly-true »*.

**Notre choix : ne jamais détruire cette information.** Concrètement :

- Le verdict d'origine est **toujours** conservé tel quel dans le champ
  `label_detail`.
- Le label binaire (`fake`/`real`) n'est attribué **que pour les cas nets**.
  Pour tout ce qui est ambigu (« Mixture », « half-true »…), le label binaire
  reste **vide** (`null`).

Exemple réel tiré du dataset :

```
title       : "Was Florida woman arrested after riding shopping cart down highway?"
label       : null              ← on n'a pas forcé un binaire trompeur
label_detail: "Originated as Satire"   ← la nuance est sauvegardée
```

Le modèle pourra ainsi apprendre des distinctions fines plus tard, plutôt que
de recevoir une vérité binaire appauvrie.

## 4. L'histoire la plus instructive : le piège du label Guardian

Voici le genre de bug qui ne provoque aucune erreur, ne fait planter aucun
test, mais qui **ruine silencieusement la qualité d'un jeu de données**. Il
mérite d'être raconté car il est très formateur.

### Le point de départ

The Guardian sert de source d'articles **fiables** : on lui attribue le label
`real`. Pour récupérer ces articles, la première version interrogeait l'API
avec la recherche suivante :

```
"misinformation OR disinformation OR fact-check OR fake news"
```

Cela semblait logique — le projet parle de désinformation, alors on cherche
des articles sur la désinformation.

### Le problème caché

En y regardant de plus près : cette recherche ne ramène pas des articles
*fiables sur des sujets variés*, elle ramène des articles **qui parlent de
désinformation**. Des textes bourrés des mots « hoax », « false claim »,
« fake news »… mais étiquetés `real`.

Que va apprendre un modèle entraîné là-dessus ? Il va voir que les textes
contenant le vocabulaire de la désinformation sont… `real`. C'est l'inverse de
ce qu'on veut lui enseigner. On appelle ça une **fuite de données** (*data
leakage*) : le modèle apprend une corrélation parasite (ici, le *sujet* de
l'article) au lieu de ce qu'on veut vraiment qu'il apprenne (le caractère vrai
ou faux de l'information).

> **Analogie.** C'est comme entraîner quelqu'un à reconnaître les faux billets
> en ne lui montrant que des manuels intitulés « Comment repérer un faux
> billet ». Il finira par associer le mot « faux » à… un document parfaitement
> authentique.

### La correction

On a supprimé complètement la recherche par mot-clé. À la place, Guardian
collecte désormais de **l'actualité générale neutre**, sur des rubriques riches
en texte et factuelles : `world`, `science`, `technology`, `business`,
`environment`. On a aussi ajouté un filtre pour ne garder que les **vrais
articles** (`type = article`), en excluant les directs sportifs (« liveblogs »),
mots croisés et galeries photo, dont le texte est inexploitable.

Résultat, vérifié sur une vraie collecte : 45 articles récupérés, 100 % de type
« article », répartis sur des rubriques variées, et **zéro** titre contenant du
vocabulaire de désinformation. Le label `real` redevient honnête.

## 5. Comment on a travaillé : les tests d'abord (TDD)

Tout le code de cette étape a été écrit en **TDD** (*Test-Driven Development*,
développement piloté par les tests). Le principe, contre-intuitif au premier
abord :

1. On écrit d'abord un **test** qui décrit le comportement attendu.
2. On le lance et on **vérifie qu'il échoue** (la fonctionnalité n'existe pas
   encore).
3. On écrit le **minimum de code** pour que le test passe.
4. On recommence pour le comportement suivant.

Pourquoi se compliquer la vie ? Parce qu'un test écrit *après* le code a un
défaut : il passe du premier coup, et on ne sait jamais s'il teste vraiment
quelque chose. Un test écrit *avant*, qu'on a vu échouer puis réussir, prouve
qu'il détecte réellement un problème. C'est une garantie, pas une formalité.

L'ensemble du travail décrit ici est couvert par **76 tests** qui tournent en
moins d'une seconde. Ils documentent le comportement attendu et permettront de
modifier le code plus tard sans crainte de tout casser.

## 6. Le découpage train / validation / test

Une fois les données unifiées, on ne peut pas les jeter telles quelles dans un
modèle. Il faut les **découper en trois paquets** :

- **train** (entraînement, 70 %) : ce que le modèle voit pour apprendre.
- **validation** (15 %) : pour régler les réglages sans tricher.
- **test** (15 %) : gardé sous scellés, pour mesurer la performance finale.

Deux exigences rendent ce découpage moins trivial qu'il n'y paraît.

**Il doit être équilibré (stratifié).** Si, par malchance, tous les articles
Snopes tombaient dans le test, le modèle n'en verrait jamais à l'entraînement.
On découpe donc *à l'intérieur de chaque groupe* `(source × label)` : chaque
paquet reçoit la même proportion de chaque source et de chaque label.

**Il doit être étanche (« leakage-safe »).** Si le même texte se retrouvait à la
fois en entraînement et en test, le modèle aurait déjà « vu les réponses » le
jour de l'examen — son score serait gonflé et mensonger. On regroupe donc les
records au contenu identique et on garantit qu'ils atterrissent **dans le même
paquet**.

> **Analogie.** C'est un examen : on révise sur les annales (train), on s'auto-
> évalue sur des exercices blancs (validation), et on passe l'épreuve finale sur
> des sujets qu'on n'a *jamais* vus (test). Laisser fuiter un sujet d'examen dans
> les annales, c'est fausser la note.

Enfin, le découpage est **déterministe** (graine aléatoire fixe) : relancer le
pipeline produit toujours la même répartition, sinon les scores ne seraient pas
comparables d'une exécution à l'autre.

Tout cela est résumé dans une **fiche dataset** (`docs/data_card.md`) générée
automatiquement à chaque exécution — elle ne se périme donc jamais.

## 7. Rendre le dataset vraiment multimodal : les images

Le projet promet du *multimodal* : texte **et** image. Or, jusqu'ici, on ne
stockait que des *adresses* d'images (`image_url`), pas les images elles-mêmes.
Problème : ces adresses peuvent disparaître du jour au lendemain. Une dernière
étape télécharge donc réellement chaque image et l'archive localement
(`data/images/<id>`), pour que le dataset ne dépende plus d'Internet.

Deux décisions de bon sens encadrent cette étape :

- **Que faire quand une image refuse de se télécharger** (lien mort, délai
  dépassé, fichier qui n'est pas une image) ? On **garde quand même le record**,
  en le marquant « sans image » (`has_image = false`). Le texte reste
  exploitable ; on ne jette rien.
- **L'étape est mise en dernier**, après le découpage, car c'est la plus lente
  (une requête réseau par record) et la plus susceptible d'échouer. Ainsi, un
  problème de téléchargement ne bloque jamais la production du dataset, et on
  peut relancer la seule acquisition d'images sans tout recommencer.

Résultat sur la collecte réelle : **58 images téléchargées** (Guardian et
Snopes), **5 records basculés en texte seul** (les liens Fakeddit de
l'échantillon de test étaient factices et renvoyaient une erreur 404), et 100
records LIAR ignorés (ils n'ont pas d'image par nature). La fiche dataset est
ensuite régénérée pour refléter le nombre **réel** d'images, et non le nombre
optimiste de records qui *annonçaient* une image.

## 8. Où on en est — état du dataset au 29 mai 2026

Le pipeline tourne de bout en bout :
`extraction → transformation → découpage → acquisition des images`.

| Source | Lignes brutes | Lignes valides | Commentaire |
|---|---|---|---|
| Fakeddit | 5 | 5 | échantillon de test (images factices) |
| Guardian | 45 | 45 | actualité neutre, label `real`, images téléchargées |
| Snopes | 20 | 13 | 7 articles narratifs sans verdict, écartés |
| LIAR | 100 | 100 | déclarations politiques (texte seul) |
| **Total** | | **163** | |

- **Labels** : `real` = 66, `fake` = 35, `null` (nuancé) = 62.
- **Découpage** : 114 train / 24 validation / 25 test, stratifié, sans fuite.
- **Images** : 58 réellement téléchargées, 105 records en texte seul.

Les 7 articles Snopes écartés ne sont pas un bug : ce sont des articles
narratifs (rubrique « news ») sans verdict formel. Les écarter est voulu.

## 9. Ce qui reste au backlog : Fakeddit à l'échelle

Un seul grand chantier reste ouvert, et il est conservé en backlog **par choix
assumé** : le passage de **Fakeddit à l'échelle**.

**De quoi s'agit-il ?** Fakeddit est censé être la source d'entraînement
*principale* du projet : près d'un million de posts Reddit nativement
multimodaux (texte + image) avec des labels fins. C'est elle qui doit donner au
modèle le volume nécessaire pour apprendre.

**Pourquoi seulement 5 lignes aujourd'hui ?** Les 5 records Fakeddit actuels
sont un **échantillon factice** servant à valider le pipeline (d'où les liens
d'images en erreur 404). Le code sait déjà lire le vrai fichier *en flux*
(`chunksize`), justement pour ne pas saturer la mémoire avec un million de
lignes — cette partie est prête.

**Pourquoi ce n'est pas encore fait ?** Le blocage n'est pas du code, c'est une
**dépendance de données** : il faut d'abord récupérer le vrai fichier TSV de
Fakeddit (plusieurs gigaoctets), le rendre accessible au pipeline via la
variable `FAKEDDIT_TSV_PATH`, puis lancer une collecte sur un volume réel. C'est
une opération lourde (téléchargement, espace disque, temps de traitement et
d'acquisition d'images à grande échelle) qui mérite d'être planifiée à part
plutôt que bâclée.

**Pourquoi ce n'est pas bloquant.** Tout le reste du pipeline — normalisation,
découpage stratifié, acquisition d'images — est **agnostique au volume**. Le
jour où le vrai Fakeddit est branché, ces étapes le traiteront sans aucune
modification. La fondation est prête ; il ne manque que le carburant.

Les deux sources encore non démarrées (FakeNewsNet, NewsCLIPpings) restent par
ailleurs dans le backlog d'exploration, comme prévu au cadrage initial.
