"""Tests des règles de tri (aucun appel à l'API, aucun coût).

Lancer depuis la racine du projet :   python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from pipeline import criteres, regles
from pipeline.schemas import Offre

C = criteres.charger(config.FICHIER_CRITERES)


def offre(**changements) -> Offre:
    """Une offre qui passe tous les contrôles ; chaque test en modifie un seul point."""
    base = dict(
        intitule="Stage développeur web", entreprise="Acme", type_contrat="stage",
        lieux=["Lille"], departement="59",
        debut_au_plus_tot="2027-03", debut_au_plus_tard="2027-03",
        duree_min_semaines=16, duree_max_semaines=16,
        niveau_min_bac=3, niveau_max_bac=5,
        teletravail_jours_min=2, teletravail_jours_max=2,
        domaine="web", technologies=["TypeScript"],
    )
    base.update(changements)
    return Offre(**base)


def statut(**changements) -> str:
    return regles.evaluer(offre(**changements), C).statut


class TestRegles(unittest.TestCase):
    def test_offre_parfaite(self):
        self.assertEqual(statut(), "retenue")

    # --- Lieu
    def test_lieu_prefixe_sur(self):
        self.assertEqual(statut(lieux=["Lille Euratechnologies"]), "retenue")

    def test_lieu_accents_et_tirets(self):
        self.assertEqual(statut(lieux=["Villeneuve d'Ascq"]), "retenue")
        self.assertEqual(statut(lieux=["Marcq-en-Baroeul 59700"]), "retenue")

    def test_homonyme_hors_mel(self):
        # Loos-en-Gohelle (62) ne doit PAS être pris pour Loos (MEL).
        self.assertEqual(statut(lieux=["Loos-en-Gohelle"], departement="62"), "a_verifier")

    def test_lieux_multiples(self):
        self.assertEqual(statut(lieux=["Paris", "Lille"], departement=None), "retenue")

    def test_paris_ecarte(self):
        self.assertEqual(statut(lieux=["Paris"], departement="75"), "ecartee")

    def test_ville_voisine(self):
        self.assertEqual(statut(lieux=["Tournai"], departement=None), "a_verifier")

    # --- Télétravail
    def test_teletravail(self):
        self.assertEqual(statut(teletravail_jours_min=3, teletravail_jours_max=3), "a_verifier")
        self.assertEqual(statut(teletravail_jours_min=4, teletravail_jours_max=4), "ecartee")
        self.assertEqual(statut(teletravail_jours_min=2, teletravail_jours_max=3), "a_verifier")
        self.assertEqual(statut(teletravail_complet=True), "ecartee")
        # Non précisé = accepté (criteres.md) ; « mentionné sans chiffre » reste à vérifier.
        self.assertEqual(statut(teletravail_jours_min=None, teletravail_jours_max=None), "retenue")
        self.assertEqual(statut(teletravail_jours_min=None, teletravail_jours_max=None,
                                teletravail_sans_chiffre=True), "a_verifier")
        self.assertEqual(statut(teletravail_jours_min=0, teletravail_jours_max=0), "retenue")

    # --- Dates
    def test_dates(self):
        self.assertEqual(statut(debut_au_plus_tot="2027-05", debut_au_plus_tard="2027-05"), "ecartee")
        self.assertEqual(statut(debut_au_plus_tot="2026-11", debut_au_plus_tard="2026-11"), "ecartee")
        self.assertEqual(statut(debut_au_plus_tot="2027-02", debut_au_plus_tard="2027-06"), "retenue")
        self.assertEqual(statut(debut_au_plus_tot="2026-11", debut_au_plus_tard=None), "a_verifier")
        self.assertEqual(statut(debut_au_plus_tot=None, debut_au_plus_tard=None, debut_flou=True), "retenue")
        self.assertEqual(statut(debut_au_plus_tot=None, debut_au_plus_tard=None), "retenue")

    # --- Niveau
    def test_niveau(self):
        self.assertEqual(statut(niveau_min_bac=4, niveau_max_bac=5), "a_verifier")
        self.assertEqual(statut(niveau_min_bac=5, niveau_max_bac=5), "a_verifier")
        self.assertEqual(statut(niveau_min_bac=0, niveau_max_bac=3), "retenue")
        self.assertEqual(statut(niveau_min_bac=None, niveau_max_bac=2), "retenue")
        self.assertEqual(statut(niveau_min_bac=3, niveau_max_bac=5), "retenue")
        self.assertEqual(statut(niveau_min_bac=None, niveau_max_bac=None), "retenue")

    # --- Durée
    def test_duree(self):
        self.assertEqual(statut(duree_min_semaines=None, duree_max_semaines=None), "retenue")
        self.assertEqual(statut(duree_min_semaines=26, duree_max_semaines=26), "a_verifier")
        self.assertEqual(statut(duree_min_semaines=17, duree_max_semaines=26), "retenue")
        self.assertEqual(statut(duree_min_semaines=13, duree_max_semaines=13), "ecartee")

    # --- Technologies
    def test_technos(self):
        self.assertEqual(statut(technologies=["Spring Boot"]), "retenue")
        self.assertEqual(statut(technologies=["Node.js", "MongoDB"]), "retenue")
        self.assertEqual(statut(technologies=[]), "retenue")
        self.assertEqual(statut(technologies=["Kotlin"], domaine="mobile"), "a_verifier")
        self.assertEqual(statut(technologies=["React Native", "Firebase"], domaine="mobile"), "a_verifier")
        self.assertEqual(statut(technologies=["Android"], domaine="mobile"), "a_verifier")
        self.assertEqual(statut(technologies=["PHP", "Symfony"]), "ecartee")
        # Toutes les bases de données sont acceptées.
        for base in ("MongoDB", "MariaDB", "PostgreSQL", "Oracle"):
            self.assertEqual(statut(technologies=[base]), "retenue", base)
        # Python et C# : à vérifier, mais une techno de ma liste à côté suffit.
        self.assertEqual(statut(technologies=["Python", "Django"]), "a_verifier")
        self.assertEqual(statut(technologies=["C#", ".NET"]), "a_verifier")
        self.assertEqual(statut(technologies=["Python", "React"]), "retenue")
        self.assertEqual(statut(technologies=["Java", "Kotlin"], domaine="mobile"), "retenue")

    def test_tout_non_precise_reste_retenue_avec_notes(self):
        v = regles.evaluer(offre(duree_min_semaines=None, duree_max_semaines=None, debut_au_plus_tot=None,
                                 debut_au_plus_tard=None, niveau_min_bac=None, niveau_max_bac=None,
                                 teletravail_jours_min=None, teletravail_jours_max=None), C)
        self.assertEqual(v.statut, "retenue")
        self.assertEqual(len(v.points_a_verifier), 0)
        self.assertEqual(len([n for n in v.notes if "acceptée" in n]), 4)

    # --- Domaine, contrat, alternance
    def test_domaine_et_contrat(self):
        self.assertEqual(statut(domaine="autre"), "ecartee")
        self.assertEqual(statut(type_contrat="autre"), "ecartee")

    def test_alternance(self):
        alt = dict(type_contrat="alternance", debut_au_plus_tot="2027-09", debut_au_plus_tard="2027-09",
                   duree_min_semaines=None, duree_max_semaines=None, niveau_min_bac=4, niveau_max_bac=5)
        self.assertEqual(statut(**alt), "veille_alternance")
        self.assertEqual(statut(**{**alt, "lieux": ["Paris"], "departement": "75"}), "ecartee")
        self.assertEqual(statut(**{**alt, "debut_au_plus_tot": "2026-11", "debut_au_plus_tard": "2026-11"}), "ecartee")


if __name__ == "__main__":
    unittest.main()
