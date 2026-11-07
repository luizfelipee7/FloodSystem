#!/usr/bin/env bash
# Explicit maintenance: preserve previous DB and sidecars; never delete them.
set -euo pipefail
if test "$(id -u)" -ne 0 || test "$#" -ne 2 || test "$2" != --confirm-replace; then
    echo 'Usage: sudo bash /srv/floodsystem/deploy/restore-production.sh /absolute/backup.db --confirm-replace' >&2
    exit 2
fi
source=$(realpath -- "$1")
db=/srv/floodsystem/database/production.db
test "$source" != "$db"
python3 /srv/floodsystem/deploy/sqlite_backup.py verify "$source"
stamp=$(date -u +%Y%m%dT%H%M%S%NZ)
candidate="/srv/floodsystem/database/restore-$stamp.db"
python3 /srv/floodsystem/deploy/sqlite_backup.py restore "$source" "$candidate"
chown floodsystem:floodsystem "$candidate"
systemctl stop floodsystem-api.service
archive="/srv/floodsystem/database/before-restore-$stamp"
recover_on_failure() {
    result=$?
    trap - EXIT
    set +e
    if test "$result" -ne 0 && test -f "$archive/production.db"; then
        systemctl stop floodsystem-api.service
        install -d -m 0700 "$archive/failed-replacement"
        for file in "$db" "$db-wal" "$db-shm" "$db-journal"; do
            test ! -e "$file" || mv -- "$file" "$archive/failed-replacement/"
        done
        for file in "$archive"/production.db*; do
            test ! -f "$file" || mv -- "$file" /srv/floodsystem/database/
        done
    fi
    systemctl start floodsystem-api.service
    exit "$result"
}
trap recover_on_failure EXIT
if test -f "$db"; then
    python3 /srv/floodsystem/deploy/sqlite_backup.py backup "$db" /var/backups/floodsystem
fi
install -d -m 0700 "$archive"
# Move sidecars with the old database, after all API writers have stopped.
for file in "$db" "$db-wal" "$db-shm" "$db-journal"; do
    if test -e "$file"; then mv -- "$file" "$archive/"; fi
done
mv -- "$candidate" "$db"
systemctl start floodsystem-api.service
sleep 2
curl --fail --silent --show-error http://127.0.0.1:8000/health
trap - EXIT
echo
echo "Previous database preserved at $archive. Restored: $source"
