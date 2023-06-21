from django.contrib import admin

from .models import (
    Guest,
    Event,
    Schedule,
    Question,
    Donation,
    Friend,
    EventGuests,
)


@admin.register(EventGuests)
class ClientAdmin(admin.ModelAdmin):
    pass


@admin.register(Friend)
class ClientAdmin(admin.ModelAdmin):
    pass


@admin.register(Guest)
class ClientAdmin(admin.ModelAdmin):
    pass


@admin.register(Schedule)
class ClientAdmin(admin.ModelAdmin):
    pass


class ScheduleInline(admin.TabularInline):
    model = Schedule


@admin.register(Event)
class ClientAdmin(admin.ModelAdmin):
    model = Event
    inlines = [
        ScheduleInline,
    ]


@admin.register(Question)
class ClientAdmin(admin.ModelAdmin):
    pass


@admin.register(Donation)
class ClientAdmin(admin.ModelAdmin):
    pass
