#!/usr/bin/env bash
# Production install on a fresh Ubuntu 24.04 VPS (e.g. Hostinger KVM).
#
#   sudo bash deploy/setup-vps.sh <domain> <email-for-https-certificate>
#
# Safe to re-run: re-running after uploading new code rebuilds and restarts.
#
# Result:
#   nginx :80/:443  ->  Next.js on 127.0.0.1:3000   (the UI)
#                   ->  FastAPI on 127.0.0.1:8000   (/api/*)
#   user code runs inside nsjail, as an unprivileged service user.
set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
  echo "usage: sudo bash $0 <domain> <email>" >&2
  exit 1
fi
[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo)." >&2; exit 1; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER=cpsolve
export DEBIAN_FRONTEND=noninteractive

step() { printf '\n==> %s\n' "$*"; }

step "System packages"
apt-get update
apt-get install -y build-essential python3 python3-venv python3-pip curl ca-certificates \
  nginx certbot python3-certbot-nginx ufw
if [ "${INSTALL_JAVA:-0}" = "1" ]; then
  apt-get install -y openjdk-17-jdk-headless
fi

step "Node.js 22"
if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

step "nsjail (sandbox for user code)"
if ! command -v nsjail >/dev/null; then
  if ! apt-get install -y nsjail; then
    apt-get install -y git autoconf bison flex libtool pkg-config \
      libprotobuf-dev protobuf-compiler libnl-route-3-dev
    rm -rf /tmp/nsjail-src
    git clone --depth 1 https://github.com/google/nsjail.git /tmp/nsjail-src
    make -C /tmp/nsjail-src -j"$(nproc)"
    install -m 0755 /tmp/nsjail-src/nsjail /usr/local/bin/nsjail
  fi
fi
NSJAIL_BIN="$(command -v nsjail)"

# Ubuntu 24.04 blocks unprivileged user namespaces unless an AppArmor profile
# allows them. Grant that to nsjail alone rather than switching it off globally.
if [ -e /proc/sys/kernel/apparmor_restrict_unprivileged_userns ]; then
  sed "s#@NSJAIL_BIN@#${NSJAIL_BIN}#" "$APP_DIR/deploy/apparmor-nsjail" > /etc/apparmor.d/nsjail
  apparmor_parser -r /etc/apparmor.d/nsjail
fi

step "Service user and files"
id "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  sed -i "s#^CPSOLVE_CORS_ORIGINS=.*#CPSOLVE_CORS_ORIGINS=https://${DOMAIN}#" "$APP_DIR/.env"
fi
chmod 600 "$APP_DIR/.env"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

step "Python engine"
sudo -u "$APP_USER" bash -c "cd '$APP_DIR' && { [ -d .venv ] || python3 -m venv .venv; } \
  && .venv/bin/pip install --quiet --upgrade pip \
  && .venv/bin/pip install --quiet -r requirements.txt"

step "Web front end (build)"
sudo -u "$APP_USER" bash -c "cd '$APP_DIR/web' && npm ci --no-audit --no-fund && npm run build"

step "systemd services"
for unit in instant-solver-api instant-solver-web; do
  sed -e "s#@APP_DIR@#${APP_DIR}#g" -e "s#@APP_USER@#${APP_USER}#g" \
    "$APP_DIR/deploy/${unit}.service" > "/etc/systemd/system/${unit}.service"
done
systemctl daemon-reload
systemctl enable instant-solver-api instant-solver-web
systemctl restart instant-solver-api instant-solver-web

step "nginx"
# Keep the HTTPS block certbot adds on earlier runs: only write the site once.
if [ ! -f /etc/nginx/sites-available/instant-solver ]; then
  sed "s#@DOMAIN@#${DOMAIN}#g" "$APP_DIR/deploy/nginx-instant-solver.conf" \
    > /etc/nginx/sites-available/instant-solver
fi
ln -sf /etc/nginx/sites-available/instant-solver /etc/nginx/sites-enabled/instant-solver
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

step "Firewall"
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

step "HTTPS certificate (Let's Encrypt)"
if [ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
  certbot --nginx -d "$DOMAIN" -m "$EMAIL" --agree-tos --redirect --non-interactive \
    || echo "!! certbot failed. Check that the domain's A record points to this server, then run:
   certbot --nginx -d $DOMAIN -m $EMAIL --redirect"
fi

step "Health check"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/api/health; then echo; break; fi
  sleep 1
done
curl -fsS -o /dev/null -w 'web: HTTP %{http_code}\n' http://127.0.0.1:3000/ || true

echo
echo "Done: https://${DOMAIN}"
echo "Logs: journalctl -u instant-solver-api -f   |   journalctl -u instant-solver-web -f"
