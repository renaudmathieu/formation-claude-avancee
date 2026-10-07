"""Section 1, le contrat.

Si ces tests passent, le code de l'atelier est pret : il ne reste qu'a le
lancer contre la vraie API, remplir le tableau, ecrire votre regle de
routage dans NOTES.md, puis commiter le checkpoint etape/01-premier-appel.
"""

from __future__ import annotations

import inspect
import re

import anthropic
import pytest
from fakes import Usage, texte

from doc42.config import MAX_TOKENS_DEFAUT, MODELE_DEFAUT, MODELE_PROFOND, MODELE_RAPIDE, TARIFS
from doc42.corpus import trouver

CLE_FACTICE = "sk-ant-api03-FACTICE-NE-PAS-AFFICHER"


def horloge_factice(*instants: float):
    """Une horloge qui rend les instants donnes, puis echoue si on en demande trop."""
    restants = list(instants)

    def lire() -> float:
        assert restants, (
            "L'horloge a ete lue plus de fois que prevu : deux lectures par "
            "appel, juste avant et juste apres."
        )
        return restants.pop(0)

    return lire


# --- Etape 1 : l'environnement ----------------------------------------------


def test_diagnostic_vert(module):
    problemes = module.diagnostiquer({"ANTHROPIC_API_KEY": CLE_FACTICE}, (3, 12))
    assert problemes == [], f"Environnement correct, aucun probleme attendu. Recu : {problemes}"


def test_diagnostic_cle_absente(module):
    for environ in ({}, {"ANTHROPIC_API_KEY": ""}):
        problemes = module.diagnostiquer(environ, (3, 13))
        assert any("ANTHROPIC_API_KEY" in p for p in problemes), (
            "Une cle absente ou vide doit etre signalee, en nommant ANTHROPIC_API_KEY."
        )


@pytest.mark.parametrize(
    "cle",
    ["cle-copiee-du-mauvais-endroit", '"sk-ant-api03-ENTRE-GUILLEMETS"', "sk-ant-api03-COUPEE EN"],
)
def test_diagnostic_cle_mal_formee_sans_la_reveler(module, cle):
    problemes = module.diagnostiquer({"ANTHROPIC_API_KEY": cle}, (3, 12))
    assert any("ANTHROPIC_API_KEY" in p for p in problemes), (
        f"La cle {cle!r} est mal formee (prefixe sk-ant-, espace ou guillemet) et "
        "doit etre signalee."
    )
    assert not any(cle in p or cle.strip('"') in p for p in problemes), (
        "Le diagnostic affiche la cle. Decrivez le defaut, jamais la valeur."
    )


def test_diagnostic_ne_revele_jamais_la_cle(module):
    problemes = module.diagnostiquer({"ANTHROPIC_API_KEY": CLE_FACTICE}, (3, 10))
    assert not any("FACTICE" in p for p in problemes), (
        "Un message de diagnostic contient la cle. Elle finira dans un terminal "
        "partage ou un ticket : decrivez le probleme sans jamais l'afficher."
    )


def test_diagnostic_version_python(module):
    problemes = module.diagnostiquer({"ANTHROPIC_API_KEY": CLE_FACTICE}, (3, 11))
    assert any("3.12" in p for p in problemes), "Python 3.11 doit etre signale (3.12+ requis)."


def test_diagnostic_modele_sans_tarif(module, monkeypatch):
    monkeypatch.setattr(module, "TARIFS", {MODELE_DEFAUT: TARIFS[MODELE_DEFAUT]})
    problemes = module.diagnostiquer({"ANTHROPIC_API_KEY": CLE_FACTICE}, (3, 12))
    for modele in (MODELE_RAPIDE, MODELE_PROFOND):
        assert any(modele in p for p in problemes), (
            f"{modele} n'a pas de tarif : le tableau comparatif serait faux. "
            "Signalez chaque modele de MODELES absent de TARIFS."
        )


# --- Etape 2 : le premier appel ---------------------------------------------


def test_premier_appel_rend_texte_usage_et_stop_reason(module, client):
    usage = Usage(input_tokens=14, output_tokens=23)
    client.programmer(texte("Je suis Claude.", usage=usage))

    resultat = module.premier_appel(client)

    assert isinstance(resultat, tuple) and len(resultat) == 3, (
        "premier_appel doit retourner un tuple (texte, usage, stop_reason)."
    )
    sortie, usage_rendu, stop_reason = resultat
    assert sortie == "Je suis Claude.", "Le texte doit etre une chaine, pas l'objet reponse."
    assert usage_rendu is usage, "usage doit etre l'objet usage de la reponse, tel quel."
    assert stop_reason == "end_turn"

    envoye = client.appels[0]
    assert envoye["model"] == MODELE_DEFAUT, (
        "Le modele doit venir de doc42.config (MODELE_DEFAUT), pas etre code en dur."
    )
    assert envoye["max_tokens"] == MAX_TOKENS_DEFAUT
    assert envoye["messages"] == [{"role": "user", "content": "Presente-toi en une phrase."}]

    # La regle de la section : un identifiant de modele s'ecrit a un seul endroit.
    trouves = re.findall(r"claude-[a-z0-9.-]+", inspect.getsource(module))
    assert not trouves, (
        f"Identifiant(s) de modele ecrit(s) en dur : {trouves}. "
        "Ils vivent dans doc42/config.py et nulle part ailleurs."
    )


def test_premier_appel_ne_suppose_pas_stop_reason(module, client):
    client.programmer(texte("Je suis", stop_reason="max_tokens"))
    _, _, stop_reason = module.premier_appel(client, "Raconte ta vie.")
    assert stop_reason == "max_tokens", (
        "stop_reason doit venir de la reponse : ici elle a ete coupee par max_tokens."
    )
    assert client.appels[0]["messages"][0]["content"] == "Raconte ta vie."


# --- Etape 3 : mesurer et comparer -------------------------------------------


def test_cout_estime_par_million(module):
    entree, sortie = TARIFS[MODELE_DEFAUT]
    assert module.cout_estime(MODELE_DEFAUT, 1_000_000, 0) == pytest.approx(entree), (
        "Les tarifs de TARIFS sont en dollars par MILLION de tokens d'entree."
    )
    assert module.cout_estime(MODELE_DEFAUT, 0, 1_000_000) == pytest.approx(sortie)
    attendu = (2_000 * entree + 500 * sortie) / 1_000_000
    assert module.cout_estime(MODELE_DEFAUT, 2_000, 500) == pytest.approx(attendu), (
        "Cout = entree x tarif d'entree + sortie x tarif de sortie, divise par un million."
    )


def test_cout_modele_inconnu(module):
    with pytest.raises(ValueError):
        module.cout_estime("modele-inexistant", 10, 10)


def test_mesurer_remplit_la_mesure(module, client):
    client.programmer(
        texte("- a\n- b\n- c", usage=Usage(input_tokens=1200, output_tokens=80)),
    )

    mesure = module.mesurer(
        client, MODELE_RAPIDE, "Resume.", horloge=horloge_factice(100.0, 101.25)
    )

    assert isinstance(mesure, module.Mesure)
    assert mesure.modele == MODELE_RAPIDE
    assert mesure.texte == "- a\n- b\n- c"
    assert (mesure.tokens_entree, mesure.tokens_sortie) == (1200, 80), (
        "Les tokens viennent de usage.input_tokens et usage.output_tokens."
    )
    assert mesure.duree == pytest.approx(1.25), (
        "La duree est la difference entre les deux lectures de l'horloge injectee."
    )
    assert mesure.cout == pytest.approx(module.cout_estime(MODELE_RAPIDE, 1200, 80))
    assert mesure.stop_reason == "end_turn"

    envoye = client.appels[0]
    assert envoye["model"] == MODELE_RAPIDE
    assert envoye["max_tokens"] == MAX_TOKENS_DEFAUT, (
        "Meme max_tokens pour tous les modeles, sinon la comparaison n'est pas equitable."
    )
    assert "system" not in envoye, "Sans systeme, n'envoyez pas de parametre system."


def test_mesurer_encadre_l_appel(module, client):
    lectures: list[int] = []

    def horloge() -> float:
        lectures.append(len(client.appels))
        return float(len(lectures))

    module.mesurer(client, MODELE_DEFAUT, "Bonjour.", horloge=horloge)

    assert lectures == [0, 1], (
        f"L'horloge a ete lue apres {lectures} appel(s). Attendu : une lecture juste "
        "avant l'appel (0 appel fait) et une juste apres (1 appel fait)."
    )


def test_comparer_meme_consigne_trois_modeles(module, client):
    document = trouver("note_rh_teletravail")
    consigne = module.consigne_resume(document)
    client.programmer(
        texte("rapide", usage=Usage(input_tokens=400, output_tokens=60)),
        texte("defaut", usage=Usage(input_tokens=400, output_tokens=90)),
        texte("profond", usage=Usage(input_tokens=400, output_tokens=150)),
    )

    mesures = module.comparer(client, consigne, horloge=horloge_factice(0, 1, 1, 3, 3, 7))

    assert [m.modele for m in mesures] == [MODELE_RAPIDE, MODELE_DEFAUT, MODELE_PROFOND], (
        "Un resultat par modele, dans l'ordre de MODELES (du plus leger au plus capable)."
    )
    assert [a["model"] for a in client.appels] == [MODELE_RAPIDE, MODELE_DEFAUT, MODELE_PROFOND]
    assert all(a["messages"] == client.appels[0]["messages"] for a in client.appels), (
        "Les trois modeles doivent recevoir exactement la meme consigne."
    )
    assert "trois puces" in client.appels[0]["messages"][0]["content"]
    assert "2,50 euros" in client.appels[0]["messages"][0]["content"], (
        "Le document du corpus doit etre dans la consigne."
    )
    assert [m.duree for m in mesures] == [1, 2, 4]
    assert [m.tokens_sortie for m in mesures] == [60, 90, 150]


def test_tache_triviale_l_ecart_de_cout_reste(module, client):
    # Trois fois la meme reponse, au token pres : la qualite ne departage plus.
    client.programmer(
        *(texte("oui", usage=Usage(input_tokens=60, output_tokens=1)) for _ in range(3))
    )

    mesures = module.comparer(
        client,
        module.consigne_reclamation("Troisieme relance, la facture est toujours fausse."),
        horloge=horloge_factice(0, 1, 1, 2, 2, 3),
    )

    assert {m.texte for m in mesures} == {"oui"}
    rapide, defaut, profond = (m.cout for m in mesures)
    assert rapide < defaut < profond, (
        "A reponse identique, le cout doit suivre le tarif de chaque modele. "
        "Verifiez que cout_estime recoit bien le modele de la mesure."
    )


def test_bonus_systeme_transmis_a_tous(module, client):
    module.comparer(
        client, "Resume.", horloge=horloge_factice(0, 1, 1, 2, 2, 3), systeme=module.SYSTEME_CONCIS
    )
    assert [a.get("system") for a in client.appels] == [module.SYSTEME_CONCIS] * 3, (
        "Le prompt systeme du bonus doit etre transmis a chacun des trois modeles."
    )


def test_tableau_markdown(module):
    mesures = [
        module.Mesure(MODELE_RAPIDE, "x", 400, 60, 1.0, 0.0007, "end_turn"),
        module.Mesure(MODELE_PROFOND, "y", 400, 150, 4.256, 0.00575, "end_turn"),
    ]

    lignes = module.tableau(mesures).split("\n")

    assert lignes[0] == "| Modele | Entree | Sortie | Cout ($) | Duree (s) | Qualite |"
    assert lignes[1] == "|---|---|---|---|---|---|"
    assert len(lignes) == 4, "Un en-tete, un separateur, puis une ligne par mesure."
    assert lignes[2] == f"| {MODELE_RAPIDE} | 400 | 60 | 0.000700 | 1.00 |  |"
    assert lignes[3] == f"| {MODELE_PROFOND} | 400 | 150 | 0.005750 | 4.26 |  |", (
        "Cout avec 6 decimales, duree avec 2, colonne Qualite vide : "
        "la qualite est votre jugement, pas celui du code."
    )


# --- Etape 5 : la regle de routage -------------------------------------------


@pytest.mark.parametrize(
    ("tache", "attendu"),
    [
        ("tri", MODELE_RAPIDE),
        ("classification", MODELE_RAPIDE),
        ("support", MODELE_RAPIDE),
        ("analyse", MODELE_DEFAUT),
        (" Redaction ", MODELE_DEFAUT),
        ("r" + chr(0xE9) + "daction", MODELE_DEFAUT),  # avec accent
        ("code", MODELE_DEFAUT),
        ("raisonnement", MODELE_PROFOND),
        ("AGENT", MODELE_PROFOND),
    ],
)
def test_choisir_modele(module, tache, attendu):
    assert module.choisir_modele(tache) == attendu, (
        f"choisir_modele({tache!r}) : attendu {attendu}. Majuscules, accents et "
        "espaces autour ne doivent pas changer le resultat."
    )


def test_choisir_modele_commence_leger(module):
    assert module.choisir_modele("tache jamais vue") == MODELE_RAPIDE, (
        "Pour une tache inconnue, on essaie le plus leger d'abord, et on ne monte "
        "que si on constate qu'il echoue."
    )


def test_monter_en_gamme(module):
    assert module.monter_en_gamme(MODELE_RAPIDE) == MODELE_DEFAUT
    assert module.monter_en_gamme(MODELE_DEFAUT) == MODELE_PROFOND
    assert module.monter_en_gamme(MODELE_PROFOND) is None, (
        "Au-dessus du modele profond, il n'y a plus de palier : None."
    )
    with pytest.raises(ValueError):
        module.monter_en_gamme("modele-inexistant")


@pytest.mark.reel
def test_premier_appel_reel(module, pytestconfig):
    if not pytestconfig.getoption("--reel"):
        pytest.skip("Ajoutez --reel pour appeler la vraie API.")
    assert module.diagnostiquer() == [], "Corrigez l'environnement avant l'appel reel."
    sortie, usage, stop_reason = module.premier_appel(anthropic.Anthropic())
    assert sortie
    assert usage.input_tokens > 0 and usage.output_tokens > 0
    assert stop_reason in ("end_turn", "max_tokens")
