"""Point d'entrée. C'est CE script qui orchestre les étapes (pas un agent « chef »).

Utilisation (voir README.md) :
    python main.py tri    offre.txt
    python main.py lettre offre.txt --entreprise-fichier fiche.txt
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import re
import sys
import unicodedata
from dataclasses import asdict
from pathlib import Path

import config
from pipeline import (criteres, etape1_lot, etape1_offres, etape1_recherche, etape2_entreprise, etape3_lettre,
                      etape4_cv, llm, rapport, regles)
from pipeline.schemas import Verdict

LIBELLES = {
    "retenue": "RETENUE",
    "a_verifier": "À VÉRIFIER",
    "ecartee": "ÉCARTÉE",
    "veille_alternance": "VEILLE ALTERNANCE",
}


def slug(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texte.lower()).strip("-")[:40] or "offre"


def afficher_verdict(offre, verdict: Verdict) -> None:
    print(f"\n{offre.intitule} — {offre.entreprise}")
    print(f"Verdict : {LIBELLES[verdict.statut]}   (score de préférence : {verdict.score})")
    for r in verdict.raisons_ecart:
        print(f"  ✗ {r}")
    for p in verdict.points_a_verifier:
        print(f"  ? {p}")
    for n in verdict.notes:
        print(f"  • {n}")


def dossier_sortie(entreprise: str) -> Path:
    jour = config.DOSSIER_SORTIES / datetime.date.today().isoformat()
    jour.mkdir(parents=True, exist_ok=True)
    numero = len([d for d in jour.iterdir() if d.is_dir()]) + 1
    dossier = jour / f"{numero:02d}_{slug(entreprise)}"
    dossier.mkdir()
    return dossier


async def faire_lettre(args: argparse.Namespace, offre, cv: str, dossier: Path) -> None:
    """Étape 2 (fiche entreprise) puis étape 3 (lettre) : la lettre a besoin de la fiche, donc dans cet ordre."""
    fiche = args.entreprise
    if args.entreprise_fichier:
        fiche = Path(args.entreprise_fichier).read_text(encoding="utf-8")
    if not fiche and not args.sans_recherche:
        # Étape 2 : recherche web sur l'entreprise, avec contrôle d'identité.
        resultat = await etape2_entreprise.rechercher_entreprise(offre)
        (dossier / "entreprise.md").write_text(etape2_entreprise.en_markdown(offre, resultat), encoding="utf-8")
        if resultat.confiance == "haute":
            fiche = resultat.resume
            print(f"\nEntreprise identifiée : {resultat.entite}")
        else:
            print(f"\n! Identité de l'entreprise NON confirmée ({' '.join(resultat.alertes)})")
            print(f"  La lettre est écrite sans la fiche ; relis {dossier / 'entreprise.md'}.")
    modele = config.FICHIER_MODELE_LETTRE.read_text(encoding="utf-8")
    lettre, alertes = await etape3_lettre.rediger_lettre(offre, fiche, cv, modele)
    (dossier / "lettre.md").write_text(lettre, encoding="utf-8")
    print(f"\nLettre écrite : {dossier / 'lettre.md'}")
    for a in alertes:
        print(f"  ! {a}")


async def faire_conseils_cv(offre, cv: str, dossier: Path) -> None:
    conseils, alertes = await etape4_cv.conseils_cv(offre, cv)
    (dossier / "conseils_cv.md").write_text(conseils, encoding="utf-8")
    print(f"\nConseils CV écrits : {dossier / 'conseils_cv.md'}")
    for a in alertes:
        print(f"  ! {a}")


async def recherche(args: argparse.Namespace) -> None:
    """Étape 1 automatique : chercher des offres, trier, écrire le rapport."""
    c = criteres.charger(config.FICHIER_CRITERES)
    vues = etape1_recherche.OffresVues(config.FICHIER_OFFRES_VUES)
    stats = etape1_recherche.Stats()

    candidats = await etape1_recherche.rechercher(c, args.max_recherches, args.max_offres, stats, vues)
    resultats = await etape1_recherche.analyser(candidats, c, vues, args.max_offres, stats)
    vues.sauver()   # sauvegardé même si le rapport échoue ensuite : on ne repaie pas les mêmes offres

    dossier = config.DOSSIER_SORTIES / datetime.date.today().isoformat() / f"recherche_{datetime.datetime.now():%H%M}"
    rapport_md = rapport.ecrire(dossier, resultats, stats, llm.COMPTEUR.cout_eur())
    compte = {s: sum(1 for r in resultats if r.verdict.statut == s) for s in LIBELLES}
    print("\n" + " · ".join(f"{LIBELLES[s]} : {n}" for s, n in compte.items()))
    print(f"Rapport : {rapport_md}")
    print("Requêtes web envoyées :\n" + "\n".join(f"  - {q}" for q in stats.requetes))
    for e in stats.erreurs:
        print(f"  ! {e}")
    print(f"\nConsommation :\n{llm.COMPTEUR.resume()}")


AIDE_LOT = """Dépose tes annonces dans ce dossier, au format .txt :
  - une annonce par fichier, ou plusieurs dans un même fichier séparées par une ligne contenant seulement ===
  - copie tout le texte de l'annonce ; mets le lien de la page sur la première ligne si tu l'as
Puis lance :  python main.py lot
Une annonce déjà traitée n'est jamais repayée, même si tu la laisses dans le dossier."""


async def lot(args: argparse.Namespace) -> None:
    """Étape 1 en mode lot : trier les annonces déposées dans un dossier."""
    dossier_entree = Path(args.dossier)
    if not dossier_entree.exists():
        dossier_entree.mkdir(parents=True)
        (dossier_entree / "LISEZ-MOI.txt").write_text(AIDE_LOT + "\n", encoding="utf-8")
        print(f"Dossier créé : {dossier_entree}\n\n{AIDE_LOT}")
        return
    annonces = etape1_lot.lire_dossier(dossier_entree)
    if not annonces:
        print(f"Aucune annonce trouvée dans {dossier_entree}\n\n{AIDE_LOT}")
        return

    c = criteres.charger(config.FICHIER_CRITERES)
    vues = etape1_recherche.OffresVues(config.FICHIER_OFFRES_VUES)
    stats = etape1_recherche.Stats()
    resultats = await etape1_lot.traiter_lot(annonces, c, vues, args.max_offres, stats, retraiter=args.retraiter)
    vues.sauver()

    dossier = config.DOSSIER_SORTIES / datetime.date.today().isoformat() / f"lot_{datetime.datetime.now():%H%M}"
    rapport_md = rapport.ecrire(dossier, resultats, stats, llm.COMPTEUR.cout_eur(), mode="lot")
    compte = {s: sum(1 for r in resultats if r.verdict.statut == s) for s in LIBELLES}
    print("\n" + " · ".join(f"{LIBELLES[s]} : {n}" for s, n in compte.items()))
    print(f"Annonces lues : {stats.trouvees} · déjà traitées : {stats.deja_vues} · doublons : {stats.doublons}")
    print(f"Rapport : {rapport_md}")
    for e in stats.erreurs:
        print(f"  ! {e}")
    print(f"\nConsommation :\n{llm.COMPTEUR.resume()}")


async def traiter(args: argparse.Namespace) -> None:
    c = criteres.charger(config.FICHIER_CRITERES)
    texte = Path(args.offre).read_text(encoding="utf-8")

    # Étape 1 : modèle léger (extraction) puis règles Python (verdict).
    offre = await etape1_offres.extraire_offre(texte)
    verdict = regles.evaluer(offre, c)
    afficher_verdict(offre, verdict)

    dossier = dossier_sortie(offre.entreprise)
    (dossier / "offre.json").write_text(json.dumps(asdict(offre), ensure_ascii=False, indent=2), encoding="utf-8")
    (dossier / "verdict.json").write_text(json.dumps(asdict(verdict), ensure_ascii=False, indent=2), encoding="utf-8")

    if args.commande in ("lettre", "cv", "candidature"):
        if verdict.statut in ("ecartee", "veille_alternance") and not args.forcer:
            print("\nOffre écartée ou en veille : rien n'est rédigé (utilise --forcer pour passer outre).")
        else:
            cv = config.FICHIER_CV.read_text(encoding="utf-8")
            taches = []
            # Les étapes 3 et 4 ne dépendent que de l'offre : on les lance EN PARALLÈLE.
            if args.commande in ("lettre", "candidature"):
                taches.append(faire_lettre(args, offre, cv, dossier))
            if args.commande in ("cv", "candidature"):
                taches.append(faire_conseils_cv(offre, cv, dossier))
            # return_exceptions : si une tâche échoue, l'autre va jusqu'au bout et on affiche le coût.
            for echec in await asyncio.gather(*taches, return_exceptions=True):
                if isinstance(echec, Exception):
                    print(f"\n! Une étape a échoué : {echec}")

    print(f"\nDossier : {dossier}\nConsommation :\n{llm.COMPTEUR.resume()}")


def main() -> None:
    # Pour que les accents et les symboles s'affichent bien dans le terminal Windows.
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Pipeline de candidature")
    sous = parser.add_subparsers(dest="commande", required=True)

    p_tri = sous.add_parser("tri", help="lit une annonce et donne le verdict (très peu coûteux)")
    p_tri.add_argument("offre", help="fichier texte contenant l'annonce collée")

    p_rech = sous.add_parser("recherche", help="cherche des offres récentes, les trie et écrit un rapport")
    p_rech.add_argument("--max-recherches", type=int, default=config.MAX_RECHERCHES_PAR_LANCEMENT,
                        help="nombre de recherches web (≈ 0,01 $ chacune)")
    p_rech.add_argument("--max-offres", type=int, default=config.MAX_OFFRES_PAR_LANCEMENT,
                        help="nombre maximum d'offres analysées")

    p_lot = sous.add_parser("lot", help="trie toutes les annonces déposées dans le dossier offres_a_trier (sans recherche web)")
    p_lot.add_argument("--dossier", default=str(config.DOSSIER_OFFRES_A_TRIER), help="dossier des annonces .txt")
    p_lot.add_argument("--max-offres", type=int, default=config.MAX_OFFRES_LOT, help="nombre maximum d'annonces analysées")
    p_lot.add_argument("--retraiter", action="store_true",
                       help="retrie aussi les annonces déjà traitées (après un changement de critères ou de prompt)")

    aides = {"lettre": "verdict + lettre de motivation", "cv": "verdict + conseils CV",
             "candidature": "verdict + lettre + conseils CV (en parallèle)"}
    for nom, aide in aides.items():
        p = sous.add_parser(nom, help=aide)
        p.add_argument("offre", help="fichier texte contenant l'annonce collée")
        p.add_argument("--forcer", action="store_true", help="rédige même si l'offre est écartée")
        if nom != "cv":
            p.add_argument("--entreprise", help="résumé de l'entreprise (texte court)")
            p.add_argument("--entreprise-fichier", help="fichier texte contenant le résumé de l'entreprise")
            p.add_argument("--sans-recherche", action="store_true",
                           help="ne pas chercher l'entreprise sur le web (sans --entreprise, la lettre n'aura pas de fiche)")

    args = parser.parse_args()
    if args.commande == "recherche":
        asyncio.run(recherche(args))
        return
    if args.commande == "lot":
        asyncio.run(lot(args))
        return
    if args.commande == "tri":
        args.forcer = False
    asyncio.run(traiter(args))


if __name__ == "__main__":
    main()
