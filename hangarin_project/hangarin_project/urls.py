"""
URL configuration for hangarin_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from . import views as site_views
from tasks import views as task_views

urlpatterns = [
    # Root route reuses the existing task_list view (no name: the
    # canonical `task_list` reverse target remains /tasks/).
    path("", task_views.task_list),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('tasks/', include('tasks.urls')),
    path('manifest.json', site_views.manifest, name='manifest'),
    path('service-worker.js', site_views.service_worker, name='service_worker'),
    path('offline/', site_views.offline, name='offline'),
]
