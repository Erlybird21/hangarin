# Hangarin

A Django web application for task and to-do management.

## Features

- Task management with titles, descriptions, and deadlines
- Priority levels (high, medium, low, critical, optional)
- Categories (Work, School, Personal, Finance, Projects)
- SubTasks linked to parent Tasks
- Notes linked to Tasks
- Task status tracking (Pending, In Progress, Completed)
- Django admin interface for managing all models
- Faker-based development data generation

## Tech Stack

- Python 3.13.7
- Django 6.1
- Faker 40.36.0
- SQLite (development database)

## Project Structure

```
hangarin_project/
├── manage.py
├── hangarin_project/        # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── tasks/                   # Main application
    ├── models.py            # Data models
    ├── admin.py             # Admin configuration
    └── management/
        └── commands/
            └── create_initial_data.py  # Faker data generator
```

## Setup

1. Clone the repository:

```powershell
git clone https://github.com/Erlybird21/hangarin.git
cd hangarin
```

2. Create a virtual environment:

```powershell
python -m venv hangarinenv
```

3. Activate the virtual environment:

```powershell
hangarinenv\Scripts\activate
```

4. Install dependencies:

```powershell
pip install -r requirements.txt
```

5. Navigate to the Django project directory:

```powershell
cd hangarin_project
```

6. Run migrations:

```powershell
python manage.py migrate
```

7. Generate development data (optional):

```powershell
python manage.py create_initial_data
```

8. Start the development server:

```powershell
python manage.py runserver
```

9. Visit http://127.0.0.1:8000/ to view the application.

## Development Data

The project includes a management command to generate fake development data using Faker:

```powershell
python manage.py create_initial_data
```

This command creates:
- Priority records (high, medium, low, critical, optional)
- Category records (Work, School, Personal, Finance, Projects)
- Task records with fake titles, descriptions, statuses, and deadlines
- SubTask records linked to Tasks
- Note records linked to Tasks

The command is safe to run multiple times — it uses `get_or_create` for Priority and Category records.

## Django Admin

To access the Django admin interface:

1. Create a superuser:

```powershell
python manage.py createsuperuser
```

2. Start the development server:

```powershell
python manage.py runserver
```

3. Visit http://127.0.0.1:8000/admin/ and log in with your superuser credentials.

The admin interface provides full management of:
- Priorities
- Categories
- Tasks
- SubTasks
- Notes

## Deployment

The application is deployed to PythonAnywhere:

**Production URL:** https://erlybird21hangarin.pythonanywhere.com/

### Deployment Configuration

- Python 3.13
- Django 6.1
- SQLite database
- Static files served via `collectstatic`

### PythonAnywhere Setup

1. Clone the repository:
```bash
git clone https://github.com/Erlybird21/hangarin.git ~/hangarin
```

2. Create a virtual environment:
```bash
python3.13 -m venv ~/hangarin-venv
source ~/hangarin-venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r ~/hangarin/requirements.txt
```

4. Run migrations:
```bash
cd ~/hangarin/hangarin_project
python manage.py migrate
```

5. Collect static files:
```bash
python manage.py collectstatic --noinput
```

6. Configure the WSGI file:
```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hangarin_project.settings')
application = get_wsgi_application()
```

7. Configure the web app in PythonAnywhere dashboard:
- Python version: 3.13
- Working directory: `/home/erlybird21hangarin/hangarin/hangarin_project`
- WSGI file: `/home/erlybird21hangarin/hangarin/hangarin_project/hangarin_project/wsgi.py`
- Virtual environment: `/home/erlybird21hangarin/hangarin-venv`

8. Reload the web app.

## Current Development Status

The project includes:
- Django project scaffold
- Data models (BaseModel, Priority, Category, Task, SubTask, Note)
- Admin configuration with list displays, search, and filters
- Faker development data generation command
- Dependency specification (requirements.txt)
- Documentation
- PythonAnywhere deployment
