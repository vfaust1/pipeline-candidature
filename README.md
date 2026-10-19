# Pipeline de candidature

Outil personnel qui t'aide à préparer tes candidatures de stage de fin d'études :

1. **Trier** une annonce selon tes critères (retenue, à vérifier, écartée, veille alternance).
2. **Chercher** des informations sur l'entreprise (avec un contrôle pour être sûr que c'est la bonne).
3. **Rédiger** une lettre de motivation à partir de ton modèle.
4. **Conseiller** des modifications précises de ton CV, sans jamais inventer.

Un script Python (`main.py`) orchestre les étapes. Les modèles d'IA (API Anthropic) ne servent qu'à lire du texte et à rédiger ; les décisions de tri sont prises par des règles Python écrites à partir de `criteres.md`.

## Pourquoi ce projet

Projet personnel d'un étudiant en 3e année de BUT Informatique, pour préparer ses candidatures de stage de fin d'études (16 semaines, début mars 2027, métropole lilloise) et pratiquer Python, les API de modèles de langage et l'orchestration d'étapes. Ses choix de conception :

- **Un script orchestre, pas un « agent chef »** : l'ordre des étapes, le parallélisme et le budget sont décidés par du code.
- **Chaque étape ne reçoit que le strict nécessaire** : jamais de pages web brutes, seulement des fiches de faits et des résumés, pour limiter les tokens.
- **Le modèle lit, le code décide** : l'IA extrait des faits d'une annonce, des règles Python (alimentées par `criteres.md`) rendent le verdict. Le même verdict à chaque fois, sans coût, avec les cas flous commentés dans le code.
- **Deux modèles** : un modèle léger pour trier, extraire et résumer ; un modèle plus puissant pour la lettre.
- **La confiance se vérifie** : contrôle d'identité de l'entreprise, extraits exacts du CV exigés pour chaque conseil, détection des technologies absentes du CV, détection des liens morts, tests automatiques.
- **Un échec documenté** : la recherche web d'offres renvoyait surtout des pages périmées (mesuré sur plusieurs lancements). Le projet a donc ajouté le mode `lot`, plus fiable.

Ce projet a été conçu et écrit avec l'aide d'un assistant IA (Claude Code). Les critères, les règles de tri, les cas flous et les arbitrages entre coût et fiabilité sont ceux de l'auteur.

```
annonce (texte collé, ou dossier offres_a_trier/)
   │
   ▼
[1] Extraction (modèle léger) ──► fiche de faits (Offre)
   │
   ▼
règles Python + criteres.md ──► verdict : retenue / à vérifier / écartée / veille alternance
   │
   ├──► [2] Fiche entreprise (modèle léger + recherche web + contrôle d'identité)
   │            │
   │            ▼
   │      [3] Lettre de motivation (modèle puissant, phrases variables insérées dans le modèle)
   │
   └──► [4] Conseils CV (modèle léger, en parallèle de [2] puis [3])
```

---

## 1. Installation (une seule fois)

1. **Python 3.11 ou plus récent** : https://www.python.org/downloads/ (coche « Add python.exe to PATH »). Ouvre un nouveau terminal et vérifie : `python --version`.
2. **Bibliothèque Anthropic**, dans le dossier du projet :
   ```powershell
   python -m pip install -r requirements.txt
   ```
3. **Clé API Anthropic** en variable d'environnement. Ne la mets jamais dans un fichier du projet ni dans une conversation :
   ```powershell
   setx ANTHROPIC_API_KEY "ta-clé"
   ```
   Ferme puis rouvre le terminal. Vérification sans afficher la clé :
   ```powershell
   if ($env:ANTHROPIC_API_KEY) { "clé présente" } else { "clé absente" }
   ```
4. **Tes fichiers personnels.** Le dépôt contient des exemples fictifs ; copie-les puis remplace leur contenu par le tien (ces copies ne sont jamais versionnées, voir `.gitignore`) :
   ```powershell
   Copy-Item data/cv.example.md data/cv.md
   Copy-Item data/modele_lettre.example.md data/modele_lettre.md
   ```
   Garde les emplacements `{{ ... }}` du modèle de lettre tels quels : le programme les remplit. Relis aussi `criteres.md` et adapte-le à ton cas (voir la section 9).
5. **Test sans clé et sans coût** :
   ```powershell
   python -m unittest discover -s tests -v
   ```
   Tous les tests doivent afficher `ok`.

---

## 2. Les commandes

Toutes se lancent depuis le dossier du projet avec `python main.py <commande>`.

### Vue d'ensemble

| Commande | Ce qu'elle fait | Coût observé |
|---|---|---|
| `tri offre.txt` | Lit une annonce, applique tes règles, affiche le verdict | ≈ 0,001 € |
| `lot` | Trie toutes les annonces déposées dans `offres_a_trier/` et écrit un rapport | ≈ 0,001 € par annonce |
| `lettre offre.txt` | Verdict + fiche entreprise + lettre de motivation | ≈ 0,03 € |
| `cv offre.txt` | Verdict + conseils pour adapter ton CV | ≈ 0,003 € avec le modèle léger |
| `candidature offre.txt` | Verdict + fiche entreprise + lettre + conseils CV (lettre et CV en parallèle) | ≈ 0,035 € (2 recherches web) |
| `recherche` | Cherche des offres sur le web, les trie, écrit un rapport | 0,06 à 0,09 €, **résultats décevants** (voir plus bas) |

Les coûts viennent de tes lancements réels (le script les affiche à la fin de chaque commande). Ils dépendent de la longueur des annonces et des recherches web (environ 0,01 $ chacune).

### `tri` : juger une annonce

```powershell
python main.py tri offre.txt
```
- `offre.txt` : un fichier texte contenant l'annonce copiée. Le nom est libre.
- Affiche le verdict, les raisons d'élimination ou les points à vérifier, et crée un dossier de sortie avec `offre.json` (les faits extraits) et `verdict.json`.
- N'appelle que le modèle léger, sans recherche web.

### `lot` : trier plusieurs annonces d'un coup (le mode recommandé)

```powershell
python main.py lot
```
1. Dépose tes annonces en `.txt` dans le dossier `offres_a_trier/`. **Ce dossier n'existe pas dans le dépôt : il est créé automatiquement** la première fois que tu lances `python main.py lot` (la commande s'arrête alors après l'avoir créé et te rappelle quoi faire). Il est ignoré par Git. Une annonce par fichier, ou plusieurs dans le même fichier séparées par une ligne contenant seulement `===`. Copie tout le texte de l'annonce ; mets le lien de la page sur la première ligne si tu l'as.
2. Lance la commande : elle écrit `sorties/AAAA-MM-JJ/lot_HHMM/rapport.md`.
3. Une annonce déjà traitée n'est jamais repayée, même si elle reste dans le dossier. Une même offre republiée ou trouvée sur un autre site est repérée comme doublon.

Options :
- `--max-offres 20` : nombre maximum d'annonces analysées (30 par défaut).
- `--retraiter` : retrie aussi les annonces déjà traitées. Utile après avoir changé `criteres.md` ou un prompt.

Le rapport classe les offres en **Retenues**, **À vérifier**, **Veille alternance** et **Écartées** (avec la raison). Pour chaque offre à regarder, il donne la commande `candidature` prête à copier.

### `lettre`, `cv`, `candidature` : préparer une candidature

```powershell
python main.py candidature offre.txt
python main.py lettre offre.txt
python main.py cv offre.txt
```
`offre.txt` peut être un fichier à toi ou un fichier `offres/NN_entreprise.txt` produit par `lot` ou `recherche`.

- **`lettre`** : fiche entreprise, puis lettre. **`cv`** : conseils CV seuls. **`candidature`** : les deux, avec les conseils CV et la lettre calculés en parallèle.
- Si l'offre est « Écartée » ou en « Veille alternance », rien n'est rédigé. `--forcer` passe outre.
- Options de la lettre :
  - `--entreprise "texte"` : fournis toi-même un résumé de l'entreprise (pas de recherche web, donc moins cher).
  - `--entreprise-fichier fiche.txt` : même chose depuis un fichier.
  - `--sans-recherche` : pas de recherche web ; la lettre est écrite sans fiche entreprise.
- Sans `--entreprise`, le script cherche l'entreprise sur le web (jusqu'à 3 recherches). Voir « Contrôle d'identité » plus bas.

### `recherche` : chercher des offres sur le web (déconseillé pour l'instant)

```powershell
python main.py recherche
python main.py recherche --max-recherches 3 --max-offres 6
```
Quatre recherches en parallèle (stage web, stage Java, stage full stack, alternance), des contrôles automatiques (liens vivants, récence, doublons), puis le tri.

**Les mots recherchés.** Ils sont définis dans la liste `ANGLES` de `config.py`. Pour chaque angle, `requetes` contient les requêtes exactes envoyées au moteur de recherche (le modèle ne les modifie pas) ; sans `requetes`, le modèle choisit lui-même ses mots à partir de `consigne`. Chaque requête consomme une recherche (≈ 0,01 $), et le total est plafonné par `--max-recherches`. Le terminal et le rapport affichent les requêtes réellement envoyées. Les villes citées au modèle sont dans `VILLES_REQUETE` (`config.py`) ; celles utilisées pour le tri sont dans `villes_mel` (`criteres.md`, section 6). En pratique, le moteur de recherche web remonte surtout des pages d'offres périmées, et très peu d'offres actives : lors des essais, la plupart des liens étaient morts. Le mode `lot` donne de meilleurs résultats pour moins cher. La commande reste disponible.

---

## 3. Où trouver quoi

### Les résultats : `sorties/`

Ce dossier n'existe pas dans le dépôt : **il est créé automatiquement** à la première commande qui produit un résultat. Comme `offres_a_trier/` et `data/offres_vues.json`, il est ignoré par Git (voir la section 10).

```
sorties/
└── AAAA-MM-JJ/
    ├── 05_entreprise/             # une candidature (commandes tri, lettre, cv, candidature)
    │   ├── offre.json             # faits extraits de l'annonce
    │   ├── verdict.json           # verdict, raisons, points à vérifier, score
    │   ├── entreprise.md          # fiche entreprise + contrôle d'identité
    │   ├── lettre.md              # la lettre de motivation
    │   └── conseils_cv.md         # les conseils CV classés par priorité
    ├── lot_HHMM/                  # un lancement de « lot »
    │   ├── rapport.md             # le rapport trié
    │   └── offres/NN_entreprise.txt   # les annonces à regarder, prêtes pour « candidature »
    └── recherche_HHMM/            # un lancement de « recherche » (même structure)
```
Tu peux supprimer les anciens dossiers de `sorties/` sans risque.

### Les fichiers que tu modifies

| Fichier | À quoi il sert |
|---|---|
| `criteres.md` | Tes critères de recherche. Les sections 1 à 5 sont pour toi ; **la section 6 est lue par le script** (dates, durée, télétravail, villes, technologies, cas flous). |
| `data/cv.md` | Ton CV (**non versionné**, copie de `data/cv.example.md`). Les lettres et les conseils CV s'appuient uniquement sur lui. |
| `data/modele_lettre.md` | Ton modèle de lettre (**non versionné**, copie de `data/modele_lettre.example.md`). Les `{{ }}` sont remplis par le script ; le reste du texte n'est jamais modifié. |
| `data/cv.example.md`, `data/modele_lettre.example.md` | Exemples fictifs fournis avec le dépôt, à copier puis à remplacer (voir l'installation). |
| `offre.txt` | Un fichier de travail pour coller une annonce (nom libre). |
| `offres_a_trier/` | Le dossier où tu déposes les annonces pour la commande `lot`. |
| `prompts/*.md` | Les consignes données aux modèles (voir ci-dessous). |
| `config.py` | Les réglages techniques : modèles, limites de tokens, budgets. |

### Les fichiers que le programme gère seul

| Fichier | À quoi il sert |
|---|---|
| `data/offres_vues.json` | La mémoire des offres déjà traitées (par adresse web, par contenu et par signature entreprise/titre/ville). Supprime-le pour repartir de zéro. Non versionné. |
| `sorties/` | Les résultats (voir ci-dessus). Non versionnés. |
| `.gitignore` | Liste ce que Git ne versionne pas : CV, modèle de lettre, offres, résultats, historique, clés. |
| `LICENSE` | La licence MIT du projet. |

### Le code

| Fichier | À quoi il sert |
|---|---|
| `main.py` | Le point d'entrée : lit la commande, enchaîne les étapes, lance en parallèle ce qui peut l'être, affiche le coût. |
| `pipeline/llm.py` | Le seul fichier qui parle à l'API Anthropic. Gère les appels, les recherches web, un second essai si une réponse est coupée, et le compteur de tokens et de coût. |
| `pipeline/criteres.py` | Lit la section 6 de `criteres.md` et normalise les noms (villes, technologies, mois). |
| `pipeline/schemas.py` | La forme des données échangées entre les étapes (`Offre`, `Verdict`) et les schémas JSON demandés à l'API. |
| `pipeline/regles.py` | **Les règles de tri**, en Python pur (aucune IA) : lieu, télétravail, niveau, durée, dates, technologies. Tous les cas flous sont commentés `CAS FLOU`. |
| `pipeline/etape1_offres.py` | Étape 1, extraction : le modèle léger lit une annonce et remplit la fiche de faits. |
| `pipeline/etape1_lot.py` | Étape 1, mode lot : lit le dossier `offres_a_trier/`, découpe, dédoublonne, trie. |
| `pipeline/etape1_recherche.py` | Étape 1, mode recherche web : agents de recherche, contrôle des adresses et de la récence, tri. |
| `pipeline/liens.py` | Vérifie qu'un lien est vivant avant de payer l'analyse : erreur 404, message « offre expirée », date de fin de validité dépassée ou date de publication trop ancienne (dates `schema.org` lues dans la page, comme sur Wizbii). |
| `pipeline/vues.py` | La mémoire des offres vues et la détection de doublons approchants. |
| `pipeline/rapport.py` | Écrit `rapport.md`. |
| `pipeline/etape2_entreprise.py` | Étape 2 : fiche entreprise par recherche web, avec contrôle d'identité. |
| `pipeline/etape3_lettre.py` | Étape 3 : le modèle puissant écrit les phrases variables, Python les insère dans ton modèle et contrôle le résultat. |
| `pipeline/etape4_cv.py` | Étape 4 : conseils CV, avec vérification que chaque conseil s'appuie sur un extrait exact de ton CV. |
| `tests/` | Les tests automatiques (règles, recherche, entreprise, lettre). Aucun ne coûte quoi que ce soit. |
| `requirements.txt` | La liste des bibliothèques Python à installer. |

### Les prompts : `prompts/`

| Fichier | Rôle |
|---|---|
| `extraction.md` | Comment lire une annonce et remplir la fiche de faits (dates, durée, niveau, télétravail, entreprise...). |
| `lettre.md` | Les règles de rédaction de la lettre (ton, pas d'invention, un seul projet, noms de projets...). |
| `cv.md` | Les règles des conseils CV (jamais d'ajout de compétence, priorités calibrées...). |
| `entreprise.md` | Comment identifier la bonne entreprise et résumer ce qu'on en sait. |
| `recherche.md` | Les consignes de la recherche automatique d'offres. |

Si une lettre ou un conseil te déplaît de façon répétée, c'est souvent là qu'il faut ajouter une règle.

---

## 4. Comment le tri décide

Le modèle léger n'émet jamais de verdict : il extrait des faits (lieu, dates, durée, niveau, télétravail, technologies...). Les règles de `pipeline/regles.py`, alimentées par `criteres.md`, décident ensuite :

- **Écartée** : un critère éliminatoire n'est clairement pas respecté (lieu hors MEL, 4 jours de télétravail ou plus, durée trop courte, domaine hors développement, technologies hors de ta liste, début hors janvier–avril 2027...). La raison est toujours indiquée.
- **À vérifier** : information ambiguë (Bac+4/5, 3 jours de télétravail, ville proche de la MEL, Python/C#, technologies mobiles que tu ne maîtrises pas, télétravail « mentionné sans nombre de jours », date ouverte...).
- **Retenue** : tous les critères sont respectés. Une information absente (niveau, durée, date de début, télétravail) est acceptée, avec une note dans le rapport. Tu changes ce comportement dans la section 6 de `criteres.md` (`retenue` ou `a_verifier`).
- **Veille alternance** : offre d'alternance qui respecte les règles lieu, télétravail, domaine, technologies et date (rentrée 2027).

Le **score de préférence** classe les offres d'un même groupe (technologies de ton profil, produit propre, missions concrètes, équipe identifiable, début en mars 2027).

---

## 5. Contrôles de fiabilité

- **Pas d'invention dans la lettre** : le modèle ne voit que ton CV, l'offre résumée et la fiche entreprise. Un contrôle Python prévient si une technologie absente de ton CV apparaît, si la lettre est trop longue ou si une phrase dépasse sa limite.
- **Informations manquantes** : date, entreprise, référence et civilité viennent du code, jamais du modèle. Si une info manque, la lettre contient `[… — à compléter]`.
- **Contrôle d'identité de l'entreprise** : la recherche reçoit une carte d'identité (nom, ville, site web, secteur, contexte de l'offre). Python vérifie ensuite que le site de l'offre apparaît dans les pages consultées et qu'il y a assez d'éléments en cas d'homonymes. Si le contrôle échoue, la fiche n'est pas transmise à la lettre. Relis toujours `entreprise.md`.
- **Conseils CV** : chaque conseil cite un extrait exact de ton CV ; sinon il est marqué « ⚠️ à vérifier ».
- **Liens** : en mode recherche, un lien que la recherche n'a pas réellement renvoyé est ignoré, et les liens morts sont éliminés avant l'analyse. Les sites qui bloquent les programmes ne sont pas vérifiables : ouvre le lien toi-même.

---

## 6. Coûts et réglages

- Les prix par million de tokens sont dans `config.py` (`PRIX`). Modèle léger : `claude-haiku-5-5` (tri, extraction, fiche entreprise, conseils CV). Modèle puissant : `claude-sonnet-5-5` (lettre).
- Les conseils CV peuvent passer au modèle puissant en changeant `MODELE_CONSEILS_CV` dans `config.py` (environ 0,03 € de plus par candidature, conseils plus fiables).
- Le coût estimé s'affiche à la fin de chaque commande.
- `MAX_RECHERCHES_ENTREPRISE` (3) plafonne les recherches web de la fiche entreprise ; `--sans-recherche` ou `--entreprise` les évitent.
- Si une réponse est coupée (« max_tokens atteint »), le script réessaie une fois avec une limite doublée ; sinon augmente la limite concernée dans `config.py`.

---

## 7. Problèmes fréquents

| Message | Cause et solution |
|---|---|
| `python` n'est pas reconnu | Rouvre le terminal ou l'application. Sinon utilise `py`, ou le chemin complet de `python.exe`. |
| Erreur d'authentification / clé absente | La variable `ANTHROPIC_API_KEY` n'est pas définie dans ce terminal. Refais la section 1.3 et rouvre le terminal. |
| `ModuleNotFoundError: anthropic` | Lance `python -m pip install -r requirements.txt`. |
| `Réponse coupée (max_tokens atteint)` | La réponse a dépassé sa limite de longueur (réflexion du modèle comprise). Augmente la limite dans `config.py`. |
| `Annonce trop longue` | Garde seulement le texte de l'offre (sans menus ni offres similaires) ou augmente `MAX_CARACTERES_OFFRE`. |
| `offres_vues.json est illisible` | Corrige le fichier ou supprime-le. |
| `lot` ne traite rien | Les annonces sont déjà dans la mémoire des offres vues : ajoute `--retraiter`, ou supprime `data/offres_vues.json`. |

---

## 8. Limites à connaître

- **Le projet est écrit pour un profil précis** : le nom de l'auteur et quelques faits sur ses compétences sont écrits dans les prompts, et ses critères de recherche dans `criteres.md` (voir la section 9).

- Une annonce, même « Retenue », reste à vérifier à la main : durée, date de début et télétravail manquent souvent. Ouvre toujours le lien avant d'envoyer.
- La lettre et la fiche entreprise sont des brouillons : relis chaque fait sur le site de l'entreprise.
- Le tri extrait les faits d'un résumé ou d'un texte copié : si l'annonce est ambiguë ou mal copiée, le verdict le sera aussi.
- Le projet n'envoie rien, ne candidate pas à ta place et ne publie rien. Tu restes seul maître de ce qui part.

---

## 9. Utiliser ce dépôt et l'adapter à ton profil

```powershell
git clone <adresse-du-dépôt>
cd pipeline_candidature
python -m pip install -r requirements.txt
Copy-Item data/cv.example.md data/cv.md
Copy-Item data/modele_lettre.example.md data/modele_lettre.md
```
Puis remplace le contenu de `data/cv.md` et `data/modele_lettre.md` par le tien et définis la clé API (section 1).

Le projet a été écrit pour un profil précis (étudiant en BUT Informatique à Lille). Voici tout ce qui est propre à cet auteur et que tu dois adapter :

| Où | Quoi |
|---|---|
| `criteres.md`, section 6 | **Lue par le script** : dates de début, durée, télétravail, villes de la métropole lilloise (`villes_mel`), technologies maîtrisées et à vérifier, comportement quand une information manque. À réécrire pour ton cas. |
| `criteres.md`, sections 1 à 5 | Explications pour toi, non lues par le script. La ligne « Profil » du début cite l'auteur. |
| `data/cv.md`, `data/modele_lettre.md` | Ton CV et ton modèle de lettre (non versionnés). Garde les emplacements `{{ ... }}` du modèle. |
| `prompts/lettre.md` | Le nom de l'auteur et des précisions sur ses compétences (Git pratiqué au quotidien, Scrum seulement connu). À réécrire avec les tiennes. |
| `prompts/cv.md` | Le nom de l'auteur. |
| `config.py` | `VILLES_REQUETE`, la liste `ANGLES` (mots recherchés) et `NOMS_PROJETS_AFFICHES` (voir ci-dessous). |

**Les projets citables dans la lettre sont lus dans ton CV** : ce sont les titres `### Nom | type` de la section `## Projets` de `data/cv.md`. Le programme n'en choisit qu'un seul par lettre. `NOMS_PROJETS_AFFICHES` (`config.py`) dit comment écrire un nom dans la lettre (par exemple `ECODROP` devient `EcoDrop`) ; un nom tout en majuscules qui n'y figure pas devient « Nom », et un nom déjà normal reste tel quel. Le CV d'exemple montre le format attendu.

---

## 10. Git, confidentialité et licence

- **Versionné** : le code, les prompts, les tests, `criteres.md`, les exemples (`*.example.md`) et ce README.
- **Jamais versionné** (voir `.gitignore`) : `data/cv.md`, `data/modele_lettre.md`, `data/offres_vues.json`, `sorties/`, `offre.txt`, `offres_a_trier/`, `.env`. Ce sont tes données personnelles (CV, téléphone, e-mail), les lettres générées et les annonces que tu tries. `data/cv.md` et `data/modele_lettre.md` viennent de ta copie des exemples ; `sorties/`, `offres_a_trier/` et `data/offres_vues.json` sont **créés automatiquement** par le programme à la première utilisation, tu n'as rien à créer.
- **Ce qui part vers l'API Anthropic** : le texte des annonces, le contenu de ton CV, des résumés d'entreprise et les requêtes de recherche web. Ne déposes pas d'informations que tu ne veux pas envoyer.
- **La clé API** n'est jamais écrite dans un fichier : elle reste dans la variable d'environnement `ANTHROPIC_API_KEY`.
- **Avant de rendre le dépôt public** : lance `git ls-files` et vérifie que seuls les fichiers que tu acceptes d'exposer apparaissent. Si tu as un doute sur l'historique, cherche tes données personnelles avec `git log -p`.
- **Licence** : MIT (fichier `LICENSE`). Tout le monde peut utiliser, copier et modifier ce code, à condition de conserver la mention de copyright ; il est fourni sans garantie. La licence couvre le code, les prompts et les fichiers d'exemple, pas tes données personnelles (qui ne sont de toute façon pas dans le dépôt).

Mettre le dépôt en ligne en privé : crée un dépôt **vide et privé** sur github.com, puis dans le dossier du projet :
```powershell
git remote add origin <adresse-du-dépôt>
git push -u origin main
```
