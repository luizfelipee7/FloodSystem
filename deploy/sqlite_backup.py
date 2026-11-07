"""Consistent SQLite snapshots. Restore only to a NEW file, never overwrite a DB."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import tempfile

TABLES = {"devices", "calibrations", "level_readings", "rain_tip_events"}


def verify(path: Path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite integrity_check failed")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("SQLite foreign_key_check failed")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not TABLES.issubset(tables) or db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("Not a supported FloodSystem database (schema version 1)")
        return {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in sorted(TABLES)}


def snapshot(source: Path, destination: Path):
    source, destination = source.resolve(), destination.absolute()
    if not source.is_file():
        raise ValueError("Source database does not exist")
    if destination.exists() or destination.is_symlink() or source == destination:
        raise ValueError("Destination must be a NEW file")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".floodsystem-", suffix=".db", dir=destination.parent)
    os.close(fd)
    temp = Path(temporary)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=30)) as src:
            with closing(sqlite3.connect(temp)) as dst:
                src.backup(dst, pages=256, sleep=0.1)
        counts = verify(temp)
        os.chmod(temp, 0o600)
        with temp.open("r+b") as stream:
            os.fsync(stream.fileno())
        # Hard-link publishes atomically and refuses a destination created concurrently.
        os.link(temp, destination)
        if os.name == "posix":
            dir_fd = os.open(destination.parent, os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        return counts
    finally:
        temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("source", type=Path)
    backup.add_argument("directory", type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("source", type=Path)
    restore.add_argument("destination", type=Path)
    check = commands.add_parser("verify")
    check.add_argument("source", type=Path)
    args = parser.parse_args()
    if args.command == "verify":
        print(verify(args.source))
    else:
        destination = args.destination if args.command == "restore" else args.directory / (
            "production-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".db")
        counts = snapshot(args.source, destination)
        print(destination)
        print(counts)


if __name__ == "__main__":
    main()
