from django.contrib import admin

from .models import AssistanceRecord, AssistedFamily


class AssistanceRecordInline(admin.TabularInline):
    model = AssistanceRecord
    extra = 0


@admin.register(AssistedFamily)
class AssistedFamilyAdmin(admin.ModelAdmin):
    list_display = (
        "reference_name",
        "contact_name",
        "phone",
        "neighborhood",
        "city",
        "active",
    )
    list_filter = ("active", "neighborhood")
    search_fields = (
        "reference_name",
        "contact_name",
        "phone",
        "postal_code",
        "street",
        "neighborhood",
        "city",
        "address",
    )
    inlines = (AssistanceRecordInline,)


@admin.register(AssistanceRecord)
class AssistanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "family",
        "aid_type",
        "quantity",
        "assistance_date",
        "status",
        "recorded_by",
    )
    list_filter = ("status", "aid_type", "assistance_date")
    search_fields = ("family__reference_name", "description")
    readonly_fields = ("recorded_by", "delivered_by", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = AssistanceRecord.objects.get(pk=obj.pk).status
        if (
            obj.status == AssistanceRecord.Status.DELIVERED
            and previous_status != AssistanceRecord.Status.DELIVERED
        ):
            obj.delivered_by = request.user
        elif obj.status != AssistanceRecord.Status.DELIVERED:
            obj.delivered_by = None
        super().save_model(request, obj, form, change)
