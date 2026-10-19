"""Étape 1 (mode manuel) : lire une annonce collée à la main, puis appliquer les règles.

Deux temps, volontairement séparés :
  1. extraire_offre() : le modèle LÉGER lit l'annonce et remplit une fiche de faits (coût minime).
  2. evaluer()        : du Python décide (regles.py), sans IA.
"""
from __future__ import annotations

import config

from . import llm
from .schemas import OFFRE_SCHEMA, Offre


async def extraire_offre(texte_annonce: str) -> Offre:
    if len(texte_annonce) > config.MAX_CARACTERES_OFFRE:
        raise ValueError(
            f"Annonce trop longue ({len(texte_annonce)} caractères, limite {config.MAX_CARACTERES_OFFRE}). "
            "Garde seulement le texte de l'offre ou augmente MAX_CARACTERES_OFFRE dans config.py."
        )
    systeme = (config.DOSSIER_PROMPTS / "extraction.md").read_text(encoding="utf-8")
    donnees = await llm.appeler(
        modele=config.MODELE_LEGER,
        system=systeme,
        user=f"Annonce :\n\n{texte_annonce}",
        max_tokens=config.MAX_TOKENS_EXTRACTION,
        effort="low",
        schema=OFFRE_SCHEMA,
    )
    return Offre.from_dict(donnees)
