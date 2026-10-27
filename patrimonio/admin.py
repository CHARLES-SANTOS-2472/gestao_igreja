from django.contrib import admin

from .models import (
    AdministrativeTask,
    AdministrativeTaskAudit,
    AssetMaintenance,
    ChurchAsset,
    Contract,
    Supplier,
)


class AssetMaintenanceInline(admin.TabularInline):
    model = AssetMaintenance
    extra = 0


@admin.register(ChurchAsset)
class ChurchAssetAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "asset_tag", "location", "status")
    list_filter = ("category", "status")
    search_fields = ("name", "asset_tag", "serial_number", "location")
    inlines = (AssetMaintenanceInline,)


@admin.register(AssetMaintenance)
class AssetMaintenanceAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "maintenance_date",
        "performed_by",
        "cost",
        "next_maintenance_on",
    )
    list_filter = ("maintenance_date", "next_maintenance_on")
    search_fields = ("asset__name", "description", "performed_by")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "cnpj", "contact_name", "phone", "active")
    list_filter = ("active",)
    search_fields = ("name", "cnpj", "contact_name", "email")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("title", "supplier", "start_date", "end_date", "value", "status")
    list_filter = ("status", "end_date", "supplier")
    search_fields = ("title", "contract_number", "supplier__name")


@admin.register(AdministrativeTask)
class AdministrativeTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "priority", "due_date", "assigned_to")
    list_filter = ("status", "priority", "due_date")
    search_fields = ("title", "description", "assigned_to__username")


@admin.register(AdministrativeTaskAudit)
class AdministrativeTaskAuditAdmin(admin.ModelAdmin):
    list_display = ("task_title", "action", "actor", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("task_title", "actor__username")
    readonly_fields = tuple(
        field.name for field in AdministrativeTaskAudit._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
