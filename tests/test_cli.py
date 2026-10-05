"""
Unit tests for ontoprune.cli.
"""

from pathlib import Path

from ontoprune.cli import main


def test_cli_translate_stdout(capsys) -> None:
    fixture_path = str(Path(__file__).parent.parent / "fixtures" / "sample_service.py")
    ret = main(["translate", fixture_path, "procesar_orden", "--format", "stubs"])
    assert ret == 0

    captured = capsys.readouterr()
    assert "procesar_orden" in captured.out
    assert "def emitir_factura" in captured.out


def test_cli_check_stdout(tmp_path, capsys) -> None:
    contract_file = tmp_path / "contract.txt"
    contract_file.write_text("def validar_orden(order: Order) -> bool: ...\n", encoding="utf-8")

    resp_file = tmp_path / "resp.txt"
    resp_file.write_text("self.validar_orden(order)", encoding="utf-8")

    ret = main(["check", str(resp_file), "--against", str(contract_file)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "VALID" in captured.out
