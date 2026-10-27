from django.contrib import admin

from .models import CboOccupation, FamilyRelationship, Member


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
    list_filter = ("status", "is_placeholder", "city", "email_consent", "whatsapp_consent")
    search_fields = ("first_name", "last_name", "cpf", "email", "mobile")
    inlines = (FamilyRelationshipInline,)


@admin.register(CboOccupation)
class CboOccupationAdmin(admin.ModelAdmin):
    list_display = ("code", "title")
    search_fields = ("code", "title")
    ordering = ("title",)


admin.site.site_header = "Gestão da Igreja"
admin.site.site_title = "Administração"
admin.site.index_title = "Administração do sistema"
