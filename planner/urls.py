from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("signup/", views.signup, name="signup"),
    path("export/", views.export, name="export"),
    path("api/state/", views.api_state, name="api_state"),
    path("api/import/", views.api_import, name="api_import"),
    path("api/<str:kind>/", views.api_create, name="api_create"),
    path("api/<str:kind>/<int:pk>/", views.api_item, name="api_item"),
]
