#!/usr/bin/env bash
# Run as root from the reviewed deployment staging directory.
set -euo pipefail
test "$(id -u)" -eq 0
stage=$(cd -- "$(dirname -- "$0")/.." && pwd)
test -f "$stage/frontend/dist/index.html"
test -f "$stage/database/migrations/001_initial.sql"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv nginx certbot iptables-persistent
if ! id floodsystem >/dev/null 2>&1; then
    useradd --system --home-dir /srv/floodsystem --shell /usr/sbin/nologin floodsystem
fi
install -d -m 0755 /srv/floodsystem
install -d -o floodsystem -g floodsystem -m 0700 /srv/floodsystem/database
install -d -o root -g floodsystem -m 0750 /etc/floodsystem
install -d -o root -g root -m 0700 /var/backups/floodsystem
install -d -m 0755 /var/www/letsencrypt
if test -f /srv/floodsystem/database/production.db; then
    python3 "$stage/deploy/sqlite_backup.py" backup /srv/floodsystem/database/production.db /var/backups/floodsystem
fi
cp -a "$stage/backend" "$stage/deploy" "$stage/frontend" /srv/floodsystem/
cp -a "$stage/database/migrations" /srv/floodsystem/database/
python3 -m venv /srv/floodsystem/.venv
/srv/floodsystem/.venv/bin/python -m pip install -r /srv/floodsystem/backend/requirements.txt
python3 - <<'PY'
import grp, json, os, secrets
from pathlib import Path
p = Path('/etc/floodsystem/api.env')
if not p.exists():
    content = ('FLOODSYSTEM_ENV=production\n'
               'FLOODSYSTEM_DB_PATH=/srv/floodsystem/database/production.db\n'
               "FLOODSYSTEM_DEVICE_TOKENS_JSON='" + json.dumps({'esp32-01': secrets.token_urlsafe(48)}) + "'\n")
    fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o640)
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)
    os.chown(p, 0, grp.getgrnam('floodsystem').gr_gid)
PY
runuser -u floodsystem -- bash -c 'cd /srv/floodsystem; set -a; . /etc/floodsystem/api.env; set +a; export PYTHONDONTWRITEBYTECODE=1; exec .venv/bin/python -m deploy.initialize_production'
chmod 0600 /srv/floodsystem/database/production.db
install -m 0644 /srv/floodsystem/deploy/systemd/floodsystem-api.service.example /etc/systemd/system/floodsystem-api.service
install -m 0644 /srv/floodsystem/deploy/systemd/floodsystem-backup.service /etc/systemd/system/floodsystem-backup.service
install -m 0644 /srv/floodsystem/deploy/systemd/floodsystem-backup.timer /etc/systemd/system/floodsystem-backup.timer
systemctl daemon-reload
systemctl enable --now floodsystem-api.service floodsystem-backup.timer
systemctl restart floodsystem-api.service
systemctl start floodsystem-backup.service
if test -f /etc/nginx/sites-available/default && ! test -e /var/backups/floodsystem/nginx-default-before-stage8; then
    cp -a /etc/nginx/sites-available/default /var/backups/floodsystem/nginx-default-before-stage8
fi
if ! test -f /etc/letsencrypt/live/floodsystem.duckdns.org/fullchain.pem; then
    install -m 0644 /srv/floodsystem/deploy/nginx/floodsystem-http.conf /etc/nginx/sites-available/floodsystem
else
    install -m 0644 /srv/floodsystem/deploy/nginx/floodsystem.conf /etc/nginx/sites-available/floodsystem
fi
ln -sfn /etc/nginx/sites-available/floodsystem /etc/nginx/sites-enabled/floodsystem
if test -L /etc/nginx/sites-enabled/default; then unlink /etc/nginx/sites-enabled/default; fi
nginx -t
systemctl enable nginx
systemctl reload nginx
systemctl is-active floodsystem-api nginx
