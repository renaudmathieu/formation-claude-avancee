"""Section 9, atelier. Une chaine RAG mesuree, une heure trente.

Completez les fonctions marquees TODO, puis lancez :

    uv run pytest tests/test_section09.py -v

L'ordre des exercices est celui de l'atelier, et il n'est pas arbitraire :
on ecrit le jeu de questions et la mesure AVANT de construire la recherche.
Si le bon document ne remonte pas, aucun prompt ne rattrapera l'affaire.

Tout tourne hors ligne : l'embedder par defaut est un sac de mots hache,
deterministe. Un vrai modele d'embeddings (EmbedderVoyage, fourni) reste une
option, jamais appelee par les tests.

Les enonces sont dans les docstrings. Vous n'avez pas besoin de revenir
sur Notion pendant l'atelier.
"""

from __future__ import annotations

import dataclasses  # noqa: F401  (utile pour verifier_citations)
import html
import json  # noqa: F401  (utile pour charger_jeu)
import math
import re
import zlib  # noqa: F401  (utile pour EmbedderHache)
from collections import Counter  # noqa: F401  (utile pour IndexBM25)
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from doc42.config import (  # noqa: F401  (vous en aurez besoin)
    DOSSIER_CORPUS,
    MAX_TOKENS_DEFAUT,
    MODELE_DEFAUT,
    MODELE_RAPIDE,
    RACINE,
    SYSTEME_DOC42,
)
from doc42.corpus import Document, charger_corpus
from doc42.outils import chercher_documents, mots, normaliser  # noqa: F401

FICHIER_QUESTIONS = RACINE / "evals" / "section09_questions.json"

# Une recherche, pour l'evaluation : (question, k) -> identifiants de documents classes.
Recherche = Callable[[str, int], list[str]]
# Un embedder : une liste de textes -> une liste de vecteurs, dans le meme ordre.
Embedder = Callable[[list[str]], list[list[float]]]


# ---------------------------------------------------------------------------
# Exercice 1 : le jeu d'evaluation, avant toute ligne de code
# ---------------------------------------------------------------------------


def charger_jeu(
    chemin: str | Path = FICHIER_QUESTIONS, dossier: str | Path = DOSSIER_CORPUS
) -> list[dict[str, Any]]:
    """Charge le jeu de questions et le valide contre le corpus.

    Le fichier evals/section09_questions.json a la forme :
        {"questions": [{"id": "q01", "question": "...", "attendus": ["contrat_alpha"]}, ...]}
    "attendus" liste les documents qui contiennent VRAIMENT la reponse. Une
    liste vide signifie : la reponse n'est pas dans le corpus.

    Relisez ce fichier avant de coder, et ajoutez-y vos propres questions :
    c'est lui qui decidera de tout le reste.

    Attendu :
      - la fonction renvoie la liste des questions
      - chaque question a les champs "id", "question" et "attendus" (une liste),
        sinon ValueError (TypeError si "attendus" n'est pas une liste)
      - deux questions avec le meme "id" : ValueError
      - un document attendu qui n'existe pas dans `dossier` : ValueError dont le
        message cite l'identifiant fautif. Une faute de frappe ici fausserait
        la mesure en silence.
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 2 : mesurer avant de construire
# ---------------------------------------------------------------------------


def rappel_a_k(classement: Sequence[str], attendus: Sequence[str], k: int) -> float:
    """Part des documents attendus presents dans les k premiers du classement.

    Attendu :
      - les doublons du classement sont retires AVANT de couper a k (deux
        passages du meme document ne comptent qu'une fois)
      - rappel_a_k(["a", "a", "b", "c"], ["b", "c"], 2) == 0.5
      - ValueError si `attendus` est vide : le rappel n'a pas de sens
    """
    # TODO
    raise NotImplementedError


def rang_reciproque(
    classement: Sequence[str], attendus: Sequence[str], k: int | None = None
) -> float:
    """1 / rang du premier document attendu dans le classement (sans doublons), 0 sinon.

    Attendu :
      - rang_reciproque(["a", "a", "b"], ["b"]) == 0.5
      - avec k, on ne regarde que les k premiers
    """
    # TODO
    raise NotImplementedError


def evaluer(recherche: Recherche, jeu: Sequence[dict[str, Any]], k: int = 5) -> dict[str, Any]:
    """Mesure une recherche sur le jeu.

    Attendu :
      - renvoie {"n": ..., "rappel": ..., "mrr": ..., "echecs": [...]}
      - les questions hors corpus (attendus vide) sont ECARTEES : elles testent
        la generation (le refus), pas la recuperation
      - "rappel" et "mrr" sont les moyennes sur les questions retenues, avec
        recherche(question, k) comme classement
      - "echecs" liste les id des questions dont le rappel a k est inferieur a 1
    """
    # TODO
    raise NotImplementedError


def recherche_mots_cles(question: str, k: int = 5) -> list[str]:
    """Le point de comparaison : la recherche par mots-cles de doc42.outils (fournie)."""
    return [r["id"] for r in chercher_documents(question, limite=min(k, 10))]


# ---------------------------------------------------------------------------
# Exercice 3 : le decoupage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Passage:
    """Un fragment de document, avec les metadonnees qui permettent de le citer (fourni)."""

    id: str
    document_id: str
    titre: str
    section: str
    texte: str
    date: str = ""
    type: str = ""
    page: int | None = None


def _metadonnee(texte: str, motif: str) -> str:
    """La valeur d'une ligne "Motif... : valeur" (fourni). Ex : _metadonnee(t, "Date")."""
    trouve = re.search(rf"^{motif}[^:\n]*:\s*(.+)$", texte, flags=re.MULTILINE)
    return trouve.group(1).strip() if trouve else ""


def decouper(document: Document, taille_max: int = 200, chevauchement: int = 40) -> list[Passage]:
    """Decoupe un document en passages : d'abord aux sections, puis en fenetres glissantes.

    Attendu :
      - une section commence a chaque ligne "## Titre" (la ligne de titre fait
        partie du texte du passage, et `section` vaut "Titre") ; ce qui precede
        le premier "## " forme la section "Preambule"
      - les sections vides sont ignorees
      - une section de plus de `taille_max` mots (texte.split()) est coupee en
        fenetres de `taille_max` mots qui se chevauchent de `chevauchement`
        mots ; la derniere fenetre s'arrete a la fin de la section
      - ValueError sauf si 0 <= chevauchement < taille_max (sinon la fenetre
        n'avance pas)
      - id = "<document.id>#<numero>", numerote a partir de 1 dans le document
      - metadonnees conservees : document_id, titre, section, date (ligne
        "Date ... : ..."), type (ligne "Type : ...") ; utilisez _metadonnee
    """
    # TODO
    raise NotImplementedError


def decouper_corpus(documents: Sequence[Document], **reglages: int) -> list[Passage]:
    """Tous les passages d'un corpus (fourni)."""
    return [passage for document in documents for passage in decouper(document, **reglages)]


# ---------------------------------------------------------------------------
# Exercice 4 : BM25, ecrit a la main
# ---------------------------------------------------------------------------


class IndexBM25:
    """Index lexical BM25 (Okapi), sans dependance.

    Pour un terme t de la requete et un texte d :
        idf(t)   = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
        score   += idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |d| / longueur_moyenne))
    N : nombre de textes ; df(t) : nombre de textes qui contiennent t ;
    tf : occurrences de t dans d ; |d| : nombre de termes de d.

    Attendu :
      - les termes viennent de doc42.outils.mots (minuscules, sans accents,
        au moins trois caracteres), pour les textes comme pour la requete
      - un terme repete dans la requete ne compte qu'une fois
      - scores(requete) renvoie un score par texte, dans l'ordre des textes
      - classer(requete, k) renvoie [(indice, score), ...] tries par score
        decroissant (a egalite, par indice), SANS les scores nuls, coupe a k
        (k=None : tout)
    """

    def __init__(self, textes: Sequence[str], k1: float = 1.5, b: float = 0.75) -> None:
        # TODO : precalculez ici tout ce qui ne depend pas de la requete
        raise NotImplementedError

    def scores(self, requete: str) -> list[float]:
        # TODO
        raise NotImplementedError

    def classer(self, requete: str, k: int | None = None) -> list[tuple[int, float]]:
        # TODO
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 5 : la composante vectorielle
# ---------------------------------------------------------------------------

# Sans IDF, les mots outils domineraient un sac de mots : on les retire.
MOTS_VIDES = frozenset(
    {
        "les", "des", "une", "est", "que", "qui", "pour", "dans", "par", "sur", "avec",
        "aux", "pas", "son", "ses", "sont", "elle", "ils", "cette", "ces", "leur", "peut",
        "quel", "quelle", "quels", "quelles", "comment", "combien", "quand", "doit",
        "tout", "tous", "plus", "entre", "apres", "avant",
    }
)  # fmt: skip


class EmbedderHache:
    """Embedder deterministe hors ligne : un sac de mots et de trigrammes, hache.

    Attendu :
      - __call__(textes) renvoie un vecteur de `dimension` flottants par texte
      - les caracteristiques d'un texte : chaque mot de mots(texte) hors
        MOTS_VIDES (poids 1), plus ses trigrammes de caracteres avec bords,
        "<mot>" (poids 0.5) : ils rapprochent "teletravail" et "teletravailler"
      - chaque caracteristique tombe dans une case choisie par une empreinte
        STABLE (zlib.crc32), jamais hash() : hash() change a chaque processus
        (PYTHONHASHSEED) et l'index d'hier ne correspondrait plus aux requetes
        d'aujourd'hui. Le test lance deux processus pour le verifier.
      - le vecteur est normalise (norme 1), sauf s'il est nul
    """

    def __init__(self, dimension: int = 512) -> None:
        self.dimension = dimension

    def vecteur(self, texte: str) -> list[float]:
        # TODO
        raise NotImplementedError

    def __call__(self, textes: list[str]) -> list[list[float]]:
        # TODO
        raise NotImplementedError


class EmbedderVoyage:
    """Option documentee (fournie) : un vrai modele d'embeddings, Voyage AI.

    Jamais appele par les tests. Necessite le paquet `voyageai` (hors des
    dependances du projet) et la variable VOYAGE_API_KEY. Le nom du modele est
    un parametre : son identifiant a sa place dans doc42/config.py (voir 9.3).
    Changer de modele oblige a reindexer tout le corpus.
    """

    def __init__(self, modele: str, type_entree: str | None = None, lot: int = 64) -> None:
        import voyageai  # import tardif : dependance optionnelle

        self.client = voyageai.Client()
        self.modele = modele
        self.type_entree = type_entree
        self.lot = lot

    def __call__(self, textes: list[str]) -> list[list[float]]:
        vecteurs: list[list[float]] = []
        for debut in range(0, len(textes), self.lot):
            reponse = self.client.embed(
                textes[debut : debut + self.lot], model=self.modele, input_type=self.type_entree
            )
            vecteurs.extend(reponse.embeddings)
        return vecteurs


def cosinus(a: Sequence[float], b: Sequence[float]) -> float:
    """Similarite cosinus (fournie)."""
    produit = sum(x * y for x, y in zip(a, b, strict=True))
    normes = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return produit / normes if normes else 0.0


class IndexVectoriel:
    """Index vectoriel en memoire, embedder injectable.

    Attendu :
      - le constructeur appelle l'embedder UNE seule fois, avec tous les textes
        (avec un vrai fournisseur, chaque appel est un aller-retour facture)
      - ValueError si l'embedder ne rend pas un vecteur par texte
      - classer(requete, k) appelle l'embedder une fois avec [requete] et
        renvoie [(indice, similarite cosinus), ...] tries par similarite
        decroissante (a egalite, par indice), coupe a k (k=None : tout)
    """

    def __init__(self, textes: Sequence[str], embedder: Embedder) -> None:
        # TODO
        raise NotImplementedError

    def classer(self, requete: str, k: int | None = None) -> list[tuple[int, float]]:
        # TODO
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 6 : la recherche hybride
# ---------------------------------------------------------------------------


def fusion_rrf(classements: Sequence[Sequence[Any]], k_rrf: int = 60) -> list[tuple[Any, float]]:
    """Reciprocal Rank Fusion de plusieurs classements.

    Chaque element recoit la somme, sur les classements ou il apparait, de
    1 / (k_rrf + rang), le rang commencant a 1.

    Attendu :
      - renvoie [(element, score), ...] par score decroissant ; a egalite,
        l'ordre de premiere apparition
      - un element present dans un seul classement est garde
      - on fusionne des RANGS, jamais les scores bruts : un score BM25 et un
        cosinus ne sont pas sur la meme echelle
    """
    # TODO
    raise NotImplementedError


MODES = ("lexical", "vectoriel", "hybride")


class IndexHybride:
    """Les passages du corpus, indexes deux fois : BM25 et vecteurs.

    Le constructeur est fourni. Le contextualiser (exercice 7) prefixe le texte
    INDEXE, jamais passage.texte : les citations se verifient contre le texte
    d'origine.
    """

    def __init__(
        self,
        passages: Sequence[Passage],
        embedder: Embedder | None = None,
        contextualiser: Callable[[Passage], str] | None = None,
        profondeur: int = 20,
    ) -> None:
        self.passages = list(passages)
        self.embedder = embedder or EmbedderHache()
        self.contextualiser = contextualiser
        self.profondeur = profondeur
        textes = [self.texte_indexe(p) for p in self.passages]
        self.bm25 = IndexBM25(textes)
        self.vectoriel = IndexVectoriel(textes, self.embedder)

    def texte_indexe(self, passage: Passage) -> str:
        if self.contextualiser is None:
            return passage.texte
        return f"{self.contextualiser(passage)}\n{passage.texte}"

    def chercher(self, requete: str, k: int = 5, mode: str = "hybride") -> list[Passage]:
        """Les k meilleurs passages.

        Attendu :
          - mode "lexical" : l'ordre de self.bm25.classer(requete, self.profondeur)
          - mode "vectoriel" : l'ordre de self.vectoriel.classer(requete, self.profondeur)
          - mode "hybride" : fusion_rrf des deux classements (lexical d'abord)
          - ValueError pour un mode inconnu
        """
        # TODO
        raise NotImplementedError

    def documents(self, requete: str, k: int = 5, mode: str = "hybride") -> list[str]:
        """Les k meilleurs DOCUMENTS (identifiants, sans doublons).

        Piege : k passages ne font pas k documents. Classez tous les passages,
        dedupliquez les document_id dans l'ordre, puis coupez a k.
        """
        # TODO
        raise NotImplementedError


def construire_index(
    dossier: str | Path = DOSSIER_CORPUS,
    embedder: Embedder | None = None,
    contextualiser: Callable[[Passage], str] | None = None,
    taille_max: int = 200,
    chevauchement: int = 40,
) -> IndexHybride:
    """L'index du corpus (fourni)."""
    passages = decouper_corpus(
        charger_corpus(dossier), taille_max=taille_max, chevauchement=chevauchement
    )
    return IndexHybride(passages, embedder=embedder, contextualiser=contextualiser)


# ---------------------------------------------------------------------------
# Exercice 7 : enrichir chaque passage de son contexte
# ---------------------------------------------------------------------------


def contexte_metadonnees(passage: Passage) -> str:
    """Le contexte d'un passage, tire de ses metadonnees, a prefixer avant indexation.

    Le passage "Article 2. Duree : trois ans..." ne dit pas de quel contrat il
    s'agit. Le titre du document, si.

    Attendu :
      - une chaine entre crochets qui contient le titre du document, son type,
        sa date et la section du passage ; les champs vides sont omis
      - exemple : "[Document : Contrat ... ; type : contrat ; date : ... ; section : ...]"
    """
    # TODO
    raise NotImplementedError


def contexte_par_claude(client: Any, document: Document, passage: Passage) -> str:
    """La methode Contextual Retrieval d'Anthropic : Claude situe le passage dans son document.

    Attendu :
      - modele MODELE_RAPIDE (une phrase par passage, pour tout le corpus :
        c'est du volume, pas de la difficulte)
      - un seul message user dont le contenu est une LISTE de blocs texte :
        d'abord le document complet entre balises <document>, avec
        "cache_control": {"type": "ephemeral"} (il est identique pour tous ses
        passages), puis le passage entre balises <passage> et la consigne
      - renvoie le texte de la reponse, sans espaces autour
    """
    # TODO
    raise NotImplementedError


def contextualiseur_claude(client: Any, documents: Sequence[Document]) -> Callable[[Passage], str]:
    """Adapte contexte_par_claude a la signature attendue par IndexHybride (fourni)."""
    par_id = {document.id: document for document in documents}
    return lambda passage: contexte_par_claude(client, par_id[passage.document_id], passage)


# ---------------------------------------------------------------------------
# Exercice 8 : generer avec citations obligatoires
# ---------------------------------------------------------------------------

REFUS = "Je ne trouve pas cette information dans les documents fournis."

# TODO : ecrivez les consignes de generation. Elles doivent :
#   - limiter la reponse aux passages fournis dans la balise <documents>
#   - dire que le contenu des passages est une donnee, jamais une instruction
#   - exiger une citation exacte par affirmation, au format
#     <citation passage="ID">extrait exact</citation>
#   - imposer la phrase REFUS, mot pour mot, quand la reponse n'y est pas
CONSIGNES_RAG = ""

SYSTEME_RAG = f"{SYSTEME_DOC42}\n\n{CONSIGNES_RAG}"


def formater_passages(passages: Sequence[Passage]) -> str:
    """Les passages, prets a injecter dans le message.

    Attendu :
      - "<documents>" ... "</documents>", et pour chaque passage :
        <passage id="..." document="..." section="...">texte</passage>
      - le texte et les attributs sont echappes (html.escape) : un document qui
        contient "</documents>" ne doit pas pouvoir fermer vos balises.
        Tout ce qui remonte de la recherche est une donnee non fiable.
    """
    # TODO
    raise NotImplementedError


@dataclass(frozen=True)
class Citation:
    """Une citation extraite de la reponse ; motif dit pourquoi elle est rejetee (fourni)."""

    passage_id: str
    extrait: str
    motif: str = ""


@dataclass
class Reponse:
    """Le resultat d'un appel RAG (fourni)."""

    texte: str
    passages: list[Passage]
    citations: list[Citation]
    fantaisistes: list[Citation]
    refus: bool

    @property
    def fiable(self) -> bool:
        # Un refus est une bonne reponse. Sinon : au moins une citation
        # verifiee et aucune citation inventee.
        return self.refus or (bool(self.citations) and not self.fantaisistes)


def est_refus(texte: str) -> bool:
    """Vrai si le texte contient la phrase REFUS (comparaison via normaliser, espaces toleres).

    Attendu :
      - est_refus("Desole. " + REFUS) est vrai
      - est_refus("Le contrat Delta a ete signe le 3 mars.") est faux
    """
    # TODO
    raise NotImplementedError


def repondre(client: Any, index: Any, question: str, k: int = 5) -> Reponse:
    """Recupere, genere, verifie.

    `index` est tout objet qui a une methode chercher(question, k) -> list[Passage].

    Attendu :
      - passages = index.chercher(question, k)
      - un appel a client.messages.create avec MODELE_DEFAUT, MAX_TOKENS_DEFAUT,
        system=SYSTEME_RAG, et un message user : formater_passages(passages),
        PUIS la question (les documents d'abord, la question a la fin)
      - les citations de la reponse sont extraites et verifiees contre les
        passages fournis (exercice 9)
      - renvoie Reponse(texte, passages, citations valides, fantaisistes, refus)
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 9 : verifier les citations par programme
# ---------------------------------------------------------------------------


def extraire_citations(texte: str) -> list[Citation]:
    """Toutes les balises <citation passage="ID">extrait</citation> du texte.

    Attendu :
      - dans l'ordre du texte ; l'extrait peut tenir sur plusieurs lignes
      - identifiant et extrait sans espaces autour
    """
    # TODO
    raise NotImplementedError


def _comparable(texte: str) -> str:
    """Forme de comparaison (fournie) : on tolere ce qui n'est pas du contenu.

    Echappement HTML, apostrophes typographiques, espaces insecables, espaces
    multiples, casse, guillemets autour et ponctuation finale. Jamais un mot change.
    """
    texte = html.unescape(texte)
    for avant, apres in (("\u2019", "'"), ("\u00a0", " "), ("\u202f", " ")):
        texte = texte.replace(avant, apres)
    texte = " ".join(texte.split()).casefold()
    return texte.strip(" \"'\u00ab\u00bb").rstrip(".;:,").strip()


def verifier_citations(
    citations: Sequence[Citation], passages: Sequence[Passage]
) -> tuple[list[Citation], list[Citation]]:
    """Separe les citations valides des fantaisistes.

    Attendu :
      - renvoie (valides, fantaisistes) ; les fantaisistes ont un `motif` :
        "passage non fourni" : l'identifiant n'est pas parmi les passages
          REELLEMENT fournis a cet appel (meme s'il existe dans le corpus :
          le modele ne l'a pas recu, la citation vient de sa memoire)
        "extrait vide" : rien a verifier
        "extrait absent du passage" : _comparable(extrait) n'est pas contenu
          dans _comparable(texte du passage)
      - utilisez dataclasses.replace(citation, motif=...)
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 10 : rebrancher chercher_documents
# ---------------------------------------------------------------------------


def chercher_documents_rag(
    requete: str, limite: int = 5, index: IndexHybride | None = None
) -> list[dict[str, str]]:
    """Meme entree, meme sortie que doc42.outils.chercher_documents, moteur hybride.

    La boucle d'outils de la section 4 et le serveur MCP de la section 6 ne
    doivent pas voir la difference.

    Attendu :
      - index absent : construire_index()
      - limite ramenee entre 1 et 10
      - une liste de {"id", "titre", "extrait"}, un par document (sans
        doublons), dans l'ordre de index.chercher ; l'extrait est le texte du
        meilleur passage du document, espaces reduits, 300 caracteres au plus
    """
    # TODO
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exercice 11 : comparer, et trouver ce qui regresse
# ---------------------------------------------------------------------------


def comparer(
    recherches: dict[str, Recherche], jeu: Sequence[dict[str, Any]], k: int = 5
) -> dict[str, dict[str, Any]]:
    """Les memes questions pour toutes les variantes (fourni)."""
    return {nom: evaluer(recherche, jeu, k) for nom, recherche in recherches.items()}


def trouver_regressions(
    jeu: Sequence[dict[str, Any]], reference: Recherche, candidate: Recherche, k: int = 5
) -> list[str]:
    """Les id des questions ou `candidate` fait PIRE que `reference`.

    Une moyenne qui monte peut cacher des questions qui baissent.

    Attendu :
      - on compare le rappel a k question par question ; strictement pire
        seulement (une egalite n'est pas une regression)
      - les questions hors corpus sont ignorees
    """
    # TODO
    raise NotImplementedError


# Etape 2 de l'atelier, sans test
#
# Mesurez la recherche par mots-cles existante, avant de construire quoi que
# ce soit :
#
#     jeu = charger_jeu()
#     print(evaluer(recherche_mots_cles, jeu, k=5))
#
# Rappel a 5 de la recherche par mots-cles :        MRR :
# Notez aussi k=1 et k=3 : sur un corpus de onze documents, le rappel a 5 sature
# vite, c'est le MRR et le rappel a 1 qui departagent les variantes.
#
#
# Etapes 4 et 6 de l'atelier, sans test : un changement a la fois
#
#     brut = construire_index()
#     enrichi = construire_index(contextualiser=contexte_metadonnees)
#     for k in (1, 3, 5):
#         print(k, comparer({
#             "mots-cles": recherche_mots_cles,
#             "bm25": lambda q, k: brut.documents(q, k, "lexical"),
#             "vectoriel": lambda q, k: brut.documents(q, k, "vectoriel"),
#             "hybride": lambda q, k: brut.documents(q, k, "hybride"),
#             "hybride + contexte": lambda q, k: enrichi.documents(q, k, "hybride"),
#         }, jeu, k))
#
# Mes chiffres (rappel, MRR) pour chaque variante :
#
# La variante qui gagne n'est pas forcement celle que vous attendiez : regardez
# aussi les colonnes "echecs", pas seulement les moyennes.
#
#
# Etape 5 de l'atelier, sans test
#
# Avec trouver_regressions, trouvez une question ou la recherche vectorielle fait
# pire que les mots-cles (essayez k=1). Lisez le passage attendu : pourquoi ?
#
# Ma question, et pourquoi :
#
#
# Etape 7 de l'atelier, sans test
#
# Avec un vrai client (doc42.client.creer_client), passez les vingt questions par
# repondre() et comptez les citations fantaisistes (reponse.fantaisistes).
#
# Nombre de citations fantaisistes sur vingt questions :
#
#
# Etape 8 de l'atelier, sans test
#
# Posez les questions hors corpus du jeu (h01, h02, h03). La recuperation remonte
# toujours quelque chose : c'est la generation qui doit refuser. Si
# reponse.refus est faux, corrigez CONSIGNES_RAG et remesurez.
#
# Ce que j'ai observe :
#
#
# Definition de termine, sans test
#
# Une question ou ma recherche echoue encore, et pourquoi :
#
#
# Bonus, sans test
#
# Faites varier taille_max (par exemple 20, 40, 80, 200 mots, chevauchement d'un
# quart) dans construire_index et tracez le MRR. L'optimum n'est presque jamais
# celui qu'on avait devine.
#
#
# Etape 9 : commitez le checkpoint etape/09-rag.
