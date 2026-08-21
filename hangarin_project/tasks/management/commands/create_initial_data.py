from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from tasks.models import Priority, Category, Task, SubTask, Note


class Command(BaseCommand):
    help = 'Create initial data for the application'

    def handle(self, *args, **kwargs):
        self.create_priorities()
        self.create_categories()
        self.create_tasks(30)
        self.create_subtasks()
        self.create_notes()

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

    def create_tasks(self, count):
        fake = Faker()
        statuses = ['Pending', 'In Progress ', 'Completed']

        for _ in range(count):
            Task.objects.create(
                title=fake.sentence(),
                description=fake.paragraph(),
                status=fake.random_element(statuses),
                deadline=timezone.make_aware(fake.date_time_this_month()),
                priority=Priority.objects.order_by('?').first(),
                category=Category.objects.order_by('?').first()
            )
        self.stdout.write(self.style.SUCCESS(
            'Tasks created successfully.'))

    def create_subtasks(self):
        fake = Faker()
        statuses = ['Pending', 'In Progress ', 'Completed']

        for task in Task.objects.all():
            for _ in range(fake.random_int(min=1, max=5)):
                SubTask.objects.create(
                    task=task,
                    title=fake.sentence(),
                    status=fake.random_element(statuses)
                )
        self.stdout.write(self.style.SUCCESS(
            'SubTasks created successfully.'))

    def create_notes(self):
        fake = Faker()

        for task in Task.objects.all():
            for _ in range(fake.random_int(min=1, max=3)):
                Note.objects.create(
                    task=task,
                    content=fake.paragraph()
                )
        self.stdout.write(self.style.SUCCESS(
            'Notes created successfully.'))
