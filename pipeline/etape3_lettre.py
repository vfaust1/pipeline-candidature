"""Étape 3 : lettre de motivation.

Choix de conception important : le modèle puissant n'écrit PAS la lettre entière.
Il remplit seulement les quelques phrases variables (les {{ }} créatifs). Python
insère ces phrases dans ton modèle. Avantages :
  - ton texte fixe n'est jamais modifié, même par accident ;
  - on paie beaucoup moins de tokens de sortie ;
  - les infos factuelles (date, entreprise, référence, civilité) sont gérées par le code,
    donc jamais inventées : si elles manquent, une mention [entre crochets] apparaît.
"""
from __future__ import annotations

import datetime
import json
import re

import config

from . import llm
from .criteres import norm_texte
from .schemas import Offre, schema_lettre

_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
         "août", "septembre", "octobre", "novembre", "décembre"]

# Technologies courantes ABSENTES de ton CV : si l'une apparaît dans les phrases générées,
# on affiche un avertissement (le modèle a peut-être prétendu maîtriser quelque chose).
_ABSENTES_DU_CV = ["python", "c#", ".net", "php", "laravel", "symfony", "angular", "vue", "kotlin", "swift",
                   "flutter", "react native", "spring", "docker", "kubernetes", "aws", "azure", "mongodb",
                   "mysql", "django", "c++", "ruby", "rust", "jenkins", "terraform", "golang"]
_MAX_MOTS = 430   # ordre de grandeur pour tenir sur une page


def _date_fr(d: datetime.date) -> str:
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {_MOIS[d.month - 1]} {d.year}"


def _ou_crochets(valeur: str | None, libelle: str) -> str:
    return valeur.strip() if valeur and valeur.strip() else f"[{libelle} — à compléter]"


def _intitule_propre(intitule: str) -> str:
    """« Développeuse / Développeur Fullstack - Stage » -> « développeuse / développeur Fullstack ».
    Le modèle de lettre dit déjà « stage de ... » : on retire donc « stage » et « (H/F) » de l'intitulé."""
    s = re.sub(r"\(?\b[hf]\s*/\s*[hf]\b\)?", "", intitule, flags=re.I)
    s = re.sub(r"\s*[-–—|:,]\s*(stage|stagiaire)\b.*$", "", s, flags=re.I)
    s = re.sub(r"^\s*(stage|stagiaire)\s*(d['’]|de\s+)?\s*[-–—:]?\s*", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" -–—|:,")
    if len(s) > 1 and s[0].isupper() and s[1].islower():   # « Développeur » -> « développeur » (après « stage de »)
        s = s[0].lower() + s[1:]
    s = re.sub(r"(/\s*)([A-ZÀ-Ý])(?=[a-zà-ÿ])", lambda m: m.group(1) + m.group(2).lower(), s)   # « / Développeur »
    return s or intitule


def _salutation(offre: Offre) -> str:
    # La civilité vient UNIQUEMENT de l'annonce (jamais déduite d'un prénom).
    if offre.contact_civilite in ("Madame", "Monsieur") and offre.contact_nom_famille:
        return f"{offre.contact_civilite} {offre.contact_nom_famille.strip()}"
    return "Madame, Monsieur"


def _cle_slot(contenu: str) -> str:
    """Reconnaît un {{...}} du modèle à partir de son début."""
    n = norm_texte(contenu)
    table = [
        ("nom entreprise", "entreprise"), ("service ou nom", "destinataire"), ("adresse", "adresse"),
        ("date du jour", "date"), ("intitule", "intitule"), ("ref", "reference"), ("madame", "salutation"),
        ("phrase sur l activite", "phrase_activite"), ("raison precise", "raison_offre"),
        ("phrase sur une valeur", "phrase_valeur"), ("projet lie", "phrase_projet"),
        ("phrase faisant le lien", "phrase_lien_profil"), ("de l equipe", "equipe_ou_projet_vise"),
    ]
    for debut, cle in table:
        if n.startswith(debut):
            return cle
    raise KeyError(f"Emplacement inconnu dans modele_lettre.md : {{{{{contenu}}}}}")


def _remplir(modele: str, valeurs: dict[str, str]) -> str:
    def remplacer(m: re.Match) -> str:
        return valeurs[_cle_slot(m.group(1))]
    texte = re.sub(r"\{\{(.+?)\}\}", remplacer, modele)
    texte = re.sub(r"(?<=\S)  +", " ", texte)      # espaces doubles (référence absente)
    texte = re.sub(r"[ \t]+\n", "\n", texte)       # espaces en fin de ligne
    return texte


def projets_du_cv(cv: str) -> list[str]:
    """Noms des projets du CV : les titres « ### NOM | type » de la section « ## Projets »."""
    section = re.search(r"^##\s*Projets\s*$(.*?)(?=^##\s|\Z)", cv, re.M | re.S)
    if not section:
        return []
    noms = re.findall(r"^###\s*(.+?)\s*(?:\|.*)?$", section.group(1), re.M)
    return [n.strip() for n in noms if n.strip()]


def _nom_affiche(nom: str) -> str:
    """Comment écrire un nom de projet dans la lettre (tableau NOMS_PROJETS_AFFICHES de config.py)."""
    if nom.upper() in config.NOMS_PROJETS_AFFICHES:
        return config.NOMS_PROJETS_AFFICHES[nom.upper()]
    return nom.capitalize() if nom.isupper() else nom


def _noms_projets(texte: str, projets: list[str]) -> str:
    """Remet en forme les noms de projets du CV cités dans le texte généré (« ECODROP » -> « EcoDrop »)."""
    if not projets:
        return texte
    par_majuscules = {p.upper(): p for p in projets}
    motif = r"(?<!\w)(" + "|".join(re.escape(p) for p in sorted(projets, key=len, reverse=True)) + r")(?!\w)"

    def remplacer(m: re.Match) -> str:
        nom = _nom_affiche(par_majuscules[m.group(1).upper()])
        return nom[0].upper() + nom[1:] if m.start() == 0 else nom   # majuscule en début de phrase
    return re.sub(motif, remplacer, texte, flags=re.IGNORECASE)


def _sans_point(s: str) -> str:
    return s.strip().rstrip(" .")


# Longueur maximale (en mots) de chaque phrase générée, comme annoncé au modèle dans prompts/lettre.md.
_LIMITES_MOTS = {"phrase_activite": 30, "raison_offre": 35, "phrase_valeur": 30, "phrase_projet": 35,
                 "phrase_lien_profil": 40, "equipe_ou_projet_vise": 15}


def _controler_phrases(ia: dict) -> list[str]:
    """Le modèle peut dépasser une consigne : on le vérifie en Python plutôt que de lui faire confiance."""
    alertes = []
    for cle, limite in _LIMITES_MOTS.items():
        mots = len(ia[cle].split())
        if mots > limite:
            alertes.append(f"« {cle} » est trop longue ({mots} mots, limite {limite}) : à raccourcir à la main.")
    if "," in ia["equipe_ou_projet_vise"]:
        alertes.append("« equipe_ou_projet_vise » contient une virgule : relis la phrase « au service de ... et continuer à progresser ».")
    return alertes


def _controler(lettre: str, projets: list[str], textes_ia: list[str]) -> list[str]:
    alertes = []
    if "{{" in lettre or "}}" in lettre:
        alertes.append("Il reste des accolades {{ }} dans la lettre.")
    mots = len(lettre.split())
    if mots > _MAX_MOTS:
        alertes.append(f"Lettre longue ({mots} mots) : elle risque de dépasser une page.")
    cites = [p for p in projets if re.search(rf"(?<!\w){re.escape(_nom_affiche(p))}(?!\w)", lettre, re.IGNORECASE)]
    if len(cites) > 1:
        alertes.append(f"Plus d'un projet du CV cité ({', '.join(cites)}) : la règle est maximum 2 projets au total, "
                       "en comptant celui du stage déjà raconté dans le modèle.")
    ia = " ".join(textes_ia).lower()
    for techno in _ABSENTES_DU_CV:
        if re.search(rf"(?<![a-z0-9]){re.escape(techno)}(?![a-z0-9])", ia):
            alertes.append(f"« {techno} » apparaît dans les phrases générées mais n'est pas dans ton CV : à vérifier ou supprimer.")
    manquants = re.findall(r"\[[^\]]+à compléter\]", lettre)
    if manquants:
        alertes.append("Informations à compléter à la main : " + " ; ".join(sorted(set(manquants))))
    return alertes


async def rediger_lettre(offre: Offre, fiche_entreprise: str | None, cv: str, modele_lettre: str,
                         aujourdhui: datetime.date | None = None) -> tuple[str, list[str]]:
    """Renvoie (lettre, avertissements)."""
    aujourdhui = aujourdhui or datetime.date.today()

    # Ce que le modèle puissant voit : l'offre RÉSUMÉE (pas l'annonce brute), la fiche entreprise, le CV.
    offre_resumee = {
        "intitule": offre.intitule, "entreprise": offre.entreprise, "domaine": offre.domaine,
        "technologies": offre.technologies, "competences_cles": offre.competences_cles,
        "resume_mission": offre.resume_mission,
    }
    projets = projets_du_cv(cv)   # lus dans la section « ## Projets » du CV
    liste_projets = " ; ".join(projets) if projets else "(aucun projet listé dans le CV)"
    utilisateur = (
        f"OFFRE (résumée) :\n{json.dumps(offre_resumee, ensure_ascii=False, indent=1)}\n\n"
        f"FICHE ENTREPRISE :\n{fiche_entreprise or '(aucune information supplémentaire)'}\n\n"
        f"PROJETS DU CV (projet_choisi doit être l'un d'eux, écrit exactement ainsi) : {liste_projets}\n\n"
        f"MON CV :\n{cv}"
    )
    systeme = (config.DOSSIER_PROMPTS / "lettre.md").read_text(encoding="utf-8")
    ia = await llm.appeler(
        modele=config.MODELE_PUISSANT, system=systeme, user=utilisateur,
        max_tokens=config.MAX_TOKENS_LETTRE, effort="medium", schema=schema_lettre(projets),
    )

    ia = {cle: (_noms_projets(v, projets) if isinstance(v, str) and cle != "projet_choisi" else v)
          for cle, v in ia.items()}
    phrase_projet = ia["phrase_projet"].strip()
    if not phrase_projet.endswith((".", "!", "?")):
        phrase_projet += "."

    reference = f"(Réf. {offre.reference.strip()})" if offre.reference and offre.reference.strip() else ""
    destinataire = offre.contact_nom or offre.service
    valeurs = {
        "entreprise": _ou_crochets(offre.entreprise, "Nom de l'entreprise"),
        "destinataire": _ou_crochets(destinataire, "Nom du recruteur ou service"),
        "adresse": _ou_crochets(offre.adresse_entreprise, "Adresse de l'entreprise"),
        "date": _date_fr(aujourdhui),
        "intitule": _ou_crochets(_intitule_propre(offre.intitule), "Intitulé du poste"),
        "reference": reference,
        "salutation": _salutation(offre),
        "phrase_activite": _sans_point(ia["phrase_activite"]),
        "raison_offre": _sans_point(ia["raison_offre"]),
        "phrase_valeur": _sans_point(ia["phrase_valeur"]),
        "phrase_projet": phrase_projet,
        "phrase_lien_profil": _sans_point(ia["phrase_lien_profil"]),
        "equipe_ou_projet_vise": _sans_point(ia["equipe_ou_projet_vise"]),
    }
    lettre = _remplir(modele_lettre, valeurs)
    textes_ia = [ia[k] for k in ("phrase_activite", "raison_offre", "phrase_valeur", "phrase_projet",
                                 "phrase_lien_profil", "equipe_ou_projet_vise")]
    return lettre, _controler_phrases(ia) + _controler(lettre, projets, textes_ia)
