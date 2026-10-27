import hashlib
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import RateBucket


def limited(request, action, limit, seconds, identity=None):
    # REMOTE_ADDR only: never trust arbitrary client-supplied forwarding headers.
    # On a shared proxy the IP limit is shared; username/user limits are separate.
    key = hashlib.sha256(f'{action}:{identity or request.META.get("REMOTE_ADDR", "unknown")}'.encode()).hexdigest()
    now = timezone.now()
    with transaction.atomic():
        RateBucket.objects.filter(expires_at__lt=now).delete()
        bucket, _ = RateBucket.objects.select_for_update().get_or_create(key=key, defaults={'expires_at': now + timedelta(seconds=seconds)})
        if bucket.count >= limit:
            return True
        bucket.count += 1
        bucket.save(update_fields=['count'])
    return False
