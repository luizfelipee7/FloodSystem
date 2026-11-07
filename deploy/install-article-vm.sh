#!/usr/bin/env bash
# Install the isolated, read-only weather experiment API and integrated frontend.
set -euo pipefail

if [[ ${EUID} -ne 0 || $# -ne 1 ]]; then
    echo 'Uso: sudo bash install-article-vm.sh /home/ubuntu/PASTA_EXTRAIDA' >&2
    exit 2
fi

bundle=$(realpath -- "$1")
test -f "$bundle/SHA256SUMS"
test -f "$bundle/site/index.html"
test -f "$bundle/article-app/backend/app/article_public.py"
test -f "$bundle/database/article-simulations.db"
(cd "$bundle" && sha256sum --status -c SHA256SUMS)
python3 "$bundle/deploy/verify_article_db.py" "$bundle/database/article-simulations.db"

if ! id floodarticle >/dev/null 2>&1; then
    useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin floodarticle
fi

app_target=/srv/floodsystem/article-app
data_dir=/srv/floodsystem/article-data
data_target="$data_dir/article-simulations.db"
site_target=/srv/floodsystem/frontend/dist
nginx_target=/etc/nginx/sites-available/floodsystem
unit_target=/etc/systemd/system/floodsystem-article-api.service
stamp=$(date -u +%Y%m%dT%H%M%SZ)-$$

install -d -o root -g floodarticle -m 0750 "$data_dir"
if [[ -e "$data_target" ]]; then
    cmp -s "$bundle/database/article-simulations.db" "$data_target" || {
        echo 'Já existe um banco científico diferente na VM; nenhum dado será substituído.' >&2
        exit 1
    }
else
    install -o root -g floodarticle -m 0640 "$bundle/database/article-simulations.db" "$data_target"
fi

app_stage=$(mktemp -d /srv/floodsystem/.article-app.XXXXXX)
cp -a "$bundle/article-app/." "$app_stage/"
chown -R root:root "$app_stage"
find "$app_stage" -type d -exec chmod 0755 {} +
find "$app_stage" -type f -exec chmod 0644 {} +
if [[ -e "$app_target" ]]; then
    mv "$app_target" "/srv/floodsystem/article-app.before-$stamp"
fi
mv "$app_stage" "$app_target"

install -o root -g root -m 0644 "$bundle/deploy/floodsystem-article-api.service" "$unit_target"
systemctl daemon-reload
systemctl enable floodsystem-article-api.service
systemctl restart floodsystem-article-api.service
systemctl is-active --quiet floodsystem-article-api.service
curl --retry 15 --retry-delay 1 --retry-connrefused --fail --silent --show-error http://127.0.0.1:8010/health >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8010/api/v1/experiments/status >/dev/null

site_stage=$(mktemp -d /srv/floodsystem/frontend/.article-dist.XXXXXX)
cp -a "$bundle/site/." "$site_stage/"
chown -R root:root "$site_stage"
find "$site_stage" -type d -exec chmod 0755 {} +
find "$site_stage" -type f -exec chmod 0644 {} +

nginx_backup="/etc/nginx/sites-available/floodsystem.before-article-$stamp"
cp -a "$nginx_target" "$nginx_backup"
install -o root -g root -m 0644 "$bundle/deploy/floodsystem.conf" "$nginx_target"
if ! nginx -t || ! systemctl reload nginx; then
    cp -a "$nginx_backup" "$nginx_target"
    nginx -t
    systemctl reload nginx
    echo 'Configuração anterior do Nginx restaurada.' >&2
    exit 1
fi

test -d "$site_target"
mv "$site_target" "/srv/floodsystem/frontend/dist.before-article-$stamp"
mv "$site_stage" "$site_target"

public=https://floodsystem.duckdns.org
curl --resolve floodsystem.duckdns.org:443:127.0.0.1 --fail --silent --show-error "$public/health" >/dev/null
curl --resolve floodsystem.duckdns.org:443:127.0.0.1 --fail --silent --show-error "$public/ensaios/" >/dev/null
curl --resolve floodsystem.duckdns.org:443:127.0.0.1 --fail --silent --show-error "$public/article-api/v1/experiments/status" >/dev/null
curl --resolve floodsystem.duckdns.org:443:127.0.0.1 --fail --silent --show-error "$public/article-api/v1/experiments" >/dev/null
post_status=$(curl --resolve floodsystem.duckdns.org:443:127.0.0.1 --silent --output /dev/null --write-out '%{http_code}' --request POST "$public/article-api/v1/experiments")
test "$post_status" = 403
systemctl is-active --quiet floodsystem-api.service
systemctl is-active --quiet nginx.service

echo 'Publicação concluída: API física, API científica e frontend ativos.'
echo "Backup do site anterior: /srv/floodsystem/frontend/dist.before-article-$stamp"
echo "Backup da configuração anterior: $nginx_backup"
