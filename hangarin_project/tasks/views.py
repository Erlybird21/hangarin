from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import NoteForm, SubTaskForm, TaskForm
from .models import Note, SubTask, Task


@login_required
def dashboard(request):
    """Authenticated overview of the current user's own Tasks.

    Every metric is scoped to ``request.user``: Tasks via
    ``Task.objects.filter(user=request.user)`` and SubTasks via
    ``SubTask.objects.filter(task__user=request.user)``. Category and
    Priority are global objects, so their counts are derived by
    aggregating the user's Tasks — never by counting global usage.
    """
    tasks = Task.objects.filter(user=request.user)
    context = {
        "total_tasks": tasks.count(),
        "completed_tasks": tasks.filter(status="Completed").count(),
        "pending_tasks": tasks.filter(status="Pending").count(),
        "in_progress_tasks": tasks.filter(status="In Progress").count(),
        "overdue_tasks": tasks.filter(deadline__lt=timezone.now())
        .exclude(status="Completed")
        .count(),
        "tasks_by_priority": tasks.values("priority__name").annotate(
            count=Count("priority")
        ),
        "tasks_by_category": tasks.values("category__name").annotate(
            count=Count("category")
        ),
        "incomplete_subtasks": SubTask.objects.filter(
            task__user=request.user, status__in=["Pending", "In Progress"]
        ).count(),
        "completed_subtasks": SubTask.objects.filter(
            task__user=request.user, status="Completed"
        ).count(),
        "recent_tasks": tasks.order_by("-created_at")[:5],
    }
    return render(request, "tasks/dashboard.html", context)


def _owned_task_or_404(request, pk):
    """Return the Task owned by the current user, or 404.

    The ownership filter is applied BEFORE the pk lookup, so guessing
    another user's Task ID never exposes their data — it simply 404s.
    """
    return get_object_or_404(Task.objects.filter(user=request.user), pk=pk)


@login_required
def task_list(request):
    tasks = Task.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "tasks/task_list.html", {"tasks": tasks})


@login_required
def task_detail(request, pk):
    task = _owned_task_or_404(request, pk)
    return render(request, "tasks/task_detail.html", {"task": task})


@login_required
def task_create(request):
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            return redirect("task_detail", pk=task.pk)
    else:
        form = TaskForm()
    return render(request, "tasks/task_form.html", {"form": form})


@login_required
def task_update(request, pk):
    task = _owned_task_or_404(request, pk)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            updated = form.save(commit=False)
            # Ownership can never change through the form: re-assert it.
            updated.user = request.user
            updated.save()
            return redirect("task_detail", pk=task.pk)
    else:
        form = TaskForm(instance=task)
    return render(request, "tasks/task_form.html", {"form": form, "task": task})


@login_required
def task_delete(request, pk):
    task = _owned_task_or_404(request, pk)
    if request.method == "POST":
        task.delete()
        return redirect("task_list")
    return render(request, "tasks/task_confirm_delete.html", {"task": task})


def _owned_subtask_or_404(request, task_pk, pk):
    """Return the SubTask of the user's owned Task, or 404.

    Both the parent ownership AND the child-parent relationship are
    verified: a child ID belonging to a different Task never resolves,
    even under a Task the user does own.
    """
    owned_task = _owned_task_or_404(request, task_pk)
    return get_object_or_404(SubTask, task=owned_task, pk=pk)


def _owned_note_or_404(request, task_pk, pk):
    """Return the Note of the user's owned Task, or 404."""
    owned_task = _owned_task_or_404(request, task_pk)
    return get_object_or_404(Note, task=owned_task, pk=pk)


@login_required
def subtask_list(request, task_pk):
    owned_task = _owned_task_or_404(request, task_pk)
    subtasks = owned_task.subtask_set.all().order_by("-created_at")
    return render(
        request,
        "tasks/subtask_list.html",
        {"task": owned_task, "subtasks": subtasks},
    )


@login_required
def subtask_create(request, task_pk):
    owned_task = _owned_task_or_404(request, task_pk)
    if request.method == "POST":
        form = SubTaskForm(request.POST)
        if form.is_valid():
            subtask = form.save(commit=False)
            subtask.task = owned_task
            subtask.save()
            return redirect("subtask_list", task_pk=task_pk)
    else:
        form = SubTaskForm()
    return render(
        request, "tasks/subtask_form.html", {"form": form, "task": owned_task}
    )


@login_required
def subtask_update(request, task_pk, pk):
    subtask = _owned_subtask_or_404(request, task_pk, pk)
    owned_task = subtask.task
    if request.method == "POST":
        form = SubTaskForm(request.POST, instance=subtask)
        if form.is_valid():
            updated = form.save(commit=False)
            # The parent can never change through the form: re-assert it.
            updated.task = owned_task
            updated.save()
            return redirect("subtask_list", task_pk=task_pk)
    else:
        form = SubTaskForm(instance=subtask)
    return render(
        request,
        "tasks/subtask_form.html",
        {"form": form, "task": owned_task, "subtask": subtask},
    )


@login_required
def subtask_delete(request, task_pk, pk):
    subtask = _owned_subtask_or_404(request, task_pk, pk)
    owned_task = subtask.task
    if request.method == "POST":
        subtask.delete()
        return redirect("subtask_list", task_pk=task_pk)
    return render(
        request,
        "tasks/subtask_delete.html",
        {"task": owned_task, "subtask": subtask},
    )


@login_required
def note_list(request, task_pk):
    owned_task = _owned_task_or_404(request, task_pk)
    notes = owned_task.note_set.all().order_by("-created_at")
    return render(
        request, "tasks/note_list.html", {"task": owned_task, "notes": notes}
    )


@login_required
def note_create(request, task_pk):
    owned_task = _owned_task_or_404(request, task_pk)
    if request.method == "POST":
        form = NoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.task = owned_task
            note.save()
            return redirect("note_list", task_pk=task_pk)
    else:
        form = NoteForm()
    return render(
        request, "tasks/note_form.html", {"form": form, "task": owned_task}
    )


@login_required
def note_update(request, task_pk, pk):
    note = _owned_note_or_404(request, task_pk, pk)
    owned_task = note.task
    if request.method == "POST":
        form = NoteForm(request.POST, instance=note)
        if form.is_valid():
            updated = form.save(commit=False)
            # The parent can never change through the form: re-assert it.
            updated.task = owned_task
            updated.save()
            return redirect("note_list", task_pk=task_pk)
    else:
        form = NoteForm(instance=note)
    return render(
        request,
        "tasks/note_form.html",
        {"form": form, "task": owned_task, "note": note},
    )


@login_required
def note_delete(request, task_pk, pk):
    note = _owned_note_or_404(request, task_pk, pk)
    owned_task = note.task
    if request.method == "POST":
        note.delete()
        return redirect("note_list", task_pk=task_pk)
    return render(
        request, "tasks/note_delete.html", {"task": owned_task, "note": note}
    )
