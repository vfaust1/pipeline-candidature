"""Tests de la mise en forme de la lettre (aucun appel à l'API)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import etape3_lettre as e


class TestNomsProjets(unittest.TestCase):
    def test_majuscules_retirees(self):
        self.assertEqual(e._noms_projets("j'ai réalisé ECODROP, une API"), "j'ai réalisé EcoDrop, une API")
        self.assertEqual(e._noms_projets("Dans PANDORA et sur mon PORTFOLIO"), "Dans Pandora et sur mon portfolio")

    def test_deja_correct_et_debut_de_phrase(self):
        self.assertEqual(e._noms_projets("EcoDrop m'a appris"), "EcoDrop m'a appris")
        self.assertEqual(e._noms_projets("PORTFOLIO présente mes projets"), "Portfolio présente mes projets")

    def test_mots_proches_inchanges(self):
        self.assertEqual(e._noms_projets("un portfolio personnel"), "un portfolio personnel")
        self.assertEqual(e._noms_projets("PANDORAS"), "PANDORAS")


if __name__ == "__main__":
    unittest.main()
