#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" -eq 0
test -f /etc/letsencrypt/live/floodsystem.duckdns.org/fullchain.pem
install -m 0644 /srv/floodsystem/deploy/nginx/floodsystem.conf /etc/nginx/sites-available/floodsystem
nginx -t
systemctl reload nginx
install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
install -m 0755 /srv/floodsystem/deploy/renew-nginx.sh /etc/letsencrypt/renewal-hooks/deploy/floodsystem-nginx
systemctl enable --now certbot.timer
