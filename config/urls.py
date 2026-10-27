from django.contrib import admin
from django.urls import include, path
urlpatterns = [path('admin/', admin.site.urls), path('', include('market.urls'))]
admin.site.site_header = '작지의나라 운영 관리'
admin.site.site_title = '작지의나라'
