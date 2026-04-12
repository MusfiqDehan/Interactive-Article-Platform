from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"", views.CategoryViewSet, basename="category")
router.register(r"subcategories", views.SubCategoryViewSet, basename="subcategory")

urlpatterns = [
    path("", include(router.urls)),
]
