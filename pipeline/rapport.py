"""Écrit sorties/AAAA-MM-JJ/rapport.md à partir des résultats du tri."""
from __future__ import annotations

import datetime
import re
import unicodedata
from pathlib import Path

import config

from .etape1_recherche import Resultat, Stats
from .schemas import Offre

_SECTIONS = [
    ("retenue", "Retenues"),
    ("a_verifier", "À vérifier"),
    ("veille_alternance", "Veille alternance"),
    ("ecartee", "Écartées"),
]


def _intervalle(a, b, unite: str = "") -> str:
    if a is None and b is None:
        return "non précisé"
    if a is None or b is None or a == b:
        return f"{(a if a is not None else b):g}{unite}"
    return f"{a:g}–{b:g}{unite}"


def _niveau(o: Offre) -> str:
    a, b = o.niveau_min_bac, o.niveau_max_bac
    if a is None and b is None:
        return "non précisé"
    if a == b or b is None or a is None:
        return f"Bac+{a if a is not None else b}"
    return f"Bac+{a} à Bac+{b}"


def _teletravail(o: Offre) -> str:
    if o.teletravail_complet:
        return "complet"
    if o.teletravail_jours_min is None and o.teletravail_jours_max is None:
        return "mentionné sans nombre de jours" if o.teletravail_sans_chiffre else "non précisé"
    return _intervalle(o.teletravail_jours_min, o.teletravail_jours_max, " j/semaine")


def _debut(o: Offre) -> str:
    a, b = o.debut_au_plus_tot, o.debut_au_plus_tard
    if a and b:
        return a if a == b else f"{a} → {b}"
    if a or b:
        return f"à partir de {a}" if a else f"avant {b}"
    return "non précisé" + (" (dès que possible ?)" if o.debut_flou else "")


def _ligne_lien(o: Offre, statut: str) -> str:
    if statut == "manuel":
        return f"- Lien : {o.lien or '(non fourni)'} (annonce déposée par toi)"
    if statut == "vivante":
        return f"- Lien : {o.lien} (vérifié : page en ligne)"
    return f"- Lien : {o.lien} (non vérifiable automatiquement : ouvre-le pour confirmer que l'offre est active)"


def _bloc(r: Resultat, fichier: str | None) -> str:
    o, v = r.offre, r.verdict
    lignes = [f"### {o.intitule or '(sans titre)'} — {o.entreprise or '(entreprise inconnue)'}",
              f"- Ville : {', '.join(o.lieux) or 'non précisée'}",
              f"- Début : {_debut(o)} · Durée : {_intervalle(o.duree_min_semaines, o.duree_max_semaines, ' sem.')}",
              f"- Niveau : {_niveau(o)} · Télétravail : {_teletravail(o)}",
              f"- Technologies : {', '.join(o.technologies) or 'non précisées'}",
              _ligne_lien(o, r.candidat.lien_statut)]
    if r.candidat.publiee:
        lignes.append(f"- Publiée le : {r.candidat.publiee.isoformat()}")
    if v.statut == "ecartee":
        lignes.append("- Raison de l'élimination : " + " ; ".join(v.raisons_ecart))
    else:
        raison = "respecte tous les critères éliminatoires" if v.statut == "retenue" else "voir les points ci-dessous"
        if v.statut == "veille_alternance":
            raison = "alternance rangée à part (début rentrée 2027)"
        lignes.append(f"- Raison de la sélection : {raison} · score de préférence {v.score}")
        lignes += [f"- À vérifier : {p}" for p in v.points_a_verifier]
    lignes += [f"- Note : {n}" for n in v.notes]
    if fichier:
        lignes.append(f"- Pour préparer la candidature : `python main.py candidature {fichier}`")
    return "\n".join(lignes)


def _slug(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texte.lower()).strip("-")[:35] or "offre"


def ecrire(dossier: Path, resultats: list[Resultat], stats: Stats, cout_eur: float, mode: str = "recherche") -> Path:
    """Écrit le rapport et, pour chaque offre à regarder, un fichier .txt utilisable avec `main.py candidature`."""
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "offres").mkdir(exist_ok=True)
    fichiers: dict[int, str] = {}
    for i, r in enumerate(resultats, 1):
        if r.verdict.statut in ("retenue", "a_verifier"):
            chemin = dossier / "offres" / f"{i:02d}_{_slug(r.offre.entreprise)}.txt"
            entete = f"Lien : {r.candidat.url}\n\n" if r.candidat.url and r.candidat.url not in r.candidat.texte else ""
            chemin.write_text(f"{entete}{r.candidat.texte}\n", encoding="utf-8")
            try:
                affiche = chemin.relative_to(config.RACINE)   # chemin court, relatif au projet
            except ValueError:
                affiche = chemin
            fichiers[id(r)] = str(affiche).replace("\\", "/")

    titre_rapport = "Rapport de tri (annonces déposées)" if mode == "lot" else "Rapport de recherche"
    lignes = [f"# {titre_rapport} — {datetime.date.today().isoformat()}", "",
              f"{stats.analysees} offre(s) analysée(s) · coût estimé {cout_eur:.3f} €", ""]
    for statut, titre in _SECTIONS:
        # Les offres avec le moins de points à vérifier d'abord, puis par score de préférence.
        groupe = sorted((r for r in resultats if r.verdict.statut == statut),
                        key=lambda r: (len(r.verdict.points_a_verifier), -r.verdict.score))
        lignes += [f"## {titre} ({len(groupe)})", ""]
        if not groupe:
            lignes += ["_Aucune._", ""]
        for r in groupe:
            lignes += [_bloc(r, fichiers.get(id(r))), ""]

    if mode == "lot":
        stat_lignes = [f"- Annonces lues dans le dossier : {stats.trouvees}",
                       f"- Déjà traitées lors d'un lancement précédent : {stats.deja_vues}",
                       f"- Doublons (même offre republiée ou sur un autre site) : {stats.doublons}",
                       f"- Non analysées (plafond de budget) : {stats.non_analysees_budget}"]
    else:
        stat_lignes = [f"- Offres trouvées par la recherche : {stats.trouvees}",
                       f"- Adresses non vérifiées (ignorées) : {stats.url_non_verifiee}",
                       f"- Trop anciennes (plus de 30 jours) : {stats.trop_anciennes}",
                       f"- Déjà vues lors d'un lancement précédent : {stats.deja_vues}",
                       f"- Doublons (même offre republiée ou sur un autre site) : {stats.doublons}",
                       f"- Liens morts (offre expirée ou 404), ignorés : {stats.liens_morts}",
                       f"- Liens non vérifiables automatiquement (gardés) : {stats.liens_non_verifiables}",
                       f"- Non analysées (plafond de budget) : {stats.non_analysees_budget}"]
    lignes += ["## Statistiques du lancement", ""] + stat_lignes
    if stats.requetes:
        lignes += ["", "## Requêtes web envoyées", ""] + [f"- {q}" for q in stats.requetes]
    lignes += [f"- Erreur : {e}" for e in stats.erreurs]
    chemin_rapport = dossier / "rapport.md"
    chemin_rapport.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return chemin_rapport
