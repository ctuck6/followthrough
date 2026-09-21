from django.urls import path
from . import views

urlpatterns = [
    path("api/manual-trades/", views.manual_trade),
    path("api/trades/<str:key>/journal/", views.trade_journal),
    path("api/trades/<str:key>/attachments/", views.trade_attachments),
    path("api/trades/<str:key>/attachments/<int:attachment_id>/", views.trade_attachments),
    path("api/executions/", views.executions),
    path("api/days/<str:day>/attachments/<int:attachment_id>/", views.delete_attachment),
    path("api/days/<str:day>/attachments/", views.attachments),
    path("api/attachments/<int:attachment_id>/file/", views.attachment_file),
    path("api/state/", views.state), path("api/rules/", views.rules),
    path("api/days/<str:day>/", views.day)
]
