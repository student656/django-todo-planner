from django.contrib import admin

from .models import DayItem, ShopItem, Task, WaitItem


@admin.register(DayItem)
class DayItemAdmin(admin.ModelAdmin):
    list_display = ("date", "text", "done", "user")
    list_filter = ("done", "date")
    search_fields = ("text",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("text", "category", "done", "user")
    list_filter = ("category", "done")
    search_fields = ("text",)


@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    list_display = ("text", "category", "done", "user")
    list_filter = ("category", "done")
    search_fields = ("text",)


@admin.register(WaitItem)
class WaitItemAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "status", "user")
    list_filter = ("status",)
    search_fields = ("title", "notes")
