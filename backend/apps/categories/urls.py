from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

category_router = DefaultRouter()
category_router.register(r"", views.CategoryViewSet, basename="category")

subcategory_router = DefaultRouter()
subcategory_router.register(r"", views.SubCategoryViewSet, basename="subcategory")

urlpatterns = [
    path("subcategories/", include(subcategory_router.urls)),
    path("", include(category_router.urls)),
]
