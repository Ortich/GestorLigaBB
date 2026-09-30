#!/usr/bin/env bash
# Apunta un nombre gratuito de DuckDNS a la IP publica de esta maquina.
#
#   sudo bash scripts/update-dns.sh miliga TU_TOKEN
#
# Sin argumentos lo usa el cron: lee DUCKDNS_DOMAIN y DUCKDNS_TOKEN de
# /etc/gestor-liga.env y avisa a DuckDNS por si la IP ha cambiado.
set -euo pipefail

ENV_FILE="${GESTOR_ENV_FILE:-/etc/gestor-liga.env}"
CRON_FILE="${GESTOR_DNS_CRON:-/etc/cron.d/gestor-liga-dns}"
API="${GESTOR_DNS_URL:-https://www.duckdns.org/update}"
SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

upsert_env() {
  local key="$1" value="$2" tmp
  tmp="$(mktemp)"
  if [ -f "$ENV_FILE" ]; then
    grep -v "^${key}=" "$ENV_FILE" > "$tmp" || true
  fi
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  mv "$tmp" "$ENV_FILE"
  chmod 600 "$ENV_FILE" 2>/dev/null || true
}

install_cron() {
  local dir
  dir="$(dirname "$CRON_FILE")"
  mkdir -p "$dir"
  cat > "$CRON_FILE" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
*/5 * * * * root ${SCRIPT} >> /var/log/gestor-liga-dns.log 2>&1
EOF
  chmod 644 "$CRON_FILE"
}

if [ "$#" -eq 2 ]; then
  domain="${1%.duckdns.org}"
  token="$2"
  if ! [[ "$domain" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; then
    echo "El nombre solo puede llevar minusculas, numeros y guiones. Ejemplo: miliga" >&2
    exit 1
  fi
  if [ -z "$token" ]; then
    echo "Falta el token de DuckDNS." >&2
    exit 1
  fi
  touch "$ENV_FILE"
  upsert_env DUCKDNS_DOMAIN "$domain"
  upsert_env DUCKDNS_TOKEN "$token"
elif [ "$#" -ne 0 ]; then
  echo "Uso: sudo bash scripts/update-dns.sh <nombre> <token>" >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Todavia no hay nombre. Ejemplo: sudo bash scripts/update-dns.sh miliga TU_TOKEN" >&2
  exit 1
fi

domain="$(grep '^DUCKDNS_DOMAIN=' "$ENV_FILE" | cut -d= -f2- || true)"
token="$(grep '^DUCKDNS_TOKEN=' "$ENV_FILE" | cut -d= -f2- || true)"
domain="${domain%.duckdns.org}"
if [ -z "$domain" ] || [ -z "$token" ]; then
  echo "Todavia no hay nombre. Ejemplo: sudo bash scripts/update-dns.sh miliga TU_TOKEN" >&2
  exit 1
fi

response="$(curl -fsS --max-time 20 --get "$API" \
  --data-urlencode "domains=${domain}" \
  --data-urlencode "token=${token}" \
  --data-urlencode "ip=" || true)"
response="$(printf '%s' "$response" | tr -d '[:space:]')"

if [ "$response" != "OK" ]; then
  echo "DuckDNS no ha aceptado el nombre. Revisa el token en duckdns.org." >&2
  exit 1
fi

if [ ! -f "$CRON_FILE" ] || [ "$#" -eq 2 ]; then
  install_cron
fi

echo "Listo. La liga queda en http://${domain}.duckdns.org"
echo "Si la IP cambia, este servidor actualiza el nombre solo."
