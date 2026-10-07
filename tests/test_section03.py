"""Section 3, le contrat.

Si ces tests passent, la definition de termine est atteinte cote code et vous
pouvez commiter le checkpoint etape/03-prompts. Les mesures sur la vraie API
(etapes 5 et 6) restent a faire et a ecrire dans prompts/CHANGELOG.md.

Le faux client ne juge pas un prompt : il rend des reponses scenarisees
(client.programmer) pour verifier que VOTRE code decode, valide, relance et
note correctement.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import anthropic
import pytest
from fakes import erreur_sdk, texte

from doc42.config import MAX_TOKENS_DEFAUT, MODELE_DEFAUT, MODELE_PROFOND, MODELE_RAPIDE
from doc42.corpus import trouver

RACINE = Path(__file__).parent.parent
CHEMIN_JEU = RACINE / "evals" / "attendu.json"
MODELES = (MODELE_DEFAUT, MODELE_RAPIDE, MODELE_PROFOND)


def _jeu() -> list[dict]:
    # Lu directement, sans passer par le module : le jeu de reference ne doit
    # pas dependre du code qu'il sert a evaluer.
    return json.loads(CHEMIN_JEU.read_text(encoding="utf-8"))["cas"]


def _attendu(document: str) -> dict:
    return copy.deepcopy(next(c["attendu"] for c in _jeu() if c["document"] == document))


def _json(donnees: dict) -> str:
    return json.dumps(donnees, ensure_ascii=False)


def _bloc(prompt: str, balise: str) -> str:
    trouve = re.search(rf"<{balise}>(.*?)</{balise}>", prompt, re.DOTALL)
    assert trouve, f"Bloc <{balise}>...</{balise}> absent ou non ferme dans le prompt."
    return trouve.group(1)


# Exercice 1 : le prompt systeme structure


def test_systeme_balises_dans_l_ordre(module):
    prompt = module.construire_systeme()
    assert isinstance(prompt, str) and prompt

    positions = []
    for balise in ("role", "context", "instructions", "constraints", "examples"):
        _bloc(prompt, balise)
        positions.append(prompt.index(f"<{balise}>"))
    assert positions == sorted(positions), (
        "Les blocs doivent venir dans l'ordre role, context, instructions, constraints, "
        "examples : du plus general au plus concret."
    )
    assert re.search(r"^\s*1\.", _bloc(prompt, "instructions"), re.MULTILINE), (
        "Les instructions doivent etre numerotees (« 1. », « 2. »...)."
    )


def test_systeme_decrit_tout_le_contrat(module):
    prompt = module.construire_systeme()
    for cle in module.CLES + module.CLES_ECHEANCE:
        assert cle in prompt, f"La cle {cle!r} n'apparait pas : le modele ne peut pas la deviner."
    for valeur in module.TYPES:
        assert valeur in prompt, (
            f"La valeur de type {valeur!r} n'apparait pas. Sans la liste, le modele "
            "invente ses propres types et la validation echoue."
        )
    contraintes = _bloc(prompt, "constraints")
    assert "[]" in contraintes or "liste vide" in contraintes.lower(), (
        "Les contraintes doivent dire qu'un document sans echeance donne une liste vide. "
        "Sinon le modele comble le vide avec des dates inventees."
    )


def test_systeme_exemple_valide_et_fictif(module):
    exemples = _bloc(module.construire_systeme(), "examples")
    debut, fin = exemples.find("{"), exemples.rfind("}")
    assert debut != -1, "Le bloc <examples> doit contenir la sortie JSON attendue."
    sortie = json.loads(exemples[debut : fin + 1])
    assert module.valider(sortie) == [], (
        "L'exemple ne respecte pas le schema. Le modele imite l'exemple plus que la "
        "consigne : un exemple faux enseigne l'erreur."
    )

    prompt = module.construire_systeme().lower()
    for cas in _jeu():
        for partie in cas["attendu"]["parties"]:
            nom = partie.lower().split()[0]
            if nom != "hexalis":
                assert nom not in prompt, (
                    f"Le prompt cite {partie!r}, une partie du jeu de test. Un exemple tire "
                    "du jeu donne la reponse au modele et fausse la mesure : prenez un "
                    "document fictif."
                )


def test_systeme_sans_exemple(module):
    prompt = module.construire_systeme(exemple=False)
    assert "<examples>" not in prompt, "exemple=False doit retirer le bloc <examples>."
    for balise in ("role", "context", "instructions", "constraints"):
        _bloc(prompt, balise)


# Exercice 2 : extraire_json


@pytest.mark.parametrize(
    "brut",
    [
        '{"type": "facture"}',
        '```json\n{"type": "facture"}\n```',
        '```\n{"type": "facture"}\n```',
        'Voici le resultat :\n{"type": "facture"}\nBonne journee.',
        'Voici :\n```json\n{"type": "facture"}\n```\nN\'hesitez pas.',
    ],
)
def test_extraire_json_nettoie(module, brut):
    assert module.extraire_json(brut) == {"type": "facture"}, (
        "Le JSON doit etre retrouve meme entre balises de code ou entoure de texte."
    )


@pytest.mark.parametrize(
    "brut",
    ['{"type": "facture", "date": ', "Pas de JSON ici.", "", "[1, 2, 3]", "```json\n```"],
)
def test_extraire_json_refuse(module, brut):
    with pytest.raises(ValueError):
        module.extraire_json(brut)


# Exercice 3 : valider


def test_valider_accepte_tout_le_jeu(module):
    for cas in _jeu():
        assert module.valider(cas["attendu"]) == [], (
            f"{cas['document']} : l'attendu du jeu de reference est refuse. "
            "valider() est trop strict (montant null ? liste vide ? date null ?)."
        )


@pytest.mark.parametrize(
    ("modification", "cle"),
    [
        (lambda d: d.pop("echeances"), "echeances"),
        (lambda d: d.update(resume="..."), "resume"),
        (lambda d: d.update(type="memo"), "type"),
        (lambda d: d.update(date="02/11/2026"), "date"),
        (lambda d: d.update(date="2027-02-30"), "date"),
        (lambda d: d.update(parties="Hexalis SAS"), "parties"),
        (lambda d: d["echeances"][0].update(montant_ht="16 000"), "montant_ht"),
        (lambda d: d["echeances"][0].update(montant_ht=True), "montant_ht"),
        (lambda d: d["echeances"][1].update(date="15/04/2027"), "date"),
        (lambda d: d["echeances"][2].pop("montant_ht"), "montant_ht"),
    ],
)
def test_valider_refuse_et_nomme_la_cle(module, modification, cle):
    donnees = _attendu("contrat_alpha")
    modification(donnees)
    erreurs = module.valider(donnees)
    assert erreurs, f"Donnees invalides acceptees (cle {cle!r})."
    assert any(cle in e for e in erreurs), (
        f"Aucune erreur ne nomme {cle!r} : {erreurs}. Le message part dans la relance, "
        "le modele doit savoir quoi corriger."
    )


def test_valider_ne_leve_jamais(module):
    for donnees in (None, [], "texte", {"echeances": [None, 3]}, {"parties": [1, ""]}):
        assert module.valider(donnees), f"{donnees!r} devrait donner au moins une erreur."


# Exercice 4 : extraire


def test_extraire_premier_envoi(module, client):
    document = trouver("contrat_alpha")
    client.programmer(texte(_json(_attendu("contrat_alpha"))))

    resultat = module.extraire(client, document)

    assert resultat == _attendu("contrat_alpha")
    envoye = client.appels[0]
    assert envoye["model"] in MODELES, "Le modele doit venir de doc42.config."
    assert envoye["max_tokens"] == MAX_TOKENS_DEFAUT
    assert "<role>" in envoye["system"], (
        "Sans systeme explicite, extraire() doit utiliser construire_systeme()."
    )
    assert [m["role"] for m in envoye["messages"]] == ["user"], (
        "Sans prefill, un seul message user."
    )
    contenu = envoye["messages"][0]["content"]
    assert isinstance(contenu, str) and document.texte in contenu
    ouverture, fermeture = contenu.find("<document"), contenu.find("</document>")
    assert -1 < ouverture < contenu.index(document.texte) < fermeture, (
        "Le texte du document doit etre entoure de <document ...> et </document>."
    )
    assert contenu[fermeture + len("</document>") :].strip(), (
        "La consigne vient APRES le document : sur un texte long, la question en fin "
        "de message est mieux suivie."
    )


def test_extraire_systeme_fourni(module, client):
    client.programmer(texte(_json(_attendu("facture_F2026-118"))))
    module.extraire(client, trouver("facture_F2026-118"), "PROMPT V1", modele=MODELE_RAPIDE)
    assert client.appels[0]["system"] == "PROMPT V1"
    assert client.appels[0]["model"] == MODELE_RAPIDE


def test_extraire_relance_json_invalide(module, client):
    attendu = _attendu("facture_F2026-118")
    client.programmer(
        texte('Voici : {"type": "facture", "date": '),
        texte(f"```json\n{_json(attendu)}\n```"),
    )

    resultat = module.extraire(client, trouver("facture_F2026-118"))

    assert resultat == attendu
    assert len(client.appels) == 2, "Un JSON invalide doit declencher exactement une relance."
    messages = client.appels[1]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"], (
        "La relance montre au modele sa reponse fautive (assistant) puis les erreurs (user)."
    )
    assert '"type": "facture", "date": ' in messages[1]["content"]
    assert client.appels[1]["system"] == client.appels[0]["system"]


def test_extraire_relance_schema_avec_les_erreurs(module, client):
    attendu = _attendu("contrat_alpha")
    fautif = {**attendu, "type": "memo"}
    client.programmer(texte(_json(fautif)), texte(_json(attendu)))

    assert module.extraire(client, trouver("contrat_alpha")) == attendu
    relance = client.appels[1]["messages"][-1]["content"]
    assert "type" in relance and "memo" in relance, (
        "Le message de relance doit lister les erreurs de valider(). Redemander sans "
        "dire pourquoi donne souvent la meme erreur."
    )


def test_extraire_abandonne_apres_les_tentatives(module, client):
    client.programmer(texte("non"), texte("toujours pas"), texte("{pas du json"))

    with pytest.raises(module.ErreurExtraction) as erreur:
        module.extraire(client, trouver("contrat_alpha"))

    assert len(client.appels) == 3, f"{len(client.appels)} appels au lieu de 3 (tentatives=3)."
    assert erreur.value.brut == "{pas du json", "brut doit etre le texte de la derniere reponse."
    assert erreur.value.erreurs, "Les erreurs de la derniere tentative doivent etre transmises."


def test_extraire_respecte_tentatives(module, client):
    client.programmer(texte("non"), texte("non"), texte("non"))
    with pytest.raises(module.ErreurExtraction):
        module.extraire(client, trouver("contrat_alpha"), tentatives=1)
    assert len(client.appels) == 1


def test_extraire_ne_relance_pas_une_erreur_api(module, client):
    client.programmer(erreur_sdk(anthropic.BadRequestError))
    with pytest.raises(anthropic.BadRequestError):
        module.extraire(client, trouver("contrat_alpha"))
    assert len(client.appels) == 1, (
        "Une erreur de l'API n'est pas un JSON invalide : la relance corrige un contenu, "
        "pas un transport. Laissez-la remonter."
    )


def test_extraire_prefill(module, client):
    attendu = _attendu("contrat_alpha")
    # Avec prefill, le modele continue apres « { » : sa reponse ne la contient pas.
    client.programmer(texte('"type": "contrat"}'), texte(_json(attendu)[1:]))

    resultat = module.extraire(client, trouver("contrat_alpha"), prefill=True)

    assert resultat == attendu, (
        "Le modele continue apres l'accolade prefillee : remettez « { » devant sa reponse."
    )
    for appel in client.appels:
        assert appel["messages"][-1] == {"role": "assistant", "content": "{"}, (
            "Avec prefill, CHAQUE envoi (relance comprise) se termine par l'assistant « { »."
        )
    historique = client.appels[1]["messages"]
    assert [m["role"] for m in historique] == ["user", "assistant", "user", "assistant"]
    assert historique[1]["content"].startswith("{"), (
        "La reponse fautive rendue au modele doit inclure l'accolade du prefill."
    )


# Exercice 5 : le jeu de test


def test_jeu_de_reference(module):
    jeu = module.charger_jeu()
    assert len(jeu) == 10, "Le jeu de test compte dix documents."
    identifiants = [c["document"] for c in jeu]
    assert len(set(identifiants)) == 10
    vides = [c for c in jeu if c["attendu"]["echeances"] == []]
    pleins = [c for c in jeu if c["attendu"]["echeances"]]
    assert vides, "Etape 7 : le jeu doit contenir au moins un document sans echeance."
    assert len(pleins) >= 3
    alpha = next(c for c in jeu if c["document"] == "contrat_alpha")
    assert [e["date"] for e in alpha["attendu"]["echeances"]] == [
        "2027-01-15",
        "2027-04-15",
        "2027-07-15",
    ]


def _ecrire_jeu(chemin: Path, cas: list[dict]) -> Path:
    chemin.write_text(json.dumps({"description": "test", "cas": cas}), encoding="utf-8")
    return chemin


def test_jeu_document_inconnu(module, tmp_path):
    chemin = _ecrire_jeu(
        tmp_path / "jeu.json", [{"document": "contrat_omega", "attendu": _attendu("contrat_alpha")}]
    )
    with pytest.raises(ValueError, match="contrat_omega"):
        module.charger_jeu(chemin)


def test_jeu_doublon(module, tmp_path):
    cas = {"document": "contrat_alpha", "attendu": _attendu("contrat_alpha")}
    chemin = _ecrire_jeu(tmp_path / "jeu.json", [cas, cas])
    with pytest.raises(ValueError, match="contrat_alpha"):
        module.charger_jeu(chemin)


def test_jeu_attendu_invalide(module, tmp_path):
    fautif = {**_attendu("facture_F2026-118"), "date": "30/09/2026"}
    chemin = _ecrire_jeu(
        tmp_path / "jeu.json", [{"document": "facture_F2026-118", "attendu": fautif}]
    )
    with pytest.raises(ValueError, match="facture_F2026-118"):
        module.charger_jeu(chemin)


# Exercice 6 : evaluer_cas


def test_cas_reussi(module):
    attendu = _attendu("contrat_alpha")
    resultat = module.evaluer_cas("contrat_alpha", _json(attendu), attendu)
    assert resultat.reussi and resultat.ecarts == []
    assert resultat.document == "contrat_alpha"


def test_cas_tolere_la_forme(module):
    attendu = _attendu("contrat_beta")
    obtenu = copy.deepcopy(attendu)
    obtenu["type"] = "Contrat"
    obtenu["parties"] = ["beta sante", "HEXALIS"]
    obtenu["echeances"] = list(reversed(obtenu["echeances"]))
    obtenu["echeances"][0]["montant_ht"] = 30000.0
    resultat = module.evaluer_cas("contrat_beta", f"```json\n{_json(obtenu)}\n```", attendu)
    assert resultat.reussi, (
        f"Ecarts de pure forme comptes comme des erreurs : {resultat.ecarts}. Casse, accents, "
        "forme juridique, ordre et 30000 contre 30000.0 ne changent pas le sens."
    )


def test_cas_json_invalide(module):
    resultat = module.evaluer_cas("contrat_alpha", '{"type": ', _attendu("contrat_alpha"))
    assert not resultat.json_valide and not resultat.reussi
    assert resultat.ecarts


def test_cas_cle_manquante(module):
    attendu = _attendu("contrat_alpha")
    obtenu = {k: v for k, v in attendu.items() if k != "echeances"}
    resultat = module.evaluer_cas("contrat_alpha", _json(obtenu), attendu)
    assert resultat.json_valide and not resultat.cles_ok and not resultat.reussi
    assert any("echeances" in e for e in resultat.ecarts)


def test_cas_montant_et_echeance_manquante(module):
    attendu = _attendu("contrat_alpha")
    obtenu = copy.deepcopy(attendu)
    obtenu["echeances"][1]["montant_ht"] = 15000
    obtenu["echeances"].pop(2)
    resultat = module.evaluer_cas("contrat_alpha", _json(obtenu), attendu)
    assert resultat.cles_ok and not resultat.valeurs_ok
    assert any("2027-04-15" in e for e in resultat.ecarts), (
        "L'ecart doit nommer la date dont le montant differe."
    )
    assert any("2027-07-15" in e and "manquante" in e for e in resultat.ecarts), (
        "Une echeance attendue absente doit etre signalee « manquante » avec sa date."
    )


def test_cas_sans_echeance_date_inventee(module):
    attendu = _attendu("compte_rendu_gamma")
    obtenu = {**attendu, "echeances": [{"date": "2026-10-15", "montant_ht": None}]}
    resultat = module.evaluer_cas("compte_rendu_gamma", _json(obtenu), attendu)
    assert not resultat.reussi, (
        "Etape 7 : un document sans echeance doit produire une liste vide. Une date en "
        "trop dans un JSON valide reste une invention."
    )
    assert any("2026-10-15" in e and "inventee" in e for e in resultat.ecarts)


def test_cas_mal_forme_sans_exception(module):
    attendu = _attendu("contrat_alpha")
    for obtenu in (
        {**attendu, "parties": "Hexalis SAS"},
        {**attendu, "echeances": "15/01/2027"},
        {**attendu, "echeances": [{"montant_ht": 16000}]},
    ):
        resultat = module.evaluer_cas("contrat_alpha", _json(obtenu), attendu)
        assert not resultat.reussi and resultat.ecarts


def test_cas_date_et_parties(module):
    attendu = _attendu("rapport_incident_2026-08-12")
    obtenu = {**attendu, "date": "2026-08-12", "parties": ["Hexalis SAS"]}
    resultat = module.evaluer_cas("rapport_incident_2026-08-12", _json(obtenu), attendu)
    assert not resultat.valeurs_ok
    assert any("date" in e for e in resultat.ecarts)
    assert any("parties" in e for e in resultat.ecarts)


# Exercice 7 : evaluer et resume


def test_evaluer_tout_le_jeu(module, client):
    jeu = _jeu()
    reponses = []
    for cas in jeu:
        attendu = copy.deepcopy(cas["attendu"])
        if cas["document"] == "facture_F2026-118":
            reponses.append(texte('```json\n{"type": "facture", "date": '))
        elif cas["document"] == "compte_rendu_gamma":
            attendu["echeances"] = [{"date": "2026-10-15", "montant_ht": None}]
            reponses.append(texte(_json(attendu)))
        elif cas["document"] == "contrat_alpha":
            attendu["parties"] = ["Alpha Logistique", "hexalis"]
            reponses.append(texte(f"Voici :\n```json\n{_json(attendu)}\n```"))
        else:
            reponses.append(texte(_json(attendu)))
    client.programmer(*reponses)

    rapport = module.evaluer(client, jeu)

    assert len(client.appels) == 10, (
        f"{len(client.appels)} appels pour 10 documents. Par defaut, une seule tentative : "
        "on mesure le prompt, pas la relance."
    )
    for appel, cas in zip(client.appels, jeu, strict=True):
        texte_document = trouver(cas["document"]).texte
        assert texte_document in appel["messages"][0]["content"], (
            "Les documents doivent etre envoyes dans l'ordre du jeu."
        )
    assert [r.document for r in rapport.resultats] == [c["document"] for c in jeu]
    assert rapport.taux == pytest.approx(0.8)
    assert sorted(r.document for r in rapport.echecs) == [
        "compte_rendu_gamma",
        "facture_F2026-118",
    ], "Le JSON invalide doit etre note comme un echec, pas lever d'exception."
    facture = next(r for r in rapport.resultats if r.document == "facture_F2026-118")
    assert not facture.json_valide


def test_evaluer_transmet_les_options(module, client):
    jeu = [c for c in _jeu() if c["document"] == "note_rh_teletravail"]
    client.programmer(texte('"type": "memo"}'), texte(_json(jeu[0]["attendu"])[1:]))

    rapport = module.evaluer(
        client, jeu, "PROMPT", prefill=True, tentatives=2, modele=MODELE_RAPIDE
    )

    assert rapport.taux == 1.0
    assert len(client.appels) == 2, "tentatives=2 doit etre transmis a extraire()."
    assert all(a["system"] == "PROMPT" and a["model"] == MODELE_RAPIDE for a in client.appels)
    assert client.appels[0]["messages"][-1] == {"role": "assistant", "content": "{"}


def test_resume(module):
    rapport = module.Rapport(
        [
            module.Resultat("contrat_alpha", True, True, True),
            module.Resultat("facture_F2026-118", False, False, False, ["JSON invalide"]),
            module.Resultat("compte_rendu_gamma", True, True, False, ["inventee : 2026-10-15"]),
            module.Resultat("contrat_beta", True, True, True),
        ]
    )
    texte_resume = module.resume(rapport)
    assert "2/4" in texte_resume and "50 %" in texte_resume, (
        "Le resume commence par le taux chiffre : « Taux de reussite : 2/4 (50 %) »."
    )
    for echec in ("facture_F2026-118", "JSON invalide", "compte_rendu_gamma", "2026-10-15"):
        assert echec in texte_resume, f"Le resume doit lister les echecs ({echec!r} absent)."
    assert "contrat_alpha" not in texte_resume, "Les documents reussis n'encombrent pas la liste."

    tout_bon = module.resume(module.Rapport([module.Resultat("contrat_alpha", True, True, True)]))
    assert "1/1" in tout_bon and "100 %" in tout_bon


# Bonus : le juge


def test_juger(module, client):
    document = trouver("contrat_alpha")
    extraction = _attendu("contrat_alpha")
    client.programmer(texte("<analyse>Les trois echeances sont exactes.</analyse>\n<note>4</note>"))

    assert module.juger(client, document, extraction) == 4

    envoye = client.appels[0]
    assert envoye["model"] in MODELES and envoye["max_tokens"] == MAX_TOKENS_DEFAUT
    contenu = json.dumps(envoye["messages"], ensure_ascii=False)
    assert "Alpha Logistique" in contenu and "2027-04-15" in contenu, (
        "Le juge doit voir le document ET l'extraction a noter."
    )
    assert "<note>" in envoye["system"] + contenu, "Dites au juge ou mettre sa note."


@pytest.mark.parametrize("reponse", ["Je mettrais 4/5.", "<note>7</note>", "<note>0</note>"])
def test_juger_refuse_une_note_illisible(module, client, reponse):
    client.programmer(texte(reponse))
    with pytest.raises(ValueError):
        module.juger(client, trouver("contrat_alpha"), _attendu("contrat_alpha"))


def test_divergences(module):
    humain = {"contrat_alpha": 5, "contrat_beta": 2, "facture_F2026-118": 4, "politique_achats": 3}
    juge = {"contrat_alpha": 4, "contrat_beta": 5, "facture_F2026-118": 4}
    assert module.divergences(juge, humain) == ["contrat_beta", "politique_achats"]
    assert module.divergences(juge, humain, ecart_max=0) == [
        "contrat_alpha",
        "contrat_beta",
        "politique_achats",
    ]


# Contre la vraie API


@pytest.mark.reel
def test_extraction_reelle(module, pytestconfig):
    if not pytestconfig.getoption("--reel"):
        pytest.skip("Ajoutez --reel pour appeler la vraie API.")
    vrai = anthropic.Anthropic()
    donnees = module.extraire(vrai, trouver("contrat_alpha"))
    resultat = module.evaluer_cas("contrat_alpha", _json(donnees), _attendu("contrat_alpha"))
    assert resultat.reussi, f"Extraction reelle de contrat_alpha en echec : {resultat.ecarts}"
