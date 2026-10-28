from django.contrib import admin

from .models import CboOccupation, FamilyRelationship, Member, MessageOccasion


class FamilyRelationshipInline(admin.TabularInline):
    model = FamilyRelationship
    fk_name = "child"
    extra = 0


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "status",
        "is_placeholder",
        "cbo_occupation",
        "mobile",
        "email",
        "city",
    )
    list_filter = (
        "status",
        "is_placeholder",
        "city",
        "email_consent",
        "whatsapp_consent",
        "whatsapp_daily_consent",
    )
    search_fields = ("first_name", "last_name", "cpf", "email", "mobile")
    inlines = (FamilyRelationshipInline,)
    readonly_fields = (
        "whatsapp_consent_at",
        "whatsapp_revoked_at",
        "whatsapp_daily_consent_at",
        "whatsapp_daily_revoked_at",
    )


@admin.register(CboOccupation)
class CboOccupationAdmin(admin.ModelAdmin):
    list_display = ("code", "title")
    search_fields = ("code", "title")
    ordering = ("title",)


@admin.register(MessageOccasion)
class MessageOccasionAdmin(admin.ModelAdmin):
    list_display = ("name", "day", "month", "active", "whatsapp_template_name")
    list_filter = ("active", "month")
    search_fields = ("name", "ai_guidance", "whatsapp_template_name")
    ordering = ("month", "day", "name")
    fields = (
        "name",
        "day",
        "month",
        "ai_guidance",
        "whatsapp_template_name",
        "active",
    )


admin.site.site_header = "Gestão da Igreja"
admin.site.site_title = "Administração"
admin.site.index_title = "Administração do sistema"
