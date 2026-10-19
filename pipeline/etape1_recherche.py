"""Étape 1 (mode automatique) : trouver des offres récentes, puis les trier.

Déroulement, contrôlé par ce script :
  1. Plusieurs « angles » de recherche tournent EN PARALLÈLE (un appel du modèle léger avec l'outil de
     recherche web par angle). Chacun renvoie un petit texte factuel par offre, avec son adresse web.
  2. Python vérifie : l'adresse est-elle bien une page vue par la recherche ? l'offre est-elle assez récente ?
     l'a-t-on déjà traitée (offres_vues.json) ?
  3. Chaque offre restante passe dans l'extraction (modèle léger, comme en mode manuel) puis dans les
     règles Python. Aucune page web brute ne dépasse l'étape 1 : seulement ces petits résumés.
"""
from __future__ import annotations

import asyncio
import datetime
import re
from dataclasses import dataclass, field
from itertools import zip_longest

import config

from . import liens, llm, regles
from .criteres import Criteres, fmt_mois
from .etape1_offres import extraire_offre
from .schemas import Offre, Verdict
from .vues import OffresVues, meme_signature, normaliser_url, signature


@dataclass
class Candidat:
    url: str
    texte: str
    publiee: datetime.date | None
    angle: str
    lien_statut: str = liens.INCONNU   # vivante | inconnu (les liens morts sont éliminés avant l'analyse)


@dataclass
class Resultat:
    offre: Offre
    verdict: Verdict
    candidat: Candidat


@dataclass
class Stats:
    trouvees: int = 0
    url_non_verifiee: int = 0
    trop_anciennes: int = 0
    deja_vues: int = 0
    doublons: int = 0
    liens_morts: int = 0
    liens_non_verifiables: int = 0
    requetes: list[str] = field(default_factory=list)   # requêtes web réellement envoyées
    non_analysees_budget: int = 0
    analysees: int = 0
    erreurs: list[str] = field(default_factory=list)


# --- Lecture de la réponse du modèle (testée hors ligne) ---------------------

def parser(texte: str, urls_outil: list[str], angle: str, stats: Stats,
           aujourdhui: datetime.date | None = None) -> list[Candidat]:
    aujourdhui = aujourdhui or datetime.date.today()
    urls_vues = {normaliser_url(u) for u in urls_outil}
    candidats: list[Candidat] = []
    deja: set[str] = set()

    for bloc in texte.split("=== OFFRE ===")[1:]:
        stats.trouvees += 1
        m_url = re.search(r"URL\s*\**\s*:\s*\**\s*(https?://[^\s*)>\]]+)", bloc)
        m_texte = re.search(r"TEXTE\s*\**\s*:\s*\**\s*(.*)\Z", bloc, re.S)
        if not m_url or not m_texte or not m_texte.group(1).strip():
            stats.erreurs.append(f"bloc illisible ({angle})")
            continue
        url = m_url.group(1).rstrip(".,;")
        cle = normaliser_url(url)
        # Garde-fou anti-invention : l'adresse doit avoir été renvoyée par l'outil de recherche.
        if cle not in urls_vues:
            stats.url_non_verifiee += 1
            continue
        if cle in deja:
            stats.doublons += 1
            continue
        deja.add(cle)

        publiee = None
        m_date = re.search(r"PUBLIEE\s*\**\s*:\s*\**\s*(\d{4})-(\d{2})-(\d{2})", bloc)
        if m_date:
            try:
                publiee = datetime.date(int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3)))
            except ValueError:
                publiee = None
        if publiee and (aujourdhui - publiee).days > config.RECENCE_JOURS:
            stats.trop_anciennes += 1
            continue
        candidats.append(Candidat(url=url, texte=m_texte.group(1).strip(), publiee=publiee, angle=angle))
    return candidats


def repartir(total: int, n: int) -> list[int]:
    """5 recherches sur 4 angles -> [2, 1, 1, 1]."""
    base, reste = divmod(total, n)
    return [base + (1 if i < reste else 0) for i in range(n)]


def melanger(listes: list[list[Candidat]]) -> list[Candidat]:
    """Un candidat de chaque angle à tour de rôle, pour qu'aucun angle ne monopolise le budget d'analyse."""
    return [c for groupe in zip_longest(*listes) for c in groupe if c is not None]


# --- Recherche ---------------------------------------------------------------

async def _chercher_un_angle(angle: dict, nb_recherches: int, nb_offres: int, c: Criteres,
                             stats: Stats, deja_traitees: list[str]) -> list[Candidat]:
    if angle["type"] == "alternance":
        periode = f"début à la rentrée {fmt_mois(c.alternance_debut_min)} à {fmt_mois(c.alternance_debut_max)}"
    else:
        periode = f"stage de {c.duree_semaines} semaines, début entre {fmt_mois(c.stage_debut_min)} et {fmt_mois(c.stage_debut_max)}"
    demande = (
        f"Date du jour : {datetime.date.today().isoformat()}\n"
        f"Angle de recherche : {angle['consigne']}\n"
        f"Lieu : métropole lilloise ({config.VILLES_REQUETE}, etc.)\n"
        f"Période : {periode}\n"
        f"Trouve au maximum {nb_offres} offres publiées depuis moins de {config.RECENCE_JOURS} jours si la date est visible. "
        f"Tu disposes de {nb_recherches} recherche(s) web : choisis des requêtes précises."
    )
    requetes_fixes = angle.get("requetes", [])[:nb_recherches]
    if requetes_fixes:
        # Mode « je choisis les mots » : le modèle ne les modifie pas (voir ANGLES dans config.py).
        demande += ("\nLance EXACTEMENT ces requêtes de recherche web, mot pour mot, sans les modifier ni en ajouter, "
                    "dans cet ordre :\n" + "\n".join(f"- {r}" for r in requetes_fixes))
    elif angle.get("sources"):
        demande += f"\nSites à essayer en priorité : {angle['sources']}."
    if deja_traitees:
        # Évite de repayer des offres déjà vues : la recherche doit aller chercher AUTRE chose.
        demande += ("\nOffres déjà traitées, à NE PAS rapporter (fais d'autres requêtes, d'autres sites) :\n"
                    + "\n".join(f"- {x}" for x in deja_traitees))
    systeme = (config.DOSSIER_PROMPTS / "recherche.md").read_text(encoding="utf-8")
    texte, urls, requetes = await llm.appeler_avec_recherche(
        modele=config.MODELE_LEGER, system=systeme, user=demande,
        max_tokens=config.MAX_TOKENS_RECHERCHE, max_recherches=nb_recherches,
    )
    stats.requetes += [f"[{angle['nom']}] {q}" for q in requetes]
    return parser(texte, urls, angle["nom"], stats)


async def rechercher(c: Criteres, max_recherches: int, max_offres: int, stats: Stats,
                     vues: OffresVues) -> list[Candidat]:
    angles = config.ANGLES
    repartition = repartir(max_recherches, len(angles))
    # Marge plus large qu'avant : une partie des offres sera éliminée (lien mort, déjà vue).
    nb_offres = -(-max_offres // len(angles)) + 3
    deja = vues.exemples(30)
    taches = [_chercher_un_angle(a, k, nb_offres, c, stats, deja) for a, k in zip(angles, repartition) if k > 0]
    resultats = await asyncio.gather(*taches, return_exceptions=True)
    listes = []
    for r in resultats:
        if isinstance(r, Exception):
            stats.erreurs.append(f"recherche en échec : {r}")
        else:
            listes.append(r)
    return melanger(listes)


# --- Tri des candidats -------------------------------------------------------

async def analyser(candidats: list[Candidat], c: Criteres, vues: OffresVues,
                   max_offres: int, stats: Stats) -> list[Resultat]:
    # 1. Retire ce qui a déjà été traité lors d'un lancement précédent (avant de payer l'extraction).
    nouveaux = []
    for cand in candidats:
        if vues.deja_vue(normaliser_url(cand.url)):
            stats.deja_vues += 1
        else:
            nouveaux.append(cand)
    # 2. Vérifie que les liens sont vivants (gratuit). Les liens morts sont mémorisés pour ne plus revenir.
    sem_liens = asyncio.Semaphore(8)

    async def tester(cand: Candidat) -> str:
        async with sem_liens:
            return await liens.verifier(cand.url)

    etats = await asyncio.gather(*(tester(x) for x in nouveaux))
    vivants = []
    for cand, etat in zip(nouveaux, etats):
        if etat == liens.MORTE:
            stats.liens_morts += 1
            vues.ajouter([normaliser_url(cand.url)], "lien_mort", cand.texte[:60], "", cand.url)
            continue
        if etat == liens.INCONNU:
            stats.liens_non_verifiables += 1
        cand.lien_statut = etat
        vivants.append(cand)
    nouveaux = vivants

    # 3. Plafond de budget (appliqué après le tri des liens : on ne dépense rien pour une page morte).
    stats.non_analysees_budget = max(0, len(nouveaux) - max_offres)
    nouveaux = nouveaux[:max_offres]

    sem = asyncio.Semaphore(4)   # au plus 4 extractions à la fois

    async def traiter(cand: Candidat) -> Resultat | None:
        async with sem:
            try:
                offre = await extraire_offre(f"Lien : {cand.url}\n\n{cand.texte}")
            except Exception as e:   # une offre en échec ne doit pas bloquer les autres
                stats.erreurs.append(f"extraction en échec pour {cand.url} : {e}")
                return None
        offre.lien = cand.url   # le lien vient de la recherche, pas du modèle
        return Resultat(offre=offre, verdict=regles.evaluer(offre, c), candidat=cand)

    resultats: list[Resultat] = []
    signatures: list[str] = []
    for r in await asyncio.gather(*(traiter(x) for x in nouveaux)):
        if r is None:
            continue
        ville = r.offre.lieux[0] if r.offre.lieux else ""
        sig = signature(r.offre.entreprise, r.offre.intitule, ville)
        # Même offre trouvée par deux angles, publiée sur un autre site, ou republiée plus tard.
        if any(meme_signature(sig, s) for s in signatures) or vues.signature_vue(sig):
            stats.doublons += 1
            vues.ajouter([normaliser_url(r.candidat.url)], "doublon", r.offre.intitule, r.offre.entreprise, r.candidat.url)
            continue
        signatures.append(sig)
        vues.ajouter([normaliser_url(r.candidat.url), "sig:" + sig], r.verdict.statut,
                     r.offre.intitule, r.offre.entreprise, r.candidat.url)
        resultats.append(r)
        stats.analysees += 1
    return resultats
