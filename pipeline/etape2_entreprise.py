"""Étape 2 : fiche entreprise courte, avec contrôle d'identité.

Le risque : chercher « Alpha » et résumer la mauvaise société Alpha. Trois protections :
  1. On ne transmet pas que le nom : on envoie une « carte d'identité » (nom, ville, site web, secteur)
     tirée de l'offre, et le prompt exige de vérifier que l'entreprise trouvée y correspond.
  2. Le modèle doit déclarer l'entreprise trouvée, la source qui le prouve et les homonymes croisés.
  3. Python contrôle ensuite SANS IA : si l'offre donne un site web, il doit apparaître dans les pages
     consultées ; et s'il y a des homonymes, il faut au moins deux éléments d'identification.
Si le contrôle échoue, le résumé n'est PAS donné à l'étape suivante (la lettre) : tu le relis toi-même.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import config

from . import llm
from .schemas import Offre


@dataclass
class Fiche:
    confiance: str                      # "haute" | "incertaine"
    resume: str = ""
    entite: str = ""
    source_identite: str = ""
    homonymes: str = ""
    urls: list[str] = field(default_factory=list)
    alertes: list[str] = field(default_factory=list)
    requetes: list[str] = field(default_factory=list)   # recherches web réellement faites par le modèle


def carte_identite(offre: Offre) -> dict[str, str]:
    """Ce qui permet de reconnaître la bonne entreprise. Rien d'autre n'est transmis à l'étape 2."""
    return {
        "nom": offre.entreprise,
        "ville_ou_adresse": offre.adresse_entreprise or ", ".join(offre.lieux),
        "site_web": offre.site_entreprise or "",
        "secteur": offre.secteur_entreprise or "",
        "poste_propose": offre.intitule,
        # Le contexte de la mission aide à reconnaître la bonne entité (filiale, direction informatique...).
        "contexte_de_l_offre": (offre.resume_mission or "")[:300],
    }


def _domaine(adresse: str) -> str:
    adresse = adresse.strip().lower()
    if "//" not in adresse:
        adresse = "//" + adresse
    hote = urlparse(adresse).netloc or ""
    return hote.removeprefix("www.")


def _champ(texte: str, cle: str) -> str:
    m = re.search(rf"^\s*{cle}\s*:\s*(.*)$", texte, re.M)
    return m.group(1).strip() if m else ""


def analyser(texte: str, urls: list[str], carte: dict[str, str]) -> Fiche:
    """Lit la réponse du modèle et applique les contrôles d'identité (testé hors ligne)."""
    fiche = Fiche(confiance="incertaine", urls=list(dict.fromkeys(urls)))
    fiche.entite = _champ(texte, "ENTITE_TROUVEE")
    fiche.source_identite = _champ(texte, "SOURCE_IDENTITE")
    fiche.homonymes = _champ(texte, "HOMONYMES")
    m = re.search(r"^\s*RESUME\s*:\s*(.*)\Z", texte, re.M | re.S)
    fiche.resume = m.group(1).strip() if m else ""

    if _champ(texte, "IDENTITE").lower() != "oui":
        fiche.alertes.append("Le modèle n'est pas sûr d'avoir trouvé la bonne entreprise.")
        return fiche

    elements = [k for k in ("ville_ou_adresse", "site_web", "secteur") if carte.get(k)]
    homonymes = bool(fiche.homonymes) and fiche.homonymes.lower() not in ("aucun", "aucune", "non", "-")
    if not elements:
        fiche.alertes.append("L'offre ne donne ni ville, ni site web, ni secteur : impossible de vérifier l'identité.")
        return fiche
    if homonymes and len(elements) < 2:
        fiche.alertes.append(f"Homonymes rencontrés ({fiche.homonymes}) et un seul élément d'identification dans l'offre.")
        return fiche
    if carte.get("site_web"):
        domaine = _domaine(carte["site_web"])
        if domaine and not any(domaine in _domaine(u) for u in fiche.urls):
            fiche.alertes.append(f"Le site de l'offre ({domaine}) n'apparaît dans aucune page consultée.")
            return fiche
    if not fiche.resume:
        fiche.alertes.append("Résumé vide.")
        return fiche

    fiche.confiance = "haute"
    return fiche


async def rechercher_entreprise(offre: Offre) -> Fiche:
    carte = carte_identite(offre)
    systeme = (config.DOSSIER_PROMPTS / "entreprise.md").read_text(encoding="utf-8")
    texte, urls, requetes = await llm.appeler_avec_recherche(
        modele=config.MODELE_LEGER, system=systeme,
        user="Carte d'identité de l'entreprise :\n" + json.dumps(carte, ensure_ascii=False, indent=1),
        max_tokens=config.MAX_TOKENS_ENTREPRISE, max_recherches=config.MAX_RECHERCHES_ENTREPRISE,
    )
    fiche = analyser(texte, urls, carte)
    fiche.requetes = requetes
    return fiche


def en_markdown(offre: Offre, fiche: Fiche) -> str:
    statut = "identité confirmée" if fiche.confiance == "haute" else "⚠️ IDENTITÉ NON CONFIRMÉE : à relire avant tout usage"
    lignes = [f"# Fiche entreprise — {offre.entreprise}", "", f"**Contrôle d'identité :** {statut}", "",
              f"- Entreprise trouvée : {fiche.entite or '(inconnue)'}",
              f"- Source de confirmation : {fiche.source_identite or '(aucune)'}",
              f"- Homonymes croisés : {fiche.homonymes or '(non précisé)'}"]
    lignes += [f"- ! {a}" for a in fiche.alertes]
    lignes += ["", "## Résumé", "", fiche.resume or "(aucun)", "", "## Recherches effectuées", ""]
    lignes += [f"- {q}" for q in fiche.requetes] or ["- (aucune)"]
    lignes += ["", "## Pages consultées", ""]
    lignes += [f"- {u}" for u in fiche.urls] or ["- (aucune)"]
    return "\n".join(lignes) + "\n"
