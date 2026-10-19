"""Tests de la recherche automatique : lecture des réponses, offres déjà vues, rapport (sans API).

Lancer :   python -m unittest discover -s tests -v
"""
import datetime
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from pipeline import criteres, etape1_lot, liens, rapport, regles
from pipeline.etape1_recherche import Candidat, Resultat, Stats, melanger, parser, repartir
from pipeline.schemas import Offre
from pipeline.vues import OffresVues, meme_signature, normaliser_url, signature

AUJOURDHUI = datetime.date(2026, 10, 20)

REPONSE = """Je lance les recherches.
=== OFFRE ===
URL: https://emploi.example.com/offre/123?utm_source=x
PUBLIEE: 2026-10-10
TEXTE: Stage développeur web chez Acme à Lille, React et Node.js, 16 semaines.
=== OFFRE ===
URL: https://emploi.example.com/offre/inventee
PUBLIEE: inconnue
TEXTE: Offre dont l'adresse n'a jamais été vue par la recherche.
=== OFFRE ===
URL: https://emploi.example.com/offre/vieille
PUBLIEE: 2026-06-01
TEXTE: Offre trop ancienne.
=== OFFRE ===
**URL:** https://emploi.example.com/offre/456
**PUBLIEE:** inconnue
**TEXTE:** Stage Java chez Beta à Roubaix.
=== OFFRE ===
URL: https://emploi.example.com/offre/123
PUBLIEE: 2026-10-10
TEXTE: Même offre que la première (doublon).
"""
URLS = ["https://www.emploi.example.com/offre/123", "https://emploi.example.com/offre/vieille",
        "https://emploi.example.com/offre/456"]


class TestParser(unittest.TestCase):
    def test_lecture_et_garde_fous(self):
        stats = Stats()
        c = parser(REPONSE, URLS, "stage_ts", stats, aujourdhui=AUJOURDHUI)
        self.assertEqual([x.url.split("/")[-1].split("?")[0] for x in c], ["123", "456"])
        self.assertEqual(stats.trouvees, 5)
        self.assertEqual(stats.url_non_verifiee, 1)   # adresse inventée
        self.assertEqual(stats.trop_anciennes, 1)
        self.assertEqual(stats.doublons, 1)
        self.assertEqual(c[0].publiee, datetime.date(2026, 10, 10))
        self.assertIsNone(c[1].publiee)               # date inconnue = gardée

    def test_repartition_et_melange(self):
        self.assertEqual(repartir(5, 4), [2, 1, 1, 1])
        self.assertEqual(repartir(2, 4), [1, 1, 0, 0])
        a = [Candidat("a1", "", None, "A"), Candidat("a2", "", None, "A")]
        b = [Candidat("b1", "", None, "B")]
        self.assertEqual([x.url for x in melanger([a, b])], ["a1", "b1", "a2"])


class TestLot(unittest.TestCase):
    def test_decoupage(self):
        a = "Stage développeur web chez Acme à Lille. " * 4
        b = "Stage Java chez Beta à Roubaix, 16 semaines. " * 4
        texte = f"{a}\n===\n{b}\n=====\ncourt\n"
        self.assertEqual(len(etape1_lot.decouper(texte)), 2)   # le fragment « court » est ignoré

    def test_empreinte_et_lien(self):
        self.assertEqual(etape1_lot.empreinte("Stage  Java\nà Lille"), etape1_lot.empreinte("stage java à lille"))
        self.assertEqual(etape1_lot.lien_du_texte("Lien : https://a.fr/x.\nTexte"), "https://a.fr/x")
        self.assertIsNone(etape1_lot.lien_du_texte("Texte sans lien"))


class TestLiens(unittest.TestCase):
    def test_classement(self):
        self.assertEqual(liens.classer(404, ""), liens.MORTE)
        self.assertEqual(liens.classer(410, ""), liens.MORTE)
        self.assertEqual(liens.classer(200, "<p>This vacancy has now expired.</p>"), liens.MORTE)
        self.assertEqual(liens.classer(200, "Cette page n’est plus disponible."), liens.MORTE)
        self.assertEqual(liens.classer(200, "Cette offre d'emploi chez X n'est plus disponible"), liens.MORTE)
        self.assertEqual(liens.classer(200, "Stage développeur Java. Postuler"), liens.VIVANTE)
        self.assertEqual(liens.classer(403, ""), liens.INCONNU)   # site qui bloque les programmes
        self.assertEqual(liens.classer(502, ""), liens.INCONNU)   # panne passagère
        self.assertEqual(liens.classer(None, ""), liens.INCONNU)

    def test_dates_schema_org(self):
        aujourdhui = datetime.date(2026, 10, 18)
        # Cas réel de Wizbii : « Expire bientôt » affiché, mais la date de fin de validité est dépassée.
        wizbii_expiree = ('<meta itemprop="datePosted" content="2026-09-20T09:00:00.000Z">'
                          '<meta itemprop="validThrough" content="2026-10-17T14:54:39.305Z"> Expire bientôt')
        self.assertEqual(liens.classer(200, wizbii_expiree, aujourdhui), liens.MORTE)
        wizbii_active = wizbii_expiree.replace("2026-10-17", "2026-11-17")
        self.assertEqual(liens.classer(200, wizbii_active, aujourdhui), liens.VIVANTE)
        # Cas réel : page publiée en 2018, encore en ligne.
        ancienne = '<meta itemprop="datePosted" content="2018-10-11T12:36:53.000Z"><p>Postuler</p>'
        self.assertEqual(liens.classer(200, ancienne, aujourdhui), liens.MORTE)
        # Format JSON-LD.
        json_ld = '{"@type":"JobPosting","datePosted":"2026-10-01","validThrough":"2026-10-10T00:00"}'
        self.assertEqual(liens.classer(200, json_ld, aujourdhui), liens.MORTE)
        # Page sans aucune date : on ne peut rien conclure.
        self.assertEqual(liens.classer(200, "Stage Java. Postuler", aujourdhui), liens.VIVANTE)

    def test_adresses_locales_refusees(self):
        self.assertFalse(liens._adresse_publique("http://localhost/x"))
        self.assertFalse(liens._adresse_publique("http://192.168.1.10/x"))
        self.assertFalse(liens._adresse_publique("file:///etc/passwd"))
        self.assertTrue(liens._adresse_publique("https://www.hellowork.com/x"))


class TestDoublons(unittest.TestCase):
    def test_meme_offre_republiee(self):
        a = signature("Gfi Informatique", "Stage développement JAVA JEE H/F", "Lille")
        b = signature("Gfi Informatique", "Stage - Développement Java JEE", "Lille")
        self.assertTrue(meme_signature(a, b))

    def test_meme_offre_sur_un_autre_site(self):
        a = signature("Gfi", "Stage de développeur Java JEE (H/F)", "Lille")
        b = signature("Gfi Informatique", "Développeur Java JEE", "Lille")
        self.assertTrue(meme_signature(a, b))

    def test_offres_differentes(self):
        a = signature("Gfi", "Stage développeur Java JEE", "Lille")
        self.assertFalse(meme_signature(a, signature("Gfi", "Stage développeur React", "Lille")))      # autre poste
        self.assertFalse(meme_signature(a, signature("Gfi", "Stage développeur Java JEE", "Paris")))   # autre ville
        self.assertFalse(meme_signature(a, signature("Orange", "Stage développeur Java JEE", "Lille"))) # autre entreprise


class TestVues(unittest.TestCase):
    def test_normalisation(self):
        self.assertEqual(normaliser_url("https://www.Site.com/offre/1/?utm_campaign=x&fbclid=y#haut"),
                         normaliser_url("http://site.com/offre/1"))
        self.assertNotEqual(normaliser_url("https://site.com/emploi?jk=aaa"), normaliser_url("https://site.com/emploi?jk=bbb"))

    def test_signature_meme_offre_sur_deux_sites(self):
        self.assertEqual(signature("Acme", "Stage Développeur Web (H/F)", "Lille"),
                         signature("ACME", "Développeur web", "lille"))

    def test_fichier_vide_ou_absent(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "vues.json"
            self.assertEqual(OffresVues(chemin).offres, {})            # fichier absent
            chemin.write_text("", encoding="utf-8")
            self.assertEqual(OffresVues(chemin).offres, {})            # fichier vide : accepté
            chemin.write_text("  \n", encoding="utf-8")
            self.assertEqual(OffresVues(chemin).offres, {})            # seulement des espaces
            chemin.write_text("{pas du json", encoding="utf-8")
            with self.assertRaises(RuntimeError):                      # contenu cassé : on prévient
                OffresVues(chemin)

    def test_sauvegarde_et_relecture(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "vues.json"
            v = OffresVues(chemin)
            v.ajouter(["u1", "sig:x"], "retenue", "Titre", "Acme", "https://a")
            v.sauver()
            v2 = OffresVues(chemin)
            self.assertTrue(v2.deja_vue("u1"))
            self.assertFalse(v2.deja_vue("u2"))


class TestRapport(unittest.TestCase):
    def test_rapport_complet(self):
        c = criteres.charger(config.FICHIER_CRITERES)
        base = dict(intitule="Stage dev", entreprise="Acme", lieux=["Lille"], departement="59", type_contrat="stage",
                    debut_au_plus_tot="2027-03", debut_au_plus_tard="2027-03", duree_min_semaines=16,
                    duree_max_semaines=16, niveau_min_bac=3, niveau_max_bac=5, teletravail_jours_min=2,
                    teletravail_jours_max=2, domaine="web", technologies=["TypeScript"], lien="https://a")
        offres = [Offre(**base), Offre(**{**base, "lieux": ["Paris"], "departement": "75"}),
                  Offre(**{**base, "niveau_min_bac": 4, "niveau_max_bac": 5})]
        res = [Resultat(o, regles.evaluer(o, c), Candidat("https://a", "texte", None, "x")) for o in offres]
        with tempfile.TemporaryDirectory() as d:
            chemin = rapport.ecrire(Path(d) / "r", res, Stats(analysees=3), 0.05)
            texte = chemin.read_text(encoding="utf-8")
            for titre in ("## Retenues (1)", "## À vérifier (1)", "## Écartées (1)", "## Veille alternance (0)"):
                self.assertIn(titre, texte)
            self.assertIn("Raison de l'élimination", texte)


if __name__ == "__main__":
    unittest.main()
