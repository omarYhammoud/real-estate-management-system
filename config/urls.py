"""
Root URL configuration.

Each app owns its own urls.py and is included here under its own namespace
and prefix. Add your app's line when you start wiring up views — you should
not need to touch any other app's block.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    path('accounts/', include('apps.accounts.urls')),        # Chaheen
    path('', include('apps.properties.urls')),                # Omar
    path('billing/', include('apps.billing.urls')),           # Waad
    path('operations/', include('apps.operations.urls')),     # Alyousof
    path('', include('apps.finance.urls')),                   # Chaheen (dashboard/reports at root)
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
