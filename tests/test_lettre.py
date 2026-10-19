"""Tests de la mise en forme de la lettre (aucun appel à l'API)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from pipeline import etape3_lettre as e
from pipeline.schemas import schema_lettre

PROJETS_PERSO = ["ECODROP", "PANDORA", "PORTFOLIO"]


class TestNomsProjets(unittest.TestCase):
    def test_majuscules_retirees(self):
        self.assertEqual(e._noms_projets("j'ai réalisé ECODROP, une API", PROJETS_PERSO), "j'ai réalisé EcoDrop, une API")
        self.assertEqual(e._noms_projets("Dans PANDORA et sur mon PORTFOLIO", PROJETS_PERSO),
                         "Dans Pandora et sur mon portfolio")

    def test_deja_correct_et_debut_de_phrase(self):
        self.assertEqual(e._noms_projets("EcoDrop m'a appris", PROJETS_PERSO), "EcoDrop m'a appris")
        self.assertEqual(e._noms_projets("PORTFOLIO présente mes projets", PROJETS_PERSO), "Portfolio présente mes projets")

    def test_mots_proches_inchanges(self):
        self.assertEqual(e._noms_projets("un portfolio personnel", PROJETS_PERSO), "un portfolio personnel")
        self.assertEqual(e._noms_projets("PANDORAS", PROJETS_PERSO), "PANDORAS")

    def test_noms_qui_ne_sont_pas_dans_la_config(self):
        # Un nom tout en majuscules inconnu de la config devient « Nom » ; un nom déjà normal reste tel quel.
        self.assertEqual(e._noms_projets("le projet ZEBRE et l'API de réservation", ["ZEBRE", "API de réservation"]),
                         "le projet Zebre et l'API de réservation")

    def test_sans_projets(self):
        self.assertEqual(e._noms_projets("ECODROP", []), "ECODROP")


class TestProjetsDuCv(unittest.TestCase):
    def test_lecture_de_l_exemple_fourni(self):
        cv = (config.RACINE / "data" / "cv.example.md").read_text(encoding="utf-8")
        self.assertEqual(e.projets_du_cv(cv), ["API de réservation", "Jeu multijoueur", "Portfolio"])

    def test_format_du_cv_de_l_auteur(self):
        cv = "## Expériences\n### Stage | Asso\n## Projets\n\n### ECODROP | Universitaire\n*2026*\n- x\n\n### PANDORA | Universitaire\n\n## Compétences\n### Autre | y\n"
        self.assertEqual(e.projets_du_cv(cv), ["ECODROP", "PANDORA"])   # s'arrête avant « Compétences »

    def test_pas_de_section_projets(self):
        self.assertEqual(e.projets_du_cv("## Expériences\n### Stage | Asso\n"), [])

    def test_schema_limite_aux_projets_du_cv(self):
        schema = schema_lettre(["A", "B"])
        self.assertEqual(schema["properties"]["projet_choisi"]["enum"], ["A", "B"])
        self.assertNotIn("enum", schema_lettre([])["properties"]["projet_choisi"])


if __name__ == "__main__":
    unittest.main()
