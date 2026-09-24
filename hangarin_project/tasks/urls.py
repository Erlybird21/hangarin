from django.urls import path

from . import views

urlpatterns = [
    path("", views.task_list, name="task_list"),
    path("create/", views.task_create, name="task_create"),
    path("<int:pk>/", views.task_detail, name="task_detail"),
    path("<int:pk>/edit/", views.task_update, name="task_update"),
    path("<int:pk>/delete/", views.task_delete, name="task_delete"),
    path("<int:task_pk>/subtasks/", views.subtask_list, name="subtask_list"),
    path(
        "<int:task_pk>/subtasks/create/",
        views.subtask_create,
        name="subtask_create",
    ),
    path(
        "<int:task_pk>/subtasks/<int:pk>/edit/",
        views.subtask_update,
        name="subtask_update",
    ),
    path(
        "<int:task_pk>/subtasks/<int:pk>/delete/",
        views.subtask_delete,
        name="subtask_delete",
    ),
    path("<int:task_pk>/notes/", views.note_list, name="note_list"),
    path(
        "<int:task_pk>/notes/create/", views.note_create, name="note_create"
    ),
    path(
        "<int:task_pk>/notes/<int:pk>/edit/",
        views.note_update,
        name="note_update",
    ),
    path(
        "<int:task_pk>/notes/<int:pk>/delete/",
        views.note_delete,
        name="note_delete",
    ),
]
