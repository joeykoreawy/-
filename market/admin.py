from django.contrib import admin
from .models import AuditEvent

@admin.register(AuditEvent)
class AuditAdmin(admin.ModelAdmin):
    list_display = ['actor', 'listing_id_snapshot', 'action', 'created_at']
    readonly_fields = ['actor', 'listing', 'listing_id_snapshot', 'action', 'created_at']
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
# Reports are handled in /operations/reports/ to enforce the moderation audit.
# Contacts and proposals are deliberately not registered for general admin browsing.
