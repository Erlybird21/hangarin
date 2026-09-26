from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

import importlib
import os
from datetime import timedelta
from unittest.mock import patch

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


class LoginPageTests(TestCase):
    """Login page layout: social buttons, Remember Me, no duplicate links.

    GitHub is configuration-only here (no real credentials, no external
    requests); these tests verify the provider is registered, its login
    URL resolves, and the button links to the real allauth route.
    """

    def test_login_page_loads_for_logged_out_users(self):
        response = self.client.get(reverse("account_login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/login.html")

    def test_google_social_login_button_exists(self):
        response = self.client.get(reverse("account_login"))
        self.assertContains(response, "Continue with Google")
        self.assertContains(response, reverse("google_login"))

    def test_github_login_url_resolves_through_allauth(self):
        self.assertTrue(reverse("github_login"))

    def test_github_social_login_button_links_to_allauth_route(self):
        response = self.client.get(reverse("account_login"))
        self.assertContains(response, "Continue with GitHub")
        self.assertContains(response, reverse("github_login"))

    def test_remember_me_uses_actual_allauth_field(self):
        response = self.client.get(reverse("account_login"))
        # Bound allauth field: same name/id allauth posts back as.
        self.assertContains(response, 'name="remember"')
        self.assertContains(response, 'id="id_remember"')
        self.assertContains(response, "Remember Me")
        # Checkbox and label grouped in one aligned control.
        self.assertContains(response, "remember-me")

    def test_login_button_exists(self):
        response = self.client.get(reverse("account_login"))
        self.assertContains(response, 'type="submit"')
        self.assertContains(response, ">Login</button>")

    def test_username_and_password_fields_present(self):
        response = self.client.get(reverse("account_login"))
        self.assertContains(response, 'name="login"')
        self.assertContains(response, 'name="password"')

    def test_password_reset_link_not_duplicated(self):
        response = self.client.get(reverse("account_login"))
        content = response.content.decode()
        self.assertEqual(
            content.count(reverse("account_reset_password")),
            1,
            "password-reset link must appear exactly once",
        )

    def test_github_provider_configured_without_committed_secrets(self):
        providers = settings.SOCIALACCOUNT_PROVIDERS
        self.assertIn("github", providers)
        app = providers["github"]["APP"]
        # Credentials must come from the environment; defaults are empty so
        # nothing secret can leak into the repository.
        import os

        self.assertEqual(
            app["client_id"], os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
        )
        self.assertEqual(
            app["secret"], os.environ.get("GITHUB_OAUTH_SECRET", "")
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


class DashboardTests(TestCase):
    """Phase 4: dashboard metrics, scoped to the current user."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user(username="alice", password="x")
        cls.bob = User.objects.create_user(username="bob", password="x")
        cls.high = Priority.objects.create(name="high")
        cls.low = Priority.objects.create(name="low")
        cls.work = Category.objects.create(name="Work")
        cls.personal = Category.objects.create(name="Personal")

    def make_task(
        self,
        user,
        title="Sample task",
        status="Pending",
        deadline=None,
        priority=None,
        category=None,
    ):
        if deadline is None:
            deadline = timezone.now() + timedelta(days=1)
        return Task.objects.create(
            user=user,
            title=title,
            description="desc",
            status=status,
            deadline=deadline,
            priority=priority or self.high,
            category=category or self.work,
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_authenticated_user_can_access(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_own_task_statistics(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Done", status="Completed")
        self.make_task(self.alice, title="Todo", status="Pending")
        self.make_task(self.alice, title="Doing", status="In Progress")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["total_tasks"], 3)
        self.assertEqual(response.context["completed_tasks"], 1)
        self.assertEqual(response.context["pending_tasks"], 1)
        self.assertEqual(response.context["in_progress_tasks"], 1)

    def test_cross_user_isolation(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="A1", status="Completed")
        self.make_task(self.alice, title="A2", status="Pending")
        for i in range(20):
            self.make_task(
                self.bob, title=f"Bob task {i}", status="Completed"
            )
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["total_tasks"], 2)
        self.assertEqual(response.context["completed_tasks"], 1)
        self.assertEqual(response.context["pending_tasks"], 1)
        titles = [t.title for t in response.context["recent_tasks"]]
        self.assertNotIn("Bob task 0", titles)

    def test_overdue_logic(self):
        self.client.force_login(self.alice)
        past = timezone.now() - timedelta(days=1)
        future = timezone.now() + timedelta(days=1)
        self.make_task(
            self.alice,
            title="Overdue pending",
            status="Pending",
            deadline=past,
        )
        self.make_task(
            self.alice,
            title="Overdue in progress",
            status="In Progress",
            deadline=past,
        )
        self.make_task(
            self.alice,
            title="Overdue but completed",
            status="Completed",
            deadline=past,
        )
        self.make_task(
            self.alice, title="Future", status="Pending", deadline=future
        )
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["overdue_tasks"], 2)

    def test_priority_aggregation_is_user_scoped(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="A high 1", priority=self.high)
        self.make_task(self.alice, title="A high 2", priority=self.high)
        self.make_task(self.alice, title="A low 1", priority=self.low)
        self.make_task(self.bob, title="B high", priority=self.high)
        self.make_task(self.bob, title="B low", priority=self.low)
        response = self.client.get(reverse("dashboard"))
        counts = {
            entry["priority__name"]: entry["count"]
            for entry in response.context["tasks_by_priority"]
        }
        self.assertEqual(counts, {"high": 2, "low": 1})

    def test_category_aggregation_is_user_scoped(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="A work 1", category=self.work)
        self.make_task(
            self.alice, title="A personal 1", category=self.personal
        )
        self.make_task(self.bob, title="B work", category=self.work)
        response = self.client.get(reverse("dashboard"))
        counts = {
            entry["category__name"]: entry["count"]
            for entry in response.context["tasks_by_category"]
        }
        self.assertEqual(counts, {"Work": 1, "Personal": 1})

    def test_subtask_statistics_are_user_scoped(self):
        self.client.force_login(self.alice)
        alice_task = self.make_task(self.alice)
        bob_task = self.make_task(self.bob)
        SubTask.objects.create(
            task=alice_task, title="A pending", status="Pending"
        )
        SubTask.objects.create(
            task=alice_task, title="A in progress", status="In Progress"
        )
        SubTask.objects.create(
            task=alice_task, title="A done", status="Completed"
        )
        SubTask.objects.create(
            task=bob_task, title="B pending", status="Pending"
        )
        SubTask.objects.create(
            task=bob_task, title="B done", status="Completed"
        )
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["incomplete_subtasks"], 2)
        self.assertEqual(response.context["completed_subtasks"], 1)

    def test_recent_tasks_limited_to_five_and_owned(self):
        self.client.force_login(self.alice)
        for i in range(7):
            self.make_task(self.alice, title=f"Alice task {i}")
        self.make_task(self.bob, title="Bob newest")
        response = self.client.get(reverse("dashboard"))
        recent = list(response.context["recent_tasks"])
        self.assertEqual(len(recent), 5)
        self.assertTrue(all(t.user == self.alice for t in recent))
        self.assertEqual(recent[0].title, "Alice task 6")
        self.assertEqual(recent[4].title, "Alice task 2")
        self.assertNotIn("Bob newest", [t.title for t in recent])

    def test_empty_dashboard(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_tasks"], 0)
        self.assertEqual(response.context["completed_tasks"], 0)
        self.assertEqual(response.context["pending_tasks"], 0)
        self.assertEqual(response.context["in_progress_tasks"], 0)
        self.assertEqual(response.context["overdue_tasks"], 0)
        self.assertEqual(response.context["incomplete_subtasks"], 0)
        self.assertEqual(response.context["completed_subtasks"], 0)
        self.assertEqual(list(response.context["tasks_by_priority"]), [])
        self.assertEqual(list(response.context["tasks_by_category"]), [])
        self.assertEqual(list(response.context["recent_tasks"]), [])


class TaskListFilterTests(TestCase):
    """Phase 5: task-list filtering and sorting, user-scoped."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user(username="alice", password="x")
        cls.bob = User.objects.create_user(username="bob", password="x")
        cls.high = Priority.objects.create(name="high")
        cls.low = Priority.objects.create(name="low")
        cls.work = Category.objects.create(name="Work")
        cls.personal = Category.objects.create(name="Personal")

    def make_task(
        self,
        user,
        title="Sample task",
        status="Pending",
        deadline=None,
        priority=None,
        category=None,
    ):
        if deadline is None:
            deadline = timezone.now() + timedelta(days=1)
        return Task.objects.create(
            user=user,
            title=title,
            description="desc",
            status=status,
            deadline=deadline,
            priority=priority or self.high,
            category=category or self.work,
        )

    def titles(self, response):
        return [t.title for t in response.context["tasks"]]

    def test_anonymous_still_redirected_to_login(self):
        response = self.client.get(reverse("task_list") + "?status=Pending")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_status_filter(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Done", status="Completed")
        self.make_task(self.alice, title="Todo", status="Pending")
        response = self.client.get(reverse("task_list") + "?status=Pending")
        self.assertEqual(self.titles(response), ["Todo"])

    def test_priority_filter(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="High task", priority=self.high)
        self.make_task(self.alice, title="Low task", priority=self.low)
        response = self.client.get(
            reverse("task_list") + f"?priority={self.low.pk}"
        )
        self.assertEqual(self.titles(response), ["Low task"])

    def test_category_filter(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Work task", category=self.work)
        self.make_task(
            self.alice, title="Personal task", category=self.personal
        )
        response = self.client.get(
            reverse("task_list") + f"?category={self.personal.pk}"
        )
        self.assertEqual(self.titles(response), ["Personal task"])

    def test_overdue_filter(self):
        self.client.force_login(self.alice)
        past = timezone.now() - timedelta(days=1)
        future = timezone.now() + timedelta(days=1)
        self.make_task(
            self.alice, title="Overdue", status="Pending", deadline=past
        )
        self.make_task(
            self.alice,
            title="Overdue but done",
            status="Completed",
            deadline=past,
        )
        self.make_task(
            self.alice, title="Future", status="Pending", deadline=future
        )
        response = self.client.get(reverse("task_list") + "?deadline=overdue")
        self.assertEqual(self.titles(response), ["Overdue"])

    def test_due_today_filter(self):
        self.client.force_login(self.alice)
        self.make_task(
            self.alice, title="Today", deadline=timezone.now()
        )
        self.make_task(
            self.alice,
            title="Tomorrow",
            deadline=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(
            reverse("task_list") + "?deadline=due_today"
        )
        self.assertEqual(self.titles(response), ["Today"])

    def test_upcoming_filter(self):
        self.client.force_login(self.alice)
        past = timezone.now() - timedelta(days=1)
        future = timezone.now() + timedelta(days=1)
        self.make_task(
            self.alice, title="Past", status="Pending", deadline=past
        )
        self.make_task(
            self.alice, title="Future", status="Pending", deadline=future
        )
        response = self.client.get(
            reverse("task_list") + "?deadline=upcoming"
        )
        self.assertEqual(self.titles(response), ["Future"])

    def test_combined_filters(self):
        self.client.force_login(self.alice)
        self.make_task(
            self.alice,
            title="Match",
            status="Pending",
            priority=self.high,
            category=self.work,
            deadline=timezone.now() - timedelta(hours=1),
        )
        self.make_task(
            self.alice,
            title="Wrong status",
            status="Completed",
            priority=self.high,
            category=self.work,
            deadline=timezone.now() - timedelta(hours=1),
        )
        self.make_task(
            self.alice,
            title="Wrong priority",
            status="Pending",
            priority=self.low,
            category=self.work,
            deadline=timezone.now() - timedelta(hours=1),
        )
        url = (
            reverse("task_list")
            + f"?status=Pending&priority={self.high.pk}"
            + f"&category={self.work.pk}&deadline=overdue"
        )
        response = self.client.get(url)
        self.assertEqual(self.titles(response), ["Match"])

    def test_filtered_empty_result_renders(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Todo", status="Pending")
        response = self.client.get(reverse("task_list") + "?status=Completed")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.titles(response), [])
        self.assertContains(response, "No tasks match")

    def test_invalid_status_ignored(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Todo", status="Pending")
        self.make_task(self.alice, title="Done", status="Completed")
        response = self.client.get(reverse("task_list") + "?status=Bogus")
        self.assertEqual(len(self.titles(response)), 2)

    def test_empty_status_ignored(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Todo", status="Pending")
        response = self.client.get(reverse("task_list") + "?status=")
        self.assertEqual(self.titles(response), ["Todo"])

    def test_malformed_priority_and_category_ignored(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Todo")
        for query in ("?priority=abc", "?category=abc"):
            with self.subTest(query=query):
                response = self.client.get(reverse("task_list") + query)
                self.assertEqual(self.titles(response), ["Todo"])

    def test_nonexistent_priority_and_category_match_nothing(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Todo")
        missing = 9999
        for query in (
            f"?priority={missing}",
            f"?category={missing}",
        ):
            with self.subTest(query=query):
                response = self.client.get(reverse("task_list") + query)
                self.assertEqual(self.titles(response), [])

    def test_unknown_deadline_defaults_to_all(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Todo")
        response = self.client.get(reverse("task_list") + "?deadline=bogus")
        self.assertEqual(self.titles(response), ["Todo"])
        self.assertEqual(response.context["deadline_filter"], "all")

    def test_unknown_sort_falls_back_to_newest(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="First")
        self.make_task(self.alice, title="Second")
        response = self.client.get(reverse("task_list") + "?sort=bogus")
        self.assertEqual(self.titles(response), ["Second", "First"])
        self.assertEqual(response.context["sort"], "newest")

    def test_completed_and_overdue_yields_nothing(self):
        self.client.force_login(self.alice)
        self.make_task(
            self.alice,
            title="Done overdue",
            status="Completed",
            deadline=timezone.now() - timedelta(days=1),
        )
        response = self.client.get(
            reverse("task_list") + "?status=Completed&deadline=overdue"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.titles(response), [])

    def test_default_ordering_is_newest_first(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="First")
        self.make_task(self.alice, title="Second")
        response = self.client.get(reverse("task_list"))
        self.assertEqual(self.titles(response), ["Second", "First"])

    def test_sort_oldest(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="First")
        self.make_task(self.alice, title="Second")
        response = self.client.get(reverse("task_list") + "?sort=oldest")
        self.assertEqual(self.titles(response), ["First", "Second"])

    def test_sort_title_asc_and_desc(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Charlie")
        self.make_task(self.alice, title="Alpha")
        self.make_task(self.alice, title="Bravo")
        response = self.client.get(reverse("task_list") + "?sort=title_asc")
        self.assertEqual(
            self.titles(response), ["Alpha", "Bravo", "Charlie"]
        )
        response = self.client.get(reverse("task_list") + "?sort=title_desc")
        self.assertEqual(
            self.titles(response), ["Charlie", "Bravo", "Alpha"]
        )

    def test_sort_recently_updated(self):
        self.client.force_login(self.alice)
        first = self.make_task(self.alice, title="First")
        self.make_task(self.alice, title="Second")
        first.title = "First edited"
        first.save()
        response = self.client.get(
            reverse("task_list") + "?sort=recently_updated"
        )
        self.assertEqual(
            self.titles(response), ["First edited", "Second"]
        )

    def test_sort_deadline_soonest_and_latest(self):
        self.client.force_login(self.alice)
        now = timezone.now()
        self.make_task(
            self.alice, title="Later", deadline=now + timedelta(days=3)
        )
        self.make_task(
            self.alice, title="Sooner", deadline=now + timedelta(days=1)
        )
        response = self.client.get(
            reverse("task_list") + "?sort=deadline_soonest"
        )
        self.assertEqual(self.titles(response), ["Sooner", "Later"])
        response = self.client.get(
            reverse("task_list") + "?sort=deadline_latest"
        )
        self.assertEqual(self.titles(response), ["Later", "Sooner"])

    def test_filters_do_not_expose_other_user_tasks(self):
        self.client.force_login(self.alice)
        self.make_task(
            self.alice, title="Alice pending", status="Pending"
        )
        self.make_task(
            self.bob,
            title="Bob pending",
            status="Pending",
            priority=self.high,
            category=self.work,
        )
        self.make_task(self.bob, title="Bob done", status="Completed")
        for query in (
            "",
            "?status=Pending",
            f"?priority={self.high.pk}",
            f"?category={self.work.pk}",
            "?deadline=all",
            "?sort=title_asc",
            f"?status=Pending&priority={self.high.pk}"
            f"&category={self.work.pk}&sort=title_asc",
        ):
            with self.subTest(query=query):
                response = self.client.get(reverse("task_list") + query)
                titles = self.titles(response)
                self.assertIn("Alice pending", titles)
                self.assertNotIn("Bob pending", titles)
                self.assertNotIn("Bob done", titles)


class TaskKanbanTests(TestCase):
    """Phase 6: Kanban board groups the user's own Tasks by status."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user(username="alice", password="x")
        cls.bob = User.objects.create_user(username="bob", password="x")
        cls.priority = Priority.objects.create(name="high")
        cls.category = Category.objects.create(name="Work")

    def make_task(self, user, title="Sample task", status="Pending"):
        return Task.objects.create(
            user=user,
            title=title,
            description="desc",
            status=status,
            deadline=timezone.now() + timedelta(days=1),
            priority=self.priority,
            category=self.category,
        )

    def columns(self, response):
        return {
            status: [t.title for t in board_tasks]
            for status, board_tasks in response.context["columns"]
        }

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("task_kanban"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_authenticated_user_can_access(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("task_kanban"))
        self.assertEqual(response.status_code, 200)

    def test_tasks_grouped_by_status(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Todo", status="Pending")
        self.make_task(self.alice, title="Doing", status="In Progress")
        self.make_task(self.alice, title="Done", status="Completed")
        cols = self.columns(self.client.get(reverse("task_kanban")))
        self.assertEqual(cols["Pending"], ["Todo"])
        self.assertEqual(cols["In Progress"], ["Doing"])
        self.assertEqual(cols["Completed"], ["Done"])

    def test_other_user_tasks_never_appear(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Alice todo", status="Pending")
        self.make_task(self.bob, title="Bob todo", status="Pending")
        self.make_task(self.bob, title="Bob done", status="Completed")
        response = self.client.get(reverse("task_kanban"))
        cols = self.columns(response)
        self.assertEqual(cols["Pending"], ["Alice todo"])
        self.assertEqual(cols["In Progress"], [])
        self.assertEqual(cols["Completed"], [])

    def test_kanban_links_resolve_to_task_detail(self):
        self.client.force_login(self.alice)
        task = self.make_task(self.alice, title="Linked", status="Pending")
        response = self.client.get(reverse("task_kanban"))
        self.assertContains(
            response, reverse("task_detail", args=[task.pk])
        )


class PWATests(TestCase):
    """Phase 7: manifest, service worker, offline fallback, static assets.

    The service worker itself runs in the browser, which Django unit
    tests cannot simulate; these tests verify the Django endpoints that
    feed it (URLs, content types, payloads) plus the static assets.
    """

    def test_manifest_responds_with_json(self):
        response = self.client.get(reverse("manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/manifest+json", response["Content-Type"])
        manifest = response.json()
        self.assertEqual(manifest["name"], "Hangarin")
        self.assertEqual(manifest["short_name"], "Hangarin")
        self.assertEqual(manifest["start_url"], "/tasks/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["theme_color"], "#1E40AF")
        self.assertEqual(manifest["background_color"], "#F8FAFC")

    def test_manifest_icons_cover_192_and_512(self):
        manifest = self.client.get(reverse("manifest")).json()
        sizes = {icon["sizes"] for icon in manifest["icons"]}
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)
        for icon in manifest["icons"]:
            self.assertEqual(icon["type"], "image/png")

    def test_service_worker_responds_with_javascript(self):
        response = self.client.get(reverse("service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response["Content-Type"])
        js = response.content.decode()
        self.assertIn("hangarin-v1", js)
        self.assertIn("addEventListener('install'", js)
        self.assertIn("addEventListener('activate'", js)
        self.assertIn("addEventListener('fetch'", js)
        self.assertIn("/offline/", js)

    def test_service_worker_accessible_without_authentication(self):
        for name in ("manifest", "service_worker", "offline"):
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse(name)).status_code, 200
                )

    def test_service_worker_never_caches_private_routes(self):
        js = self.client.get(reverse("service_worker")).content.decode()
        for private_path in ("/tasks/", "/accounts/", "/admin/"):
            self.assertNotIn(f"'{private_path}'", js)
            self.assertNotIn(f'"{private_path}"', js)

    def test_offline_page_has_hangarin_branding(self):
        response = self.client.get(reverse("offline"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hangarin")
        self.assertContains(response, "offline")

    def test_pwa_static_assets_are_discoverable(self):
        from django.contrib.staticfiles.finders import find

        for path in (
            "icons/icon-192.png",
            "icons/icon-512.png",
            "css/hangarin.css",
        ):
            with self.subTest(path=path):
                self.assertTrue(find(path), path)

    def test_base_template_links_manifest_and_registers_worker(self):
        self.client.force_login(
            get_user_model().objects.create_user(
                username="pwa_user", password="x"
            )
        )
        response = self.client.get(reverse("task_list"))
        self.assertContains(response, reverse("manifest"))
        self.assertContains(response, reverse("service_worker"))
        self.assertContains(response, 'name="theme-color"')


class ProductionConfigTests(TestCase):
    """Phase 8: production configuration reads environment safely."""

    def helpers(self):
        from hangarin_project import settings as app_settings

        return (
            app_settings._env_bool,
            app_settings._env_list,
            app_settings._env_int,
        )

    def test_env_bool_parsing(self):
        env_bool, _, _ = self.helpers()
        for truthy in ("1", "True", "true", "TRUE", "yes", "on", " On "):
            with self.subTest(value=truthy):
                with patch.dict(os.environ, {"HANGARIN_TEST_FLAG": truthy}):
                    self.assertTrue(env_bool("HANGARIN_TEST_FLAG"))
        for falsy in ("0", "False", "false", "no", "off", "", "bogus"):
            with self.subTest(value=falsy):
                with patch.dict(os.environ, {"HANGARIN_TEST_FLAG": falsy}):
                    self.assertFalse(env_bool("HANGARIN_TEST_FLAG"))
        # Unset falls back to the default (never truthy by accident).
        os.environ.pop("HANGARIN_TEST_FLAG", None)
        self.assertFalse(env_bool("HANGARIN_TEST_FLAG"))
        self.assertTrue(env_bool("HANGARIN_TEST_FLAG", default=True))
        # "False" must not enable a flag: DEBUG stays off.
        with patch.dict(os.environ, {"HANGARIN_TEST_FLAG": "False"}):
            self.assertFalse(env_bool("HANGARIN_TEST_FLAG", default=True))

    def test_env_list_parsing(self):
        _, env_list, _ = self.helpers()
        with patch.dict(
            os.environ,
            {"HANGARIN_TEST_LIST": "a.example.com, b.example.com ,, "},
        ):
            self.assertEqual(
                env_list("HANGARIN_TEST_LIST"),
                ["a.example.com", "b.example.com"],
            )
        os.environ.pop("HANGARIN_TEST_LIST", None)
        self.assertEqual(env_list("HANGARIN_TEST_LIST"), [])
        self.assertEqual(
            env_list("HANGARIN_TEST_LIST", "x, y"), ["x", "y"]
        )

    def test_env_int_parsing(self):
        _, _, env_int = self.helpers()
        with patch.dict(os.environ, {"HANGARIN_TEST_INT": "31536000"}):
            self.assertEqual(env_int("HANGARIN_TEST_INT"), 31536000)
        with patch.dict(os.environ, {"HANGARIN_TEST_INT": "bogus"}):
            self.assertEqual(env_int("HANGARIN_TEST_INT", default=25), 25)
        os.environ.pop("HANGARIN_TEST_INT", None)
        self.assertEqual(env_int("HANGARIN_TEST_INT"), 0)

    def test_safe_local_defaults(self):
        self.assertIn("127.0.0.1", settings.ALLOWED_HOSTS)
        self.assertIn("localhost", settings.ALLOWED_HOSTS)
        self.assertNotIn("*", settings.ALLOWED_HOSTS)
        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, [])
        self.assertFalse(settings.SECURE_SSL_REDIRECT)
        self.assertFalse(settings.SESSION_COOKIE_SECURE)
        self.assertFalse(settings.CSRF_COOKIE_SECURE)
        self.assertEqual(settings.SECURE_HSTS_SECONDS, 0)
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(
            settings.SECURE_REFERRER_POLICY, "strict-origin-when-cross-origin"
        )
        self.assertEqual(settings.EMAIL_PORT, 25)
        self.assertFalse(settings.EMAIL_USE_TLS)
        self.assertFalse(settings.EMAIL_USE_SSL)
        # The test runner forces the locmem backend, so verify the
        # env-driven default wiring instead of the live value.
        os.environ.pop("DJANGO_EMAIL_BACKEND", None)
        self.assertEqual(
            os.environ.get(
                "DJANGO_EMAIL_BACKEND",
                "django.core.mail.backends.console.EmailBackend",
            ),
            "django.core.mail.backends.console.EmailBackend",
        )

    def test_dev_secret_key_is_marked_not_for_production(self):
        os.environ.pop("DJANGO_SECRET_KEY", None)
        # Only asserts the dev-only marker, never the value itself.
        self.assertTrue(settings.SECRET_KEY.startswith("django-insecure-"))

    def test_environment_overrides_apply(self):
        from hangarin_project import settings as app_settings

        env = {
            "DJANGO_SECRET_KEY": "test-env-secret-" + "z" * 40,
            "DJANGO_DEBUG": "False",
            "DJANGO_ALLOWED_HOSTS": "app.example.com, www.example.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://app.example.com",
            "DJANGO_SECURE_SSL_REDIRECT": "True",
            "DJANGO_SESSION_COOKIE_SECURE": "1",
            "DJANGO_CSRF_COOKIE_SECURE": "yes",
            "DJANGO_SECURE_HSTS_SECONDS": "31536000",
            "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "on",
            "DJANGO_SECURE_HSTS_PRELOAD": "True",
            "DJANGO_EMAIL_PORT": "587",
            "DJANGO_EMAIL_USE_TLS": "True",
        }
        with patch.dict(os.environ, env):
            importlib.reload(app_settings)
            try:
                self.assertEqual(
                    app_settings.SECRET_KEY, env["DJANGO_SECRET_KEY"]
                )
                self.assertFalse(app_settings.DEBUG)
                self.assertEqual(
                    app_settings.ALLOWED_HOSTS,
                    ["app.example.com", "www.example.com"],
                )
                self.assertEqual(
                    app_settings.CSRF_TRUSTED_ORIGINS,
                    ["https://app.example.com"],
                )
                self.assertTrue(app_settings.SECURE_SSL_REDIRECT)
                self.assertTrue(app_settings.SESSION_COOKIE_SECURE)
                self.assertTrue(app_settings.CSRF_COOKIE_SECURE)
                self.assertEqual(app_settings.SECURE_HSTS_SECONDS, 31536000)
                self.assertTrue(app_settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)
                self.assertTrue(app_settings.SECURE_HSTS_PRELOAD)
                self.assertEqual(app_settings.EMAIL_PORT, 587)
                self.assertTrue(app_settings.EMAIL_USE_TLS)
            finally:
                importlib.reload(app_settings)

    def test_requirements_file_is_clean_utf8_with_pins(self):
        from pathlib import Path

        requirements = (
            Path(settings.BASE_DIR).parent / "requirements.txt"
        )
        content = requirements.read_text(encoding="utf-8")
        self.assertIn("Django==", content)
        self.assertIn("django-allauth==", content)
        self.assertNotIn("tzdata", content)
        for line in content.splitlines():
            self.assertTrue(line.strip(), "no blank lines")


class RootRouteTests(TestCase):
    """Root route (/) reuses the existing task_list view."""

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
            deadline=timezone.now() + timedelta(days=1),
            priority=self.priority,
            category=self.category,
        )

    def test_logged_out_root_redirects_to_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_logged_in_root_returns_task_list(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Alice root task")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Alice root task", [t.title for t in response.context["tasks"]]
        )

    def test_root_does_not_expose_other_user_tasks(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Alice task")
        self.make_task(self.bob, title="Bob task")
        titles = [
            t.title for t in self.client.get("/").context["tasks"]
        ]
        self.assertIn("Alice task", titles)
        self.assertNotIn("Bob task", titles)

    def test_tasks_route_still_works(self):
        self.client.force_login(self.alice)
        self.make_task(self.alice, title="Alice list task")
        response = self.client.get(reverse("task_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Alice list task",
            [t.title for t in response.context["tasks"]],
        )

    def test_login_redirect_url_remains_root(self):
        self.assertEqual(settings.LOGIN_REDIRECT_URL, "/")


class SeedCommandTests(TestCase):
    """create_initial_data: deterministic local dev dataset.

    Runs against the empty test database, so every assertion below also
    locks in the command's exact output (30 tasks, fixed distributions).
    """

    def run_seed(self):
        call_command("create_initial_data", verbosity=0)

    def test_dev_user_created_with_unusable_password(self):
        self.run_seed()
        user = get_user_model().objects.get(username="dev_seed_user")
        self.assertEqual(user.email, "dev_seed_user@example.local")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.has_usable_password())

    def test_expected_priorities_and_categories_exist(self):
        self.run_seed()
        self.assertEqual(
            set(Priority.objects.values_list("name", flat=True)),
            {"high", "medium", "low", "critical", "optional"},
        )
        self.assertEqual(
            set(Category.objects.values_list("name", flat=True)),
            {"Work", "School", "Personal", "Finance", "Projects"},
        )

    def test_thirty_tasks_all_owned_by_dev_user(self):
        self.run_seed()
        tasks = Task.objects.all()
        self.assertEqual(tasks.count(), 30)
        owners = set(tasks.values_list("user__username", flat=True))
        self.assertEqual(owners, {"dev_seed_user"})

    def test_deterministic_status_priority_category_distributions(self):
        self.run_seed()
        tasks = Task.objects.all()
        self.assertEqual(tasks.filter(status="Pending").count(), 15)
        self.assertEqual(tasks.filter(status="In Progress").count(), 9)
        self.assertEqual(tasks.filter(status="Completed").count(), 6)
        self.assertEqual(
            {p: tasks.filter(priority__name=p).count() for p in
             ("critical", "high", "medium", "low", "optional")},
            {"critical": 4, "high": 7, "medium": 9,
             "low": 6, "optional": 4},
        )
        self.assertEqual(
            {c: tasks.filter(category__name=c).count() for c in
             ("Work", "School", "Personal", "Finance", "Projects")},
            {"Work": 7, "School": 8, "Personal": 6,
             "Finance": 4, "Projects": 5},
        )

    def test_deadlines_cover_overdue_and_upcoming(self):
        self.run_seed()
        now = timezone.now()
        overdue = Task.objects.filter(deadline__lt=now).exclude(
            status="Completed"
        )
        upcoming = Task.objects.filter(deadline__gt=now)
        self.assertGreaterEqual(overdue.count(), 3)
        self.assertGreater(upcoming.count(), 10)

    def test_subtasks_and_notes_generated(self):
        self.run_seed()
        self.assertGreater(SubTask.objects.count(), 30)
        self.assertGreater(Note.objects.count(), 10)
        # Ownership derives through the parent Task.
        self.assertEqual(
            set(SubTask.objects.values_list(
                "task__user__username", flat=True)),
            {"dev_seed_user"},
        )

    def test_rerun_does_not_duplicate_tasks(self):
        self.run_seed()
        self.run_seed()
        self.assertEqual(Task.objects.count(), 30)
