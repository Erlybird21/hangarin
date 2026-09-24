from django import forms

from .models import Task


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
