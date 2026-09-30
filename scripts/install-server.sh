#!/usr/bin/env bash
# Instala la liga como servicio en un Ubuntu (el destino previsto es una
# maquina Always Free de Oracle Cloud). Un solo proceso de Python, sin Docker.
#
#   git clone https://github.com/Ortich/GestorLigaBB.git
#   cd GestorLigaBB
#   sudo scripts/install-server.sh
#
# Al terminar, la app escucha en el puerto 80 y sobrevive a los reinicios.
# La base de datos sigue siendo backend/liga.db.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Ejecutalo con sudo: sudo scripts/install-server.sh" >&2
  exit 1
fi

OWNER="${SUDO_USER:-}"
if [ -z "$OWNER" ] || [ "$OWNER" = "root" ]; then
  echo "Entra por SSH como ubuntu y lanza el script con sudo, no desde una sesion de root." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE=/etc/gestor-liga.env
PINS_FILE=/etc/gestor-liga-pins.txt
UNIT=/etc/systemd/system/gestor-liga.service
export DEBIAN_FRONTEND=noninteractive

echo "==> Paquetes del sistema"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git curl ca-certificates iptables

if ! command -v node >/dev/null 2>&1 || ! node -e 'const [M,m]=process.versions.node.split(".").map(Number); process.exit((M>18||(M===18&&m>=18))?0:1)'; then
  echo "==> Node.js 22 (hace falta para compilar la interfaz una vez)"
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

# La maquina Micro de Oracle tiene 1 GB. Compilar Next.js no cabe sin swap.
MEM_KB="$(awk '/MemTotal/{print $2}' /proc/meminfo)"
if [ "$MEM_KB" -lt 1800000 ] && ! swapon --show | grep -q .; then
  echo "==> Anadiendo 2 GB de swap para la compilacion"
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "==> Generando claves de sesion y de comisario"
  SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  MASTER="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
  umask 077
  cat > "$ENV_FILE" <<EOF
SECRET_KEY=${SECRET}
MASTER_KEY=${MASTER}
EOF
  umask 022
  chmod 600 "$ENV_FILE"
  NEW_KEYS=1
else
  echo "==> Se conservan las claves de $ENV_FILE"
  NEW_KEYS=0
fi

echo "==> Dependencias y base de datos"
sudo -u "$OWNER" bash -lc "cd '$ROOT' && bash scripts/setup.sh"
echo "==> Compilando la interfaz"
sudo -u "$OWNER" bash -lc "cd '$ROOT/frontend' && NODE_OPTIONS='--max-old-space-size=1024' npm run build"

NEW_PINS=0
if [ ! -f "$PINS_FILE" ]; then
  echo "==> Sustituyendo los PIN de ejemplo"
  sudo -u "$OWNER" bash -lc "cd '$ROOT/backend' && .venv/bin/python '$ROOT/scripts/rotate_pins.py'" > "$PINS_FILE"
  chmod 600 "$PINS_FILE"
  NEW_PINS=1
fi

echo "==> Servicio systemd"
GROUP="$(id -gn "$OWNER")"
sed -e "s|__USER__|${OWNER}|g" -e "s|__GROUP__|${GROUP}|g" -e "s|__ROOT__|${ROOT}|g" \
  "$ROOT/deploy/gestor-liga.service" > "$UNIT"
systemctl daemon-reload
systemctl enable gestor-liga
systemctl restart gestor-liga

echo "==> Abriendo el puerto 80 en el cortafuegos de la maquina"
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp
else
  if ! iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null; then
    iptables -I INPUT -p tcp --dport 80 -m state --state NEW -j ACCEPT
  fi
  if ! dpkg -s iptables-persistent >/dev/null 2>&1; then
    echo iptables-persistent iptables-persistent/autosave_v4 boolean true | debconf-set-selections
    echo iptables-persistent iptables-persistent/autosave_v6 boolean true | debconf-set-selections
    apt-get install -y iptables-persistent
  fi
  netfilter-persistent save
fi

wait_health() {
  local url="$1"
  local _try
  for _try in 1 2 3 4 5 6 7 8 9 10 11 12; do
    if curl -fsS --max-time 2 "$url" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

if ! wait_health http://127.0.0.1/api/health; then
  echo "==> El puerto 80 no ha respondido. La app pasa al 8000 y el 80 redirige ahi."
  sed -i 's/--port 80/--port 8000/' "$UNIT"
  systemctl daemon-reload
  systemctl restart gestor-liga
  if ! iptables -t nat -C PREROUTING -p tcp --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null; then
    iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-ports 8000
  fi
  if ! iptables -t nat -C OUTPUT -p tcp -o lo --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null; then
    iptables -t nat -A OUTPUT -p tcp -o lo --dport 80 -j REDIRECT --to-ports 8000
  fi
  netfilter-persistent save || true
fi

if ! wait_health http://127.0.0.1/api/health && ! wait_health http://127.0.0.1:8000/api/health; then
  echo "La app no responde. Ultimas lineas del servicio:" >&2
  journalctl -u gestor-liga -n 40 --no-pager >&2 || true
  exit 1
fi

CRON=/etc/cron.d/gestor-liga
cat > "$CRON" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
0 4 * * * ${OWNER} ${ROOT}/scripts/backup-liga.sh >> ${ROOT}/backend/backups/backup.log 2>&1
EOF
chmod 644 "$CRON"
sudo -u "$OWNER" mkdir -p "$ROOT/backend/backups"

IP="$(curl -fsS --max-time 5 -H 'Authorization: Bearer Oracle' http://169.254.169.254/opc/v2/vnics/ 2>/dev/null | python3 -c 'import json,sys
try:
    data=json.load(sys.stdin)
except Exception:
    sys.exit(0)
for nic in data:
    ip=nic.get("publicIp")
    if ip:
        print(ip)
        break
' || true)"
if [ -z "$IP" ]; then
  IP="$(curl -4 -fsS --max-time 5 https://ifconfig.me || true)"
fi

DUCK_NAME="$(grep '^DUCKDNS_DOMAIN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
if [ -n "$DUCK_NAME" ]; then
  bash "$ROOT/scripts/update-dns.sh" || true
fi

echo
echo "Liga en marcha."
if [ -n "$DUCK_NAME" ]; then
  echo "  Direccion:       http://${DUCK_NAME%.duckdns.org}.duckdns.org"
elif [ -n "$IP" ]; then
  echo "  Direccion:       http://${IP}"
else
  echo "  Direccion:       http://<ip-publica-de-la-maquina>"
fi
echo "  Base de datos:   ${ROOT}/backend/liga.db"
echo "  Copias:          ${ROOT}/backend/backups/  (cada dia, a las 04:00)"
echo "  PIN de equipos:  ${PINS_FILE}   (sudo cat para volver a verlos)"
if [ "$NEW_KEYS" -eq 1 ]; then
  echo "  Clave comisario: $(grep '^MASTER_KEY=' "$ENV_FILE" | cut -d= -f2-)"
fi
if [ "$NEW_PINS" -eq 1 ]; then
  echo
  echo "PIN de esta liga (anotalos; cada entrenador usa el suyo):"
  cat "$PINS_FILE"
fi
if [ "$NEW_KEYS" -eq 1 ] || [ "$NEW_PINS" -eq 1 ]; then
  echo
  echo "Estas claves no vuelven a imprimirse. La de comisario esta en ${ENV_FILE}."
fi
if [ -z "$DUCK_NAME" ]; then
  echo
  echo "Para un nombre fijo, en vez de la IP:"
  echo "  sudo bash scripts/update-dns.sh miliga TU_TOKEN"
fi
echo
echo "En la consola de Oracle, la lista de seguridad de la subnet tiene que"
echo "permitir TCP 80 desde 0.0.0.0/0. Sin esa regla el movil no llega."
echo
