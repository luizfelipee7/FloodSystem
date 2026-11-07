"""Create an explicit, credential-free bundle for the public article page."""

import hashlib
import io
import sqlite3
import tarfile
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from verify_article_db import verify

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".deploy"
SITE = ROOT / "frontend" / "dist-article"
SOURCE_DB = ROOT / "database" / "article-simulations.db"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_files() -> list[tuple[Path, str]]:
    files = [(ROOT / "backend" / "__init__.py", "article-app/backend/__init__.py")]
    files += [(path, "article-app/" + path.relative_to(ROOT).as_posix())
              for path in sorted((ROOT / "backend" / "app").rglob("*.py"))]
    files += [(ROOT / "tools" / "__init__.py", "article-app/tools/__init__.py")]
    files += [(ROOT / "tools" / "weather_simulator" / name,
               "article-app/tools/weather_simulator/" + name)
              for name in ("__init__.py", "model.py")]
    files += [(path, "article-app/" + path.relative_to(ROOT).as_posix())
              for path in sorted((ROOT / "database" / "migrations").glob("*.sql"))]
    allowed_site = {".html", ".js", ".css", ".svg", ".woff", ".woff2"}
    for path in sorted(SITE.rglob("*")):
        if path.is_file():
            if path.name == ".gitkeep":
                continue
            if path.suffix not in allowed_site:
                raise RuntimeError(f"Arquivo inesperado no build: {path.name}")
            files.append((path, "site/" + path.relative_to(SITE).as_posix()))
    files += [(ROOT / "deploy" / "nginx" / "floodsystem.conf", "deploy/floodsystem.conf")]
    files += [(ROOT / "deploy" / "systemd" / "floodsystem-article-api.service",
               "deploy/floodsystem-article-api.service")]
    files += [(ROOT / "deploy" / "verify_article_db.py", "deploy/verify_article_db.py")]
    files += [(ROOT / "deploy" / "install-article-vm.sh", "deploy/install-article-vm.sh")]
    for path, _name in files:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Arquivo exigido ausente ou link simbólico: {path}")
    return files


def main() -> None:
    if not (SITE / "index.html").is_file() or not SOURCE_DB.is_file():
        raise SystemExit("Build integrado ou banco científico ausente.")
    OUTPUT.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="article-snapshot-", suffix=".db", dir=OUTPUT,
                                     delete=False) as temporary:
        snapshot = Path(temporary.name)
    try:
        with closing(sqlite3.connect(SOURCE_DB)) as source, closing(sqlite3.connect(snapshot)) as target:
            source.backup(target)
        runs, tips = verify(snapshot)
        print(f"SQLite científico íntegro: {runs} ensaio(s), {tips} basculada(s).")
        files = source_files() + [(snapshot, "database/article-simulations.db")]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = OUTPUT / f"floodsystem-article-{timestamp}.tar.gz"
        hashes = []
        with tarfile.open(archive, "w:gz") as bundle:
            for path, name in files:
                bundle.add(path, arcname=name, recursive=False)
                hashes.append(f"{sha256(path)}  {name}\n")
            content = "".join(hashes).encode("ascii")
            info = tarfile.TarInfo("SHA256SUMS")
            info.size = len(content)
            info.mode = 0o644
            bundle.addfile(info, io.BytesIO(content))
        print(f"Pacote criado: {archive}")
        print(f"Arquivos: {len(files)}; tamanho: {archive.stat().st_size} bytes")
    finally:
        snapshot.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
