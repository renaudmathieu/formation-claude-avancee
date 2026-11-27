import pytest

from escale.toolbox import Toolbox, ToolError
from escale.tools.files import MAX_FILE_CHARS, file_tools, resolve_inside


def test_write_then_read(tmp_path):
    box = Toolbox(file_tools(tmp_path))

    _, is_error = box.run("write_file", {"path": "a/route.md", "content": "Lyon"})

    assert not is_error
    assert box.run("read_file", {"path": "a/route.md"}) == ("Lyon", False)


@pytest.mark.parametrize("path", ["../secret.txt", "/etc/passwd", "a/../../secret.txt", "."])
def test_paths_outside_the_folder_are_refused(tmp_path, path):
    root = tmp_path / "sortie"
    root.mkdir()

    with pytest.raises(ToolError):
        resolve_inside(root, path)


def test_symlink_cannot_escape_the_folder(tmp_path):
    root = tmp_path / "sortie"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("clé")
    (root / "lien.txt").symlink_to(tmp_path / "secret.txt")

    content, is_error = Toolbox(file_tools(root)).run("read_file", {"path": "lien.txt"})

    assert is_error
    assert "clé" not in content


def test_missing_file_is_an_error_result(tmp_path):
    _, is_error = Toolbox(file_tools(tmp_path)).run("read_file", {"path": "absent.md"})

    assert is_error


def test_symlink_cannot_be_used_to_write_outside_the_folder(tmp_path):
    root = tmp_path / "sortie"
    root.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("intact")
    (root / "lien.txt").symlink_to(secret)

    _, is_error = Toolbox(file_tools(root)).run(
        "write_file", {"path": "lien.txt", "content": "écrasé"}
    )

    assert is_error
    assert secret.read_text() == "intact"


def test_too_long_file_is_refused(tmp_path):
    (tmp_path / "long.txt").write_text("x" * (MAX_FILE_CHARS + 1))

    _, is_error = Toolbox(file_tools(tmp_path)).run("read_file", {"path": "long.txt"})

    assert is_error


def test_writing_outside_the_folder_is_an_error_result(tmp_path):
    root = tmp_path / "sortie"
    root.mkdir()

    content, is_error = Toolbox(file_tools(root)).run(
        "write_file", {"path": "../evasion.md", "content": "x"}
    )

    assert is_error
    assert "refusé" in content
    assert not (tmp_path / "evasion.md").exists()
