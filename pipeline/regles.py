"""Les règles de tri : du Python pur, aucun appel à l'IA, donc gratuit et reproductible.

Chaque contrôle renvoie (statut, message) avec statut = OK, VERIF ou ECART.
  OK    : le critère est respecté.
  VERIF : information manquante ou cas flou -> « À vérifier » (jamais écartée d'office).
  ECART : critère clairement non respecté -> « Écartée » avec la raison.

Les cas flous sont tous regroupés ici et commentés (« CAS FLOU »), pour que tu
puisses relire et contester chaque choix.
"""
from __future__ import annotations

import re

from .criteres import Criteres, fmt_mois, norm_techno, norm_texte, parse_mois
from .schemas import Offre, Verdict

OK, VERIF, ECART = "ok", "verifier", "ecarte"
# NOTE : l'information manque mais criteres.md dit de l'accepter. L'offre n'est pas pénalisée,
# mais le rapport l'indique (« non précisé ») pour que tu saches ce qu'il reste à contrôler.
NOTE = "note"


def _manquant(reglage: str, message: str) -> tuple[str, str]:
    """Information absente de l'annonce : acceptée (NOTE) ou « à vérifier », selon criteres.md."""
    return (NOTE, message + " (acceptée)") if reglage == "retenue" else (VERIF, message)

# Villes (normalisées) pour lesquelles on accepte aussi « Lille Euratechnologies »,
# « Roubaix centre », etc. On NE le fait PAS pour les noms courts qui ont des
# homonymes hors métropole (Loos-en-Gohelle, Croix-en-Ternois, Hem-Lenglet...).
_PREFIXES_SURS = ("lille", "roubaix", "tourcoing", "villeneuve d ascq", "marcq en baroeul")
_MOTS_BRUIT_VILLE = {"cedex", "metropole", "metropolitaine", "europeenne", "environs", "alentours", "mel"}

# Équivalences de noms de technologies (clé normalisée -> nom normalisé de la liste).
_ALIAS_TECHNOS = {
    "js": "javascript", "ecmascript": "javascript", "ts": "typescript",
    "reactjs": "react", "nodejs": "nodejs", "node": "nodejs", "expressjs": "express",
    "postgres": "postgresql", "psql": "postgresql",
    "jee": "javaee", "j2ee": "javaee", "jakartaee": "javaee",
    # Spring est un framework Java : une offre « Spring Boot » cite donc Java.
    "spring": "java", "springboot": "java",
    # Ces moteurs de bases de données s'interrogent en SQL.
    "mysql": "sql", "mariadb": "sql", "plsql": "sql", "sqlserver": "sql", "mssql": "sql", "sqlite": "sql",
    "kotlinandroid": "kotlin", "reactnative": "reactnative",
    "mongo": "mongodb", "mangodb": "mongodb", "mssqlserver": "sqlserver", "oracledb": "oracle",
    # Variantes de C# / Python.
    "csharp": "csharp", "net": "csharp", "dotnet": "csharp", "aspnet": "csharp",
    "django": "python", "flask": "python", "fastapi": "python",
}

# Mots qui décrivent un contexte, pas une technologie : ils n'entrent pas dans le filtre.
_TECHNOS_NEUTRES = {
    "git", "github", "gitlab", "html", "css", "html5", "css3", "rest", "api", "restapi", "agile", "scrum",
    "docker", "linux", "figma", "jira", "cicd", "tests", "web", "mobile", "frontend", "backend", "fullstack",
}
# Plateformes mobiles sans langage : on ne sait pas si c'est Java ou Kotlin.
_PLATEFORMES_MOBILES = {"android", "ios"}


# --- Outils ------------------------------------------------------------------

def _technos_normalisees(offre: Offre) -> set[str]:
    resultat = set()
    for t in offre.technologies:
        n = norm_techno(t)
        if n:
            resultat.add(_ALIAS_TECHNOS.get(n, n))
    return resultat


def _ville_propre(brut: str) -> str:
    """Retire codes postaux, « cedex », « métropole »... pour comparer des noms de villes."""
    mots = [m for m in norm_texte(brut).split() if not m.isdigit() and m not in _MOTS_BRUIT_VILLE]
    return " ".join(mots)


def _est_mel(ville: str, c: Criteres) -> bool:
    if ville in c.villes_mel:
        return True
    return any(ville.startswith(p + " ") and p in c.villes_mel for p in _PREFIXES_SURS)


# --- Les contrôles -----------------------------------------------------------

def controle_type(offre: Offre) -> tuple[str, str]:
    t = offre.type_contrat
    if t == "autre":
        return ECART, "contrat ni stage ni alternance (CDI, CDD, freelance...)"
    if t == "inconnu":
        # CAS FLOU : type de contrat illisible -> on traite comme un stage, mais on le signale.
        return VERIF, "type de contrat non précisé (stage ou alternance ?)"
    return OK, ""


def controle_domaine(offre: Offre) -> tuple[str, str]:
    if offre.domaine == "autre":
        # CAS FLOU : data/IA pure, réseau, cybersécurité, DevOps sans développement = hors domaine.
        # Back-end, full-stack, logiciel métier, jeu vidéo comptent comme « application ».
        return ECART, "domaine hors développement web, application ou mobile"
    if offre.domaine == "inconnu":
        return VERIF, "domaine du poste peu clair"
    return OK, ""


def controle_lieu(offre: Offre, c: Criteres) -> tuple[str, str]:
    villes = [v for v in (_ville_propre(x) for x in offre.lieux) if v]
    dept = (offre.departement or "").strip()

    # CAS FLOU : plusieurs lieux possibles (« Lille ou Paris ») -> OK si UN lieu est dans la MEL.
    if any(_est_mel(v, c) for v in villes):
        return OK, ""

    if not villes and not dept:
        return VERIF, "lieu non précisé"

    # CAS FLOU : ville voisine de la MEL, ou ville inconnue de ma liste mais dans le Nord / Pas-de-Calais.
    # On ne sait pas calculer le trajet : on laisse à l'étudiant le soin de trancher.
    if any(v in c.villes_a_verifier for v in villes):
        return VERIF, f"ville proche de la métropole mais hors liste : {', '.join(offre.lieux)}"
    if dept in c.departements_a_verifier:
        return VERIF, f"« {', '.join(offre.lieux) or 'lieu'} » n'est pas dans ma liste MEL mais est dans le {dept} : distance à vérifier"

    if villes and not dept:
        # Ville absente de ma liste et pas de département : je préfère douter que me tromper.
        return VERIF, f"ville absente de la liste MEL, département inconnu : {', '.join(offre.lieux)}"
    return ECART, f"lieu hors métropole lilloise : {', '.join(offre.lieux) or 'département ' + dept}"


def controle_teletravail(offre: Offre, c: Criteres) -> tuple[str, str]:
    if offre.teletravail_complet:
        return ECART, "télétravail complet (full remote)"
    jmin, jmax = offre.teletravail_jours_min, offre.teletravail_jours_max
    if jmin is None and jmax is None:
        if offre.teletravail_sans_chiffre:
            # CAS FLOU : « télétravail possible / hybride » sans nombre de jours.
            return VERIF, "télétravail mentionné sans nombre de jours"
        return _manquant(c.teletravail_non_precise, "télétravail non précisé")
    if jmax is None:
        jmax = jmin
    if jmin is None:
        jmin = jmax
    if jmax <= c.teletravail_max:
        return OK, ""
    if jmin > c.teletravail_a_verifier_jusqua:
        return ECART, f"télétravail de {jmin:g} jours par semaine ou plus (limite : {c.teletravail_a_verifier_jusqua:g})"
    # CAS FLOU : 3 jours, ou fourchette comme « 2 à 3 jours » : je tranche moi-même.
    plage = f"{jmin:g}" if jmin == jmax else f"{jmin:g} à {jmax:g}"
    return VERIF, f"télétravail de {plage} jours : au-dessus de {c.teletravail_max:g} jours, à vérifier"


def controle_niveau(offre: Offre, c: Criteres) -> tuple[str, str]:
    nmin, nmax = offre.niveau_min_bac, offre.niveau_max_bac
    if nmin is None and nmax is None:
        return _manquant(c.niveau_non_precise, "niveau demandé non précisé")
    if nmin is not None and nmin >= 4:
        # « Bac+4/5 », « M1/M2 », « Bac+5 » seul : je ne l'écarte pas, je le contrôle moi-même.
        # « Bac+3 à Bac+5 » a nmin = 3, donc il passe. « Bac » à « Bac+3 » passent aussi.
        return VERIF, f"niveau Bac+{nmin} minimum demandé (Master / Bac+5) : à vérifier"
    return OK, ""


def controle_duree(offre: Offre, c: Criteres) -> tuple[str, str]:
    dmin, dmax = offre.duree_min_semaines, offre.duree_max_semaines
    if dmin is None and dmax is None:
        return _manquant(c.duree_non_precisee, "durée non précisée")
    dmin = dmin if dmin is not None else dmax
    dmax = dmax if dmax is not None else dmin
    cible, tol = c.duree_semaines, c.tolerance_duree
    if dmax < cible - tol:
        return ECART, f"stage trop court ({dmax:g} semaines maximum pour {cible} requises)"
    if dmin > cible + tol:
        # CAS FLOU : « 6 mois » (~26 semaines) alors que je dois faire 16 semaines.
        # Une durée plus longue se négocie parfois, mais pas toujours : réglable dans criteres.md.
        message = f"durée de {dmin:g} semaines au minimum (je dois faire {cible})"
        return (ECART if c.duree_trop_longue == "ecarter" else VERIF), message
    return OK, ""


def controle_dates(offre: Offre, debut_min: int, debut_max: int, c: Criteres) -> tuple[str, str]:
    tot = parse_mois(offre.debut_au_plus_tot)
    tard = parse_mois(offre.debut_au_plus_tard)
    fenetre = f"{fmt_mois(debut_min)} à {fmt_mois(debut_max)}"
    if tot is None and tard is None:
        # « Dès que possible », « début d'année » et « non précisé » sont traités pareil (voir criteres.md).
        detail = "date de début floue (« dès que possible » ou équivalent)" if offre.debut_flou else "date de début non précisée"
        return _manquant(c.debut_non_precise, detail)
    if tard is not None and tard < debut_min:
        return ECART, f"début au plus tard en {fmt_mois(tard)}, avant la fenêtre {fenetre}"
    if tot is not None and tot > debut_max:
        return ECART, f"début au plus tôt en {fmt_mois(tot)}, après la fenêtre {fenetre}"
    if tard is None and tot is not None and tot < debut_min:
        # CAS FLOU : « à partir de novembre 2026 » sans fin : le début réel peut tomber dans ma fenêtre ou non.
        return VERIF, f"début possible dès {fmt_mois(tot)} (date ouverte) : à confirmer pour la fenêtre {fenetre}"
    return OK, ""


def controle_technos(offre: Offre, c: Criteres) -> tuple[str, str, int]:
    """Règle du OU. Renvoie aussi un bonus de score (nombre de technos de mon profil citées)."""
    citees = _technos_normalisees(offre)
    pertinentes = citees - _TECHNOS_NEUTRES - _PLATEFORMES_MOBILES
    connues = pertinentes & (c.technos_prioritaires | c.technos_proches)
    bonus = 3 * len(pertinentes & c.technos_prioritaires) + 2 * len(pertinentes & c.technos_proches)

    if connues:
        return OK, "", bonus
    if not pertinentes:
        # Aucune techno précisée.
        if citees & _PLATEFORMES_MOBILES:
            # CAS FLOU : « développeur Android » sans langage : Java (ok) ou Kotlin (non maîtrisé) ?
            return VERIF, "mobile Android/iOS sans langage précisé (Java ? Kotlin ? Swift ?)", 0
        if offre.domaine in ("web", "application", "mobile"):
            return OK, "", 0   # « poste de dev web/applicatif sans technologie précisée » = gardé
        return VERIF, "aucune technologie citée et domaine peu clair", 0
    adjacentes = pertinentes & c.technos_adjacentes
    if adjacentes:
        noms = ", ".join(sorted(adjacentes))
        return VERIF, f"seulement des technos adjacentes que je ne maîtrise pas ({noms}) : accessible sur 16 semaines ?", 0
    a_verifier = pertinentes & c.technos_a_verifier
    if a_verifier:
        # Python et C# : je vais les apprendre cette année, donc à vérifier plutôt qu'écarté.
        return VERIF, f"technos que je vais apprendre cette année ({', '.join(sorted(offre.technologies))})", 0
    # CAS FLOU : technos citées mais aucune de ma liste (PHP, Python, C#, Angular, Vue...).
    # Ma règle du OU ne les garde pas ; réglable avec « technos_hors_liste » dans criteres.md.
    noms = ", ".join(sorted(offre.technologies))
    if c.technos_hors_liste == "a_verifier":
        return VERIF, f"technologies hors de ma liste : {noms}", 0
    return ECART, f"technologies hors de ma liste : {noms}", 0


# --- Verdict global ----------------------------------------------------------

def evaluer(offre: Offre, c: Criteres) -> Verdict:
    alternance = offre.type_contrat == "alternance"
    resultats: list[tuple[str, str]] = [controle_type(offre), controle_domaine(offre),
                                        controle_lieu(offre, c), controle_teletravail(offre, c)]
    notes: list[str] = []

    if alternance:
        # Veille alternance : début à la rentrée 2027, niveau Master accepté (donc pas de contrôle de niveau),
        # durée non contrôlée (un contrat d'alternance dure 1 à 2 ans).
        resultats.append(controle_dates(offre, c.alternance_debut_min, c.alternance_debut_max, c))
    else:
        resultats += [controle_niveau(offre, c), controle_duree(offre, c),
                      controle_dates(offre, c.stage_debut_min, c.stage_debut_max, c)]
        if offre.type_contrat == "stage_ou_alternance":
            notes.append("offre « stage ou alternance » : évaluée comme un stage")

    statut_techno, msg_techno, bonus = controle_technos(offre, c)
    resultats.append((statut_techno, msg_techno))

    ecarts = [m for s, m in resultats if s == ECART]
    verifs = [m for s, m in resultats if s == VERIF]
    notes += [m for s, m in resultats if s == NOTE]

    if ecarts:
        statut = "ecartee"
    elif alternance:
        statut = "veille_alternance"
    elif verifs:
        statut = "a_verifier"
    else:
        statut = "retenue"

    # Score : sert seulement à classer les offres gardées (préférences de criteres.md §3).
    score = bonus
    score += 2 if offre.produit_propre else 0
    score += 1 if offre.missions_concretes else 0
    score += 1 if offre.equipe_identifiable else 0
    if c.stage_debut_ideal is not None and not alternance:
        tot = parse_mois(offre.debut_au_plus_tot)
        tard = parse_mois(offre.debut_au_plus_tard)
        if tot is not None and (tard if tard is not None else tot) is not None:
            haut = tard if tard is not None else tot
            if tot <= c.stage_debut_ideal <= haut:
                score += 2
                notes.append("début compatible avec mars 2027 (idéal)")
    return Verdict(statut=statut, raisons_ecart=ecarts, points_a_verifier=verifs, notes=notes, score=score)
