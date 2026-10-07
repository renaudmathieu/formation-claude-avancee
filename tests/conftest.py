"""Harnais de test de la formation.

Par defaut, les tests tournent contre un FAUX client : deterministes,
gratuits, sans reseau, sans cle API. C'est ce qui permet a l'atelier de
fonctionner meme si le service est indisponible ou si un stagiaire n'a pas
encore son abonnement.

Deux options :

    --reel        ajoute un test de fumee contre la vraie API
    --solutions   fait tourner les tests contre solutions/ au lieu de exercices/

Chaque fichier tests/test_sectionNN.py teste exercices/sectionNN.py (ou
solutions/sectionNN.py avec --solutions) via la fixture `module`.
"""

from __future__ import annotations

import importlib

import pytest
from fakes import FauxClient
from fakes import aplatir as _aplatir


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--reel", action="store_true", help="appeler la vraie API")
    parser.addoption(
        "--solutions", action="store_true", help="tester solutions/ au lieu de exercices/"
    )


@pytest.fixture
def module(request: pytest.FixtureRequest):
    """Le module a tester : exercices par defaut, solutions pour le formateur.

    Le nom vient du fichier de test : tests/test_section04.py teste section04.
    """
    section = request.module.__name__.rsplit(".", 1)[-1].removeprefix("test_")
    paquet = "solutions" if request.config.getoption("--solutions") else "exercices"
    return importlib.import_module(f"{paquet}.{section}")


@pytest.fixture
def client() -> FauxClient:
    return FauxClient()


@pytest.fixture
def aplatir():
    return _aplatir
