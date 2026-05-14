from django.urls import path
from . import views

app_name = 'dashboards'

urlpatterns = [
    path('', views.executivo, name='executivo'),
    path('operacional/', views.operacional, name='operacional'),
    path('solicitacoes-item/', views.solicitacoes_item, name='solicitacoes_item'),
    path('api/executivo/', views.executivo_api, name='executivo_api'),
    path('api/operacional/', views.operacional_api, name='operacional_api'),
]
