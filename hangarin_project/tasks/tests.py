from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Category, Note, Priority, SubTask, Task


class TaskOwnershipTests(TestCase):
    """Phase 1 foundation: Task is the ownership root.

    SubTask and Note carry no `user` field of their own; their owner is
    always derived via the parent Task (User -> Task -> SubTask / Note).
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user(username="alice", password="x")
        cls.bob = User.objects.create_user(username="bob", password="x")
        cls.priority = Priority.objects.create(name="high")
        cls.category = Category.objects.create(name="Work")

    def make_task(self, user, title="Sample task"):
        return Task.objects.create(
            user=user,
            title=title,
            description="desc",
            status="Pending",
            deadline=timezone.now(),
            priority=self.priority,
            category=self.category,
        )

    def test_task_belongs_to_user(self):
        task = self.make_task(self.alice)
        self.assertEqual(task.user, self.alice)
        self.assertIn(task, self.alice.tasks.all())

    def test_users_tasks_are_distinguished(self):
        alice_task = self.make_task(self.alice, title="Alice task")
        bob_task = self.make_task(self.bob, title="Bob task")
        self.assertQuerySetEqual(
            Task.objects.filter(user=self.alice), [alice_task]
        )
        self.assertQuerySetEqual(
            Task.objects.filter(user=self.bob), [bob_task]
        )

    def test_subtask_belongs_to_task(self):
        task = self.make_task(self.alice)
        subtask = SubTask.objects.create(
            task=task, title="Step 1", status="Pending"
        )
        self.assertEqual(subtask.task, task)
        self.assertEqual(subtask.task.user, self.alice)
        self.assertIn(subtask, task.subtask_set.all())

    def test_note_belongs_to_task(self):
        task = self.make_task(self.alice)
        note = Note.objects.create(task=task, content="Remember this")
        self.assertEqual(note.task, task)
        self.assertEqual(note.task.user, self.alice)
        self.assertIn(note, task.note_set.all())
