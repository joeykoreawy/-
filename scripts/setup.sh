#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
python_bin="${PYTHON_BIN:-python3}"
if [ ! -x .venv/bin/python ]; then
  "$python_bin" -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
mkdir -p .local
if [ ! -e .local/environment ]; then
  .venv/bin/python - <<'PY'
import os, secrets
from pathlib import Path
host = os.environ.get('WEBSITE_HOST', 'localhost,127.0.0.1,[::1]')
production = bool(os.environ.get('WEBSITE_HOST'))
with Path('.local/environment').open('x') as f:
    f.write('DJANGO_SECRET_KEY=' + secrets.token_urlsafe(64) + '\n')
    f.write('DJANGO_DEBUG=0\nDJANGO_ALLOWED_HOSTS=' + host + '\n')
    f.write('DJANGO_HTTPS=' + ('1' if production else '0') + '\n')
    if production:
        f.write('DJANGO_CSRF_TRUSTED_ORIGINS=https://' + host + '\n')
        f.write('OPERATOR_CONTACT=' + os.environ.get('OPERATOR_CONTACT', '') + '\n')
PY
fi
chmod 600 .local/environment
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput --verbosity 0
.venv/bin/python manage.py check
