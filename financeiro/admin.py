from django.contrib import admin

from .models import (
    CardMachine,
    PixKey,
    FinancialAccount,
    FinancialCategory,
    DonationRecord,
    FinancialTransaction,
    FinancialTransactionAudit,
)


@admin.register(FinancialCategory)
class FinancialCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "active")
    list_filter = ("kind", "active")
    search_fields = ("name",)


@admin.register(FinancialAccount)
class FinancialAccountAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "kind",
        "bank_name",
        "branch",
        "masked_account_number",
        "holder_name",
        "active",
    )
    list_filter = ("kind", "active")
    search_fields = ("name", "bank_name", "holder_name", "cnpj")

    @admin.display(description="número da conta")
    def masked_account_number(self, account):
        return account.masked_account_number


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "kind",
        "category",
        "amount",
        "due_on",
        "status",
        "payment_method",
        "account",
    )
    list_filter = ("kind", "status", "category", "payment_method", "account")
    search_fields = ("title", "category__name", "department__name", "event__title")
    readonly_fields = tuple(field.name for field in FinancialTransaction._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FinancialTransactionAudit)
class FinancialTransactionAuditAdmin(admin.ModelAdmin):
    list_display = ("transaction_label", "action", "actor", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("transaction_label", "actor__username")
    readonly_fields = tuple(field.name for field in FinancialTransactionAudit._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DonationRecord)
class DonationRecordAdmin(admin.ModelAdmin):
    list_display = (
        "received_on",
        "donation_type",
        "donor_name",
        "destination",
        "amount",
        "status",
        "recorded_by",
    )
    list_filter = ("donation_type", "destination", "status", "received_on")
    search_fields = ("donor_name", "description", "destination_description")
    readonly_fields = tuple(field.name for field in DonationRecord._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PixKey)
class PixKeyAdmin(admin.ModelAdmin):
    list_display = ('label', 'key_type', 'account', 'is_default', 'active')


@admin.register(CardMachine)
class CardMachineAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'account', 'active')
