from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from faker import Faker
from tasks.models import Priority, Category, Task, SubTask, Note

# Username reserved for locally generated development data. It is created
# with an unusable password so it can never be used to log in, and its name
# makes it obvious it must not be treated as real production data.
DEV_USERNAME = "dev_seed_user"

# The curated task list below is the source of truth, so output is fully
# deterministic. The Faker seed pins any Faker-derived values as well.
Faker.seed(42)

# Curated development dataset: exactly 30 tasks with a realistic mix.
# Status split: 15 Pending / 9 In Progress / 6 Completed.
# Deadlines are day offsets relative to "now" when the command runs, so the
# overdue / due-today / upcoming mix stays meaningful whenever it is seeded.
# Each entry: (title, description, category, priority, status, day_offset,
#              [(subtask title, subtask status)], [note, ...]).
TASKS_DATA = [
    (
        "Finish Database Systems lab report",
        "Write up the normalization and indexing lab, including the ER "
        "diagram and query timings.",
        "School", "high", "In Progress", 2,
        [
            ("Draft the ER diagram", "Completed"),
            ("Write the normalization section", "In Progress"),
            ("Proofread the final report", "Pending"),
        ],
        ["Lab covers 3NF and indexing; remember to include screenshots."],
    ),
    (
        "Review SQL joins for the quiz",
        "Go over INNER, LEFT, and self joins with practice queries before "
        "Friday's quiz.",
        "School", "critical", "Pending", 1,
        [
            ("Re-read INNER vs LEFT JOIN notes", "Pending"),
            ("Do 10 practice queries", "Pending"),
        ],
        ["Quiz is Friday morning, 20 questions, closed notes."],
    ),
    (
        "Prepare capstone presentation slides",
        "Build the slide deck for the capstone defense: problem, approach, "
        "demo, and results.",
        "School", "high", "In Progress", 4,
        [
            ("Outline the slide structure", "Completed"),
            ("Add demo screenshots", "In Progress"),
            ("Rehearse the 15-minute talk", "Pending"),
        ],
        ["Keep it under 15 minutes; Q&A follows."],
    ),
    (
        "Complete programming assignment 5",
        "Implement the parser and pass all hidden test cases before the "
        "late penalty kicks in.",
        "School", "critical", "Pending", -2,
        [
            ("Implement the tokenizer", "Completed"),
            ("Fix failing edge-case tests", "In Progress"),
        ],
        [
            "Already late; each day costs 10%.",
            "Ask the TA about the ambiguous grammar rule.",
        ],
    ),
    (
        "Read operating systems chapters 7-8",
        "Cover deadlocks and memory management ahead of next week's "
        "discussion.",
        "School", "medium", "Pending", 9,
        [],
        ["Focus on the Banker's algorithm example."],
    ),
    (
        "Submit scholarship application",
        "Fill out the merit scholarship form and attach transcripts and the "
        "recommendation letter.",
        "School", "medium", "Completed", -5,
        [
            ("Gather transcripts", "Completed"),
            ("Submit the online form", "Completed"),
        ],
        ["Submitted with a day to spare."],
    ),
    (
        "Organize study group for finals",
        "Coordinate a review schedule with classmates for the three final "
        "exams.",
        "School", "optional", "Pending", 12,
        [("Poll everyone for availability", "Pending")],
        [],
    ),
    (
        "Return library books",
        "Return the borrowed references before fines accumulate.",
        "School", "low", "Completed", -1,
        [],
        [],
    ),
    (
        "Update client landing page copy",
        "Rewrite the hero section and feature list based on the client's "
        "latest feedback.",
        "Work", "high", "In Progress", 3,
        [
            ("Draft the new hero copy", "Completed"),
            ("Update the feature list", "In Progress"),
            ("Get client sign-off", "Pending"),
        ],
        ["Client wants a friendlier tone throughout."],
    ),
    (
        "Review website feedback from QA",
        "Go through the QA spreadsheet and file tickets for every confirmed "
        "issue.",
        "Work", "medium", "Pending", -1,
        [
            ("Triage the QA spreadsheet", "In Progress"),
            ("File tickets for confirmed bugs", "Pending"),
        ],
        ["Most issues are on the checkout page."],
    ),
    (
        "Deploy latest staging changes",
        "Push the tested staging build to production during the maintenance "
        "window.",
        "Work", "critical", "Pending", -6,
        [
            ("Run the full test suite", "Completed"),
            ("Schedule the maintenance window", "Pending"),
        ],
        [
            "Missed the window; reschedule ASAP.",
            "Double-check the database backup first.",
        ],
    ),
    (
        "Fix broken contact form validation",
        "The email field accepts invalid input; tighten validation and show "
        "inline errors.",
        "Work", "high", "In Progress", 1,
        [
            ("Reproduce the invalid-email bug", "Completed"),
            ("Add regex validation", "In Progress"),
            ("Show inline error messages", "Pending"),
            ("Add regression tests", "Pending"),
        ],
        ["Reported by two users this week."],
    ),
    (
        "Write weekly status report",
        "Summarize completed work, blockers, and next week's plan for the "
        "team lead.",
        "Work", "low", "Completed", -7,
        [("Collect updates from the team", "Completed")],
        ["Sent on time."],
    ),
    (
        "Update team wiki onboarding page",
        "Refresh the setup instructions so new hires stop hitting the same "
        "environment issues.",
        "Work", "medium", "Pending", 20,
        [],
        ["Add the new Docker setup steps."],
    ),
    (
        "Schedule sprint retrospective",
        "Book a room and send the retro board link to the team.",
        "Work", "medium", "In Progress", 6,
        [("Send the retro board link", "Completed")],
        [],
    ),
    (
        "Organize project files and backups",
        "Clean up the downloads folder and verify the external drive backup "
        "is current.",
        "Personal", "medium", "In Progress", 5,
        [
            ("Sort downloads by project", "Completed"),
            ("Verify the backup drive", "In Progress"),
            ("Delete duplicate archives", "Pending"),
        ],
        ["Backup drive is almost full."],
    ),
    (
        "Plan weekly schedule",
        "Block out deep-work sessions, errands, and rest for the coming "
        "week.",
        "Personal", "low", "Pending", 0,
        [
            ("List fixed commitments", "Completed"),
            ("Block deep-work sessions", "Pending"),
        ],
        ["Protect Friday afternoon for catch-up."],
    ),
    (
        "Review personal side projects",
        "Decide which side project to keep maintaining and which to archive.",
        "Personal", "optional", "Pending", 15,
        [],
        ["The notes app has the most users; keep that one."],
    ),
    (
        "Book dentist appointment",
        "Call the clinic for the six-month cleaning that is already overdue.",
        "Personal", "medium", "Pending", -4,
        [("Check insurance coverage", "Completed")],
        ["Clinic is closed on Mondays."],
    ),
    (
        "Renew gym membership",
        "Renew before the promo rate expires at the end of last month.",
        "Personal", "low", "Completed", -9,
        [],
        [],
    ),
    (
        "Declutter desk and workspace",
        "Clear cables, file papers, and wipe down the desk.",
        "Personal", "optional", "In Progress", 8,
        [
            ("Sort the cable drawer", "Completed"),
            ("File loose papers", "In Progress"),
        ],
        [],
    ),
    (
        "Track monthly expenses",
        "Log this month's spending and compare against the budget.",
        "Finance", "high", "Pending", 0,
        [
            ("Export bank statements", "Completed"),
            ("Categorize each expense", "Pending"),
        ],
        ["Dining out is over budget again."],
    ),
    (
        "Review subscription payments",
        "Audit recurring charges and cancel services that are no longer "
        "used.",
        "Finance", "medium", "In Progress", -3,
        [
            ("List all recurring charges", "Completed"),
            ("Cancel the unused streaming plan", "In Progress"),
            ("Confirm cancellations by email", "Pending"),
        ],
        ["Found two duplicate subscriptions."],
    ),
    (
        "File tax documents",
        "Gather receipts and forms so everything is ready before the filing "
        "deadline.",
        "Finance", "critical", "Pending", 7,
        [
            ("Collect income forms", "In Progress"),
            ("Gather deductible receipts", "Pending"),
            ("Fill out the return draft", "Pending"),
            ("Review with an accountant", "Pending"),
            ("Submit before the deadline", "Pending"),
        ],
        [
            "Missing one freelance 1099.",
            "Accountant is available next Tuesday.",
        ],
    ),
    (
        "Set up emergency fund transfer",
        "Automate the monthly transfer into the high-yield savings account.",
        "Finance", "low", "Completed", -14,
        [("Confirm the transfer schedule", "Completed")],
        ["Set to 10% of each paycheck."],
    ),
    (
        "Fix authentication UI alignment",
        "Align the Remember Me checkbox with its label and center the login "
        "button.",
        "Projects", "high", "In Progress", 2,
        [
            ("Reproduce the misalignment", "Completed"),
            ("Fix the checkbox row", "In Progress"),
            ("Center the login button", "Pending"),
            ("Verify on mobile widths", "Pending"),
        ],
        ["Keep the existing visual style."],
    ),
    (
        "Test dashboard filters",
        "Exercise every filter and sort option and record any broken "
        "combinations.",
        "Projects", "medium", "Pending", 4,
        [
            ("Test status filters", "Pending"),
            ("Test deadline filters", "Pending"),
            ("Test sort orderings", "Pending"),
        ],
        ["Pay attention to the overdue filter."],
    ),
    (
        "Update project documentation",
        "Refresh the README setup steps and document the new environment "
        "variables.",
        "Projects", "low", "Pending", 18,
        [("Rewrite the setup section", "Pending")],
        [],
    ),
    (
        "Prototype offline sync flow",
        "Sketch how queued changes sync when the connection returns.",
        "Projects", "optional", "Pending", 25,
        [],
        ["Low priority exploratory work."],
    ),
    (
        "Review pull requests for release",
        "Go through the open PRs, leave feedback, and merge what is ready.",
        "Projects", "high", "Completed", -2,
        [
            ("Review the auth PR", "Completed"),
            ("Merge the docs PR", "Completed"),
        ],
        ["Release went out on schedule."],
    ),
]


class Command(BaseCommand):
    help = 'Create initial data for the application'

    def add_arguments(self, parser):
        parser.add_argument(
            '--superuser',
            action='store_true',
            help=(
                'Seed tasks under the existing superuser instead of '
                'dev_seed_user. Fails if no superuser exists.'
            ),
        )

    def handle(self, *args, **kwargs):
        self.create_priorities()
        self.create_categories()
        if kwargs.get('superuser'):
            owner = self.get_existing_superuser()
        else:
            owner = self.get_dev_user()
        if Task.objects.exists():
            self.stdout.write('Tasks already exist, skipping task seeding.')
            return
        self.create_tasks(owner)
        self.stdout.write(self.style.SUCCESS(
            'Development data created successfully.'))

    def get_existing_superuser(self):
        User = get_user_model()
        superuser = User.objects.filter(
            is_superuser=True, is_staff=True
        ).order_by('pk').first()
        if superuser is None:
            raise CommandError(
                'No superuser exists. Create one with '
                '"python manage.py createsuperuser" before using --superuser.'
            )
        return superuser

    def get_dev_user(self):
        user, created = get_user_model().objects.get_or_create(
            username=DEV_USERNAME,
            defaults={"email": "dev_seed_user@example.local", "is_staff": False},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS(
                f'Development user "{DEV_USERNAME}" created (login disabled).'))
        return user

    def create_priorities(self):
        priorities = ['high', 'medium', 'low', 'critical', 'optional']
        for name in priorities:
            Priority.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS(
            'Priorities created successfully.'))

    def create_categories(self):
        categories = ['Work', 'School', 'Personal', 'Finance', 'Projects']
        for name in categories:
            Category.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS(
            'Categories created successfully.'))

    def create_tasks(self, owner):
        now = timezone.now()
        priorities = {p.name: p for p in Priority.objects.all()}
        categories = {c.name: c for c in Category.objects.all()}
        for (
            title, description, category, priority, status, day_offset,
            subtasks, notes,
        ) in TASKS_DATA:
            task = Task.objects.create(
                user=owner,
                title=title,
                description=description,
                status=status,
                deadline=now + timedelta(days=day_offset),
                priority=priorities[priority],
                category=categories[category],
            )
            for sub_title, sub_status in subtasks:
                SubTask.objects.create(
                    task=task, title=sub_title, status=sub_status
                )
            for content in notes:
                Note.objects.create(task=task, content=content)
        self.stdout.write(self.style.SUCCESS(
            'Tasks created successfully.'))
