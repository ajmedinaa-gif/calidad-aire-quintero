from importlib.metadata import version as pkg_version

import pandas as pd
from typer.testing import CliRunner

import calidad_aire.cli as cli
from calidad_aire.cli import app

runner = CliRunner()


def test_version_command_prints_installed_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert pkg_version("calidad-aire-quintero") in result.stdout


def test_ingest_command_consolida_valida_y_escribe_parquet(tmp_path, monkeypatch) -> None:
    raw_dir = tmp_path / "raw" / "una_estacion"
    raw_dir.mkdir(parents=True)
    (raw_dir / "so2_horario.csv").write_text(
        "FECHA (YYMMDD);HORA (HHMM);Registros validados;Registros preliminares;"
        "Registros no validados;\n"
        "240101;0100;;12,5;;\n"
        "240101;0200;;-3;;\n",  # la segunda fila es físicamente imposible
        encoding="latin-1",
    )

    monkeypatch.setattr(cli, "RAW_DIR", raw_dir.parent)
    monkeypatch.setattr(cli, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(cli, "PARQUET_PATH", tmp_path / "processed" / "sinca.parquet")
    monkeypatch.setattr(cli, "QUARANTINE_DIR", tmp_path / "quarantine")

    result = runner.invoke(app, ["ingest"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "processed" / "sinca.parquet").exists()
    escrito = pd.read_parquet(tmp_path / "processed" / "sinca.parquet")
    assert len(escrito) == 1
    assert list((tmp_path / "quarantine").glob("*.csv"))
