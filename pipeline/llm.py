"""Le SEUL fichier qui parle à l'API Anthropic.

Pourquoi un fichier à part ? Pour que les étapes n'aient pas à connaître les détails
de l'API, et pour compter les tokens au même endroit.

Un « agent » ici, c'est simplement : un appel à un modèle avec un rôle (le prompt système),
des entrées limitées, et une sortie structurée.
"""
from __future__ import annotations

import json

import anthropic

import config

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    """Crée le client au premier appel. Il lit la clé dans la variable d'environnement ANTHROPIC_API_KEY."""
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


class Compteur:
    """Additionne les tokens consommés pour afficher une estimation du coût."""

    def __init__(self) -> None:
        self.par_modele: dict[str, list[int]] = {}
        self.recherches_web = 0   # facturées à part : 10 $ pour 1000 recherches

    def ajouter(self, modele: str, usage) -> None:
        entree, sortie = self.par_modele.setdefault(modele, [0, 0])
        self.par_modele[modele] = [entree + usage.input_tokens, sortie + usage.output_tokens]

    def cout_eur(self) -> float:
        total = 0.0
        for modele, (entree, sortie) in self.par_modele.items():
            prix_in, prix_out = config.PRIX.get(modele, (0.0, 0.0))
            total += entree / 1e6 * prix_in + sortie / 1e6 * prix_out
        total += self.recherches_web * config.PRIX_RECHERCHE_WEB_USD
        return total * config.USD_VERS_EUR

    def resume(self) -> str:
        lignes = [f"  {m} : {e} tokens en entrée, {s} en sortie" for m, (e, s) in self.par_modele.items()]
        if self.recherches_web:
            lignes.append(f"  Recherches web : {self.recherches_web}")
        lignes.append(f"  Coût estimé : {self.cout_eur():.3f} €")
        return "\n".join(lignes)


COMPTEUR = Compteur()


async def appeler(*, modele: str, system: str, user: str, max_tokens: int,
                  effort: str = "low", schema: dict | None = None):
    """Un appel au modèle.

    - effort : « low » pour les tâches simples (moins de réflexion = moins de tokens).
    - schema : si fourni, l'API force une réponse JSON conforme, et on renvoie un dict.
               Sinon on renvoie le texte.
    """
    sortie: dict = {"effort": effort}
    if schema is not None:
        sortie["format"] = {"type": "json_schema", "schema": schema}

    # max_tokens limite la LONGUEUR de la réponse (réflexion du modèle comprise), pas ton budget.
    # Si la réponse est coupée, on réessaie une fois avec une limite doublée avant d'abandonner.
    for tentative in range(2):
        reponse = await _get_client().messages.create(
            model=modele,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config=sortie,
        )
        COMPTEUR.ajouter(modele, reponse.usage)
        if reponse.stop_reason == "max_tokens" and tentative == 0:
            max_tokens *= 2
            continue
        break

    if reponse.stop_reason == "max_tokens":
        raise RuntimeError("Réponse coupée (max_tokens atteint) : augmente la limite dans config.py.")
    if reponse.stop_reason == "refusal":
        raise RuntimeError("Le modèle a refusé de répondre à cette demande.")

    texte = "".join(bloc.text for bloc in reponse.content if bloc.type == "text")
    return json.loads(texte) if schema is not None else texte


async def appeler_avec_recherche(*, modele: str, system: str, user: str, max_tokens: int,
                                 max_recherches: int) -> tuple[str, list[str], list[str]]:
    """Un appel qui peut utiliser la recherche web de l'API (outil « serveur » : c'est Anthropic
    qui exécute les recherches, on n'a rien à coder).

    Renvoie (texte final, adresses web trouvées, requêtes réellement tapées par le modèle). Pas de schéma JSON ici : le texte
    est lu par Python avec des étiquettes simples (voir etape2_entreprise.py).
    Si l'API met le tour en pause (« pause_turn »), on lui renvoie sa propre réponse pour qu'elle continue.
    """
    outils = [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_recherches}]
    messages = [{"role": "user", "content": user}]
    textes: list[str] = []
    urls: list[str] = []
    requetes: list[str] = []

    for _ in range(4):   # au plus 3 reprises après pause
        reponse = await _get_client().messages.create(
            model=modele, max_tokens=max_tokens, system=system, messages=messages,
            tools=outils, output_config={"effort": "low"},
        )
        COMPTEUR.ajouter(modele, reponse.usage)
        outil_serveur = getattr(reponse.usage, "server_tool_use", None)
        COMPTEUR.recherches_web += getattr(outil_serveur, "web_search_requests", 0) or 0

        for bloc in reponse.content:
            if bloc.type == "text":
                textes.append(bloc.text)
                for citation in getattr(bloc, "citations", None) or []:
                    if getattr(citation, "url", None):
                        urls.append(citation.url)
            elif bloc.type == "server_tool_use" and getattr(bloc, "name", "") == "web_search":
                # La requête exacte que le modèle a envoyée au moteur de recherche.
                requete = (getattr(bloc, "input", None) or {}).get("query")
                if requete:
                    requetes.append(requete)
            elif bloc.type == "web_search_tool_result" and isinstance(bloc.content, list):
                urls += [r.url for r in bloc.content if getattr(r, "url", None)]

        if reponse.stop_reason == "max_tokens":
            raise RuntimeError("Réponse coupée (max_tokens atteint) : augmente la limite dans config.py.")
        if reponse.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": reponse.content})

    return "".join(textes), urls, requetes
