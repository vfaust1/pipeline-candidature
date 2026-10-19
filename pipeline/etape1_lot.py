"""Étape 1 (mode lot) : tu déposes des annonces dans un dossier, le script les trie d'un coup.

Aucune recherche web : le seul coût est l'extraction par le modèle léger (environ 0,002 € par offre).
C'est le mode le plus fiable, car tu choisis toi-même les annonces (tu vois qu'elles sont en ligne).
Les règles, la mémoire des offres déjà vues et le rapport sont les mêmes que pour la recherche automatique.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path

from . import regles
from .criteres import Criteres, norm_texte
from .etape1_offres import extraire_offre
from .etape1_recherche import Candidat, Resultat, Stats
from .vues import OffresVues, meme_signature, normaliser_url, signature

_LONGUEUR_MIN = 80   # en dessous, ce n'est pas une annonce (un titre seul, un reste de copier-coller)


def decouper(texte: str) -> list[str]:
    """Un fichier peut contenir plusieurs annonces, séparées par une ligne de « === » (trois signes égal ou plus)."""
    morceaux = re.split(r"^\s*={3,}\s*$", texte, flags=re.M)
    return [m.strip() for m in morceaux if len(m.strip()) >= _LONGUEUR_MIN]


def empreinte(texte: str) -> str:
    """Identifie une annonce par son contenu : la recoller ne la fait pas repayer."""
    return "txt:" + hashlib.sha1(norm_texte(texte).encode("utf-8")).hexdigest()[:20]


def lien_du_texte(texte: str) -> str | None:
    m = re.search(r"https?://[^\s<>\"')\]]+", texte[:400])
    return m.group(0).rstrip(".,;") if m else None


def lire_dossier(dossier: Path) -> list[str]:
    annonces: list[str] = []
    for fichier in sorted(dossier.glob("*.txt"), key=lambda f: f.stat().st_mtime):
        if fichier.name.lower().startswith("lisez-moi"):
            continue
        annonces += decouper(fichier.read_text(encoding="utf-8", errors="replace"))
    return annonces


async def traiter_lot(annonces: list[str], c: Criteres, vues: OffresVues, max_offres: int,
                      stats: Stats, retraiter: bool = False) -> list[Resultat]:
    """retraiter=True : ignore la mémoire des offres vues (utile après avoir modifié tes critères ou un prompt)."""
    stats.trouvees = len(annonces)
    nouvelles: list[tuple[str, str]] = []
    for texte in annonces:
        cle = empreinte(texte)
        if vues.deja_vue(cle) and not retraiter:
            stats.deja_vues += 1
        else:
            nouvelles.append((cle, texte))
    stats.non_analysees_budget = max(0, len(nouvelles) - max_offres)
    nouvelles = nouvelles[:max_offres]

    sem = asyncio.Semaphore(4)

    async def un(cle: str, texte: str) -> tuple[str, str, Resultat | None]:
        async with sem:
            try:
                offre = await extraire_offre(texte)
            except Exception as e:   # une annonce en échec ne bloque pas les autres
                stats.erreurs.append(f"extraction en échec ({texte[:40]!r}…) : {e}")
                return cle, texte, None
        offre.lien = offre.lien or lien_du_texte(texte)
        cand = Candidat(url=offre.lien or "", texte=texte, publiee=None, angle="lot", lien_statut="manuel")
        return cle, texte, Resultat(offre=offre, verdict=regles.evaluer(offre, c), candidat=cand)

    resultats: list[Resultat] = []
    signatures: list[str] = []
    for cle, _texte, r in await asyncio.gather(*(un(k, t) for k, t in nouvelles)):
        if r is None:
            continue
        ville = r.offre.lieux[0] if r.offre.lieux else ""
        sig = signature(r.offre.entreprise, r.offre.intitule, ville)
        cles = [cle] + ([normaliser_url(r.offre.lien)] if r.offre.lien else [])
        if any(meme_signature(sig, s) for s in signatures) or (vues.signature_vue(sig) and not retraiter):
            stats.doublons += 1
            vues.ajouter(cles, "doublon", r.offre.intitule, r.offre.entreprise, r.offre.lien or "")
            continue
        signatures.append(sig)
        vues.ajouter(cles + ["sig:" + sig], r.verdict.statut, r.offre.intitule, r.offre.entreprise, r.offre.lien or "")
        resultats.append(r)
        stats.analysees += 1
    return resultats
