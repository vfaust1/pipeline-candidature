"""Les « formes » de données échangées entre les étapes.

Offre   : ce que le modèle léger extrait d'une annonce (que des faits, pas d'avis).
Verdict : ce que les règles Python décident ensuite (retenue, à vérifier, ...).
Les étapes suivantes ne reçoivent QUE ces objets, jamais la page web brute.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields


@dataclass
class Offre:
    intitule: str = ""
    entreprise: str = ""
    reference: str | None = None
    lien: str | None = None
    type_contrat: str = "inconnu"        # stage | alternance | stage_ou_alternance | autre | inconnu
    lieux: list[str] = field(default_factory=list)
    departement: str | None = None       # ex. "59"
    adresse_entreprise: str | None = None
    site_entreprise: str | None = None      # ex. « capgemini.com » : sert à identifier la bonne entreprise
    secteur_entreprise: str | None = None   # ex. « services numériques » : idem
    debut_au_plus_tot: str | None = None   # AAAA-MM
    debut_au_plus_tard: str | None = None  # AAAA-MM
    debut_flou: bool = False
    duree_min_semaines: float | None = None
    duree_max_semaines: float | None = None
    niveau_min_bac: int | None = None
    niveau_max_bac: int | None = None
    teletravail_complet: bool | None = None
    teletravail_jours_min: float | None = None   # par semaine
    teletravail_jours_max: float | None = None
    teletravail_sans_chiffre: bool = False
    domaine: str = "inconnu"             # web | application | mobile | autre | inconnu
    technologies: list[str] = field(default_factory=list)
    produit_propre: bool | None = None
    missions_concretes: bool | None = None
    equipe_identifiable: bool | None = None
    competences_cles: list[str] = field(default_factory=list)
    resume_mission: str = ""
    service: str | None = None
    contact_nom: str | None = None
    contact_nom_famille: str | None = None
    contact_civilite: str | None = None  # "Madame" / "Monsieur", seulement si écrit dans l'annonce

    @classmethod
    def from_dict(cls, d: dict) -> "Offre":
        noms = {f.name for f in fields(cls)}
        propre = {k: v for k, v in d.items() if k in noms}
        # Chaîne vide = information absente (voir la remarque sur _S plus bas).
        for f in fields(cls):
            if f.default is None and propre.get(f.name) == "":
                propre[f.name] = None
        return cls(**propre)


@dataclass
class Verdict:
    statut: str                          # retenue | a_verifier | ecartee | veille_alternance
    raisons_ecart: list[str] = field(default_factory=list)
    points_a_verifier: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    score: int = 0                       # sert uniquement à classer les offres


# --- Schéma JSON donné à l'API pour obtenir une réponse bien structurée -------

def _nul(type_json: str) -> dict:
    return {"anyOf": [{"type": type_json}, {"type": "null"}]}


# L'API limite à 16 champs « nullable » par schéma. Pour les textes, on demande donc une
# chaîne vide quand l'info est absente (from_dict la retransforme en None).
# Seuls les nombres et certains booléens restent vraiment nullables (10 au total).
_S = {"type": "string"}
_I, _N, _B = _nul("integer"), _nul("number"), _nul("boolean")
_L = {"type": "array", "items": {"type": "string"}}

_PROPRIETES = {
    "intitule": {"type": "string"},
    "entreprise": {"type": "string"},
    "reference": _S,
    "lien": _S,
    "type_contrat": {"type": "string", "enum": ["stage", "alternance", "stage_ou_alternance", "autre", "inconnu"]},
    "lieux": _L,
    "departement": _S,
    "adresse_entreprise": _S,
    "site_entreprise": _S,
    "secteur_entreprise": _S,
    "debut_au_plus_tot": _S,
    "debut_au_plus_tard": _S,
    "debut_flou": {"type": "boolean"},
    "duree_min_semaines": _N,
    "duree_max_semaines": _N,
    "niveau_min_bac": _I,
    "niveau_max_bac": _I,
    "teletravail_complet": _B,
    "teletravail_jours_min": _N,
    "teletravail_jours_max": _N,
    "teletravail_sans_chiffre": {"type": "boolean"},
    "domaine": {"type": "string", "enum": ["web", "application", "mobile", "autre", "inconnu"]},
    "technologies": _L,
    "produit_propre": _B,
    "missions_concretes": _B,
    "equipe_identifiable": _B,
    "competences_cles": _L,
    "resume_mission": {"type": "string"},
    "service": _S,
    "contact_nom": _S,
    "contact_nom_famille": _S,
    "contact_civilite": _S,
}

OFFRE_SCHEMA = {
    "type": "object",
    "properties": _PROPRIETES,
    "required": list(_PROPRIETES),
    "additionalProperties": False,
}

CV_SCHEMA = {
    "type": "object",
    "properties": {
        "conseils": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "priorite": {"type": "string", "enum": ["haute", "moyenne", "basse"]},
                    "type": {"type": "string", "enum": ["mot_cle", "mise_en_avant", "reformulation", "ordre"]},
                    "section_cv": {"type": "string"},
                    "modification": {"type": "string"},
                    "justification_offre": {"type": "string"},
                    "appui_cv": {"type": "string"},
                },
                "required": ["priorite", "type", "section_cv", "modification", "justification_offre", "appui_cv"],
                "additionalProperties": False,
            },
        },
        "points_non_couverts": _L,
    },
    "required": ["conseils", "points_non_couverts"],
    "additionalProperties": False,
}

LETTRE_SCHEMA = {
    "type": "object",
    "properties": {
        "phrase_activite": {"type": "string"},
        "raison_offre": {"type": "string"},
        "phrase_valeur": {"type": "string"},
        "projet_choisi": {"type": "string"},   # restreint aux projets du CV par schema_lettre()
        "phrase_projet": {"type": "string"},
        "phrase_lien_profil": {"type": "string"},
        "equipe_ou_projet_vise": {"type": "string"},
    },
    "required": [
        "phrase_activite", "raison_offre", "phrase_valeur", "projet_choisi",
        "phrase_projet", "phrase_lien_profil", "equipe_ou_projet_vise",
    ],
    "additionalProperties": False,
}


def schema_lettre(projets: list[str]) -> dict:
    """Le schéma de la lettre, avec le choix du projet limité aux projets réellement listés dans le CV."""
    schema = copy.deepcopy(LETTRE_SCHEMA)
    if projets:
        schema["properties"]["projet_choisi"] = {"type": "string", "enum": list(projets)}
    return schema
