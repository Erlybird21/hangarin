from django import forms

from .models import Note, SubTask, Task


class TaskForm(forms.ModelForm):
    """Form for creating/updating Tasks.

    The `user` (owner) field is deliberately excluded: ownership is always
    assigned in the view from `request.user`, so submitted form data can
    never choose or change the Task owner.
    """

    class Meta:
        model = Task
        fields = ["title", "description", "status", "deadline", "priority", "category"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Enter task title"}),
            "description": forms.Textarea(
                attrs={"placeholder": "Enter task details", "rows": 4}
            ),
            "deadline": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "status": forms.Select(),
            "priority": forms.Select(),
            "category": forms.Select(),
        }


class SubTaskForm(forms.ModelForm):
    """Form for creating/updating SubTasks.

    The `task` (parent) field is deliberately excluded: the parent is always
    taken from the URL's already-ownership-checked Task, so submitted form
    data can never reparent the SubTask to another user's Task.
    """

    class Meta:
        model = SubTask
        fields = ["title", "status"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Enter subtask title"}),
            "status": forms.Select(),
        }


class NoteForm(forms.ModelForm):
    """Form for creating/updating Notes.

    The `task` (parent) field is deliberately excluded: the parent is always
    taken from the URL's already-ownership-checked Task, so submitted form
    data can never reparent the Note to another user's Task.
    """

    class Meta:
        model = Note
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={"placeholder": "Write your note...", "rows": 3}
            ),
        }
