from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
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


class AccountTests(TestCase):
    """Phase 2: django-allauth registration, login, logout, password reset.

    Google OAuth is configuration-only here (no real credentials, no
    external requests); these tests verify the provider is registered and
    its login URL resolves.
    """

    def test_auth_urls_resolve(self):
        for name in (
            "account_login",
            "account_logout",
            "account_signup",
            "account_reset_password",
            "google_login",
        ):
            self.assertTrue(reverse(name), name)

    def test_signup_creates_user(self):
        response = self.client.post(
            reverse("account_signup"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "s3cure-pass-phrase",
                "password2": "s3cure-pass-phrase",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username="newuser")
        self.assertEqual(user.email, "newuser@example.com")

    def test_login_and_logout(self):
        get_user_model().objects.create_user(username="cara", password="s3cret-pw")
        response = self.client.post(
            reverse("account_login"),
            {"login": "cara", "password": "s3cret-pw"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)
        response = self.client.post(reverse("account_logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_reset_sends_email(self):
        get_user_model().objects.create_user(
            username="dave", email="dave@example.com", password="s3cret-pw"
        )
        response = self.client.post(
            reverse("account_reset_password"), {"email": "dave@example.com"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("dave@example.com", mail.outbox[0].to)

    def test_auth_backends_and_middleware_configured(self):
        self.assertIn(
            "django.contrib.auth.backends.ModelBackend",
            settings.AUTHENTICATION_BACKENDS,
        )
        self.assertIn(
            "allauth.account.auth_backends.AuthenticationBackend",
            settings.AUTHENTICATION_BACKENDS,
        )
        self.assertIn(
            "allauth.account.middleware.AccountMiddleware", settings.MIDDLEWARE
        )

    def test_google_provider_configured_without_committed_secrets(self):
        providers = settings.SOCIALACCOUNT_PROVIDERS
        self.assertIn("google", providers)
        app = providers["google"]["APP"]
        # Credentials must come from the environment; defaults are empty so
        # nothing secret can leak into the repository.
        import os

        self.assertEqual(
            app["client_id"], os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
        )
        self.assertEqual(
            app["secret"], os.environ.get("GOOGLE_OAUTH_SECRET", "")
        )


class TaskCRUDTests(TestCase):
    """Phase 3 milestone 1: Task CRUD with ownership enforcement."""

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

    def task_form_data(self, **overrides):
        data = {
            "title": "Form task",
            "description": "from form",
            "status": "Pending",
            "deadline": "2030-01-01 12:00",
            "priority": self.priority.pk,
            "category": self.category.pk,
        }
        data.update(overrides)
        return data

    def test_list_shows_only_own_tasks(self):
        self.make_task(self.alice, title="Alice task")
        self.make_task(self.bob, title="Bob task")
        self.client.force_login(self.alice)
        response = self.client.get(reverse("task_list"))
        self.assertEqual(response.status_code, 200)
        titles = [t.title for t in response.context["tasks"]]
        self.assertIn("Alice task", titles)
        self.assertNotIn("Bob task", titles)

    def test_other_user_task_detail_404(self):
        task = self.make_task(self.alice)
        self.client.force_login(self.bob)
        response = self.client.get(reverse("task_detail", args=[task.pk]))
        self.assertEqual(response.status_code, 404)

    def test_other_user_task_update_404(self):
        task = self.make_task(self.alice)
        self.client.force_login(self.bob)
        url = reverse("task_update", args=[task.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        response = self.client.post(url, self.task_form_data(title="Hijacked"))
        self.assertEqual(response.status_code, 404)
        task.refresh_from_db()
        self.assertEqual(task.title, "Sample task")

    def test_other_user_task_delete_404(self):
        task = self.make_task(self.alice)
        self.client.force_login(self.bob)
        url = reverse("task_delete", args=[task.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_create_assigns_logged_in_user(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("task_create"), self.task_form_data()
        )
        self.assertEqual(response.status_code, 302)
        task = Task.objects.get(title="Form task")
        self.assertEqual(task.user, self.alice)

    def test_form_excludes_user_field(self):
        from .forms import TaskForm

        self.assertNotIn("user", TaskForm.Meta.fields)
        # A forged owner in POST data must be ignored.
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("task_create"),
            self.task_form_data(user=self.alice.pk),
        )
        self.assertEqual(response.status_code, 302)
        task = Task.objects.get(title="Form task")
        self.assertEqual(task.user, self.bob)

    def test_owner_full_crud_cycle(self):
        self.client.force_login(self.alice)
        # Create
        self.client.post(reverse("task_create"), self.task_form_data())
        task = Task.objects.get(title="Form task")
        # Detail
        self.assertEqual(
            self.client.get(reverse("task_detail", args=[task.pk])).status_code,
            200,
        )
        # Update
        response = self.client.post(
            reverse("task_update", args=[task.pk]),
            self.task_form_data(title="Renamed"),
        )
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, "Renamed")
        self.assertEqual(task.user, self.alice)
        # Delete
        response = self.client.post(reverse("task_delete", args=[task.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_unauthenticated_users_redirected_to_login(self):
        task = self.make_task(self.alice)
        urls = [
            reverse("task_list"),
            reverse("task_create"),
            reverse("task_detail", args=[task.pk]),
            reverse("task_update", args=[task.pk]),
            reverse("task_delete", args=[task.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response["Location"])


class SubTaskCRUDTests(TestCase):
    """Phase 3 milestone 3: SubTask CRUD, ownership via parent Task."""

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

    def test_owner_can_list_create_update_delete(self):
        task = self.make_task(self.alice)
        self.client.force_login(self.alice)
        # List (empty)
        response = self.client.get(reverse("subtask_list", args=[task.pk]))
        self.assertEqual(response.status_code, 200)
        # Create
        response = self.client.post(
            reverse("subtask_create", args=[task.pk]),
            {"title": "Step 1", "status": "Pending"},
        )
        self.assertEqual(response.status_code, 302)
        sub = SubTask.objects.get(title="Step 1")
        self.assertEqual(sub.task, task)
        # List shows it
        response = self.client.get(reverse("subtask_list", args=[task.pk]))
        self.assertContains(response, "Step 1")
        # Update
        response = self.client.post(
            reverse("subtask_update", args=[task.pk, sub.pk]),
            {"title": "Step 1 done", "status": "Completed"},
        )
        self.assertEqual(response.status_code, 302)
        sub.refresh_from_db()
        self.assertEqual(sub.title, "Step 1 done")
        self.assertEqual(sub.task, task)
        # Delete
        response = self.client.post(
            reverse("subtask_delete", args=[task.pk, sub.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SubTask.objects.filter(pk=sub.pk).exists())

    def test_other_user_task_returns_404(self):
        task = self.make_task(self.alice)
        self.client.force_login(self.bob)
        for url in [
            reverse("subtask_list", args=[task.pk]),
            reverse("subtask_create", args=[task.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_other_user_subtask_returns_404(self):
        alice_task = self.make_task(self.alice)
        sub = SubTask.objects.create(
            task=alice_task, title="Alice step", status="Pending"
        )
        bob_task = self.make_task(self.bob)
        self.client.force_login(self.bob)
        # Bob's own task + Alice's subtask ID -> 404 (child not under parent)
        for url in [
            reverse("subtask_update", args=[bob_task.pk, sub.pk]),
            reverse("subtask_delete", args=[bob_task.pk, sub.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(
                    self.client.post(
                        url, {"title": "Hijacked", "status": "Completed"}
                    ).status_code,
                    404,
                )
        sub.refresh_from_db()
        self.assertEqual(sub.title, "Alice step")
        self.assertEqual(sub.task, alice_task)

    def test_wrong_child_under_owned_task_returns_404(self):
        task_a = self.make_task(self.alice, title="Task A")
        task_b = self.make_task(self.alice, title="Task B")
        sub = SubTask.objects.create(
            task=task_a, title="Step A", status="Pending"
        )
        self.client.force_login(self.alice)
        url = reverse("subtask_update", args=[task_b.pk, sub.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_forged_task_in_post_is_ignored(self):
        from .forms import SubTaskForm

        self.assertNotIn("task", SubTaskForm.Meta.fields)
        alice_task = self.make_task(self.alice)
        bob_task = self.make_task(self.bob)
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("subtask_create", args=[alice_task.pk]),
            {"title": "Forged", "status": "Pending", "task": bob_task.pk},
        )
        self.assertEqual(response.status_code, 302)
        sub = SubTask.objects.get(title="Forged")
        self.assertEqual(sub.task, alice_task)

    def test_unauthenticated_users_redirected_to_login(self):
        task = self.make_task(self.alice)
        sub = SubTask.objects.create(
            task=task, title="Step", status="Pending"
        )
        urls = [
            reverse("subtask_list", args=[task.pk]),
            reverse("subtask_create", args=[task.pk]),
            reverse("subtask_update", args=[task.pk, sub.pk]),
            reverse("subtask_delete", args=[task.pk, sub.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response["Location"])


class NoteCRUDTests(TestCase):
    """Phase 3 milestone 3: Note CRUD, ownership via parent Task."""

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

    def test_owner_can_list_create_update_delete(self):
        task = self.make_task(self.alice)
        self.client.force_login(self.alice)
        response = self.client.get(reverse("note_list", args=[task.pk]))
        self.assertEqual(response.status_code, 200)
        # Create
        response = self.client.post(
            reverse("note_create", args=[task.pk]),
            {"content": "Remember this"},
        )
        self.assertEqual(response.status_code, 302)
        note = Note.objects.get(content="Remember this")
        self.assertEqual(note.task, task)
        # List shows it
        response = self.client.get(reverse("note_list", args=[task.pk]))
        self.assertContains(response, "Remember this")
        # Update
        response = self.client.post(
            reverse("note_update", args=[task.pk, note.pk]),
            {"content": "Updated reminder"},
        )
        self.assertEqual(response.status_code, 302)
        note.refresh_from_db()
        self.assertEqual(note.content, "Updated reminder")
        self.assertEqual(note.task, task)
        # Delete
        response = self.client.post(
            reverse("note_delete", args=[task.pk, note.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Note.objects.filter(pk=note.pk).exists())

    def test_other_user_task_returns_404(self):
        task = self.make_task(self.alice)
        self.client.force_login(self.bob)
        for url in [
            reverse("note_list", args=[task.pk]),
            reverse("note_create", args=[task.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_other_user_note_returns_404(self):
        alice_task = self.make_task(self.alice)
        note = Note.objects.create(task=alice_task, content="Alice secret")
        bob_task = self.make_task(self.bob)
        self.client.force_login(self.bob)
        for url in [
            reverse("note_update", args=[bob_task.pk, note.pk]),
            reverse("note_delete", args=[bob_task.pk, note.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(
                    self.client.post(url, {"content": "Hijacked"}).status_code,
                    404,
                )
        note.refresh_from_db()
        self.assertEqual(note.content, "Alice secret")
        self.assertEqual(note.task, alice_task)

    def test_wrong_child_under_owned_task_returns_404(self):
        task_a = self.make_task(self.alice, title="Task A")
        task_b = self.make_task(self.alice, title="Task B")
        note = Note.objects.create(task=task_a, content="Note A")
        self.client.force_login(self.alice)
        url = reverse("note_update", args=[task_b.pk, note.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_forged_task_in_post_is_ignored(self):
        from .forms import NoteForm

        self.assertNotIn("task", NoteForm.Meta.fields)
        alice_task = self.make_task(self.alice)
        bob_task = self.make_task(self.bob)
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("note_create", args=[alice_task.pk]),
            {"content": "Forged note", "task": bob_task.pk},
        )
        self.assertEqual(response.status_code, 302)
        note = Note.objects.get(content="Forged note")
        self.assertEqual(note.task, alice_task)

    def test_unauthenticated_users_redirected_to_login(self):
        task = self.make_task(self.alice)
        note = Note.objects.create(task=task, content="Note")
        urls = [
            reverse("note_list", args=[task.pk]),
            reverse("note_create", args=[task.pk]),
            reverse("note_update", args=[task.pk, note.pk]),
            reverse("note_delete", args=[task.pk, note.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response["Location"])
