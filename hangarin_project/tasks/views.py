from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TaskForm
from .models import Task


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
