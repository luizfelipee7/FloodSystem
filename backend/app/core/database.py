"""SQLite connections and transactional, versioned schema initialization."""

import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator

from .config import PROJECT_ROOT, Settings

MIGRATIONS = tuple(PROJECT_ROOT / "database" / "migrations" / name for name in (
    "001_initial.sql", "002_weather_experiments.sql",
))


@contextmanager
def connection(settings: Settings, *, write: bool = False) -> Iterator[sqlite3.Connection]:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(settings.database_path, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys = ON")
        if write:
            db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def initialize_database(settings: Settings) -> None:
    with connection(settings, write=True) as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > len(MIGRATIONS):
            raise RuntimeError("Este banco usa uma versão de esquema mais recente que o código.")
        for number, migration in enumerate(MIGRATIONS, start=1):
            if number <= version:
                continue
            statement = ""
            for line in migration.read_text(encoding="utf-8").splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    db.execute(statement)
                    statement = ""
            if statement.strip():
                raise RuntimeError(f"Migração SQL incompleta: {migration.name}")
            db.execute(f"PRAGMA user_version = {number}")


if __name__ == "__main__":
    configuration = Settings.from_env()
    initialize_database(configuration)
    print(f"SQLite pronto ({configuration.environment}): {configuration.database_path}")
