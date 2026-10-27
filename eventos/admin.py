from django.contrib import admin

from .models import (
    ChurchEvent,
    ChurchSpace,
    EventAssignment,
    EventProgramItem,
    EventRegistration,
    SpaceReservation,
)


class EventProgramItemInline(admin.TabularInline):
    model = EventProgramItem
    extra = 0


class EventAssignmentInline(admin.TabularInline):
    model = EventAssignment
    extra = 0


class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0


@admin.register(ChurchEvent)
class ChurchEventAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "starts_at", "ends_at", "status", "location")
    list_filter = ("kind", "status", "registration_open")
    search_fields = ("title", "location", "description")
    inlines = (EventProgramItemInline, EventAssignmentInline, EventRegistrationInline)


@admin.register(ChurchSpace)
class ChurchSpaceAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "capacity", "active")
    list_filter = ("kind", "active")
    search_fields = ("name",)


@admin.register(SpaceReservation)
class SpaceReservationAdmin(admin.ModelAdmin):
    list_display = ("space", "purpose", "starts_at", "ends_at", "status", "event")
    list_filter = ("status", "space__kind")
    search_fields = ("space__name", "purpose", "event__title")
