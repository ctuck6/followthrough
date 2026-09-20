from django.urls import include, path

urlpatterns = [path("", include("apps.journal.urls"))]
