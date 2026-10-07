"""Section 10, le contrat.

Si ces tests passent, la definition de termine est atteinte et vous pouvez
commiter le checkpoint etape/10-prod : chaque appel produit un log JSON
complet, le cout d'une question est chiffre et sa baisse mesuree, une panne
donne une reponse degradee, les prompts sont versionnes et aucune cle ne
traine dans le code ni dans les journaux.

Tout est deterministe : l'horloge, le chronometre, les identifiants et les
attentes sont injectes. Aucun test n'attend, aucun ne touche le reseau.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anthropic
import pytest
from fakes import FausseReponse, FauxClient, Usage, texte
from fakes import erreur_sdk as _erreur

from doc42 import client as client_doc42
from doc42.config import (
    FACTEUR_CACHE_ECRIT,
    FACTEUR_CACHE_LU,
    MAX_TOKENS_DEFAUT,
    MODELE_DEFAUT,
    MODELE_PROFOND,
    MODELE_RAPIDE,
    SYSTEME_DOC42,
    TARIFS,
)

RACINE = Path(__file__).parent.parent

# Construite par morceaux pour que ce fichier ne contienne pas lui-meme
# une chaine qui ressemble a une cle (le test du code la chercherait).
FAUSSE_CLE = "sk-ant-" + "api03-" + "FAUSSEcleDEtest0123456789_abcdefXYZ"

INSTANT = datetime(2026, 10, 7, 14, 23, 45, 123000, tzinfo=UTC)

CHAMPS_OBLIGATOIRES = {
    "timestamp",
    "event",
    "request_id",
    "feature",
    "prompt_version",
    "model",
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "latency_ms",
    "stop_reason",
    "cost_usd",
    "success",
}


def chrono_scenarise(*instants: float):
    """Un chronometre qui rend les instants donnes, dans l'ordre."""
    file = list(instants)
    return lambda: file.pop(0)


def chrono_lineaire(pas: float = 0.5):
    """Un chronometre qui avance de `pas` secondes a chaque lecture."""
    etat = {"t": 0.0}

    def lire() -> float:
        etat["t"] += pas
        return etat["t"]

    return lire


def instrumenter(module, client, journal: list[str], **contexte):
    contexte.setdefault("horloge", lambda: INSTANT)
    contexte.setdefault("chrono", chrono_lineaire())
    compteur = iter(range(1, 10_000))
    contexte.setdefault("generer_id", lambda: f"req_{next(compteur):04d}")
    return module.ClientInstrumente(client, journal.append, **contexte)


def lignes(journal: list[str]) -> list[dict]:
    return [json.loads(ligne) for ligne in journal]


# ---------------------------------------------------------------------------
# Exercice 1 : le cout d'un appel
# ---------------------------------------------------------------------------


def test_cout_compte_les_quatre_postes(module):
    usage = Usage(
        input_tokens=1000,
        output_tokens=200,
        cache_read_input_tokens=10_000,
        cache_creation_input_tokens=2000,
    )
    entree, sortie = TARIFS[MODELE_DEFAUT]
    attendu = (
        1000 * entree
        + 200 * sortie
        + 10_000 * entree * FACTEUR_CACHE_LU
        + 2000 * entree * FACTEUR_CACHE_ECRIT
    ) / 1_000_000

    cout = module.cout_appel(MODELE_DEFAUT, usage)

    sans_ecriture = attendu - 2000 * entree * FACTEUR_CACHE_ECRIT / 1_000_000
    assert cout != pytest.approx(sans_ecriture), (
        "L'ecriture en cache n'est pas comptee. Elle coute "
        f"{FACTEUR_CACHE_ECRIT} fois le tarif d'entree : c'est le premier appel, "
        "le plus cher, que vous sous-estimez."
    )
    assert cout == pytest.approx(attendu), (
        f"Cout attendu {attendu:.6f} $, obtenu {cout}. Quatre postes : entree, sortie, "
        "cache lu (FACTEUR_CACHE_LU) et cache ecrit (FACTEUR_CACHE_ECRIT), en dollars "
        "par MILLION de tokens, tarifs de doc42.config.TARIFS."
    )

    leger = module.cout_appel(MODELE_RAPIDE, Usage(input_tokens=1000, output_tokens=200))
    assert leger < module.cout_appel(MODELE_DEFAUT, Usage(input_tokens=1000, output_tokens=200)), (
        "Le meme appel doit couter moins cher sur MODELE_RAPIDE : lisez le tarif du modele "
        "demande, pas un tarif unique."
    )


def test_cout_robuste_et_explicite(module):
    usage = Usage(input_tokens=100, output_tokens=10)
    usage.cache_read_input_tokens = None
    usage.cache_creation_input_tokens = None
    entree, sortie = TARIFS[MODELE_RAPIDE]
    assert module.cout_appel(MODELE_RAPIDE, usage) == pytest.approx(
        (100 * entree + 10 * sortie) / 1_000_000
    ), "Le SDK rend None pour les champs de cache inutilises : traitez None comme 0."

    with pytest.raises(ValueError):
        module.cout_appel("modele-sans-tarif", usage)


# ---------------------------------------------------------------------------
# Exercice 2 : un log JSON par appel
# ---------------------------------------------------------------------------


def test_un_log_json_complet_par_appel(module, client):
    journal: list[str] = []
    reponse_programmee = FausseReponse(
        content=texte("Trois echeances.").content,
        usage=Usage(
            input_tokens=1523,
            output_tokens=287,
            cache_read_input_tokens=1200,
            cache_creation_input_tokens=0,
        ),
    )
    client.programmer(reponse_programmee)
    instrumente = module.ClientInstrumente(
        client,
        journal.append,
        feature="question",
        prompt_version="doc42_systeme@v2#0123abcd",
        user_id="u42",
        question_id="q1",
        horloge=lambda: INSTANT,
        chrono=chrono_scenarise(10.0, 12.34),
        generer_id=lambda: "req_abc123",
    )

    reponse = instrumente.messages.create(
        model=MODELE_DEFAUT,
        max_tokens=MAX_TOKENS_DEFAUT,
        system=SYSTEME_DOC42,
        messages=[{"role": "user", "content": "Quelles echeances ?"}],
    )

    assert reponse is reponse_programmee, "Le wrapper doit rendre la reponse intacte."
    assert len(client.appels) == 1, "Le wrapper doit appeler le vrai client exactement une fois."
    assert client.appels[0]["model"] == MODELE_DEFAUT, "Les parametres passent sans modification."
    assert len(journal) == 1, f"Un appel, une ligne de journal ; obtenu {len(journal)}."
    assert "\n" not in journal[0], "Une ligne de journal tient sur une ligne (format JSON Lines)."

    ligne = json.loads(journal[0])
    manquants = CHAMPS_OBLIGATOIRES - set(ligne)
    assert not manquants, f"Champs manquants dans le log : {sorted(manquants)}"
    assert ligne["event"] == "claude_call"
    assert ligne["timestamp"] == "2026-10-07T14:23:45.123+00:00", (
        "L'horodatage vient de l'horloge injectee : horloge().isoformat(timespec='milliseconds')."
    )
    assert ligne["request_id"] == "req_abc123", "L'identifiant vient de generer_id()."
    assert ligne["latency_ms"] == 2340, (
        f"Latence attendue 2340 ms (chrono 10.0 puis 12.34), obtenu {ligne['latency_ms']}. "
        "Lisez chrono() juste avant et juste apres l'appel, convertissez en millisecondes."
    )
    assert ligne["model"] == MODELE_DEFAUT
    assert ligne["feature"] == "question"
    assert ligne["prompt_version"] == "doc42_systeme@v2#0123abcd"
    assert ligne["question_id"] == "q1" and ligne["user_id"] == "u42"
    assert (ligne["input_tokens"], ligne["output_tokens"]) == (1523, 287)
    assert ligne["cache_read_input_tokens"] == 1200
    assert ligne["stop_reason"] == "end_turn"
    assert ligne["success"] is True
    assert ligne["cost_usd"] == pytest.approx(
        module.cout_appel(MODELE_DEFAUT, reponse_programmee.usage), abs=1e-6
    ), "Le cout du log est celui de cout_appel, calcule sur le modele DEMANDE."


def test_branche_sur_le_client_existant(module, client):
    journal: list[str] = []
    instrumente = instrumenter(module, client, journal, feature="question")

    reponse = client_doc42.appel_simple(instrumente, "Quelles sont les echeances de paiement ?")
    conversation = client_doc42.Conversation(instrumente.avec(feature="conversation"))
    conversation.demander("Bonjour.")
    conversation.demander("Et les echeances ?")

    assert "15/01/2027" in reponse, "La reponse doit traverser le wrapper sans alteration."
    assert len(client.appels) == 3
    assert [ligne["feature"] for ligne in lignes(journal)] == [
        "question",
        "conversation",
        "conversation",
    ], (
        "Chaque appel de doc42.client doit produire sa ligne, sans modifier doc42.client : "
        "le wrapper se presente comme un client (instrumente.messages.create)."
    )


def test_les_logs_ne_contiennent_pas_les_conversations(module, client):
    journal: list[str] = []
    instrumente = instrumenter(module, client, journal)
    confidentiel = "Mon numero de securite sociale est 1 85 07 75 123 456 78"

    client_doc42.appel_simple(instrumente, confidentiel, systeme="Consigne interne Hexalis 7731")

    assert "1 85 07 75" not in journal[0] and "7731" not in journal[0], (
        "Le log contient le texte de la conversation. Journalisez les metadonnees "
        "(modele, tokens, cout, latence), jamais messages ni system : c'est une fuite "
        "de donnees personnelles et une explosion de stockage."
    )


def test_un_echec_est_journalise_puis_relance(module, client):
    journal: list[str] = []
    erreur = _erreur(anthropic.InternalServerError)
    client.programmer(erreur)
    instrumente = instrumenter(module, client, journal, chrono=chrono_scenarise(1.0, 1.25))

    with pytest.raises(anthropic.InternalServerError):
        instrumente.messages.create(model=MODELE_DEFAUT, max_tokens=10, messages=[])

    assert len(journal) == 1, "Un appel en echec doit aussi laisser sa ligne de journal."
    ligne = json.loads(journal[0])
    assert ligne["success"] is False
    assert ligne["error_type"] == "InternalServerError"
    assert ligne["latency_ms"] == 250
    assert ligne["model"] == MODELE_DEFAUT


def test_aucune_cle_dans_les_journaux(module, client):
    assert module.masquer_secrets(f"cle {FAUSSE_CLE} refusee") == "cle sk-ant-*** refusee"
    assert module.masquer_secrets("voir la doc sk-ant-...") == "voir la doc sk-ant-...", (
        "Ne masquez qu'une vraie cle (au moins 8 caracteres apres sk-ant-)."
    )

    journal: list[str] = []
    client.api_key = FAUSSE_CLE
    erreur = _erreur(anthropic.AuthenticationError)
    Exception.__init__(erreur, f"Invalid x-api-key: {FAUSSE_CLE}")
    client.programmer(texte("ok"), erreur)
    instrumente = instrumenter(module, client, journal)

    instrumente.messages.create(model=MODELE_DEFAUT, max_tokens=10, messages=[])
    with pytest.raises(anthropic.AuthenticationError):
        instrumente.messages.create(model=MODELE_DEFAUT, max_tokens=10, messages=[])

    assert len(journal) == 2
    for ligne in journal:
        assert "FAUSSEcleDEtest" not in ligne, (
            "Une cle API apparait dans le journal. Passez tout message d'erreur dans "
            "masquer_secrets avant de l'ecrire : un journal est lu par bien plus de "
            "monde qu'un gestionnaire de secrets."
        )


def test_un_tarif_manquant_ne_casse_pas_l_appel(module, client):
    journal: list[str] = []
    instrumente = instrumenter(module, client, journal)

    reponse = instrumente.messages.create(model="modele-sans-tarif", max_tokens=10, messages=[])

    assert reponse is not None
    ligne = json.loads(journal[0])
    assert ligne["success"] is True
    assert ligne["cost_usd"] is None, (
        "Modele sans tarif : cost_usd vaut None (inconnu), et l'appel reussit quand meme. "
        "L'observabilite ne doit jamais casser le produit."
    )


# ---------------------------------------------------------------------------
# Exercice 3 : agreger les journaux
# ---------------------------------------------------------------------------


def _ligne(feature, cout, question_id=None, version="v1", latence=100, succes=True, req="r"):
    return {
        "event": "claude_call",
        "request_id": req,
        "question_id": question_id,
        "feature": feature,
        "prompt_version": version,
        "cost_usd": cout,
        "latency_ms": latence,
        "success": succes,
    }


def test_agreger_cout_par_feature_et_par_question(module):
    journal = [
        _ligne("classification", 0.001, "q1", req="a"),
        _ligne("question", 0.010, "q1", req="b"),
        _ligne("question", 0.012, "q1", req="c"),
        _ligne("classification", 0.001, "q2", req="d"),
        _ligne("question", 0.008, "q2", req="e"),
        _ligne("question", 0.0, "q2", succes=False, req="f"),
        {"event": "autre_chose", "cost_usd": 99.0},
    ]

    bilan = module.agreger(journal)

    assert bilan["appels"] == 6, "Seules les lignes event == 'claude_call' comptent."
    assert bilan["echecs"] == 1
    assert bilan["cout_total_usd"] == pytest.approx(0.032)
    assert bilan["par_feature"]["classification"]["appels"] == 2
    assert bilan["par_feature"]["classification"]["cout_usd"] == pytest.approx(0.002)
    assert bilan["par_feature"]["question"]["cout_usd"] == pytest.approx(0.030)
    assert bilan["questions"] == 2, (
        "Une question peut couter plusieurs appels : regroupez par question_id."
    )
    assert bilan["cout_moyen_question_usd"] == pytest.approx(0.016), (
        "Cout moyen d'une question = cout total / nombre de questions distinctes, "
        "pas / nombre d'appels. C'est ce chiffre qui surprend."
    )


def test_agreger_lit_du_jsonl_versions_et_centiles(module):
    journal = [
        json.dumps(_ligne("question", 0.01, version="v1" if i % 2 else "v2", latence=i, req=str(i)))
        for i in range(1, 101)
    ]
    journal.append("")
    journal.append(json.dumps(_ligne("question", None, latence=None, req="sans_tarif")))

    bilan = module.agreger(journal)

    assert bilan["appels"] == 101, "agreger accepte des lignes JSON (str) et ignore les vides."
    assert bilan["couts_inconnus"] == 1, "Un cost_usd None compte comme inconnu, pas comme erreur."
    assert bilan["questions"] == 101, "Sans question_id, chaque appel est sa propre question."
    assert set(bilan["par_version"]) == {"v1", "v2"}, (
        "Le cout par prompt_version permet de comparer deux versions d'un prompt."
    )
    assert bilan["par_version"]["v2"]["appels"] == 50
    assert bilan["latence_p50_ms"] == 50, "p50 par la methode du rang le plus proche."
    assert bilan["latence_p99_ms"] == 99


# ---------------------------------------------------------------------------
# Exercice 4 : les trois leviers de cout
# ---------------------------------------------------------------------------


def test_routage_vers_le_bon_modele(module):
    assert module.choisir_modele("classification") == MODELE_RAPIDE, (
        "Levier 1 : la classification part sur le modele leger."
    )
    assert module.choisir_modele("extraction") == MODELE_RAPIDE
    assert module.choisir_modele("question") == MODELE_DEFAUT
    assert module.choisir_modele("raisonnement_critique") == MODELE_PROFOND
    assert module.choisir_modele("fonction_inconnue") == MODELE_DEFAUT, (
        "Une fonctionnalite inconnue va sur le modele par defaut, pas sur le plus cher."
    )


def test_parametres_prefixe_stable_et_cache(module):
    corpus = "CORPUS DE REFERENCE HEXALIS " * 50
    p1 = module.parametres("question", "Quelles echeances ?", corpus)
    p2 = module.parametres("question", "Qui signe l'avenant ?", corpus)

    assert p1["model"] == MODELE_DEFAUT
    assert isinstance(p1["system"], list), "Pour poser un point de cache, system est une liste."
    assert p1["system"] == p2["system"], (
        "Le prefixe (system) doit etre STRICTEMENT identique d'une question a l'autre, "
        "sinon le cache est annule sans aucun message. Rien de variable dans system."
    )
    assert p1["system"][0]["text"] == SYSTEME_DOC42
    assert p1["system"][-1].get("cache_control") == {"type": "ephemeral"}, (
        "Le point de cache se pose sur le DERNIER bloc stable (le corpus de reference)."
    )
    assert corpus in [bloc["text"] for bloc in p1["system"]]
    assert "Quelles echeances" not in json.dumps(p1["system"]), (
        "La question varie : elle va dans messages, apres le prefixe cache."
    )
    assert p1["messages"] == [{"role": "user", "content": "Quelles echeances ?"}]

    classif = module.parametres("classification", "Est-ce une question RH ?", corpus)
    assert classif["model"] == MODELE_RAPIDE
    assert classif["max_tokens"] <= 64, (
        f"max_tokens={classif['max_tokens']} pour une classification. Levier 3 : "
        "une etiquette tient en quelques tokens, un plafond haut laisse deriver."
    )
    assert module.parametres("fonction_inconnue", "?")["max_tokens"] == MAX_TOKENS_DEFAUT
    for feature in ("classification", "extraction", "question", "synthese"):
        assert module.parametres(feature, "?")["max_tokens"] <= MAX_TOKENS_DEFAUT


def test_la_baisse_du_cout_est_mesuree(module):
    """Avant / apres sur deux questions : la baisse doit depasser 50 %."""
    corpus = "CORPUS " * 1000
    questions = ["Le texte parle-t-il de paiement ?", "Le texte parle-t-il de RH ?"]

    # Avant : tout sur le modele par defaut, sans cache, max_tokens large.
    avant: list[str] = []
    brut = FauxClient().programmer(
        *[FausseReponse(content=texte("oui").content, usage=Usage(6000, 300)) for _ in questions]
    )
    for i, question in enumerate(questions):
        instrumente = instrumenter(module, brut, avant, feature="classification")
        instrumente.avec(question_id=f"q{i}").messages.create(
            model=MODELE_DEFAUT,
            max_tokens=MAX_TOKENS_DEFAUT,
            system=SYSTEME_DOC42 + corpus,
            messages=[{"role": "user", "content": question}],
        )

    # Apres : les parametres optimises. Le faux client simule ce que l'API
    # facturerait : ecriture en cache au premier appel, lecture au second.
    apres: list[str] = []
    optimise = FauxClient().programmer(
        FausseReponse(content=texte("oui").content, usage=Usage(100, 5, 0, 5900)),
        FausseReponse(content=texte("oui").content, usage=Usage(100, 5, 5900, 0)),
    )
    for i, question in enumerate(questions):
        instrumente = instrumenter(module, optimise, apres, feature="classification")
        instrumente.avec(question_id=f"q{i}").messages.create(
            **module.parametres("classification", question, corpus)
        )

    cout_avant = module.agreger(avant)["cout_moyen_question_usd"]
    cout_apres = module.agreger(apres)["cout_moyen_question_usd"]
    assert cout_avant > 0 and cout_apres > 0
    assert cout_apres <= cout_avant / 2, (
        f"Cout moyen d'une question : {cout_avant:.6f} $ avant, {cout_apres:.6f} $ apres. "
        "L'objectif est de diviser par deux au moins : routage, cache, max_tokens."
    )


# ---------------------------------------------------------------------------
# Exercice 5 : reprise, disjoncteur, reponse degradee
# ---------------------------------------------------------------------------


def _panne():
    return _erreur(anthropic.APIConnectionError)


def _echoue():
    raise _panne()


def test_le_disjoncteur_s_ouvre_et_protege_l_api(module):
    temps = {"t": 100.0}
    disjoncteur = module.Disjoncteur(seuil=3, delai_s=60.0, chrono=lambda: temps["t"])
    essais = {"n": 0}

    def appel():
        essais["n"] += 1
        raise _panne()

    for _ in range(3):
        with pytest.raises(anthropic.APIConnectionError):
            disjoncteur.appeler(appel)
    assert disjoncteur.etat == "ouvert", "Apres `seuil` echecs consecutifs, le circuit s'ouvre."

    temps["t"] += 30
    with pytest.raises(module.CircuitOuvert):
        disjoncteur.appeler(appel)
    assert essais["n"] == 3, (
        "Circuit ouvert : l'appel doit etre refuse SANS contacter l'API. "
        "C'est tout l'interet : ne pas aggraver une panne."
    )


def test_le_disjoncteur_se_referme_apres_le_delai(module):
    temps = {"t": 0.0}
    disjoncteur = module.Disjoncteur(seuil=2, delai_s=60.0, chrono=lambda: temps["t"])

    for _ in range(2):
        with pytest.raises(anthropic.APIConnectionError):
            disjoncteur.appeler(_echoue)

    temps["t"] = 61.0
    with pytest.raises(anthropic.APIConnectionError):
        disjoncteur.appeler(_echoue)
    assert disjoncteur.etat == "ouvert", (
        "Delai ecoule : un seul appel d'essai (semi-ouvert). S'il echoue, le circuit se "
        "rouvre immediatement, sans attendre `seuil` nouveaux echecs."
    )

    temps["t"] = 130.0
    assert disjoncteur.appeler(lambda: "ok") == "ok"
    assert disjoncteur.etat == "ferme", "Un appel d'essai reussi referme le circuit."
    assert disjoncteur.echecs == 0


def test_un_400_ne_coupe_pas_le_circuit_et_remonte(module, client):
    disjoncteur = module.Disjoncteur(seuil=1, chrono=lambda: 0.0)
    client.programmer(_erreur(anthropic.BadRequestError))

    with pytest.raises(anthropic.BadRequestError):
        module.repondre(client, "?", disjoncteur, dormir=lambda _: None)

    assert disjoncteur.etat == "ferme" and disjoncteur.echecs == 0, (
        "Un 400 est un bug de votre code, pas une panne du service : il ne doit ni "
        "ouvrir le circuit, ni etre cache derriere le message degrade."
    )
    assert len(client.appels) == 1, "Un 400 ne se rejoue pas."


def test_une_panne_donne_une_reponse_degradee(module, client):
    attentes: list[float] = []
    disjoncteur = module.Disjoncteur(seuil=3, delai_s=60.0, chrono=lambda: 0.0)
    client.programmer(*[_panne() for _ in range(10)])

    reponse = module.repondre(client, "Quelles echeances ?", disjoncteur, 5, attentes.append)

    assert reponse == module.MESSAGE_DEGRADE, (
        "Une panne doit produire le message degrade, pas une exception remontee a l'utilisateur."
    )
    assert len(client.appels) == 3, (
        f"{len(client.appels)} appels envoyes. Le disjoncteur doit etre DANS la reprise : "
        "des qu'il s'ouvre (3 echecs), CircuitOuvert arrete les tentatives restantes."
    )
    assert disjoncteur.etat == "ouvert"
    assert attentes, "La reprise attend entre deux tentatives, via `dormir` (injecte)."

    deuxieme = module.repondre(client, "Et maintenant ?", disjoncteur, 5, attentes.append)
    assert deuxieme == module.MESSAGE_DEGRADE
    assert len(client.appels) == 3, "Circuit ouvert : aucune requete de plus vers l'API."


class TransportEnPanne:
    """Transport HTTP qui echoue toujours, comme une URL injoignable.

    Aucun octet ne sort de la machine : la requete est refusee avant le reseau.
    """

    def __init__(self) -> None:
        self.requetes = 0

    def handle_request(self, requete):
        self.requetes += 1
        raise OSError("connexion refusee : doc42.invalid injoignable")

    def close(self) -> None:
        return None


def test_panne_simulee_avec_le_vrai_sdk(module):
    transport = TransportEnPanne()
    vrai = module.creer_client_production(
        FAUSSE_CLE,
        base_url="http://doc42.invalid",
        http_client=anthropic.DefaultHttpxClient(transport=transport),
    )
    assert vrai.max_retries == 0, (
        "Le SDK rejoue deja 2 fois par defaut. Sous avec_reprise, chaque tentative en "
        "deviendrait 3, avec des attentes invisibles dans vos journaux : max_retries=0."
    )
    assert vrai.timeout is not None and float(vrai.timeout) <= 60, (
        "Fixez un timeout explicite (anti-pattern 10.1 : un client pendu des minutes)."
    )

    journal: list[str] = []
    instrumente = instrumenter(module, vrai, journal)
    disjoncteur = module.Disjoncteur(seuil=2, chrono=lambda: 0.0)

    reponse = module.repondre(instrumente, "Quelles echeances ?", disjoncteur, 3, lambda _: None)

    assert reponse == module.MESSAGE_DEGRADE
    assert transport.requetes == 2, (
        f"{transport.requetes} requetes HTTP : il en faut exactement 2 (seuil du disjoncteur)."
    )
    assert [ligne["error_type"] for ligne in lignes(journal)] == ["APIConnectionError"] * 2
    assert all("FAUSSEcleDEtest" not in ligne for ligne in journal)


# ---------------------------------------------------------------------------
# Exercice 6 : prompts versionnes
# ---------------------------------------------------------------------------


def publier(dossier: Path, nom: str, version: str, contenu: str, courante: bool = True) -> None:
    """Publie un prompt dans un dossier de test, empreinte comprise."""
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{nom}.{version}.md"
    chemin.write_text(contenu, encoding="utf-8")
    registre_chemin = dossier / "registre.json"
    registre = json.loads(registre_chemin.read_text()) if registre_chemin.exists() else {}
    entree = registre.setdefault(nom, {"courante": version, "versions": {}})
    entree["versions"][version] = hashlib.sha256(chemin.read_bytes()).hexdigest()
    if courante:
        entree["courante"] = version
    registre_chemin.write_text(json.dumps(registre, indent=2), encoding="utf-8")


def test_charger_prompt_versionne(module, tmp_path):
    publier(tmp_path, "doc42_systeme", "v1", SYSTEME_DOC42 + "\n")
    publier(tmp_path, "doc42_systeme", "v2", SYSTEME_DOC42 + " Tu cites tes sources.\n")

    courant = module.charger_prompt("doc42_systeme", dossier=tmp_path)
    ancien = module.charger_prompt("doc42_systeme", "v1", dossier=tmp_path)

    assert courant.version == "v2", "Par defaut, la version 'courante' du registre."
    assert ancien.version == "v1" and ancien.texte == SYSTEME_DOC42, (
        "Le texte est le contenu du fichier sans les blancs de fin : v1 doit redonner "
        "exactement SYSTEME_DOC42, sinon le prefixe change et le cache saute."
    )
    attendu = hashlib.sha256((tmp_path / "doc42_systeme.v2.md").read_bytes()).hexdigest()
    assert courant.empreinte == attendu, "L'empreinte est le sha256 des octets du fichier."
    assert courant.identifiant == f"doc42_systeme@v2#{attendu[:8]}"

    with pytest.raises(KeyError):
        module.charger_prompt("inexistant", dossier=tmp_path)
    with pytest.raises(KeyError):
        module.charger_prompt("doc42_systeme", "v9", dossier=tmp_path)


def test_une_version_publiee_est_immuable(module, tmp_path):
    publier(tmp_path, "doc42_systeme", "v1", SYSTEME_DOC42 + "\n")
    chemin = tmp_path / "doc42_systeme.v1.md"
    chemin.write_text(SYSTEME_DOC42.replace("explicitement", "clairement") + "\n")

    with pytest.raises(ValueError):
        module.charger_prompt("doc42_systeme", dossier=tmp_path)


def test_la_version_est_journalisee_avec_chaque_appel(module, client, tmp_path):
    publier(tmp_path, "doc42_systeme", "v1", SYSTEME_DOC42 + "\n")
    prompt = module.charger_prompt("doc42_systeme", dossier=tmp_path)
    journal: list[str] = []
    instrumente = instrumenter(module, client, journal, prompt_version=prompt.identifiant)

    client_doc42.appel_simple(instrumente, "Bonjour.", systeme=prompt.texte)
    client_doc42.appel_simple(instrumente, "Encore.", systeme=prompt.texte)

    assert client.appels[0]["system"] == SYSTEME_DOC42
    versions = {ligne["prompt_version"] for ligne in lignes(journal)}
    assert versions == {prompt.identifiant}, (
        "Chaque ligne de journal porte l'identifiant du prompt (nom@version#empreinte) : "
        "c'est ce qui relie une regression a la version qui l'a introduite."
    )
    assert module.agreger(journal)["par_version"][prompt.identifiant]["appels"] == 2


def test_aucune_cle_dans_le_code(module):
    dossiers = ["doc42", "exercices", "solutions", "scripts", "prompts", ".etapes"]
    fichiers = [RACINE / ".env.example", RACINE / "pyproject.toml"]
    for nom in dossiers:
        for chemin in (RACINE / nom).rglob("*"):
            if chemin.suffix in {".py", ".md", ".json", ".toml", ".txt", ".yaml"}:
                fichiers.append(chemin)

    fuites = [
        str(chemin.relative_to(RACINE))
        for chemin in fichiers
        if chemin.is_file()
        and module.masquer_secrets(chemin.read_text(encoding="utf-8", errors="ignore"))
        != chemin.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not fuites, (
        f"Une chaine en forme de cle API apparait dans : {fuites}. La cle vit dans .env "
        "(ignore par Git) ou dans un gestionnaire de secrets, jamais dans le code. "
        "En equipe, un outil comme gitleaks en pre-commit l'empeche avant le commit."
    )


# ---------------------------------------------------------------------------
# Exercice 7 : quota par utilisateur et validation d'entree
# ---------------------------------------------------------------------------


def test_quota_depasse_volontairement(module):
    maintenant = {"t": INSTANT}
    quota = module.Quota(
        requetes_par_jour=3, budget_usd_par_jour=10.0, horloge=lambda: maintenant["t"]
    )

    for _ in range(3):
        quota.reserver("alice")
    with pytest.raises(module.QuotaDepasse):
        quota.reserver("alice")

    quota.reserver("bastien")  # le quota est PAR utilisateur

    maintenant["t"] = INSTANT + timedelta(days=1)
    quota.reserver("alice")  # nouveau jour, compteurs remis a zero


def test_quota_en_dollars(module):
    quota = module.Quota(requetes_par_jour=100, budget_usd_par_jour=1.0, horloge=lambda: INSTANT)

    quota.reserver("alice")
    quota.imputer("alice", 0.6)
    quota.reserver("alice")
    quota.imputer("alice", 0.5)  # l'appel a eu lieu : imputer ne leve jamais
    quota.imputer("alice", None)

    with pytest.raises(module.QuotaDepasse):
        quota.reserver("alice")


def test_valider_question(module):
    assert module.valider_question("  Quelles echeances ?  ") == "Quelles echeances ?"
    with pytest.raises(ValueError):
        module.valider_question("   ")
    with pytest.raises(ValueError):
        module.valider_question("x" * (module.LONGUEUR_MAX_QUESTION + 1))


# ---------------------------------------------------------------------------
# Contre la vraie API (optionnel)
# ---------------------------------------------------------------------------


@pytest.mark.reel
def test_appel_reel_instrumente(module, pytestconfig):
    if not pytestconfig.getoption("--reel"):
        pytest.skip("Ajoutez --reel pour appeler la vraie API.")
    journal: list[str] = []
    instrumente = module.ClientInstrumente(module.creer_client_production(), journal.append)

    client_doc42.appel_simple(instrumente, "Reponds exactement : PRET")

    ligne = json.loads(journal[0])
    assert ligne["success"] is True
    assert ligne["input_tokens"] > 0 and ligne["output_tokens"] > 0
    assert ligne["cost_usd"] and ligne["cost_usd"] > 0
    assert module.masquer_secrets(journal[0]) == journal[0], "Une cle apparait dans le journal."
