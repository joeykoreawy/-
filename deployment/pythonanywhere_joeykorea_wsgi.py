"""Copy into the WSGI configuration file linked from PythonAnywhere's Web tab.

This is for the joeykorea account. Configure the Web virtualenv separately as
/home/joeykorea/jakji/.venv. Private settings are loaded by config.settings.
"""
import os
import sys

project_path = '/home/joeykorea/jakji'
if project_path not in sys.path:
    sys.path.insert(0, project_path)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
