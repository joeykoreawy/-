import secrets
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from market.models import Listing, Profile

class Command(BaseCommand):
    help = 'After offline identity verification, disable and anonymize a member. Back up first.'
    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--confirm', action='store_true')
    def handle(self, username, confirm, **options):
        if not confirm:
            raise CommandError('Back up and verify the requesting member first, then pass --confirm.')
        with transaction.atomic():
            try:
                user = User.objects.select_for_update().get(username=username)
            except User.DoesNotExist:
                raise CommandError('User not found.')
            if user.is_staff or user.is_superuser:
                raise CommandError('Staff accounts require a separate administrator handover.')
            # Remove public content and stop all active matches involving this member.
            for item in Listing.objects.filter(selected_offer__knight=user).exclude(status__in=['completed', 'cancelled']):
                item.status = Listing.Status.CANCELLED
                item.save(update_fields=['status'])
            Listing.objects.filter(owner=user).exclude(status='completed').update(status='cancelled', is_hidden=True)
            Listing.objects.filter(owner=user, status='completed').update(is_hidden=True)
            Profile.objects.filter(user=user).update(nickname='탈퇴회원', contact='', contact_method='')
            user.username = 'deleted_' + secrets.token_hex(12)
            user.email = user.first_name = user.last_name = ''
            user.is_active = False
            user.set_unusable_password()
            user.save()
        self.stdout.write('Member disabled, contacts erased, listings hidden and active matches cancelled.')
