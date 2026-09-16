import json
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
    # los_maitenes/so2_horario es un par real de INICIO_OPERACION
    # (CLAUDE.md §8.6.4); una estación inventada haría fallar la validación
    # a propósito con "INICIO_OPERACION no tiene entrada para ...".
    raw_dir = tmp_path / "raw" / "los_maitenes"
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


def test_eda_command_escribe_json_y_cinco_figuras(tmp_path, monkeypatch) -> None:
    horas = pd.date_range("2020-01-01", periods=48, freq="h")
    valores_horarios = [600.0] + [10.0] * 47  # una hora de emergencia, día 1
    horaria = pd.DataFrame(
        {
            "estacion": "los_maitenes",
            "parametro": "so2_horario",
            "fecha_hora": horas,
            "valor": valores_horarios,
            "estado": "validado",
        }
    )
    diaria = pd.DataFrame(
        {
            "estacion": ["los_maitenes", "los_maitenes"],
            "parametro": ["so2_diario", "so2_diario"],
            "fecha_hora": pd.to_datetime(["2020-01-01", "2020-01-02"]),
            "valor": [
                pd.Series(valores_horarios[:24]).mean(),
                pd.Series(valores_horarios[24:]).mean(),
            ],
            "estado": ["validado", "validado"],
        }
    )
    parquet_path = tmp_path / "sinca.parquet"
    pd.concat([horaria, diaria], ignore_index=True).to_parquet(parquet_path, index=False)

    reports_dir = tmp_path / "reports"
    monkeypatch.setattr(cli, "PARQUET_PATH", parquet_path)
    monkeypatch.setattr(cli, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(cli, "FIGURES_DIR", reports_dir / "figures")

    result = runner.invoke(app, ["eda"])

    assert result.exit_code == 0, result.output
    informe = json.loads((reports_dir / "eda.json").read_text())
    assert informe["comparacion_resolucion"]["horas_emergencia"] == 1
    assert informe["reconstruccion_diaria"]["n_dias_comparados"] == 2
    assert informe["reconstruccion_diaria"]["dias_discrepantes"] == []
    assert len(list((reports_dir / "figures").glob("*.png"))) == 5
