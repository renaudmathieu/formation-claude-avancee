"""Section 2, le contrat.

Si ces tests passent, la definition de termine est atteinte et vous pouvez
commiter le checkpoint etape/02-client. Vous n'avez pas besoin d'attendre
le formateur pour savoir ou vous en etes.
"""

from __future__ import annotations

from pathlib import Path

import anthropic
import pytest
from fakes import erreur_sdk as _erreur

from doc42.config import MAX_TOKENS_DEFAUT, MODELE_DEFAUT

CORPUS = Path(__file__).parent.parent / "corpus"


def test_appel_simple_retourne_du_texte(module, client):
    resultat = module.appel_simple(client, "Bonjour Doc42.")

    assert isinstance(resultat, str), "appel_simple doit retourner une chaine, pas l'objet reponse."
    assert resultat, "La chaine retournee est vide."

    envoye = client.appels[0]
    assert envoye["model"] == MODELE_DEFAUT, (
        "Le modele doit venir de doc42.config, pas etre code en dur."
    )
    assert envoye["max_tokens"] == MAX_TOKENS_DEFAUT
    assert "system" in envoye, "Le prompt systeme de Doc42 doit etre transmis."


def test_conversation_se_souvient(module, client, aplatir):
    conversation = module.Conversation(client)
    conversation.demander("Je m'appelle Bastien.")
    conversation.demander("Je travaille sur le contrat Alpha.")
    conversation.demander("Comment je m'appelle ?")

    envoye = aplatir(client.appels[-1]["messages"])
    assert "Bastien" in envoye, (
        "Au troisieme tour, l'historique ne contient plus le premier message. "
        "L'API est sans etat : c'est vous qui portez la memoire."
    )

    roles = [m["role"] for m in client.appels[-1]["messages"]]
    assert roles == ["user", "assistant"] * 2 + ["user"], (
        f"L'alternance des roles est cassee : {roles}. "
        "Verifiez que vous ajoutez bien la reponse assistant a l'historique."
    )


def test_flux_retourne_texte_et_usage(module, client, capsys):
    texte, usage = module.appel_en_flux(client, "Resume le document.")

    assert texte == "Doc42 analyse le document.", (
        "Le texte complet doit etre la concatenation des fragments recus."
    )
    assert usage is not None and usage.output_tokens > 0, (
        "usage doit venir de get_final_message(), appele APRES la boucle."
    )
    assert capsys.readouterr().out, (
        "Rien n'a ete affiche. Le streaming sert a montrer la reponse "
        "au fil de l'eau : print(fragment, end='', flush=True)."
    )


def test_reprise_rejoue_le_429(module):
    essais = {"n": 0}
    attentes: list[float] = []

    def appel():
        essais["n"] += 1
        if essais["n"] < 3:
            raise _erreur(anthropic.RateLimitError)
        return "ok"

    resultat = module.avec_reprise(appel, dormir=attentes.append)

    assert resultat == "ok"
    assert essais["n"] == 3, "Le 429 doit etre rejoue jusqu'au succes."
    assert len(attentes) == 2, "Il doit y avoir une attente entre chaque essai."
    assert attentes[1] > attentes[0], "L'attente doit croitre de facon exponentielle."
    assert attentes[0] != 1.0, (
        "Il manque le bruit aleatoire. Sans lui, tous les processus reessaient a la meme seconde."
    )


def test_reprise_ne_rejoue_pas_le_400(module):
    essais = {"n": 0}

    def appel():
        essais["n"] += 1
        raise _erreur(anthropic.BadRequestError)

    with pytest.raises(anthropic.BadRequestError):
        module.avec_reprise(appel, dormir=lambda _: None)

    assert essais["n"] == 1, (
        f"La requete a ete jouee {essais['n']} fois. Un 400 signifie que la "
        "requete est malformee : la rejouer donnera exactement la meme erreur "
        "et consommera votre quota. Ne rattrapez que les exceptions rejouables."
    )


def test_document_extrait_les_echeances(module, client):
    resultat = module.analyser_document(
        client, CORPUS / "contrat_exemple.pdf", "Liste les echeances de paiement."
    )

    for date in ("15/01/2027", "15/04/2027", "15/07/2027"):
        assert date in resultat, f"Echeance manquante : {date}"

    contenu = client.appels[0]["messages"][0]["content"]
    assert isinstance(contenu, list), (
        "Des qu'un fichier est joint, le contenu devient une liste de blocs."
    )
    assert contenu[0]["type"] == "document", (
        "Un PDF utilise le type 'document', et il passe AVANT la question."
    )
    assert contenu[0]["source"]["media_type"] == "application/pdf"
    assert contenu[-1]["type"] == "text"


@pytest.mark.reel
def test_appel_reel(module, pytestconfig):
    if not pytestconfig.getoption("--reel"):
        pytest.skip("Ajoutez --reel pour appeler la vraie API.")
    vrai = anthropic.Anthropic()
    resultat = module.appel_simple(vrai, "Reponds exactement : PRET")
    assert "PRET" in resultat.upper()
