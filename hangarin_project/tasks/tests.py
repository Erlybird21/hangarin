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
