"""Tests du contrôle d'identité de l'étape 2 (aucun appel à l'API).

Lancer :   python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import etape2_entreprise as e

REPONSE = """IDENTITE: oui
ENTITE_TROUVEE: Alpha Soft, Lille
SOURCE_IDENTITE: https://www.alpha-soft.fr/a-propos
HOMONYMES: {homonymes}
RESUME: Alpha Soft édite un logiciel de gestion.
Deuxième ligne du résumé."""


def carte(**kw):
    base = {"nom": "Alpha", "ville_ou_adresse": "Lille", "site_web": "", "secteur": "", "poste_propose": "Stage dev"}
    base.update(kw)
    return base


class TestIdentite(unittest.TestCase):
    def test_cas_simple(self):
        f = e.analyser(REPONSE.format(homonymes="aucun"), ["https://alpha-soft.fr"], carte())
        self.assertEqual(f.confiance, "haute")
        self.assertIn("Deuxième ligne", f.resume)

    def test_homonymes_et_un_seul_element(self):
        f = e.analyser(REPONSE.format(homonymes="Alpha SAS (Lyon)"), [], carte())
        self.assertEqual(f.confiance, "incertaine")

    def test_homonymes_et_deux_elements(self):
        f = e.analyser(REPONSE.format(homonymes="Alpha SAS (Lyon)"), [], carte(secteur="logiciel"))
        self.assertEqual(f.confiance, "haute")

    def test_site_absent_des_pages_consultees(self):
        f = e.analyser(REPONSE.format(homonymes="aucun"), ["https://autre-site.com"], carte(site_web="https://www.alpha-soft.fr"))
        self.assertEqual(f.confiance, "incertaine")

    def test_site_present_dans_les_pages(self):
        f = e.analyser(REPONSE.format(homonymes="aucun"), ["https://www.alpha-soft.fr/x"], carte(site_web="alpha-soft.fr"))
        self.assertEqual(f.confiance, "haute")

    def test_aucun_element_d_identification(self):
        f = e.analyser(REPONSE.format(homonymes="aucun"), [], carte(ville_ou_adresse=""))
        self.assertEqual(f.confiance, "incertaine")

    def test_modele_pas_sur(self):
        f = e.analyser("IDENTITE: incertain\nRESUME: ?", [], carte())
        self.assertEqual(f.confiance, "incertaine")


if __name__ == "__main__":
    unittest.main()
