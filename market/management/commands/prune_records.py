from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from market.models import AuditEvent, RateBucket, Report

class Command(BaseCommand):
    help = 'Delete resolved reports after 90 days, audit logs after 180 days, and expired rate buckets.'
    def handle(self, **options):
        now = timezone.now()
        reports = Report.objects.exclude(status='open').filter(handled_at__lt=now-timedelta(days=90)).delete()[0]
        audits = AuditEvent.objects.filter(created_at__lt=now-timedelta(days=180)).delete()[0]
        buckets = RateBucket.objects.filter(expires_at__lt=now).delete()[0]
        self.stdout.write(f'Pruned: reports={reports}, audit={audits}, rate buckets={buckets}')
