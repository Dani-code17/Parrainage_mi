from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('inscription/', views.inscription_view, name='inscription'),
    path('connexion/', views.connexion_view, name='login'),
    path('deconnexion/', views.deconnexion_view, name='logout'),
    path('quiz/', views.quiz_view, name='quiz'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('teasing/', views.teasing_view, name='teasing'),
    path('revelation/', views.revelation_view, name='revelation'),
    path('mini-jeu/', views.mini_jeu, name='mini_jeu'),
    path('ma-photo/', views.photo_view, name='photo'),
]
