from django.urls import path

from . import views
from .accounts import account_data, account_detail, accounts
from .charts import trade_chart
from .statistics import statistics
from .strategies import strategies, strategy_detail, trade_strategy

urlpatterns = [
    path("api/accounts/", accounts),
    path("api/accounts/<int:pk>/", account_detail),
    path("api/accounts/<int:pk>/data/", account_data),
    path("api/statistics/", statistics),
    path("api/strategies/", strategies),
    path("api/strategies/<int:pk>/", strategy_detail),
    path("api/trades/<str:key>/strategy/", trade_strategy),
    path("api/trades/<str:key>/chart/", trade_chart),
    path("api/rules/delete/", views.remove_rules),
    path("api/executions/delete/", views.remove_executions),
    path("api/profile/", views.profile),
    path("api/manual-executions/", views.manual_execution),
    path("api/manual-trades/", views.manual_trade),
    path("api/trades/<str:key>/journal/", views.trade_journal),
    path("api/trades/<str:key>/attachments/", views.trade_attachments),
    path("api/trades/<str:key>/attachments/<int:attachment_id>/", views.trade_attachments),
    path("api/executions/", views.executions),
    path("api/days/<str:day>/attachments/<int:attachment_id>/", views.delete_attachment),
    path("api/days/<str:day>/attachments/", views.attachments),
    path("api/attachments/<int:attachment_id>/file/", views.attachment_file),
    path("api/state/", views.state),
    path("api/rules/", views.rules),
    path("api/days/<str:day>/", views.day),
]
