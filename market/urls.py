from django.contrib.auth import views as auth
from django.urls import path
from . import views
urlpatterns = [
    path('', views.home, name='home'),
    path('health/', views.health, name='health'),
    path('guide/', views.guide, name='guide'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.ThrottledLoginView.as_view(), name='login'),
    path('logout/', auth.LogoutView.as_view(), name='logout'),
    path('account/', views.account, name='account'),
    path('account/password/', auth.PasswordChangeView.as_view(template_name='market/password.html', success_url='/account/'), name='password'),
    path('mine/', views.mine, name='mine'),
    path('requests/new/', views.listing_create, name='create'),
    path('requests/<int:pk>/', views.detail, name='detail'),
    path('requests/<int:pk>/edit/', views.listing_edit, name='edit'),
    path('requests/<int:pk>/delete/', views.listing_delete, name='delete'),
    path('requests/<int:pk>/offer/', views.offer_edit, name='offer'),
    path('requests/<int:pk>/offers/<int:offer_id>/withdraw/', views.offer_withdraw, name='withdraw'),
    path('requests/<int:pk>/offers/<int:offer_id>/select/', views.select_offer, name='select'),
    path('requests/<int:pk>/status/', views.change_status, name='status'),
    path('requests/<int:pk>/report/', views.report, name='report'),
    path('operations/reports/', views.moderation, name='moderation'),
    path('operations/reports/<int:pk>/', views.moderate, name='moderate'),
]
