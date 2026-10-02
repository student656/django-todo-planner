from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(extra_context={"allow_signup": settings.ALLOW_SIGNUP}), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("planner.urls")),
]
