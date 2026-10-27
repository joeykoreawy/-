from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import BaseCommand, CommandError, call_command
from market.models import Listing

class Command(BaseCommand):
    help = 'Check production prerequisites without printing credentials or contact values.'
    def handle(self, **options):
        problems = []
        if settings.DEBUG:
            problems.append('DJANGO_DEBUG must be 0.')
        if not settings.HTTPS:
            problems.append('DJANGO_HTTPS must be 1.')
        if not settings.ALLOWED_HOSTS or any(x in ['*', 'localhost', '127.0.0.1', '[::1]'] for x in settings.ALLOWED_HOSTS):
            problems.append('Set DJANGO_ALLOWED_HOSTS to the exact public hostname only.')
        for host in settings.ALLOWED_HOSTS:
            if f'https://{host}' not in settings.CSRF_TRUSTED_ORIGINS:
                problems.append('Set DJANGO_CSRF_TRUSTED_ORIGINS to the exact HTTPS origin.')
        if not settings.OPERATOR_CONTACT.strip():
            problems.append('Set OPERATOR_CONTACT to a public support email or open-chat URL.')
        if not User.objects.filter(is_superuser=True, is_active=True).exists():
            problems.append('Create a private superuser with manage.py createsuperuser.')
        # Confirm migrations and database access as part of the check.
        call_command('migrate', check=True, verbosity=0)
        Listing.objects.exists()
        if problems:
            raise CommandError('\n'.join(problems))
        call_command('check', deploy=True, fail_level='WARNING')
        self.stdout.write(self.style.SUCCESS('Public deployment configuration checks passed. Verify the external HTTPS URL after reload.'))
