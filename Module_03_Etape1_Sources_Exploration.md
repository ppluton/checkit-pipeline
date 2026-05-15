# 📡 Rapport d'exploration des sources de données
## Projet : Pipeline ETL — Détection de Fake News Multimodales
**CheckIt.AI — Data Engineering**  
**Date :** 2026-05-15  
**Auteur :** Ingénieur Data Junior  
**Statut :** ✅ Étape 1 complétée

---

## 🎯 Objectif

Identifier des sources de données multimodales (texte + image) pertinentes pour entraîner un modèle de détection de fake news. Pour chaque source : type de données, format, langue, qualité des labels, et méthode d'extraction proposée.

---

## 📋 Critères d'évaluation des sources

Pour chaque source, on évalue :

| Critère | Description |
|---|---|
| **Modalités** | Texte seul / Image seule / Texte + Image |
| **Format** | CSV, JSON, API REST, HTML |
| **Langue** | EN, FR, multilingue |
| **Qualité des labels** | Humain expert / Communautaire / Automatique / Aucun |
| **Méthode d'extraction** | Téléchargement direct / API / Scraping |
| **Droits d'usage** | Licence libre / Recherche uniquement / Conditions à vérifier |

---

## 🗂️ Sources identifiées

---

### 1. FAKEDDIT

**Lien :** https://github.com/entitize/Fakeddit  
**Type :** Dataset public (Reddit)

| Champ | Valeur |
|---|---|
| **Modalités** | Texte + Image ✅ (titre du post + image associée) |
| **Format** | TSV + images téléchargeables |
| **Langue** | Anglais |
| **Volume** | ~1 million de publications Reddit |
| **Labels** | 2 classes (real/fake) et 6 classes (satire, misleading, false, etc.) |
| **Qualité des labels** | ⭐⭐⭐⭐ — Labels issus des subreddits vérifiés (r/worldnews vs r/TheOnion...) |
| **Droits d'usage** | Recherche académique |

**Méthode d'extraction :**
```
1. Télécharger les métadonnées TSV via GitHub
2. Utiliser l'API Reddit (PRAW) pour récupérer les images manquantes
3. Joindre images et métadonnées sur l'ID de post
```

**Champs disponibles :**
```
id | title (texte) | image_url | label_2way | label_6way | domain | score
```

**Pourquoi c'est pertinent :**  
Dataset nativement multimodal. Les labels 6-classes permettent de distinguer la satire de la vraie désinformation — nuance critique pour CheckIt.AI.

---

### 2. FakeNewsNet

**Lien :** https://github.com/KaiDMML/FakeNewsNet  
**Type :** Dataset public (fact-checking journalistique)

| Champ | Valeur |
|---|---|
| **Modalités** | Texte + URL d'image + métadonnées sociales |
| **Format** | JSON (structure arborescente par article) |
| **Langue** | Anglais |
| **Volume** | ~23 000 articles (PolitiFact + GossipCop) |
| **Labels** | Binaire : `real` / `fake` |
| **Qualité des labels** | ⭐⭐⭐⭐⭐ — Vérifiés par journalistes professionnels (PolitiFact) |
| **Droits d'usage** | Recherche académique |

**Méthode d'extraction :**
```
1. Cloner le repo GitHub
2. Exécuter le script de collecte fourni (news_scraper.py)
3. Les images sont accessibles via les URLs stockées dans le JSON
4. Télécharger les images séparément avec requests
```

**Structure JSON :**
```json
{
  "url": "https://...",
  "text": "Article content...",
  "images": ["https://image1.jpg"],
  "label": "fake",
  "source": "politifact"
}
```

**Pourquoi c'est pertinent :**  
Labels de la plus haute qualité disponible. PolitiFact est une référence mondiale en fact-checking — c'est la source la plus fiable pour entraîner un modèle robuste.

> ⚠️ **Point de vigilance :** Les URLs d'articles peuvent expirer. Il faut scraper les images dès la collecte initiale et les stocker localement.

---

### 3. NewsCLIPpings

**Lien :** https://github.com/g-luo/news_clippings  
**Type :** Dataset public (détection d'images hors contexte)

| Champ | Valeur |
|---|---|
| **Modalités** | Texte + Image ✅ (spécialement conçu pour le multimodal) |
| **Format** | JSON + images via VisualNews |
| **Langue** | Anglais |
| **Volume** | ~71 000 paires texte-image |
| **Labels** | Binaire : `pristine` (vrai) / `falsified` (faux contexte) |
| **Qualité des labels** | ⭐⭐⭐⭐ — Génération automatique contrôlée + validation humaine |
| **Droits d'usage** | Recherche académique |

**Méthode d'extraction :**
```
1. Télécharger les annotations JSON depuis GitHub
2. Télécharger VisualNews (dataset source des images)
3. Joindre les deux via l'identifiant d'article
```

**Ce qui rend ce dataset unique :**  
Il cible précisément le mécanisme "vraie image, faux contexte" — l'une des formes les plus trompeuses de fake news. Ex : photo d'une vraie inondation utilisée pour illustrer un événement fictif.

**Pourquoi c'est pertinent :**  
Cas d'usage directement aligné avec la mission CheckIt.AI. C'est le dataset le plus pertinent pour entraîner la composante *vision* du modèle.

---

### 4. NewsData.io (API temps réel)

**Lien :** https://newsdata.io  
**Type :** API REST commerciale (plan gratuit disponible)

| Champ | Valeur |
|---|---|
| **Modalités** | Texte + URL d'image ✅ |
| **Format** | JSON (API REST) |
| **Langue** | Multilingue (dont EN, FR) |
| **Volume** | ~200 requêtes/jour (plan gratuit) |
| **Labels** | ❌ Aucun label (actualités brutes) |
| **Qualité des labels** | N/A — source de données fraîches non labelisées |
| **Droits d'usage** | Plan gratuit pour usage non-commercial |

**Méthode d'extraction :**
```python
import requests

API_KEY = "your_api_key"
url = "https://newsdata.io/api/1/news"
params = {
    "apikey": API_KEY,
    "q": "fake news OR misinformation",
    "language": "en",
    "image": 1  # Uniquement les articles avec image
}
response = requests.get(url, params=params)
articles = response.json()["results"]
```

**Réponse JSON :**
```json
{
  "title": "...",
  "description": "...",
  "content": "...",
  "image_url": "https://...",
  "pubDate": "2026-05-15",
  "source_id": "bbc"
}
```

**Pourquoi c'est pertinent :**  
Alimente le pipeline avec des données fraîches en temps réel. Utilisable pour enrichir le dataset d'entraînement ou pour le scoring en production. À combiner avec un système de labellisation automatique.

> ⚠️ **Limite :** Pas de labels. Cette source doit être combinée avec un fact-checker externe ou une heuristique de labellisation.

---

### 5. LIAR Dataset

**Lien :** https://huggingface.co/datasets/liar  
**Type :** Dataset public (déclarations politiques)

| Champ | Valeur |
|---|---|
| **Modalités** | Texte uniquement ⚠️ |
| **Format** | TSV (disponible sur HuggingFace) |
| **Langue** | Anglais |
| **Volume** | 12 836 déclarations |
| **Labels** | 6 niveaux : `pants-fire`, `false`, `barely-true`, `half-true`, `mostly-true`, `true` |
| **Qualité des labels** | ⭐⭐⭐⭐⭐ — Vérification humaine experte (PolitiFact) |
| **Droits d'usage** | Libre pour la recherche |

**Méthode d'extraction :**
```python
from datasets import load_dataset
dataset = load_dataset("liar")
```

**Champs disponibles :**
```
statement | label | subject | speaker | job_title | state | party | context
```

**Pourquoi c'est pertinent :**  
Malgré l'absence d'images, les labels sont exceptionnellement précis et granulaires. Idéal pour la composante NLP du modèle. À utiliser en complément des sources multimodales pour équilibrer l'entraînement.

---

### 6. Snopes.com (flux RSS)

**Lien :** https://www.snopes.com/fact-check/  
**Flux RSS :** https://www.snopes.com/feed/  
**Type :** Site de fact-checking (scraping / RSS)

| Champ | Valeur |
|---|---|
| **Modalités** | Texte + Image ✅ |
| **Format** | RSS (XML) + HTML |
| **Langue** | Anglais |
| **Volume** | ~20 nouveaux articles/semaine |
| **Labels** | Verdict explicite : `True`, `False`, `Mixture`, `Unproven`, `Outdated`... |
| **Qualité des labels** | ⭐⭐⭐⭐⭐ — Journalistes experts, méthodologie transparente |
| **Droits d'usage** | ⚠️ Scraping : vérifier robots.txt avant d'automatiser |

**Méthode d'extraction :**
```python
import feedparser
from bs4 import BeautifulSoup
import requests

feed = feedparser.parse("https://www.snopes.com/feed/")
for entry in feed.entries:
    title = entry.title
    url = entry.link
    # Scraper la page pour récupérer le verdict et l'image
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "html.parser")
    verdict = soup.find("div", class_="rating-label")
    image = soup.find("meta", property="og:image")
```

**Champs récupérables :**
```
title | url | verdict | image_url | date | claim | explanation
```

**Pourquoi c'est pertinent :**  
Source en flux continu — permet d'enrichir le dataset automatiquement. Labels humains de haute qualité avec nuances (pas seulement vrai/faux). Idéal pour alimenter le pipeline Airflow en production.

> ⚠️ **Point de vigilance :** Vérifier `robots.txt` et respecter un délai entre les requêtes (`time.sleep(1)`). Préférer le flux RSS à du scraping massif.

---

## 📊 Tableau comparatif

| Source | Modalités | Labels | Qualité | Volume | Méthode | Usage recommandé |
|---|---|---|---|---|---|---|
| **FAKEDDIT** | Texte + Image | Oui (6 classes) | ⭐⭐⭐⭐ | ~1M | GitHub + Reddit API | Entraînement principal |
| **FakeNewsNet** | Texte + Image URLs | Oui (binaire) | ⭐⭐⭐⭐⭐ | ~23K | GitHub + scraping | Entraînement (haute qualité) |
| **NewsCLIPpings** | Texte + Image | Oui (binaire) | ⭐⭐⭐⭐ | ~71K | GitHub + VisualNews | Composante vision |
| **NewsData.io** | Texte + Image | Non | N/A | ~200/j | API REST | Données fraîches (prod) |
| **LIAR Dataset** | Texte seul | Oui (6 niveaux) | ⭐⭐⭐⭐⭐ | ~12K | HuggingFace | NLP / labels fins |
| **Snopes** | Texte + Image | Oui (nuancés) | ⭐⭐⭐⭐⭐ | ~20/sem | RSS + scraping | Enrichissement continu |

---

## 🏗️ Format de sortie recommandé

Toutes les sources seront normalisées dans le schéma suivant :

```json
{
  "id": "uuid-v4",
  "source": "fakeddit | fakenenewsnet | snopes | ...",
  "title": "Article or post title",
  "content": "Full text content",
  "image_url": "https://...",
  "label": "fake | real",
  "label_detail": "false | misleading | satire | ...",
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

**Format de stockage :** JSON Lines (`.jsonl`) — un objet JSON par ligne. Compatible avec les pipelines Airflow et les loaders HuggingFace.

---

## ⚠️ Points de vigilance généraux

1. **Ne pas confondre opinion controversée et désinformation** — Snopes distingue bien `Mixture` d'un pur `False`. Préserver cette nuance dans les labels.
2. **Vérifier l'association texte-image** — S'assurer que chaque entrée a bien les deux champs non-nuls avant d'insérer en base.
3. **Champs secondaires utiles** — Conserver `domain`, `source_credibility`, `pubDate` : ils peuvent être des features pour le modèle.
4. **Équilibre des classes** — FAKEDDIT et FakeNewsNet sont relativement équilibrés, mais vérifier avant entraînement.
5. **Droits d'usage** — LIAR et FakeNewsNet : recherche uniquement. NewsData.io : vérifier les CGU du plan gratuit.

---

## 🔗 Prochaine étape

→ **Étape 2** : Scripts d'extraction Python pour FAKEDDIT (données statiques) et NewsData.io (API temps réel)

---

*CheckIt.AI · Module 03 · Étape 1/5 · 2026-05-15*
