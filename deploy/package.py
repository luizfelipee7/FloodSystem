"""Build an allowlisted upload archive; never traverse private configuration/keys/DBs."""
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
target = root / ".deploy" / "floodsystem-stage8.tar.gz"
target.parent.mkdir(exist_ok=True)
files = [p for p in (root / "backend" / "app").rglob("*.py")]
files += [root / "backend" / "requirements.txt"]
files += list((root / "database" / "migrations").glob("*.sql"))
files += [p for p in (root / "deploy").rglob("*") if p.is_file() and p.suffix in {".py", ".sh", ".conf", ".example", ".service", ".timer"}]
files += [p for p in (root / "frontend" / "dist").rglob("*") if p.is_file()]
if not (root / "frontend" / "dist" / "index.html").is_file():
    raise RuntimeError("Build the frontend before packaging")
with tarfile.open(target, "w:gz") as bundle:
    for p in sorted(set(files)):
        if p.is_symlink() or "__pycache__" in p.parts:
            raise RuntimeError(f"Unexpected file: {p.name}")
        info = bundle.gettarinfo(str(p), arcname=p.relative_to(root).as_posix())
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        info.mode = 0o644
        with p.open("rb") as stream:
            bundle.addfile(info, stream)
print(f"{target}: {len(files)} public code/build files; no DB, firmware config or SSH keys")
