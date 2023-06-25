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
class EventGuestsAdmin(admin.ModelAdmin):
    list_display = ('event', 'guest')
    list_filter = ('event', 'guest')


@admin.register(Friend)
class FriendAdmin(admin.ModelAdmin):
    pass


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    pass


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    pass


class ScheduleInline(admin.TabularInline):
    extra=0
    model = Schedule


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    model = Event
    inlines = [
        ScheduleInline,
    ]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    pass


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    pass
