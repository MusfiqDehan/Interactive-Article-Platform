from django.urls import path

from . import views

urlpatterns = [
    path("upload/", views.MediaUploadView.as_view(), name="media-upload"),
    path("", views.MediaListView.as_view(), name="media-list"),
    path("<int:pk>/", views.MediaDetailView.as_view(), name="media-detail"),
]
