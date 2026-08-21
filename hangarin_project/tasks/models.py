from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Priority(BaseModel):
    name = models.CharField(max_length=50)

    class Meta:
        verbose_name_plural = "Priorities"

    def __str__(self):
        return self.name


class Category(BaseModel):
    name = models.CharField(max_length=50)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Task(BaseModel):
    title = models.CharField(max_length=250)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=[
        ("Pending", "Pending"),
        ("In Progress ", "In Progress"),
        ("Completed", "Completed"),
    ])
    deadline = models.DateTimeField()
    priority = models.ForeignKey(Priority, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    def __str__(self):
        return self.title


class SubTask(BaseModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    title = models.CharField(max_length=250)
    status = models.CharField(max_length=20, choices=[
        ("Pending", "Pending"),
        ("In Progress ", "In Progress"),
        ("Completed", "Completed"),
    ])

    def __str__(self):
        return self.title


class Note(BaseModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    content = models.TextField()

    def __str__(self):
        return f"Note for {self.task.title}"
