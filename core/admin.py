from django.contrib import admin

from core.models import Profile, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "cohort")
    search_fields = ("user__username", "name", "cohort")
    filter_horizontal = ("focus_areas",)
