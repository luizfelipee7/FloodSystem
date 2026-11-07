"""Read-only validation of a packaged scientific SQLite snapshot."""

import sqlite3
import sys
from pathlib import Path


def verify(path: Path) -> tuple[int, int]:
    path = path.resolve()
    if not path.is_file():
        raise SystemExit("Banco científico ausente.")
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("PRAGMA user_version").fetchone()[0] != 2:
            raise SystemExit("Esquema científico diferente da versão 2.")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise SystemExit("Falha na integridade do SQLite científico.")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise SystemExit("Falha nas chaves estrangeiras do SQLite científico.")
        if db.execute("SELECT 1 FROM devices WHERE origin != 'simulation' OR device_id NOT LIKE 'sim-artigo-%' LIMIT 1").fetchone():
            raise SystemExit("Banco contém dispositivos fora dos ensaios meteorológicos.")
        runs = db.execute("SELECT count(*) FROM simulation_runs").fetchone()[0]
        tips = db.execute("SELECT count(*) FROM rain_tip_events").fetchone()[0]
        if runs < 1:
            raise SystemExit("Banco científico sem ensaios.")
    return runs, tips


def main() -> None:
    runs, tips = verify(Path(sys.argv[1]))
    print(f"SQLite científico íntegro: {runs} ensaio(s), {tips} basculada(s).")


if __name__ == "__main__":
    main()
