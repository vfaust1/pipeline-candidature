"""Réglages techniques du projet (modèles, chemins, limites).

Tes critères de recherche NE sont PAS ici : ils sont dans criteres.md.
Ici, on ne met que ce qui concerne le fonctionnement du programme.
"""
from pathlib import Path

RACINE = Path(__file__).parent

# --- Chemins -----------------------------------------------------------------
FICHIER_CRITERES = RACINE / "criteres.md"
FICHIER_CV = RACINE / "data" / "cv.md"
FICHIER_MODELE_LETTRE = RACINE / "data" / "modele_lettre.md"
DOSSIER_PROMPTS = RACINE / "prompts"
DOSSIER_SORTIES = RACINE / "sorties"

# --- Modèles -----------------------------------------------------------------
# Léger et pas cher : tri, extraction, résumés.
MODELE_LEGER = "claude-haiku-5-5"
# Plus puissant : rédaction de la lettre.
MODELE_PUISSANT = "claude-sonnet-5-5"
# Conseils CV : modèle léger par défaut (budget). Mets MODELE_PUISSANT si la qualité te déçoit.
MODELE_CONSEILS_CV = MODELE_LEGER

# Prix en dollars par million de tokens (entrée, sortie). Sert uniquement à
# afficher une estimation du coût à la fin d'un lancement.
PRIX = {
    MODELE_LEGER: (0.10, 0.50),
    MODELE_PUISSANT: (2.00, 10.00),
}
PRIX_RECHERCHE_WEB_USD = 0.01   # 10 $ pour 1000 recherches, en plus des tokens
USD_VERS_EUR = 0.92  # approximation, juste pour l'affichage

# --- Limites pour maîtriser les tokens ---------------------------------------
# Une annonce plus longue est refusée plutôt que tronquée en silence.
MAX_CARACTERES_OFFRE = 15000
MAX_TOKENS_EXTRACTION = 3000
MAX_TOKENS_LETTRE = 4000
MAX_TOKENS_CV = 10000
MAX_TOKENS_ENTREPRISE = 6000
MAX_RECHERCHES_ENTREPRISE = 3   # chaque recherche coûte environ 0,01 $

# --- Recherche automatique d'offres (étape 1) --------------------------------
FICHIER_OFFRES_VUES = RACINE / "data" / "offres_vues.json"
DOSSIER_OFFRES_A_TRIER = RACINE / "offres_a_trier"   # mode lot : tu y déposes des annonces en .txt
MAX_OFFRES_LOT = 30                                  # extraction ≈ 0,002 € par offre : large marge
MAX_RECHERCHES_PAR_LANCEMENT = 5   # budget : chaque recherche web ≈ 0,01 $ ; réduis ce nombre si c'est trop cher
MAX_OFFRES_PAR_LANCEMENT = 10      # nombre maximum d'offres analysées (extraction + tri) par lancement
ANCIENNETE_MAX_JOURS = 120         # une page dont la date de publication (schema.org) dépasse ce délai est considérée périmée
RECENCE_JOURS = 30                # une offre publiée il y a plus longtemps est ignorée (date inconnue = gardée)
MAX_TOKENS_RECHERCHE = 12000
# Villes citées au modèle comme zone de recherche (c'est une indication : pour le TRI, ce qui compte est
# la liste « villes_mel » de criteres.md, section 6).
VILLES_REQUETE = "Lille, Villeneuve-d'Ascq, Roubaix, Tourcoing, Marcq-en-Barœul, Ronchin, Lezennes, Fretin"

# Chaque « angle » est une recherche différente, lancée en parallèle. Modifie-les librement.
#   "consigne"  : ce que le modèle doit chercher, dit avec tes mots (sert aussi à juger si une offre est hors sujet).
#   "requetes"  : (facultatif) les requêtes EXACTES envoyées au moteur de recherche, dans l'ordre. Le modèle ne les
#                 modifie pas. Chaque requête consomme une recherche (≈ 0,01 $). Sans « requetes », le modèle choisit
#                 lui-même ses mots à partir de la consigne et des « sources ».
#   "sources"   : (facultatif, utilisé seulement sans « requetes ») sites à essayer en priorité.
# Les requêtes sont volontairement COURTES : plus une requête contient de mots, plus elle exclut d'annonces.
# Le tri fin (technologies, niveau, dates) est fait ensuite par tes règles, pas par le moteur de recherche.
# L'ordre compte : avec le budget par défaut (5 recherches), seules les premières requêtes de chaque angle
# sont lancées (2, 1, 1 et 1). Les suivantes servent quand tu augmentes --max-recherches.
ANGLES = [
    {"nom": "stage_web", "type": "stage",
     "consigne": "stage de fin d'études en développement web",
     "requetes": ["stage développeur web Lille", "stage développeur Lille", "stage développeur web Nord"],
     "sources": "Welcome to the Jungle, Indeed, LinkedIn, sites carrières des entreprises"},
    {"nom": "stage_java", "type": "stage",
     "consigne": "stage de fin d'études en développement Java",
     "requetes": ["stage développeur Java Lille", "stage développeur Java Nord"],
     "sources": "Hellowork, Wizbii, JobTeaser, sites carrières des ESN et des entreprises"},
    {"nom": "stage_app", "type": "stage",
     "consigne": "stage de fin d'études en développement full stack, application ou mobile",
     "requetes": ["stage développeur full stack Lille", "stage développeur full stack Nord"],
     "sources": "L'Etudiant, Stage.fr, Jobijoba, Jooble"},
    {"nom": "alternance", "type": "alternance",
     "consigne": "alternance en développement web ou applicatif, rentrée 2027",
     "requetes": ["alternance développeur Lille", "alternance développeur Nord"],
     "sources": "alternance.emploi.gouv.fr, JobTeaser, Hellowork, sites carrières"},
]
