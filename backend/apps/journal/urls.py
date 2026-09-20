from django.urls import path
from . import views

urlpatterns = [
    path("api/days/<str:day>/attachments/<int:attachment_id>/", views.delete_attachment),
    path("api/days/<str:day>/attachments/", views.attachments),
    path("api/attachments/<int:attachment_id>/file/", views.attachment_file),
    path("api/state/", views.state), path("api/rules/", views.rules),
    path("api/days/<str:day>/", views.day)
]
