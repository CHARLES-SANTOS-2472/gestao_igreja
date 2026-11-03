from django.contrib import admin

from .models import MessageLog


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "member", "kind", "channel", "status", "reference_date")
    list_filter = ("status", "kind", "channel", "reference_date")
    search_fields = ("member__first_name", "member__last_name", "text")
    readonly_fields = [field.name for field in MessageLog._meta.fields]

    def has_add_permission(self, request):
        return False
