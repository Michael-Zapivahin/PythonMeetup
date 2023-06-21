from django.contrib import admin
from adminsortable2.admin import SortableInlineAdminMixin
from adminsortable2.admin import SortableAdminBase

from .models import (
    Guest,
    Event,
    Schedule,
    Question,
    Donation
)


class ScheduleInline(SortableInlineAdminMixin, admin.TabularInline):
    model = Schedule


@admin.register(Schedule)
class ClientAdmin(admin.ModelAdmin):
    pass


@admin.register(Guest)
class ClientAdmin(admin.ModelAdmin):
    pass


@admin.register(Event)
class ClientAdmin(SortableAdminBase, admin.ModelAdmin):
    pass
    # inlines = [
    #     ScheduleInline,
    # ]


@admin.register(Question)
class ClientAdmin(admin.ModelAdmin):
    pass


@admin.register(Donation)
class ClientAdmin(admin.ModelAdmin):
    pass
