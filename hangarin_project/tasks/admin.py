from django.contrib import admin

from .models import Priority, Category, Task, SubTask, Note


@admin.register(Priority)
class PriorityAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)
    list_filter = ("created_at",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)
    list_filter = ("created_at",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "priority", "category", "deadline", "created_at")
    search_fields = ("title", "description")
    list_filter = ("status", "priority", "category", "user")


@admin.register(SubTask)
class SubTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "task", "status", "created_at")
    search_fields = ("title",)
    list_filter = ("status",)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("task", "content", "created_at")
    search_fields = ("content",)
    list_filter = ("created_at",)
