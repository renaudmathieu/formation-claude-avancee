"""Section 5, le contrat.

Dans cette section, c'est Claude Code qui ecrit le code : ces tests sont ce
que vous lui donnez a satisfaire, et ce qui vous dit, sans lui faire
confiance, que le travail est fait. Si tout passe, la commande `resume`
existe, le CLAUDE.md du checkpoint est court et verifiable, et vous pouvez
commiter etape/05-claude-code.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import anthropic
import pytest
from fakes import erreur_sdk, texte

from doc42.config import MODELE_DEFAUT, SYSTEME_DOC42

RACINE = Path(__file__).parent.parent
CORPUS = RACINE / "corpus"
PIEGE = RACINE / "corpus_pieges" / "note_fournisseur_piegee.md"

CINQ_POINTS = (
    "- Contrat entre Hexalis et Alpha Logistique.\n"
    "- Duree de douze mois a partir du 1er janvier 2027.\n"
    "- Prix annuel de 48 000 euros HT.\n"
    "- Trois echeances : 15/01/2027, 15/04/2027, 15/07/2027.\n"
    "- Disponibilite garantie de 99,5 %."
)

BROUILLON_INIT = "\n".join(
    [
        "# CLAUDE.md",
        "",
        "This file provides guidance to Claude Code when working with this repository.",
        "",
        "## Structure",
        "doc42/",
        "\u251c\u2500\u2500 config.py",
        "\u251c\u2500\u2500 client.py",
        "\u2514\u2500\u2500 outils.py",
        "",
        "## Conventions",
        "- Ecris du code propre et respecte les bonnes pratiques.",
    ]
    + [f"- La fonction numero {i} fait quelque chose d'utile." for i in range(60)]
)

BON_CLAUDE_MD = """# Doc42

## Commandes
- Tests : `uv run pytest -q`

## R\u00e8gles m\u00e9tier
- Toute reponse cite le document source.
"""


def _du_checkpoint(relatif: str) -> Path:
    """Le fichier tel qu'il est au checkpoint : sous .etapes/05/ sur main, a la racine apres."""
    for candidat in (RACINE / ".etapes" / "05" / relatif, RACINE / relatif):
        if candidat.exists():
            return candidat
    pytest.skip(f"{relatif} n'existe qu'a partir du checkpoint etape/05-claude-code.")


def _existe_au_checkpoint(relatif: str) -> bool:
    return (RACINE / ".etapes" / "05" / relatif).exists() or (RACINE / relatif).exists()


# Exercice 1 : verifier_claude_md


def test_claude_md_le_brouillon_de_init_ne_passe_pas(module):
    problemes = module.verifier_claude_md(BROUILLON_INIT)
    tout = "\n".join(problemes)

    assert isinstance(problemes, list), "verifier_claude_md doit retourner une liste de chaines."
    assert "long" in tout, "Plus de 60 lignes : le brouillon de /init doit etre coupe de moitie."
    assert "Commandes" in tout, (
        "Il manque la section Commandes : c'est elle qui rend Claude autonome."
    )
    assert "Regles metier" in tout, (
        "Il manque la section Regles metier : la seule que Claude ne peut pas deviner du code."
    )
    assert "code propre" in tout and "bonnes pratiques" in tout, (
        "Les consignes vagues doivent etre signalees : 'code propre' ne se constate dans aucun diff."
    )
    assert "arborescence" in tout, (
        "L'arborescence recopiee doit etre signalee : Claude la lit deja."
    )


def test_claude_md_court_et_verifiable_passe(module):
    assert module.verifier_claude_md(BON_CLAUDE_MD) == [], (
        "Un CLAUDE.md court, avec ses commandes et ses regles metier, ne doit avoir aucun "
        "probleme. Comparez les titres sans accents ni majuscules (doc42.outils.normaliser)."
    )


def test_claude_md_commandes_sans_tests(module):
    sans_tests = BON_CLAUDE_MD.replace("Tests : `uv run pytest -q`", "Installer : `uv sync`")
    problemes = module.verifier_claude_md(sans_tests)
    assert any("pytest" in p for p in problemes), (
        "Une section Commandes qui ne dit pas comment lancer les tests ne permet pas a Claude "
        "de verifier son propre travail."
    )


def test_claude_md_du_checkpoint_dit_vrai(module):
    chemin = _du_checkpoint("CLAUDE.md")
    contenu = chemin.read_text(encoding="utf-8")

    assert module.verifier_claude_md(contenu) == [], f"{chemin} ne passe pas le verificateur."

    for fichier in sorted(set(re.findall(r"[\w/]+\.py\b", contenu))):
        if "/" in fichier:
            assert _existe_au_checkpoint(fichier), (
                f"CLAUDE.md cite {fichier}, qui n'existe pas. Un CLAUDE.md qui ment coute "
                "plus cher qu'un CLAUDE.md absent."
            )
    if "python -m doc42" in contenu:
        assert _existe_au_checkpoint("doc42/__main__.py"), (
            "CLAUDE.md cite `python -m doc42`, mais doc42/__main__.py n'existe pas."
        )


# Exercice 2 : resoudre_document


def test_resoudre_accepte_les_trois_formes(module):
    for forme in ("contrat_alpha", "contrat_alpha.md", str(CORPUS / "contrat_alpha.md")):
        document = module.resoudre_document(forme, CORPUS)
        assert document.id == "contrat_alpha", f"'{forme}' doit designer contrat_alpha."
        assert "48 000 euros" in document.texte


def test_resoudre_refuse_ce_qui_sort_du_corpus(module, tmp_path):
    copie = tmp_path / "contrat_alpha.md"
    shutil.copy(CORPUS / "contrat_alpha.md", copie)

    for forme in ("../.env", str(PIEGE), str(copie), "contrat_exemple.pdf", "contrat_alfa"):
        with pytest.raises(module.DocumentInconnu):
            module.resoudre_document(forme, CORPUS)
            pytest.fail(
                f"'{forme}' a ete accepte. Le corpus est le perimetre : un chemin vers un "
                "autre dossier, un PDF ou une faute de frappe doivent lever DocumentInconnu."
            )


def test_resoudre_liste_les_documents_disponibles(module):
    with pytest.raises(module.DocumentInconnu) as erreur:
        module.resoudre_document("contrat_alfa", CORPUS)
    assert "contrat_alpha" in str(erreur.value), (
        "Le message doit lister les identifiants disponibles : c'est ce qui permet de "
        "corriger la faute de frappe sans ouvrir le dossier."
    )


# Exercice 3 : en_puces


def test_en_puces_normalise_la_reponse(module):
    reponse = (
        "Voici le resume demande :\n\n"
        "1. Premier point\n"
        "2) Deuxieme point\n"
        "* Troisieme point\n"
        "\u2022 Quatrieme point  \n"
        "  - Cinquieme point\n"
        "- Sixieme point\n\n"
        "N'hesitez pas si vous avez des questions."
    )
    points = module.en_puces(reponse)
    assert points == [
        "Premier point",
        "Deuxieme point",
        "Troisieme point",
        "Quatrieme point",
        "Cinquieme point",
    ], (
        f"Obtenu : {points}. Seules les lignes a puce comptent (preambule et conclusion "
        "ignores), sans leur marque, et au plus cinq."
    )


def test_en_puces_n_invente_rien(module):
    assert module.en_puces("- Un\n- Deux\n- Trois") == ["Un", "Deux", "Trois"], (
        "Trois points restent trois points : on ne complete jamais pour faire le compte."
    )
    assert module.en_puces("Un paragraphe sans aucune puce.") == [], (
        "Un texte sans puce ne donne aucun point."
    )


# Exercice 4 : consigne_resume et resumer


def test_consigne_resume(module):
    document = module.resoudre_document("contrat_alpha", CORPUS)
    consigne = module.consigne_resume(document)

    assert document.texte in consigne, "Le texte complet du document doit etre envoye."
    apres = consigne[consigne.index(document.texte) + len(document.texte) :]
    assert "resume" in apres.lower(), (
        "Le document passe AVANT la consigne, comme le fichier avant la question en section 2."
    )
    assert "contrat_alpha" in consigne, "Le document doit etre delimite et identifie."
    assert "5" in consigne or "cinq" in consigne.lower(), "La consigne doit dire combien de points."
    assert "invent" in consigne.lower(), "La consigne doit interdire d'inventer."


def test_resumer_un_seul_appel_par_dessus_le_client(module, client, aplatir):
    document = module.resoudre_document("contrat_alpha", CORPUS)
    client.programmer(texte("Voici :\n" + CINQ_POINTS + "\n- Un sixieme point en trop."))

    points = module.resumer(client, document)

    assert len(points) == 5, f"Il faut cinq points, pas {len(points)}."
    assert points[0] == "Contrat entre Hexalis et Alpha Logistique."
    assert len(client.appels) == 1, "Un resume, c'est un seul appel."
    envoye = client.appels[0]
    assert envoye["model"] == MODELE_DEFAUT, "Le modele vient de doc42.config, via appel_simple."
    assert envoye["system"] == SYSTEME_DOC42, "Le prompt systeme de Doc42 doit etre transmis."
    assert document.texte in aplatir(envoye["messages"]), "Le document n'a pas ete envoye."


# Exercice 5 : la commande


def test_main_affiche_le_resume_et_la_source(module, client, capsys):
    client.programmer(texte(CINQ_POINTS))

    code = module.main(["resume", "contrat_alpha"], fabrique=lambda: client, dossier=CORPUS)

    sortie = capsys.readouterr().out.splitlines()
    assert code == 0, f"Code de sortie {code}, attendu 0."
    assert len(sortie) == 6, f"Attendu cinq puces et la ligne Source, obtenu : {sortie}"
    assert all(ligne.startswith("- ") for ligne in sortie[:5]), "Une puce '- ' par ligne."
    assert sortie[-1] == "Source : contrat_alpha", (
        "Regle metier du CLAUDE.md : toute reponse cite son document source."
    )


def test_main_document_inconnu_sans_appel(module, capsys):
    fabriques: list[int] = []

    def fabrique():
        fabriques.append(1)
        raise AssertionError("le client ne devait pas etre cree")

    code = module.main(["resume", "contrat_alfa"], fabrique=fabrique, dossier=CORPUS)

    sorties = capsys.readouterr()
    assert code == 2, f"Document inconnu : code 2 attendu, obtenu {code}."
    assert not fabriques, (
        "Le client a ete cree pour un document inconnu. Resolvez le document AVANT : "
        "une faute de frappe ne doit ni couter un appel ni exiger une cle."
    )
    assert sorties.out == "", "Rien sur stdout en cas d'erreur."
    assert "contrat_alpha" in sorties.err, "Le message d'erreur va sur stderr."


def test_main_reponse_sans_puce(module, client, capsys):
    client.programmer(texte("Je ne peux pas resumer ce document."))

    code = module.main(["resume", "contrat_alpha"], fabrique=lambda: client, dossier=CORPUS)

    sorties = capsys.readouterr()
    assert code == 1, f"Aucun point exploitable : code 1 attendu, obtenu {code}."
    assert sorties.out == "", (
        "Rien sur stdout : un script qui lit cette sortie ne doit pas prendre un echec "
        "pour un resume. Ni puce inventee, ni ligne Source seule."
    )
    assert sorties.err, "Expliquez l'echec sur stderr."


def test_main_erreur_api_sans_trace(module, client, capsys):
    client.programmer(erreur_sdk(anthropic.AuthenticationError))

    code = module.main(["resume", "contrat_alpha"], fabrique=lambda: client, dossier=CORPUS)

    sorties = capsys.readouterr()
    assert code == 1, (
        "Une anthropic.AnthropicError (cle absente, 401, reseau) doit etre rattrapee : "
        "un message sur stderr et le code 1, pas une trace Python."
    )
    assert sorties.out == ""
    assert sorties.err


def test_client_reel_verifie_la_cle(module, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(anthropic.AnthropicError) as erreur:
        module.client_reel()
    assert "ANTHROPIC_API_KEY" in str(erreur.value), (
        "Sans cle, levez une anthropic.AnthropicError qui nomme ANTHROPIC_API_KEY : le SDK, "
        "lui, leverait un TypeError illisible au premier appel."
    )

    # Une cle factice suffit a construire le client : aucun appel reseau ici.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-factice-pour-le-test")
    assert isinstance(module.client_reel(), anthropic.Anthropic)


def test_main_sans_cle_message_lisible(module, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    code = module.main(["resume", "contrat_alpha"], dossier=CORPUS)

    sorties = capsys.readouterr()
    assert code == 1, "Sans cle et sans fabrique, main doit passer par client_reel et rendre 1."
    assert "ANTHROPIC_API_KEY" in sorties.err and sorties.out == ""


def test_main_aide_et_sous_commande_obligatoire(module, capsys):
    with pytest.raises(SystemExit) as fin:
        module.main(["--help"])
    assert fin.value.code == 0
    assert "resume" in capsys.readouterr().out, "--help doit presenter la commande resume."

    with pytest.raises(SystemExit) as fin:
        module.main([])
    assert fin.value.code == 2, "Sans sous-commande, argparse doit refuser (code 2)."


# Exercice 6 (bonus) : les permissions de l'equipe


def _regles(settings: dict, genre: str) -> list[str]:
    return list(settings.get("permissions", {}).get(genre, []))


def test_settings_equipe(module):
    settings = module.settings_equipe()
    json.dumps(settings)  # settings.json est du JSON strict

    refus = _regles(settings, "deny")
    assert "Read(./.env)" in refus, (
        "Il faut un deny Read(./.env) : CLAUDE.md oriente, settings.json empeche."
    )
    assert any(r.startswith("Edit(") and "corpus/" in r for r in refus), (
        "Interdisez la modification du corpus par une regle Edit sur corpus/."
    )
    assert "Bash(git push *)" in refus, "La regle Git 'jamais de push' doit etre imposee."
    assert "Bash(uv run pytest *)" in _regles(settings, "allow"), (
        "Laissez Claude lancer les tests sans demander : c'est ainsi qu'il verifie son travail."
    )
    toutes = [r for genre in ("allow", "ask", "deny") for r in _regles(settings, genre)]
    assert not [r for r in toutes if r.startswith("Write(")], (
        "Une regle de chemin pour Write est acceptee mais jamais consultee par Claude Code. "
        "Utilisez Edit, qui couvre toutes les ecritures."
    )


def test_settings_du_checkpoint(module):
    chemin = _du_checkpoint(".claude/settings.json")
    fichier = json.loads(chemin.read_text(encoding="utf-8"))
    manquantes = set(_regles(module.settings_equipe(), "deny")) - set(_regles(fichier, "deny"))
    assert not manquantes, f"{chemin} n'impose pas ces regles deny : {sorted(manquantes)}"


@pytest.mark.reel
def test_resume_reel(module, pytestconfig):
    if not pytestconfig.getoption("--reel"):
        pytest.skip("Ajoutez --reel pour appeler la vraie API.")
    document = module.resoudre_document("contrat_alpha", CORPUS)
    points = module.resumer(anthropic.Anthropic(), document)
    assert 1 <= len(points) <= 5, f"Resume reel inattendu : {points}"
