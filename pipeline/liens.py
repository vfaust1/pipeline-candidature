"""Vérifie qu'une offre est toujours en ligne AVANT de payer son analyse.

La recherche web remonte souvent des pages d'offres périmées. Ce contrôle est du Python pur (gratuit) :
il télécharge la page (comme le ferait ton navigateur) et cherche une erreur 404/410 ou un message du
type « cette offre n'est plus disponible ».

Limites honnêtes : certains sites (LinkedIn, Indeed, Welcome to the Jungle...) bloquent les programmes ou
affichent leur contenu avec du JavaScript. Dans ce cas le statut est « inconnu » : l'offre est gardée mais
signalée dans le rapport, et c'est à toi d'ouvrir le lien.
"""
from __future__ import annotations

import asyncio
import datetime
import ipaddress
import re
import urllib.request
from urllib.error import HTTPError
from urllib.parse import urlparse

import config

from .criteres import norm_texte

VIVANTE, MORTE, INCONNU = "vivante", "morte", "inconnu"

_EN_TETES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
}

# Messages typiques d'une offre périmée (comparés après suppression des accents et de la ponctuation).
_PHRASES_EXPIREES = [norm_texte(p) for p in (
    "n'est plus disponible", "n'est plus en ligne", "n'est plus active", "n'est plus accessible",
    "offre expirée", "offre a expiré", "annonce expirée", "annonce n'est plus", "offre n'existe plus",
    "a été pourvue", "poste est pourvu", "poste a été pourvu", "offre est pourvue",
    "page introuvable", "page not found", "vacancy has now expired", "no longer available",
    "no longer accepting applications", "job has expired", "position has been filled",
    "this job is closed", "cette offre est terminée", "offre clôturée", "offre cloturée",
)]


def _adresse_publique(url: str) -> bool:
    """Refuse les adresses locales ou privées (un programme ne doit pas être guidé vers ton réseau interne)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    if p.hostname in ("localhost",) or p.hostname.endswith((".local", ".internal")):
        return False
    try:
        ip = ipaddress.ip_address(p.hostname)
    except ValueError:
        return True   # c'est un nom de domaine
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)


def _telecharger(url: str) -> tuple[int | None, str]:
    requete = urllib.request.Request(url, headers=_EN_TETES)
    try:
        with urllib.request.urlopen(requete, timeout=10) as reponse:
            brut = reponse.read(2_000_000)   # certaines pages font plus de 400 Ko (Wizbii ≈ 400 Ko)
            encodage = reponse.headers.get_content_charset() or "utf-8"
            return reponse.status, brut.decode(encodage, errors="replace")
    except HTTPError as e:
        return e.code, ""
    except Exception:   # réseau coupé, délai dépassé, certificat invalide...
        return None, ""


def _date(valeur: str) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(valeur[:10])
    except ValueError:
        return None


def dates_de_l_offre(html: str) -> tuple[datetime.date | None, datetime.date | None]:
    """Cherche dans la page les dates standard schema.org « JobPosting » : (datePosted, validThrough).
    Beaucoup de sites d'emploi les publient, soit en JSON (« "validThrough": "2026-10-17" »),
    soit en balises <meta itemprop="validThrough" content="...">. Wizbii le fait."""
    trouvees: dict[str, datetime.date | None] = {"datePosted": None, "validThrough": None}
    for cle in trouvees:
        m = re.search(rf'"{cle}"\s*:\s*"(\d{{4}}-\d{{2}}-\d{{2}})', html)
        if m:
            trouvees[cle] = _date(m.group(1))
            continue
        for balise in re.findall(r"<meta[^>]*>", html):
            if cle in balise:
                m = re.search(r'content=["\'](\d{4}-\d{2}-\d{2})', balise)
                if m:
                    trouvees[cle] = _date(m.group(1))
                    break
    return trouvees["datePosted"], trouvees["validThrough"]


def classer(code: int | None, texte: str, aujourdhui: datetime.date | None = None) -> str:
    """Testé hors ligne : transforme (code HTTP, texte de la page) en vivante / morte / inconnu."""
    aujourdhui = aujourdhui or datetime.date.today()
    if code in (404, 410):
        return MORTE
    if code is None or code >= 400:
        return INCONNU    # 403 (site qui bloque les programmes), 429, 5xx (panne passagère)...
    page = norm_texte(texte)
    if any(phrase in page for phrase in _PHRASES_EXPIREES):
        return MORTE
    publiee, valable_jusqu_au = dates_de_l_offre(texte)
    # Une date de fin de validité passée = offre expirée, même si la page affiche encore « Expire bientôt ».
    if valable_jusqu_au and valable_jusqu_au < aujourdhui:
        return MORTE
    # Une offre publiée il y a des mois n'est plus une offre active (Wizbii garde des pages de 2018).
    if publiee and (aujourdhui - publiee).days > config.ANCIENNETE_MAX_JOURS:
        return MORTE
    return VIVANTE


async def verifier(url: str) -> str:
    if not _adresse_publique(url):
        return INCONNU
    code, texte = await asyncio.to_thread(_telecharger, url)
    return classer(code, texte)
