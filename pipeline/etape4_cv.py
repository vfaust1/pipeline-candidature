"""Étape 4 : conseils pour adapter le CV à une offre.

Même principe que la lettre : le modèle renvoie des données structurées (une liste de conseils),
et c'est Python qui fabrique le fichier Markdown. Python vérifie aussi deux choses que le modèle
pourrait mal faire :
  1. chaque conseil s'appuie sur un extrait EXACT du CV (sinon il est marqué comme douteux) ;
  2. aucune technologie absente du CV n'apparaît dans les conseils.
"""
from __future__ import annotations

import json
import re

import config

from . import llm
from .criteres import norm_texte
from .etape3_lettre import _ABSENTES_DU_CV
from .schemas import CV_SCHEMA, Offre

_ORDRE = {"haute": 0, "moyenne": 1, "basse": 2}
_TITRES = {"haute": "Priorité haute", "moyenne": "Priorité moyenne", "basse": "Priorité basse"}


def _verifier(conseils: list[dict], cv: str) -> list[str]:
    """Renvoie des avertissements, et ajoute la clé « douteux » aux conseils non vérifiables."""
    alertes = []
    cv_norm = norm_texte(cv)
    for c in conseils:
        c["douteux"] = False
        appui = norm_texte(c["appui_cv"])
        if not appui or appui not in cv_norm:
            c["douteux"] = True
            alertes.append(f"Extrait de CV introuvable pour un conseil ({c['section_cv']}) : à ignorer ou vérifier.")
        texte = (c["modification"] + " " + c["justification_offre"]).lower()
        for techno in _ABSENTES_DU_CV:
            if re.search(rf"(?<![a-z0-9]){re.escape(techno)}(?![a-z0-9])", c["modification"].lower()):
                c["douteux"] = True
                alertes.append(f"« {techno} » est dans un conseil mais pas dans ton CV : ne l'ajoute pas ({c['section_cv']}).")
                break
    return alertes


def _en_markdown(offre: Offre, resultat: dict) -> str:
    conseils = sorted(resultat["conseils"], key=lambda c: _ORDRE[c["priorite"]])
    lignes = [f"# Conseils CV — {offre.intitule} ({offre.entreprise})", ""]
    numero = 0
    for priorite in ("haute", "moyenne", "basse"):
        groupe = [c for c in conseils if c["priorite"] == priorite]
        if not groupe:
            continue
        lignes += [f"## {_TITRES[priorite]}", ""]
        for c in groupe:
            numero += 1
            drapeau = " ⚠️ à vérifier" if c.get("douteux") else ""
            lignes += [
                f"{numero}. **[{c['type']}] {c['section_cv']}**{drapeau} — {c['modification']}",
                f"   - Justifié par l'offre : {c['justification_offre']}",
                f"   - Appui dans ton CV : « {c['appui_cv']} »",
                "",
            ]
    if resultat["points_non_couverts"]:
        lignes += ["## Exigences de l'offre absentes de ton CV (ne rien ajouter)", ""]
        lignes += [f"- {p}" for p in resultat["points_non_couverts"]]
        lignes.append("")
    return "\n".join(lignes)


async def conseils_cv(offre: Offre, cv: str) -> tuple[str, list[str]]:
    """Renvoie (conseils en Markdown, avertissements)."""
    offre_resumee = {
        "intitule": offre.intitule, "entreprise": offre.entreprise, "domaine": offre.domaine,
        "technologies": offre.technologies, "competences_cles": offre.competences_cles,
        "resume_mission": offre.resume_mission,
    }
    utilisateur = (f"OFFRE (résumée) :\n{json.dumps(offre_resumee, ensure_ascii=False, indent=1)}\n\n"
                   f"MON CV :\n{cv}")
    systeme = (config.DOSSIER_PROMPTS / "cv.md").read_text(encoding="utf-8")
    resultat = await llm.appeler(
        modele=config.MODELE_CONSEILS_CV, system=systeme, user=utilisateur,
        max_tokens=config.MAX_TOKENS_CV, effort="medium", schema=CV_SCHEMA,
    )
    alertes = _verifier(resultat["conseils"], cv)
    return _en_markdown(offre, resultat), alertes
