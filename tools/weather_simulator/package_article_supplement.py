"""Bundle only the scientific snapshot and offline analysis for editorial review."""

import argparse
import json
import sqlite3
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def build(*, snapshot, analysis, published_export, scientific_db, output):
    snapshot, analysis = Path(snapshot), Path(analysis)
    published_export, scientific_db, output = Path(published_export), Path(scientific_db), Path(output)
    if output.exists():
        raise FileExistsError("O suplemento já existe; escolha outro nome para preservar a versão anterior.")
    if scientific_db.name != "article-simulations.db":
        raise ValueError("O suplemento aceita somente o SQLite científico local.")
    connection = sqlite3.connect(scientific_db.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        devices = connection.execute("SELECT device_id, origin FROM devices").fetchall()
        level_count = connection.execute("SELECT COUNT(*) FROM level_readings").fetchone()[0]
        if not devices or any(origin != "simulation" for _, origin in devices) or level_count:
            raise ValueError("Banco contém origem não científica ou leituras de nível; não será empacotado.")
    finally:
        connection.close()
    analysis_manifest = json.loads((analysis / "manifest.json").read_text(encoding="utf-8"))
    required = [analysis / name for name in analysis_manifest["files_sha256"]] + [analysis / "manifest.json"]
    for path in required + [snapshot / "manifest.json", snapshot / "response.json", published_export, scientific_db]:
        if not path.is_file():
            raise FileNotFoundError(path)
    code = Path(__file__).resolve().parent
    readme = (
        "Suplemento computacional FloodSystem RICSS\n\n"
        "source/: resposta Open-Meteo/ERA5 original e manifesto.\n"
        "analysis/: oito casos computacionais, tabelas, figuras, relatório e auditoria.\n"
        "published/: exportação original do ensaio publicado.\n"
        "database/: fotografia do SQLite científico local, somente simulação.\n"
        "code/: código e dependências adicionais para reproduzir a análise.\n\n"
        "A condição ERA5 é reanálise horária; os eventos são simulados. Os cenários idealizados\n"
        "não são chuva observada e o pacote não contém dados físicos do ESP32 ou nível.\n"
        "No repositório FloodSystem, instale code/requirements-analysis.txt e execute:\n"
        "python -m tools.weather_simulator.article_analysis --snapshot source --output nova-saida\n"
        "Os argumentos --published-export e --scientific-db permitem conferir os artefatos arquivados.\n"
        "Antes de enviar a uma revista com avaliação duplo-cega, revise possíveis identificadores.\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", readme)
        for name in ("manifest.json", "response.json"):
            archive.write(snapshot / name, f"source/{name}")
        for path in required:
            archive.write(path, f"analysis/{path.name}")
        archive.write(published_export, f"published/{published_export.name}")
        archive.write(scientific_db, "database/article-simulations.db")
        for name in ("__init__.py", "model.py", "source.py", "article_analysis.py",
                     "requirements-analysis.txt", "package_article_supplement.py"):
            archive.write(code / name, f"code/{name}")
    return output.resolve()


def main():
    parser = argparse.ArgumentParser(description="Cria suplemento computacional sem acessar VM/API.")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--published-export", required=True)
    parser.add_argument("--scientific-db", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(build(**vars(args)))


if __name__ == "__main__":
    main()
