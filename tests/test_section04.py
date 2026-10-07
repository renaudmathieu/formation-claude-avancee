"""Section 4, le contrat.

Si ces tests passent, la boucle d'outils est complete, bornee, et les erreurs
d'outils repartent vers Claude au lieu de la faire planter. Il vous restera les
etapes d'observation (en fin de fichier d'exercice), et le checkpoint
etape/04-tools a commiter.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from fakes import BlocOutil, BlocTexte, FausseReponse, outil, texte

from doc42.config import MODELE_DEFAUT, SYSTEME_DOC42
from doc42.outils import mots, normaliser

CORPUS = Path(__file__).parent.parent / "corpus"


@dataclass
class BlocReflexion:
    """Un bloc de raisonnement, qui peut preceder le texte dans une vraie reponse."""

    thinking: str = "Je reflechis."
    signature: str = "sig"
    type: str = "thinking"


def parallele(*blocs: BlocOutil) -> FausseReponse:
    """Une reponse qui demande plusieurs outils dans le meme tour."""
    return FausseReponse(content=[BlocTexte("Je cherche."), *blocs], stop_reason="tool_use")


def champ(bloc: Any, cle: str) -> Any:
    """Lit un champ, que le bloc soit un dict ou un objet du SDK."""
    return bloc.get(cle) if isinstance(bloc, dict) else getattr(bloc, cle, None)


class ExecuteurFactice:
    """Enregistre les appels d'outils et repond sans rien executer."""

    def __init__(self, erreur_pour: tuple[str, ...] = ()) -> None:
        self.appels: list[tuple[str, dict[str, Any]]] = []
        self.erreur_pour = erreur_pour

    def __call__(self, nom: str, entree: dict[str, Any]) -> tuple[str, bool]:
        self.appels.append((nom, entree))
        if nom in self.erreur_pour:
            return f"Erreur simulee pour {nom}", True
        return f"resultat de {nom} #{len(self.appels)}", False


def definition(module, nom: str) -> dict[str, Any]:
    trouve = [d for d in module.OUTILS if d.get("name") == nom]
    assert trouve, f"OUTILS ne contient pas d'outil nomme '{nom}'."
    return trouve[0]


def contient(texte_libre: str, marqueurs: tuple[str, ...]) -> bool:
    return any(m in normaliser(texte_libre) for m in marqueurs)


QUAND = (
    "quand",
    "des que",
    "lorsque",
    "a utiliser",
    "utilise cet outil",
    "ne l'utilise",
    "utiliser",
)
RETOUR = ("renvoie", "retourne", "rend ")


# Exercice 1 : les definitions


def test_definitions_completes(module):
    noms = [d.get("name") for d in module.OUTILS]
    assert sorted(noms) == ["chercher_documents", "creer_fiche"], (
        f"OUTILS doit definir exactement chercher_documents et creer_fiche, pas {noms}. "
        "Les noms doivent correspondre aux fonctions de doc42/outils.py."
    )
    for d in module.OUTILS:
        schema = d.get("input_schema", {})
        assert schema.get("type") == "object", (
            f"{d['name']} : input_schema.type doit valoir 'object'."
        )
        for nom, propriete in schema.get("properties", {}).items():
            assert propriete.get("description"), (
                f"{d['name']}.{nom} n'a pas de description. Chaque parametre a la sienne, "
                "avec un exemple : c'est ce qui guide le modele pour le remplir."
            )


def test_schema_chercher_documents(module):
    schema = definition(module, "chercher_documents")["input_schema"]
    proprietes = schema.get("properties", {})
    assert proprietes.get("requete", {}).get("type") == "string"
    assert schema.get("required") == ["requete"], (
        "Seule 'requete' est obligatoire : 'limite' a une valeur par defaut."
    )
    limite = proprietes.get("limite", {})
    assert limite.get("type") == "integer"
    assert (limite.get("minimum"), limite.get("maximum")) == (1, 10), (
        "Bornez 'limite' dans le schema avec minimum et maximum (1 et 10) : "
        "la validation stricte commence dans le schema."
    )


def test_schema_creer_fiche(module):
    schema = definition(module, "creer_fiche")["input_schema"]
    assert set(schema.get("required", [])) == {"titre", "contenu"}, (
        "creer_fiche exige 'titre' et 'contenu', comme doc42.outils.creer_fiche."
    )


def test_description_dit_quoi_quand_et_retour(module):
    description = definition(module, "chercher_documents").get("description", "")
    assert len(mots(description)) >= 15, (
        "La description de chercher_documents est trop courte. Une phrase ne suffit pas : "
        "dites ce que fait l'outil, QUAND l'utiliser et ce qu'il renvoie."
    )
    assert contient(description, QUAND), (
        "La description ne dit pas QUAND utiliser l'outil. Sans ce « quand », "
        "Claude repond de memoire au lieu de chercher (c'est l'experience de l'etape 3)."
    )
    assert contient(description, RETOUR), "La description ne dit pas ce que l'outil renvoie."
    assert not contient(module.DESCRIPTION_MEDIOCRE, QUAND), "DESCRIPTION_MEDIOCRE est donnee."


def test_description_creer_fiche_signale_l_ecriture(module):
    description = definition(module, "creer_fiche").get("description", "")
    assert contient(description, ("ecrit", "enregistre")), (
        "La description de creer_fiche doit dire que l'outil ECRIT un fichier. "
        "Un outil qui agit ne se decrit pas comme un outil qui lit."
    )
    assert contient(description, ("explicitement", "uniquement", "seulement", "que si")), (
        "Dites quand NE PAS l'utiliser : seulement sur demande explicite de l'utilisateur."
    )


# Exercice 2 : casser la description sans casser la reference


def test_avec_description_ne_modifie_pas_l_original(module):
    origine = module.OUTILS
    instantane = copy.deepcopy(origine)
    cassee = module.avec_description(origine, "chercher_documents", module.DESCRIPTION_MEDIOCRE)

    assert [d["name"] for d in cassee] == [d["name"] for d in origine]
    remplacee = next(d for d in cassee if d["name"] == "chercher_documents")
    assert remplacee["description"] == module.DESCRIPTION_MEDIOCRE
    assert (
        remplacee["input_schema"]
        == next(d for d in instantane if d["name"] == "chercher_documents")["input_schema"]
    ), "Seule la description doit changer, pas le schema."
    assert origine == instantane, (
        "avec_description a modifie OUTILS. Une copie de la liste ne suffit pas : "
        "les dictionnaires sont partages. Utilisez copy.deepcopy."
    )


def test_avec_description_nom_inconnu(module):
    with pytest.raises(KeyError):
        module.avec_description(module.OUTILS, "chercher_document", "x")


# Exercice 3 : executer un outil, sans jamais lever


def test_executer_recherche(module):
    contenu, erreur = module.executer_outil(
        "chercher_documents",
        {"requete": "echeances contrat Alpha", "limite": 3},
        dossier_corpus=CORPUS,
    )
    assert erreur is False
    assert "[contrat_alpha]" in contenu, (
        "Chaque resultat commence par [id] puis le titre : Claude a besoin de l'id pour citer."
    )


def test_executer_recherche_vide_n_est_pas_une_erreur(module):
    contenu, erreur = module.executer_outil(
        "chercher_documents", {"requete": "zzzz qwxy"}, dossier_corpus=CORPUS
    )
    assert erreur is False, (
        "Une recherche sans resultat est une reponse valide, pas une panne de l'outil. "
        "is_error doit rester False, sinon Claude croit l'outil casse."
    )
    assert "aucun document" in normaliser(contenu)


def test_executer_cree_la_fiche(module, tmp_path):
    contenu, erreur = module.executer_outil(
        "creer_fiche",
        {"titre": "Echeances Alpha", "contenu": "- 15/01/2027"},
        dossier_fiches=tmp_path,
    )
    fiches = list(tmp_path.glob("*.md"))
    assert erreur is False
    assert len(fiches) == 1, "creer_fiche doit ecrire dans dossier_fiches, pas ailleurs."
    assert str(fiches[0]) in contenu, "Le resultat doit indiquer le chemin de la fiche creee."
    assert "15/01/2027" in fiches[0].read_text(encoding="utf-8")


def test_executer_outil_inconnu(module):
    contenu, erreur = module.executer_outil("supprimer_documents", {})
    assert erreur is True, "Un outil inconnu doit revenir avec is_error, pas lever."
    assert "supprimer_documents" in contenu, "Nommez l'outil demande dans le message d'erreur."


@pytest.mark.parametrize(
    ("nom", "entree", "fautif"),
    [
        ("chercher_documents", {}, "requete"),
        ("chercher_documents", {"requete": "  "}, "requete"),
        ("chercher_documents", {"requete": 42}, "requete"),
        ("chercher_documents", {"requete": "Alpha", "limite": "cinq"}, "limite"),
        ("chercher_documents", {"requete": "Alpha", "limite": 50}, "limite"),
        ("chercher_documents", {"requete": "Alpha", "limite": 0}, "limite"),
        ("creer_fiche", {"titre": "Alpha"}, "contenu"),
        ("creer_fiche", {"contenu": "texte"}, "titre"),
        ("creer_fiche", {"titre": "", "contenu": "texte"}, "titre"),
    ],
)
def test_executer_entree_invalide(module, tmp_path, nom, entree, fautif):
    contenu, erreur = module.executer_outil(
        nom, entree, dossier_corpus=CORPUS, dossier_fiches=tmp_path
    )
    assert erreur is True, (
        f"{nom}({entree}) devrait revenir en erreur. L'input_schema guide le modele, "
        "il ne valide rien : verifiez l'entree dans votre code."
    )
    assert fautif in contenu, f"Le message d'erreur doit nommer le parametre fautif '{fautif}'."
    assert not list(tmp_path.glob("*.md")), "Une entree invalide ne doit rien ecrire."


def test_executer_exception_renvoyee_a_claude(module, tmp_path):
    fichier = tmp_path / "pas_un_dossier"
    fichier.write_text("x", encoding="utf-8")
    contenu, erreur = module.executer_outil(
        "creer_fiche", {"titre": "Alpha", "contenu": "texte"}, dossier_fiches=fichier
    )
    assert erreur is True, (
        "Une exception pendant l'execution doit revenir comme (message, True), "
        "pas faire planter la boucle."
    )
    assert "creer_fiche" in contenu


# Exercice 4 : tous les tool_use d'un tour


def test_resultats_outils_tous_les_blocs(module):
    reponse = parallele(
        BlocOutil("chercher_documents", {"requete": "Alpha"}, id="toolu_a"),
        BlocOutil("chercher_documents", {"requete": "Beta"}, id="toolu_b"),
    )
    executer = ExecuteurFactice()
    resultats = module.resultats_outils(reponse, executer)

    assert len(resultats) == 2, (
        "Un tool_result par bloc tool_use, pas seulement le premier. Un tool_use "
        "sans resultat fait refuser l'appel suivant par l'API."
    )
    assert [r["tool_use_id"] for r in resultats] == ["toolu_a", "toolu_b"], (
        "Chaque tool_result reprend l'id de son tool_use, dans le meme ordre."
    )
    assert all(r["type"] == "tool_result" for r in resultats)
    assert [e["requete"] for _, e in executer.appels] == ["Alpha", "Beta"]


def test_resultats_outils_propage_is_error(module):
    reponse = parallele(
        BlocOutil("chercher_documents", {"requete": "Alpha"}, id="toolu_a"),
        BlocOutil("outil_fantome", {}, id="toolu_b"),
    )
    resultats = module.resultats_outils(reponse, ExecuteurFactice(erreur_pour=("outil_fantome",)))
    assert not resultats[0].get("is_error", False)
    assert resultats[1].get("is_error") is True, (
        "L'erreur d'outil doit remonter dans le tool_result avec is_error: True."
    )


# Exercice 5 : la boucle


def test_boucle_sans_outil(module, client):
    client.programmer(texte("Bonjour, je suis Doc42."))
    resultat = module.demander(client, "Bonjour", executer=ExecuteurFactice())

    assert resultat == "Bonjour, je suis Doc42."
    assert len(client.appels) == 1
    envoye = client.appels[0]
    assert envoye["model"] == MODELE_DEFAUT, "Le modele vient de doc42.config."
    assert envoye["system"] == SYSTEME_DOC42
    assert envoye["tools"] == module.OUTILS, "Les definitions d'outils partent avec chaque appel."
    assert "tool_choice" not in envoye, (
        "tool_choice ne doit pas etre envoye quand il n'est pas fourni (le SDK refuse None)."
    )


def test_boucle_un_outil(module, client):
    client.programmer(
        outil("chercher_documents", {"requete": "echeances Alpha"}, id="toolu_1"),
        texte("Echeances : 15/01/2027, 15/04/2027 et 15/07/2027."),
    )
    executer = ExecuteurFactice()
    resultat = module.demander(
        client, "Quelles sont les echeances du contrat Alpha ?", executer=executer
    )

    assert "15/01/2027" in resultat
    assert executer.appels == [("chercher_documents", {"requete": "echeances Alpha"})]
    assert len(client.appels) == 2, "Apres un tool_use, il faut rappeler l'API avec le resultat."

    messages = client.appels[1]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"], (
        "L'historique doit etre : question, reponse assistant (avec son tool_use), tool_result."
    )
    assert any(champ(b, "type") == "tool_use" for b in messages[1]["content"]), (
        "La reponse assistant doit entrer dans l'historique avec ses blocs tool_use : "
        "les tool_result y font reference par leur id."
    )
    retour = messages[2]["content"]
    assert isinstance(retour, list) and champ(retour[0], "type") == "tool_result"
    assert champ(retour[0], "tool_use_id") == "toolu_1"
    assert champ(retour[0], "content") == "resultat de chercher_documents #1"
    assert client.appels[1]["tools"] == module.OUTILS


def test_boucle_appels_paralleles(module, client):
    client.programmer(
        parallele(
            BlocOutil("chercher_documents", {"requete": "contrat Alpha"}, id="toolu_a"),
            BlocOutil("chercher_documents", {"requete": "contrat Beta"}, id="toolu_b"),
            BlocOutil("chercher_documents", {"requete": "facture"}, id="toolu_c"),
        ),
        texte("Synthese des trois recherches."),
    )
    executer = ExecuteurFactice()
    module.demander(client, "Compare Alpha et Beta.", executer=executer)

    assert len(executer.appels) == 3, "Les trois tool_use du tour doivent etre executes."
    messages = client.appels[1]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"], (
        "Tous les tool_result d'un tour partent dans UN SEUL message user. "
        "Un message par resultat casserait l'alternance des roles."
    )
    retour = messages[2]["content"]
    assert [champ(b, "tool_use_id") for b in retour] == ["toolu_a", "toolu_b", "toolu_c"]
    assert all(champ(b, "type") == "tool_result" for b in retour), (
        "Le message user de retour ne contient que des tool_result."
    )


def test_boucle_deux_outils_enchaines(module, client, tmp_path):
    client.programmer(
        outil("chercher_documents", {"requete": "echeances paiement"}, id="toolu_1"),
        outil(
            "creer_fiche",
            {"titre": "Echeances Alpha", "contenu": "- 15/01/2027\n- 15/04/2027\n- 15/07/2027"},
            id="toolu_2",
        ),
        texte("La fiche est creee."),
    )
    executer = partial(module.executer_outil, dossier_corpus=CORPUS, dossier_fiches=tmp_path)
    resultat = module.demander(client, "Fais une fiche sur les echeances Alpha.", executer=executer)

    assert resultat == "La fiche est creee."
    assert len(client.appels) == 3
    fiches = list(tmp_path.glob("*.md"))
    assert len(fiches) == 1, "La fiche doit etre ecrite par le second outil."
    roles = [m["role"] for m in client.appels[2]["messages"]]
    assert roles == ["user", "assistant", "user", "assistant", "user"], (
        f"Historique attendu sur deux tours d'outils : user/assistant alternes, obtenu {roles}."
    )
    premier_retour = client.appels[1]["messages"][2]["content"][0]
    assert "[contrat_alpha]" in champ(premier_retour, "content"), (
        "Le resultat reel de chercher_documents doit repartir vers Claude."
    )


def test_boucle_erreur_d_outil_ne_plante_pas(module, client):
    client.programmer(
        outil("supprimer_documents", {"id": "contrat_alpha"}, id="toolu_x"),
        texte("Je ne dispose pas de cet outil."),
    )
    resultat = module.demander(client, "Supprime le contrat Alpha.")

    assert resultat == "Je ne dispose pas de cet outil.", (
        "Une erreur d'outil ne doit pas interrompre la boucle : Claude doit pouvoir l'expliquer."
    )
    retour = client.appels[1]["messages"][2]["content"][0]
    assert champ(retour, "is_error") is True, "L'outil inconnu doit remonter avec is_error: True."


def test_boucle_bornee(module, client):
    client.programmer(
        *[outil("chercher_documents", {"requete": "Alpha"}, id=f"t{i}") for i in range(5)]
    )
    resultat = module.demander(client, "Boucle !", executer=ExecuteurFactice(), tours_max=3)

    assert len(client.appels) == 3, (
        f"{len(client.appels)} appels pour tours_max=3. Sans borne, une boucle d'outils "
        "tourne tant que le modele demande des outils : c'est votre budget qui sert de borne."
    )
    assert resultat == module.MESSAGE_BORNE


def test_boucle_tours_max_un(module, client):
    client.programmer(outil("chercher_documents", {"requete": "Alpha"}), texte("jamais lu"))
    resultat = module.demander(client, "Question", executer=ExecuteurFactice(), tours_max=1)
    assert resultat == module.MESSAGE_BORNE
    assert len(client.appels) == 1


def test_boucle_texte_sans_content_zero(module, client):
    client.programmer(
        FausseReponse(
            content=[BlocReflexion(), BlocTexte("Premiere partie. "), BlocTexte("Suite.")]
        )
    )
    resultat = module.demander(client, "Question", executer=ExecuteurFactice())
    assert resultat == "Premiere partie. Suite.", (
        "Concatenez tous les blocs de type texte. content[0] peut etre un bloc de "
        "raisonnement ou un tool_use : content[0].text casse des qu'un outil est declare."
    )


def test_boucle_transmet_tool_choice_et_outils(module, client):
    cassee = module.avec_description(
        module.OUTILS, "chercher_documents", module.DESCRIPTION_MEDIOCRE
    )
    client.programmer(texte("ok"))
    module.demander(client, "Question", outils=cassee, tool_choice={"type": "any"})
    envoye = client.appels[0]
    assert envoye["tool_choice"] == {"type": "any"}, "tool_choice doit etre transmis tel quel."
    assert envoye["tools"] == cassee, "Les outils passes en parametre remplacent OUTILS."


# Exercice 6 (bonus) : journaliser


def test_journaliser(module):
    journal: list[dict[str, Any]] = []
    interne = ExecuteurFactice(erreur_pour=("outil_fantome",))
    executer = module.journaliser(interne, journal)

    assert executer("chercher_documents", {"requete": "Alpha"}) == (
        "resultat de chercher_documents #1",
        False,
    ), "L'executeur journalise doit rendre exactement ce que rend l'executeur d'origine."
    executer("outil_fantome", {})

    assert [e["nom"] for e in journal] == ["chercher_documents", "outil_fantome"]
    assert journal[0]["entree"] == {"requete": "Alpha"}
    assert [e["is_error"] for e in journal] == [False, True]
    assert all(isinstance(e["duree"], float) and e["duree"] >= 0 for e in journal)


@pytest.mark.reel
def test_boucle_reelle(module, pytestconfig, tmp_path):
    if not pytestconfig.getoption("--reel"):
        pytest.skip("Ajoutez --reel pour appeler la vraie API.")
    import anthropic

    journal: list[dict[str, Any]] = []
    executer = module.journaliser(partial(module.executer_outil, dossier_fiches=tmp_path), journal)
    resultat = module.demander(
        anthropic.Anthropic(), "Quelles sont les echeances du contrat Alpha ?", executer=executer
    )
    assert any(e["nom"] == "chercher_documents" for e in journal), (
        "Avec la description complete, Claude devrait chercher dans le corpus avant de repondre."
    )
    assert resultat and resultat != module.MESSAGE_BORNE
