from django.contrib import admin

from core.models import AIFeedback, Goal, LearningSession, Profile, Resource, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "cohort")
    search_fields = ("user__username", "name", "cohort")
    filter_horizontal = ("focus_areas",)


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("title", "description", "user__username")


@admin.register(LearningSession)
class LearningSessionAdmin(admin.ModelAdmin):
    list_display = ("goal", "date", "duration")
    list_filter = ("date",)
    search_fields = ("goal__title", "notes")
    filter_horizontal = ("tags",)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "goal", "type", "created_at")
    list_filter = ("type",)
    search_fields = ("title", "url", "goal__title")


@admin.register(AIFeedback)
class AIFeedbackAdmin(admin.ModelAdmin):
    list_display = ("goal", "feedback_type", "created_at")
    list_filter = ("feedback_type",)
    search_fields = ("goal__title", "content")
