"""Mémoire des offres déjà traitées (data/offres_vues.json).

Sans elle, chaque lancement referait payer l'analyse des mêmes offres. On retient deux clés par offre :
  - son adresse web nettoyée (sans les paramètres de suivi) ;
  - une « signature » entreprise|intitulé|ville, pour reconnaître la même offre republiée plus tard
    ou publiée sur un autre site. La comparaison de signatures est approximative (voir meme_signature).
"""
from __future__ import annotations

import datetime
import json
import os
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

from .criteres import norm_texte

_PARAMETRES_SUIVI = {"fbclid", "gclid", "ref", "referrer", "source", "src", "trk", "mc_cid", "mc_eid"}
# Mots sans valeur pour comparer deux intitulés (« Stage de développeur web H/F » = « Développeur web »).
_MOTS_VIDES = {"de", "d", "du", "des", "la", "le", "les", "en", "et", "a", "au", "aux", "pour", "stage", "stagiaire",
               "h", "f", "fin", "etudes", "alternance"}


def normaliser_url(url: str) -> str:
    """Enlève la casse, « www. », le fragment et les paramètres de suivi (utm_*, fbclid...)."""
    p = urlparse(url.strip())
    hote = p.netloc.lower().removeprefix("www.")
    params = sorted((k, v) for k, v in parse_qsl(p.query)
                    if not k.lower().startswith("utm_") and k.lower() not in _PARAMETRES_SUIVI)
    return f"{hote}{p.path.rstrip('/')}" + (f"?{urlencode(params)}" if params else "")


def signature(entreprise: str, intitule: str, ville: str) -> str:
    titre = [m for m in norm_texte(intitule).split() if m not in _MOTS_VIDES]
    return "|".join([norm_texte(entreprise), " ".join(titre), norm_texte(ville)])


def meme_signature(a: str, b: str) -> bool:
    """Deux annonces décrivent-elles probablement la même offre ?
    Il faut la même ville (si les deux la connaissent), un nom d'entreprise contenu dans l'autre
    (« Gfi » ~ « Gfi Informatique ») et des intitulés très proches (mêmes mots, ou 80 % de ressemblance)."""
    try:
        ent_a, titre_a, ville_a = a.split("|")
        ent_b, titre_b, ville_b = b.split("|")
    except ValueError:
        return a == b
    if ville_a and ville_b and ville_a != ville_b:
        return False
    mots_a, mots_b = set(ent_a.split()), set(ent_b.split())
    if not mots_a or not mots_b or not (mots_a <= mots_b or mots_b <= mots_a):
        return False
    if not titre_a or not titre_b:
        return False
    return set(titre_a.split()) == set(titre_b.split()) or SequenceMatcher(None, titre_a, titre_b).ratio() >= 0.8


class OffresVues:
    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin
        self.offres: dict[str, dict] = {}
        if chemin.exists():
            try:
                contenu = chemin.read_text(encoding="utf-8")
                # Un fichier vide (par exemple après avoir effacé son contenu) = aucune offre vue.
                if contenu.strip():
                    self.offres = json.loads(contenu).get("offres", {})
            except (json.JSONDecodeError, OSError, AttributeError):
                raise RuntimeError(f"{chemin} est illisible : corrige-le ou supprime-le pour repartir de zéro.")

    def deja_vue(self, cle: str) -> bool:
        return cle in self.offres

    def signature_vue(self, sig: str) -> bool:
        """Vrai si une offre ressemblante est déjà mémorisée (exacte ou approchante)."""
        return any(meme_signature(cle[4:], sig) for cle in self.offres if cle.startswith("sig:"))

    def exemples(self, n: int = 30) -> list[str]:
        """« Entreprise — titre » des dernières offres traitées, pour dire à la recherche de ne pas les ramener."""
        vus: dict[tuple[str, str], str] = {}
        for info in self.offres.values():
            if info.get("entreprise") or info.get("titre"):
                vus[(info.get("entreprise", ""), info.get("titre", ""))] = info.get("vu_le", "")
        recents = sorted(vus.items(), key=lambda kv: kv[1], reverse=True)[:n]
        return [f"{e} — {t}" for (e, t), _ in recents]

    def ajouter(self, cles: list[str], statut: str, titre: str, entreprise: str, lien: str) -> None:
        info = {"vu_le": datetime.date.today().isoformat(), "statut": statut,
                "titre": titre, "entreprise": entreprise, "lien": lien}
        for cle in cles:
            self.offres[cle] = info

    def sauver(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        temporaire = self.chemin.with_suffix(".tmp")
        temporaire.write_text(json.dumps({"offres": self.offres}, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporaire, self.chemin)   # écriture atomique : pas de fichier à moitié écrit
