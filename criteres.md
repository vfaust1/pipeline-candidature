# Critères de recherche de stage

Profil : étudiant en 3e année de BUT Informatique (parcours Réalisation d'applications), IUT de Lille.

---

## 1. Critères éliminatoires (stage)

Une offre qui ne respecte pas l'un de ces critères est écartée.

- **Type** : stage de fin d'études, durée de 16 semaines.
- **Niveau** : accessible à un étudiant de 3e année de BUT (Bac+3), ou niveau non précisé.
  - Garder les offres de « Bac » à « Bac+3 », et les offres du type « Bac+3 à Bac+5 ».
  - Les offres qui demandent Bac+4 et/ou Bac+5 (M1, M2) ne sont pas écartées : elles sont marquées **À vérifier**, je les contrôle moi-même.
- **Date de début** : entre janvier et avril 2027, idéalement mars 2027.
- **Lieu** : métropole lilloise (Lille, Villeneuve-d'Ascq, Roubaix, Tourcoing, Marcq-en-Barœul, Lesquin, Seclin, Lomme, Hellemmes, Mons-en-Barœul, Loos, Wasquehal, Hem, etc.).
- **Télétravail** : 2 jours par semaine maximum. Exclure le télétravail complet (full remote) et les offres à 4 jours ou plus. Les offres à 3 jours sont marquées **À vérifier**.
- **Domaine** : développement web, application ou mobile.

---

## 2. Filtre technologique (règle du OU)

Garder l'offre (étiquette **Retenue**) si **au moins une** de ces conditions est vraie :
- une technologie prioritaire ou proche est citée ;
- le poste est du développement web ou applicatif, sans technologie précisée.

**Technologies prioritaires** : Java (y compris Android en Java), TypeScript, SQL.
**Technologies proches** : JavaScript, React, Next.js, Node.js, Express, Java EE.
**Bases de données** : toutes sont acceptées (PostgreSQL, MySQL, MariaDB, MongoDB, SQL Server, Oracle, SQLite, Redis...).
**À vérifier** : Python et C# (je vais en faire cette année). Une offre qui ne cite que ces technologies, sans rien de ma liste, est marquée **À vérifier**.

**Technologies adjacentes (non maîtrisées)** : Kotlin, React Native, Flutter, Swift.
Je ne les ai pas apprises, donc elles ne suffisent pas à elles seules à retenir une offre. Une offre mobile qui ne cite que ces technologies est marquée **À vérifier**, jamais écartée d'office : un stage de 16 semaines laisse le temps d'apprendre. Kotlin (proche de Java) et React Native (basé sur React et TypeScript) sont les plus accessibles pour moi.

---

## 3. Préférences (classement, jamais éliminatoires)

Elles servent à trier les offres retenues, de la plus pertinente à la moins pertinente :
- Stack proche de mon expérience (TypeScript / React / Node.js / PostgreSQL ou Java).
- Entreprise avec un produit propre plutôt qu'une prestation de service.
- Mission avec responsabilités concrètes (conception, développement, tests).
- Équipe technique identifiable (développeurs, tuteur de stage).

---

## 4. Veille alternance (pour une éventuelle poursuite en Master)

Les offres d'alternance ne sont pas utiles pour le stage de 2027, mais peuvent servir pour la rentrée suivante si je continue en Master. Elles ne sont donc pas supprimées, mais **rangées à part**, dans une section « Veille alternance », sans les mélanger avec les stages.

Pour cette section :
- **Début** : rentrée 2027 (septembre à octobre).
- **Niveau** : offres Master (M1, M2) acceptées.
- **Lieu, télétravail, domaine, technologies** : mêmes règles que pour le stage.

---

## 5. Règles de décision

Chaque offre reçoit l'une de ces étiquettes :
- **Retenue** : respecte tous les critères éliminatoires.
- **À vérifier** : une information est ambiguë ou contradictoire (niveau Bac+4/5, 3 jours de télétravail, ville proche de la MEL, technologies Python/C#...). Ne jamais écarter une offre uniquement parce qu'une information est absente.
- **Informations non précisées** (niveau, durée, date de début, nombre de jours de télétravail) : l'offre reste **Retenue**, avec une note dans le rapport. Ce comportement se règle dans la section 6.
- **Écartée** : ne respecte pas un critère éliminatoire. Toujours indiquer la raison.
- **Veille alternance** : offre d'alternance rangée à part.

Autres règles :
- Dédoublonner : une même offre publiée sur plusieurs sites ne compte qu'une fois.
- Pour chaque offre retenue, indiquer : intitulé, entreprise, ville, date de début, durée, niveau demandé, télétravail, technologies, lien, raison de la sélection.

---

## 6. Paramètres lus par le script (modifiables)

Cette section est lue par le code Python. Garde le format « - clé : valeur » (une ligne par paramètre). Les dates sont au format AAAA-MM. Les listes sont séparées par des virgules. Le reste du fichier (sections 1 à 5) est pour toi : le script ne le lit pas.

**Durée**
- `duree_semaines` : 16
- `tolerance_duree_semaines` : 2

**Dates de début**
- `stage_debut_min` : 2027-01
- `stage_debut_max` : 2027-04
- `stage_debut_ideal` : 2027-03
- `alternance_debut_min` : 2027-09
- `alternance_debut_max` : 2027-10

**Télétravail**
- `teletravail_max_jours` : 2
- `teletravail_a_verifier_jusqua` : 3

**Lieu**
- `villes_mel` : Lille, Lomme, Hellemmes, Villeneuve-d'Ascq, Roubaix, Tourcoing, Marcq-en-Barœul, Lesquin, Seclin, Mons-en-Barœul, Loos, Wasquehal, Hem, La Madeleine, Lambersart, Saint-André-lez-Lille, Marquette-lez-Lille, Wambrechies, Ronchin, Faches-Thumesnil, Haubourdin, Wattignies, Croix, Mouvaux, Bondues, Wattrelos, Halluin, Comines, Armentières, Lezennes, Sequedin, Templemars, Santes, Englos, Emmerin, Lys-lez-Lannoy, Leers, Lannoy, Toufflers, Forest-sur-Marque, Sainghin-en-Mélantois, Anstaing, Baisieux, Gruson, Linselles, Bousbecque, Pérenchies, Neuville-en-Ferrain, Tressin, Capinghem, Houplin-Ancoisne, Wavrin, Don, Fretin
- `villes_a_verifier` : Phalempin, Pont-à-Marcq, Orchies, Carvin, Cysoing, Douai, Tournai, Mouscron, Courtrai, Kortrijk
- `departements_a_verifier` : 59, 62

**Technologies**
- `technos_prioritaires` : Java, TypeScript, SQL
- `technos_proches` : JavaScript, React, Next.js, Node.js, Express, Java EE
- `bases_de_donnees` : PostgreSQL, MySQL, MariaDB, MongoDB, SQL Server, Oracle, SQLite, Redis, Cassandra, Elasticsearch, DynamoDB
- `technos_adjacentes` : Kotlin, React Native, Flutter, Swift
- `technos_a_verifier` : Python, C#

**Cas flous : « a_verifier » ou « ecarter » (ou « retenue » pour le niveau)**
- `niveau_non_precise` : retenue
- `duree_non_precisee` : retenue
- `debut_non_precise` : retenue
- `teletravail_non_precise` : retenue
- `technos_hors_liste` : ecarter
- `duree_trop_longue` : a_verifier
