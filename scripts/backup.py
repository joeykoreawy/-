"""Run with .venv/bin/python scripts/backup.py. Never place backups in static/."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.conf import settings
os.umask(0o077)
backup_dir = settings.DATA_DIR / 'backups'
backup_dir.mkdir(parents=True, exist_ok=True)
dest = backup_dir / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
with sqlite3.connect(settings.DATABASES['default']['NAME']) as source, sqlite3.connect(dest) as target:
    source.backup(target)
print('Backup saved:', dest)
# Keep no more than seven recent snapshots. Run regularly and download encrypted
# copies to a trusted location if you need disaster recovery outside this host.
for old in sorted(backup_dir.glob('*.sqlite3'), reverse=True)[7:]:
    old.unlink()
