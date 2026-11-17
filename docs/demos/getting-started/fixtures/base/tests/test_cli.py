from todo.cli import main


def test_add_list_done(tmp_path, capsys):
    path = tmp_path / "t.json"
    assert main(["add", "write"], path=path) == 0
    assert main(["done", "1"], path=path) == 0
    assert main(["list"], path=path) == 0
    assert "1 [x] write" in capsys.readouterr().out


def test_done_unknown_id_fails(tmp_path):
    assert main(["done", "9"], path=tmp_path / "t.json") == 1
