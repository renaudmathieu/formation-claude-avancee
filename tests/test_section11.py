"""Section 11, le contrat commun aux trois variantes.

Ces tests ne disent pas si votre variante est bonne : ils disent si elle est
livrable. Quelle que soit la variante choisie (support, analyseur, code),
elle doit les passer avant la presentation et avant de commiter le
checkpoint etape/11-final.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import anthropic
import pytest
from fakes import Usage, outil, texte
from fakes import erreur_sdk as _erreur

from doc42 import outils as outils_doc42
from doc42.config import FACTEUR_CACHE_ECRIT, FACTEUR_CACHE_LU, MODELE_DEFAUT, TARIFS

RACINE = Path(__file__).parent.parent
CORPUS = RACINE / "corpus"

SPEC_VALIDE = """# Specification : analyseur de contrats

## Quoi
Doc42 repond aux questions sur les contrats d'Hexalis et cite ses sources.
Entree : « Quelles sont les echeances du contrat Alpha ? »
Sortie : « 15/01/2027, 15/04/2027 et 15/07/2027 [contrat_alpha] »

## Critere de reussite
Huit questions sur dix du jeu d'evaluation recoivent une reponse correctement sourcee.

## Hors perimetre
- Interface graphique
- Documents scannes
- Deploiement en production

## Risque principal
L'extraction des dates echoue sur les formats ecrits en toutes lettres.
"""

EXTRAIT_ALPHA = (
    "[contrat_alpha] Contrat Alpha\n16 000 euros HT au 15/01/2027, 15/04/2027, 15/07/2027"
)


def _executeur(appels: list):
    def executer(nom, entree):
        appels.append((nom, entree))
        if nom == "chercher_documents":
            return EXTRAIT_ALPHA
        return "Fiche creee : fiches/test.md"

    return executer


def _variante(module, appels=None, irreversibles=frozenset({"creer_fiche"}), **kwargs):
    return module.Variante(
        nom="test",
        systeme="Tu es Doc42. Cite tes sources entre crochets.",
        outils=outils_doc42.DEFINITIONS,
        executer=_executeur(appels if appels is not None else []),
        irreversibles=irreversibles,
        **kwargs,
    )


def _cas(module, n=10):
    return [
        module.CasEval(question=f"q{i}", attendus=["15/04/2027"], sources=["contrat_alpha"])
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Exercice 1 : specification
# ---------------------------------------------------------------------------


def test_specification_valide(module):
    assert module.verifier_specification(SPEC_VALIDE) == [], (
        "Une specification complete ne doit lever aucun probleme. Un critere ecrit en "
        "lettres (« huit questions sur dix ») est chiffre lui aussi."
    )
    en_chiffres = SPEC_VALIDE.replace("Huit questions sur dix", "8 questions sur 10")
    assert module.verifier_specification(en_chiffres) == []


def test_specification_accepte_les_titres_de_la_page(module):
    spec = (
        SPEC_VALIDE.replace("## Critere de reussite", "## Comment on saura que ça marche")
        .replace("## Hors perimetre", "## Ce qui est hors périmètre")
        .replace("## Risque principal", "## Le risque principal")
    )
    assert module.verifier_specification(spec) == [], (
        "Les titres de la page Notion (avec accents) doivent etre reconnus : "
        "comparez des textes normalises (doc42.outils.normaliser)."
    )


def test_specification_signale_chaque_manque(module):
    sans_risque = SPEC_VALIDE.split("## Risque principal")[0]
    problemes = module.verifier_specification(sans_risque)
    assert any("Risque" in p for p in problemes), "La section Risque principal manque."

    pourquoi = SPEC_VALIDE.replace("## Quoi", "## Pourquoi")
    assert any("Quoi" in p for p in module.verifier_specification(pourquoi)), (
        "« Pourquoi » n'est pas « Quoi » : cherchez le mot en debut de mot, pas n'importe ou."
    )

    vague = SPEC_VALIDE.replace(
        "Huit questions sur dix du jeu d'evaluation recoivent", "Les questions recoivent"
    )
    assert any("chiffre" in p for p in module.verifier_specification(vague)), (
        "Un critere sans chiffre est une opinion, pas un constat : signalez-le."
    )


def test_specification_exige_trois_hors_perimetre(module):
    spec = SPEC_VALIDE.replace("- Documents scannes\n", "")
    problemes = module.verifier_specification(spec)
    assert any("Hors perimetre" in p for p in problemes), (
        "Deux elements hors perimetre ne suffisent pas, la page en demande au moins trois."
    )


def test_specification_exige_un_exemple(module):
    spec = SPEC_VALIDE.replace("Entree :", "Question :")
    assert any("Quoi" in p for p in module.verifier_specification(spec)), (
        "Le Quoi doit contenir un exemple d'entree ET un exemple de sortie attendue."
    )


# ---------------------------------------------------------------------------
# Exercice 2 : anonymisation
# ---------------------------------------------------------------------------


def test_anonymiser_retire_les_donnees_personnelles(module):
    brut = (
        "Contact : rh@hexalis.example, tel 06 12 34 56 78 ou +33 1 23 45 67 89.\n"
        "IBAN FR76 3000 6000 0112 3456 7890 189 pour le virement."
    )
    propre, n = module.anonymiser(brut)
    assert "rh@hexalis.example" not in propre and "[EMAIL]" in propre
    assert "06 12 34 56 78" not in propre and "+33 1 23 45 67 89" not in propre, (
        "Les numeros de telephone (0X XX XX XX XX et +33) doivent etre masques."
    )
    assert "FR76" not in propre and "[IBAN]" in propre, (
        "L'IBAN doit etre masque en entier, pas decoupe en faux numeros de telephone : "
        "traitez-le avant les telephones."
    )
    assert n == 4, f"Quatre remplacements attendus, {n} comptes."


def test_anonymiser_ne_touche_pas_aux_dates_ni_aux_montants(module):
    contrat = (CORPUS / "contrat_alpha.md").read_text(encoding="utf-8")
    propre, n = module.anonymiser(contrat)
    assert n == 0 and propre == contrat, (
        "Le contrat Alpha ne contient aucune donnee personnelle detectable : dates "
        "(15/01/2027) et montants (16 000 euros) doivent rester intacts."
    )


# ---------------------------------------------------------------------------
# Exercice 3 : la variante declare ses garde-fous
# ---------------------------------------------------------------------------


def test_variante_conforme(module):
    assert module.verifier_variante(_variante(module)) == []


def test_variante_garde_fou_fantome(module):
    variante = _variante(module, irreversibles=frozenset({"creer_fiche", "creer_fiches"}))
    problemes = module.verifier_variante(variante)
    assert any("creer_fiches" in p for p in problemes), (
        "Un outil declare irreversible mais qui n'existe pas est un garde-fou qui ne se "
        "declenchera jamais. Signalez-le."
    )


def test_variante_outil_qui_ecrit_non_declare(module):
    problemes = module.verifier_variante(_variante(module, irreversibles=frozenset()))
    assert any("creer_fiche" in p for p in problemes), (
        "creer_fiche ecrit un fichier (sa description le dit) : s'il n'est pas declare "
        "irreversible, il passera sans confirmation humaine."
    )
    assert not any("chercher_documents" in p for p in problemes), (
        "chercher_documents ne fait que lire : ne le signalez pas."
    )


def test_variante_modele_sans_tarif_et_outil_sans_description(module):
    definitions = [dict(outils_doc42.DEFINITIONS[0], description="")]
    variante = module.Variante(
        nom="test", systeme="s", outils=definitions, executer=lambda n, e: "", modele="inconnu"
    )
    problemes = module.verifier_variante(variante)
    assert any("TARIFS" in p for p in problemes), (
        "Un modele absent de TARIFS rend le cout d'une requete incalculable."
    )
    assert any("description" in p for p in problemes), "Un outil sans description est aveugle."


# ---------------------------------------------------------------------------
# Exercice 4 : cout et journal
# ---------------------------------------------------------------------------


def test_cout_appel_compte_le_cache(module):
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
    assert module.cout_appel(MODELE_DEFAUT, usage) == pytest.approx(attendu), (
        "Le cout doit compter l'entree, la sortie, et le cache lu et ecrit avec leurs "
        "facteurs (doc42.config)."
    )


def test_cout_appel_tolere_les_champs_vides_et_refuse_l_inconnu(module):
    usage = Usage(cache_read_input_tokens=None, cache_creation_input_tokens=None)
    assert module.cout_appel(MODELE_DEFAUT, usage) > 0, (
        "Le SDK peut renvoyer None pour les champs de cache : comptez-les comme 0."
    )
    with pytest.raises(ValueError):
        module.cout_appel("modele-inconnu", Usage())


def test_journal_cout_par_requete(module, tmp_path):
    chemin = tmp_path / "journal.jsonl"
    journal = module.Journal(chemin)
    journal.enregistrer("r1", MODELE_DEFAUT, Usage())
    journal.enregistrer("r1", MODELE_DEFAUT, Usage())
    journal.enregistrer("r2", MODELE_DEFAUT, Usage())

    un_appel = module.cout_appel(MODELE_DEFAUT, Usage())
    assert journal.cout_requete("r1") == pytest.approx(2 * un_appel), (
        "Une requete utilisateur peut faire plusieurs appels : son cout est leur somme."
    )
    assert journal.cout_total() == pytest.approx(3 * un_appel)

    lignes = [json.loads(ligne) for ligne in chemin.read_text().splitlines()]
    assert len(lignes) == 3, "Une ligne JSON par appel dans le fichier de journal."
    for cle in ("requete", "modele", "entree", "sortie", "cout"):
        assert cle in lignes[0], f"Le journal doit contenir le champ {cle}."


# ---------------------------------------------------------------------------
# Exercice 5 : outils derriere leurs garde-fous
# ---------------------------------------------------------------------------


class _Bloc:
    type = "tool_use"

    def __init__(self, name, input, id="toolu_1"):
        self.name, self.input, self.id = name, input, id


def test_outil_irreversible_refuse_par_defaut(module):
    appels = []
    resultat = module.resultat_outil(
        _Bloc("creer_fiche", {"titre": "t", "contenu": "c"}), _variante(module, appels)
    )
    assert appels == [], (
        "creer_fiche a ete execute sans confirmation. Par defaut, une action irreversible "
        "est refusee."
    )
    assert resultat["tool_use_id"] == "toolu_1"
    assert "refus" in resultat["content"].lower(), (
        "Dites au modele que l'action a ete refusee, sinon il annoncera une fiche inexistante."
    )


def test_outil_irreversible_confirme(module):
    appels, vus = [], []

    def confirmer(nom, entree):
        vus.append(nom)
        return True

    resultat = module.resultat_outil(
        _Bloc("creer_fiche", {"titre": "t", "contenu": "c"}), _variante(module, appels), confirmer
    )
    assert vus == ["creer_fiche"] and len(appels) == 1
    assert not resultat.get("is_error")


def test_outil_en_lecture_sans_confirmation(module):
    def confirmer(nom, entree):
        raise AssertionError("Une recherche ne demande pas de confirmation.")

    resultat = module.resultat_outil(
        _Bloc("chercher_documents", {"requete": "alpha"}), _variante(module), confirmer
    )
    assert resultat["content"] == EXTRAIT_ALPHA


def test_outil_en_erreur_ou_inconnu(module):
    def casse(nom, entree):
        raise OSError("disque plein")

    variante = _variante(module)
    variante.executer = casse
    resultat = module.resultat_outil(_Bloc("chercher_documents", {"requete": "x"}), variante)
    assert resultat.get("is_error") is True and "disque plein" in resultat["content"], (
        "Une exception d'outil devient un tool_result is_error, pas un crash."
    )
    inconnu = module.resultat_outil(_Bloc("supprimer_tout", {}), variante)
    assert inconnu.get("is_error") is True


# ---------------------------------------------------------------------------
# Exercice 6 : repondre
# ---------------------------------------------------------------------------


def test_repondre_chemin_nominal(module, client, aplatir):
    client.programmer(
        outil("chercher_documents", {"requete": "echeances Alpha"}, id="toolu_a"),
        texte("Echeances : 15/01/2027, 15/04/2027, 15/07/2027 [contrat_alpha]"),
    )
    journal = module.Journal()
    variante = _variante(module)
    reponse = module.repondre(client, variante, "Echeances du contrat Alpha ?", journal=journal)

    assert not reponse.escalade, f"Reponse sourcee, pas d'escalade attendue ({reponse.raison})."
    assert reponse.sources == ["contrat_alpha"]
    assert reponse.tours == 2
    assert reponse.cout > 0
    assert reponse.cout == pytest.approx(journal.cout_requete(reponse.requete_id)), (
        "Le cout de la reponse doit etre celui du journal pour cette requete."
    )
    assert len(journal.entrees) == 2, "Chaque appel a l'API doit etre journalise."

    premier, second = client.appels
    assert premier["model"] == variante.modele and premier["system"] == variante.systeme
    assert premier["tools"] == variante.outils, "Les outils de la variante doivent etre envoyes."
    roles = [m["role"] for m in second["messages"]]
    assert roles == ["user", "assistant", "user"], f"Alternance cassee : {roles}"
    resultat = second["messages"][-1]["content"][0]
    assert resultat["type"] == "tool_result" and resultat["tool_use_id"] == "toolu_a"


def test_repondre_rejette_les_sources_inventees(module, client):
    client.programmer(
        outil("chercher_documents", {"requete": "alpha"}),
        texte("Voir [contrat_alpha] et [contrat_omega]."),
    )
    reponse = module.repondre(client, _variante(module), "Alpha ?")
    assert reponse.sources == ["contrat_alpha"], (
        "contrat_omega n'a ete renvoye par aucun outil : c'est une citation inventee."
    )


def test_repondre_sans_source_passe_la_main(module, client):
    client.programmer(texte("Je pense que c'est en mars."))
    reponse = module.repondre(client, _variante(module), "Quand ?")
    assert reponse.escalade is True and reponse.raison == "sans_source", (
        "Une reponse sans source verifiee n'est pas une reponse : c'est une escalade."
    )


def test_repondre_borne_la_question(module, client):
    bornes = module.Bornes(max_caracteres=50)
    reponse = module.repondre(client, _variante(module), "x" * 51, bornes=bornes)
    assert reponse.escalade and reponse.raison == "hors_bornes"
    assert client.appels == [], "Une question hors bornes est refusee AVANT de payer un appel."


def test_repondre_borne_les_tours(module, client):
    client.programmer(*[outil("chercher_documents", {"requete": "x"}) for _ in range(10)])
    reponse = module.repondre(client, _variante(module), "q", bornes=module.Bornes(max_tours=3))
    assert reponse.escalade and reponse.raison == "tours"
    assert len(client.appels) == 3, f"{len(client.appels)} appels pour une limite de 3 tours."


def test_repondre_borne_le_budget(module, client):
    cher = Usage(input_tokens=10_000_000)
    client.programmer(outil("chercher_documents", {"requete": "x"}, usage=cher), texte("fin"))
    reponse = module.repondre(client, _variante(module), "q")
    assert reponse.escalade and reponse.raison == "budget", (
        "Le budget est depasse apres le premier appel : on ne relance pas un tour."
    )
    assert len(client.appels) == 1


def test_repondre_erreur_api(module, client):
    client.programmer(_erreur(anthropic.BadRequestError))
    reponse = module.repondre(client, _variante(module), "q")
    assert reponse.escalade and reponse.raison == "erreur", (
        "Une erreur de l'API devient une escalade explicite, pas une trace a l'ecran."
    )


def test_repondre_confirmation_transmise(module, client, aplatir):
    appels = []
    client.programmer(
        outil("creer_fiche", {"titre": "Alpha", "contenu": "..."}), texte("Fiche refusee.")
    )
    module.repondre(client, _variante(module, appels), "Cree une fiche Alpha")
    assert appels == [], "Sans confirmer, creer_fiche ne doit pas s'executer."
    assert "refus" in aplatir(client.appels[-1]["messages"]).lower()


# ---------------------------------------------------------------------------
# Exercice 7 : evaluation
# ---------------------------------------------------------------------------


def test_evaluer_donne_un_chiffre(module):
    def repondre(question):
        if question == "q0":
            return module.Reponse(texte="Rien", escalade=True, raison="sans_source")
        if question == "q1":
            return module.Reponse(texte="Le 15/04/2027", sources=[], cout=0.01)
        if question == "q2":
            raise RuntimeError("boum")
        return module.Reponse(texte="Le 15/04/2027", sources=["contrat_alpha"], cout=0.01)

    rapport = module.evaluer(repondre, _cas(module))
    assert rapport.total == 10 and rapport.reussis == 7
    assert rapport.taux == pytest.approx(0.7)
    assert len(rapport.echecs) == 3, (
        "Trois echecs : une escalade, une source manquante, une exception. Une exception "
        "compte comme un echec, elle n'interrompt pas l'evaluation."
    )
    assert rapport.cout == pytest.approx(0.08)


def test_evaluer_mesure_l_escalade_et_ignore_les_accents(module):
    cas = _cas(module, 9) + [module.CasEval(question="hors corpus", escalade=True)]
    cas[0].attendus = ["Échéance"]

    def repondre(question):
        if question == "hors corpus":
            return module.Reponse(texte="Je ne sais pas.", escalade=True, raison="sans_source")
        return module.Reponse(texte="echeance 15/04/2027", sources=["contrat_alpha"])

    rapport = module.evaluer(repondre, cas)
    assert rapport.reussis == 10, (
        f"Echecs inattendus : {rapport.echecs}. Comparez des textes normalises, et comptez "
        "comme reussi un cas ou passer la main etait la bonne reponse."
    )


def test_evaluer_refuse_un_jeu_trop_petit(module):
    with pytest.raises(ValueError):
        module.evaluer(lambda q: module.Reponse(texte=""), _cas(module, 9))


def test_charger_cas(module, tmp_path):
    chemin = tmp_path / "cas.jsonl"
    chemin.write_text(
        '{"question": "Echeances Alpha ?", "attendus": ["15/04/2027"], '
        '"sources": ["contrat_alpha"]}\n\n'
        '{"question": "CA de Beta en 2025 ?", "escalade": true}\n',
        encoding="utf-8",
    )
    cas = module.charger_cas(chemin)
    assert len(cas) == 2, "Les lignes vides sont ignorees."
    assert cas[0].sources == ["contrat_alpha"] and cas[1].escalade is True

    chemin.write_text('{"question": "ok"}\n{"attendus": []}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="ligne 2"):
        module.charger_cas(chemin)


# ---------------------------------------------------------------------------
# Exercice 8 : le livrable
# ---------------------------------------------------------------------------


def _livrable(dossier: Path) -> Path:
    (dossier / "docs").mkdir()
    (dossier / "evals").mkdir()
    (dossier / "README.md").write_text(
        "uv sync\ncp .env.example .env  # ANTHROPIC_API_KEY\nuv run python -m doc42.variantes.x\n",
        encoding="utf-8",
    )
    (dossier / ".gitignore").write_text(".venv/\n.env\n", encoding="utf-8")
    (dossier / "docs" / "specification.md").write_text(SPEC_VALIDE, encoding="utf-8")
    lignes = [json.dumps({"question": f"q{i}"}) for i in range(10)]
    (dossier / "evals" / "cas.jsonl").write_text("\n".join(lignes), encoding="utf-8")
    return dossier


def test_livrable_complet(module, tmp_path):
    assert module.verifier_livrable(_livrable(tmp_path)) == []


def test_livrable_incomplet(module, tmp_path):
    dossier = _livrable(tmp_path)
    (dossier / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    (dossier / "README.md").write_text("Lancez le script.\n", encoding="utf-8")
    lignes = [json.dumps({"question": f"q{i}"}) for i in range(5)]
    (dossier / "evals" / "cas.jsonl").write_text("\n".join(lignes), encoding="utf-8")
    (dossier / "docs" / "specification.md").unlink()

    problemes = " | ".join(module.verifier_livrable(dossier))
    for attendu in (".env", "uv sync", "Specification", "5 cas"):
        assert attendu in problemes, f"Probleme non signale ({attendu}) : {problemes}"


def test_livrable_de_reference(module, tmp_path):
    """La variante de reference du checkpoint 11 respecte elle-meme le contrat."""
    etape = RACINE / ".etapes" / "11"
    if etape.exists():
        # Sur main : le livrable attend sous .etapes/11, on l'assemble a part.
        shutil.copy(RACINE / ".gitignore", tmp_path / ".gitignore")
        shutil.copytree(etape, tmp_path, dirs_exist_ok=True)
        dossier = tmp_path
    elif (RACINE / "docs" / "projet-final.md").exists():
        # Sur la branche etape/11-final : le livrable est a la racine.
        dossier = RACINE
    else:
        pytest.skip("Le livrable de reference n'existe qu'au checkpoint etape/11-final.")
    problemes = module.verifier_livrable(
        dossier,
        readme="docs/projet-final.md",
        spec="docs/specification-analyseur.md",
        cas="evals/analyseur_cas.jsonl",
    )
    assert problemes == [], f"Le livrable de reference ne respecte pas le contrat : {problemes}"


# ---------------------------------------------------------------------------
# Optionnel : contre la vraie API
# ---------------------------------------------------------------------------


@pytest.mark.reel
def test_repondre_reel(module, pytestconfig):
    if not pytestconfig.getoption("--reel"):
        pytest.skip("Ajoutez --reel pour appeler la vraie API.")
    variante = module.Variante(
        nom="reel",
        systeme=(
            "Tu es Doc42. Reponds uniquement a partir des documents renvoyes par tes outils "
            "et cite chaque document utilise par son identifiant entre crochets, "
            "par exemple [contrat_alpha]."
        ),
        outils=outils_doc42.DEFINITIONS,
        executer=outils_doc42.executer,
        irreversibles=frozenset({"creer_fiche"}),
    )
    reponse = module.repondre(
        anthropic.Anthropic(), variante, "Quelles sont les echeances de paiement du contrat Alpha ?"
    )
    assert "15/04/2027" in reponse.texte
    assert "contrat_alpha" in reponse.sources
    assert reponse.cout > 0
