#!/usr/bin/env bash
# Inicia o servidor no Codespace. Se o segredo DJANGO_SECRET_KEY não existir, gera uma chave temporária
# (as sessões abertas caem a cada reinício, mas o sistema sobe).
cd "$(dirname "$0")/.." || exit 1
if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
  DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
  export DJANGO_SECRET_KEY
  echo "Aviso: DJANGO_SECRET_KEY ausente; usando chave temporária."
fi
pkill -f "manage.py runserver" 2>/dev/null || true
pip install -q -r requirements.txt
python manage.py migrate --noinput
nohup python manage.py runserver 0.0.0.0:8000 --noreload --insecure > /tmp/server.log 2>&1 &
sleep 4
curl -s -o /dev/null -w "Servidor: HTTP %{http_code}\n" http://127.0.0.1:8000/entrar/ || tail -n 30 /tmp/server.log
