# Generated for Phase 1: Task ownership foundation.
#
# NOTE: The `user` field is added WITHOUT a default. This applies cleanly to
# an empty database (current local state: no db.sqlite3 exists). If this
# migration is ever applied to a database that already contains Task rows
# created before the `user` field existed (e.g. a legacy production copy),
# the database will reject it until those orphan rows are assigned an owner
# or removed. Do not add a hardcoded default user PK here.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tasks",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="category",
            name="name",
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.AlterField(
            model_name="priority",
            name="name",
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.AlterField(
            model_name="subtask",
            name="status",
            field=models.CharField(
                choices=[
                    ("Pending", "Pending"),
                    ("In Progress", "In Progress"),
                    ("Completed", "Completed"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="task",
            name="status",
            field=models.CharField(
                choices=[
                    ("Pending", "Pending"),
                    ("In Progress", "In Progress"),
                    ("Completed", "Completed"),
                ],
                max_length=20,
            ),
        ),
    ]
