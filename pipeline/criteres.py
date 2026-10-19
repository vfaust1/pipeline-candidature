"""Lecture de la section 6 de criteres.md.

Idée simple : le LLM ne décide jamais « cette offre est bonne ou mauvaise ».
Il se contente de LIRE l'annonce (étape 1). Ensuite, ce sont des règles Python,
alimentées par criteres.md, qui décident. Résultat : le même verdict à chaque fois,
et tu peux changer tes critères sans toucher au code.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


# --- Petits outils de normalisation ------------------------------------------

def norm_texte(texte: str) -> str:
    """minuscules, sans accents, ponctuation -> espaces.
    « Villeneuve-d'Ascq » et « villeneuve d ascq » deviennent identiques."""
    texte = texte.replace("œ", "oe").replace("Œ", "oe")
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c)).lower()
    texte = re.sub(r"[^a-z0-9]+", " ", texte)
    return texte.strip()


def norm_techno(texte: str) -> str:
    """« Next.js » -> « nextjs », « Java EE » -> « javaee »."""
    # « C# » et « C++ » perdraient leur symbole et deviendraient « c » : on les protège.
    texte = texte.replace("#", "sharp").replace("++", "plusplus")
    return norm_texte(texte).replace(" ", "")


def parse_mois(valeur: str | None) -> int | None:
    """« 2027-03 » -> un entier comparable (année*12 + mois-1). None si illisible."""
    if not valeur:
        return None
    m = re.match(r"^\s*(\d{4})-(\d{1,2})", str(valeur))
    if not m or not 1 <= int(m.group(2)) <= 12:
        return None
    return int(m.group(1)) * 12 + int(m.group(2)) - 1


def fmt_mois(indice: int) -> str:
    return f"{indice // 12}-{indice % 12 + 1:02d}"


# --- Les critères ------------------------------------------------------------

@dataclass
class Criteres:
    duree_semaines: int = 16
    tolerance_duree: int = 2
    stage_debut_min: int = 0
    stage_debut_max: int = 0
    stage_debut_ideal: int | None = None
    alternance_debut_min: int = 0
    alternance_debut_max: int = 0
    teletravail_max: float = 2
    teletravail_a_verifier_jusqua: float = 3
    villes_mel: set[str] = field(default_factory=set)
    villes_a_verifier: set[str] = field(default_factory=set)
    departements_a_verifier: set[str] = field(default_factory=set)
    technos_prioritaires: set[str] = field(default_factory=set)
    technos_proches: set[str] = field(default_factory=set)
    technos_adjacentes: set[str] = field(default_factory=set)
    technos_a_verifier: set[str] = field(default_factory=set)
    # Que faire quand l'annonce ne précise pas une information : « retenue » (acceptée, avec une note
    # dans le rapport) ou « a_verifier ».
    niveau_non_precise: str = "a_verifier"
    duree_non_precisee: str = "a_verifier"
    debut_non_precise: str = "a_verifier"
    teletravail_non_precise: str = "a_verifier"
    technos_hors_liste: str = "ecarter"      # ecarter | a_verifier
    duree_trop_longue: str = "a_verifier"    # a_verifier | ecarter


def _liste(valeur: str) -> list[str]:
    return [v.strip() for v in valeur.split(",") if v.strip()]


def charger(chemin: Path) -> Criteres:
    """Lit les lignes « - `clé` : valeur » situées après le titre « ## 6. »."""
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    debut = next((i for i, l in enumerate(lignes) if l.startswith("## 6.")), None)
    if debut is None:
        raise ValueError("criteres.md : la section « ## 6. Paramètres lus par le script » est introuvable.")

    brut: dict[str, str] = {}
    for ligne in lignes[debut + 1:]:
        m = re.match(r"^\s*[-*]?\s*`?([a-z_]+)`?\s*:\s*(.+?)\s*$", ligne)
        if m:
            brut[m.group(1)] = m.group(2)

    def mois(cle: str) -> int:
        valeur = parse_mois(brut.get(cle))
        if valeur is None:
            raise ValueError(f"criteres.md : « {cle} » manquant ou illisible (format AAAA-MM attendu).")
        return valeur

    c = Criteres()
    c.duree_semaines = int(brut.get("duree_semaines", 16))
    c.tolerance_duree = int(brut.get("tolerance_duree_semaines", 2))
    c.stage_debut_min = mois("stage_debut_min")
    c.stage_debut_max = mois("stage_debut_max")
    c.stage_debut_ideal = parse_mois(brut.get("stage_debut_ideal"))
    c.alternance_debut_min = mois("alternance_debut_min")
    c.alternance_debut_max = mois("alternance_debut_max")
    c.teletravail_max = float(brut.get("teletravail_max_jours", 2))
    c.teletravail_a_verifier_jusqua = float(brut.get("teletravail_a_verifier_jusqua", c.teletravail_max))
    c.villes_mel = {norm_texte(v) for v in _liste(brut.get("villes_mel", ""))}
    c.villes_a_verifier = {norm_texte(v) for v in _liste(brut.get("villes_a_verifier", ""))}
    c.departements_a_verifier = set(_liste(brut.get("departements_a_verifier", "")))
    c.technos_prioritaires = {norm_techno(t) for t in _liste(brut.get("technos_prioritaires", ""))}
    # Toutes les bases de données sont acceptées : elles comptent comme des technologies « proches ».
    c.technos_proches = {norm_techno(t) for t in _liste(brut.get("technos_proches", "")) + _liste(brut.get("bases_de_donnees", ""))}
    c.technos_adjacentes = {norm_techno(t) for t in _liste(brut.get("technos_adjacentes", ""))}
    c.technos_a_verifier = {norm_techno(t) for t in _liste(brut.get("technos_a_verifier", ""))}
    c.niveau_non_precise = brut.get("niveau_non_precise", "a_verifier")
    c.duree_non_precisee = brut.get("duree_non_precisee", "a_verifier")
    c.debut_non_precise = brut.get("debut_non_precise", "a_verifier")
    c.teletravail_non_precise = brut.get("teletravail_non_precise", "a_verifier")
    c.technos_hors_liste = brut.get("technos_hors_liste", "ecarter")
    c.duree_trop_longue = brut.get("duree_trop_longue", "a_verifier")
    if not c.villes_mel:
        raise ValueError("criteres.md : « villes_mel » est vide.")
    return c
