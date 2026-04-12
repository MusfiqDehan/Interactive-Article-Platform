from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, viewsets

from common.permissions import IsAdminUser

from .models import Category, SubCategory
from .serializers import CategoryListSerializer, CategorySerializer, SubCategorySerializer


@extend_schema(tags=["Categories"])
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.prefetch_related("subcategories")
    lookup_field = "slug"
    search_fields = ("name", "description")
    filterset_fields = ("is_active",)

    def get_serializer_class(self):
        if self.action == "list":
            return CategoryListSerializer
        return CategorySerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.annotate(article_count=Count("articles"))
        if self.action in ("list", "retrieve") and not (
            self.request.user.is_authenticated and self.request.user.role == "admin"
        ):
            qs = qs.filter(is_active=True)
        return qs


@extend_schema(tags=["Categories"])
class SubCategoryViewSet(viewsets.ModelViewSet):
    queryset = SubCategory.objects.select_related("category")
    search_fields = ("name", "description")
    filterset_fields = ("category", "is_active")

    def get_serializer_class(self):
        return SubCategorySerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in ("list", "retrieve") and not (
            self.request.user.is_authenticated and self.request.user.role == "admin"
        ):
            qs = qs.filter(is_active=True)
        return qs
