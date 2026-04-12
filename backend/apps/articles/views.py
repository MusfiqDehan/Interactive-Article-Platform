from django.db.models import F
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import IsAdminOrAuthor, IsAuthorOrReadOnly

from .models import Article
from .serializers import ArticleCreateUpdateSerializer, ArticleDetailSerializer, ArticleListSerializer


@extend_schema(tags=["Articles"])
class ArticleViewSet(viewsets.ModelViewSet):
    lookup_field = "slug"
    search_fields = ("title", "excerpt")
    filterset_fields = ("status", "category", "subcategory", "author", "is_featured")
    ordering_fields = ("published_at", "created_at", "views_count", "title")

    def get_serializer_class(self):
        if self.action == "list":
            return ArticleListSerializer
        if self.action == "retrieve":
            return ArticleDetailSerializer
        return ArticleCreateUpdateSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve", "increment_views"):
            return [permissions.AllowAny()]
        if self.action == "create":
            return [IsAdminOrAuthor()]
        return [IsAuthorOrReadOnly()]

    def get_queryset(self):
        qs = Article.objects.select_related("author", "category", "subcategory")

        # Non-admin users only see published articles in list/retrieve
        if self.action in ("list", "retrieve"):
            user = self.request.user
            if not user.is_authenticated or user.role == "reader":
                qs = qs.filter(status="published")
            elif user.role == "author":
                # Authors see published + their own drafts
                from django.db.models import Q
                qs = qs.filter(Q(status="published") | Q(author=user))

        return qs

    @action(detail=True, methods=["post"], url_path="view")
    def increment_views(self, request, slug=None):
        Article.objects.filter(slug=slug).update(views_count=F("views_count") + 1)
        return Response({"detail": "View count incremented."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="my-articles")
    def my_articles(self, request):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        qs = Article.objects.filter(author=request.user).select_related("category")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ArticleListSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = ArticleListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="featured")
    def featured(self, request):
        qs = Article.objects.filter(status="published", is_featured=True).select_related("author", "category")[:6]
        serializer = ArticleListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        if not request.user.is_authenticated or request.user.role not in ("admin", "author"):
            return Response(status=status.HTTP_403_FORBIDDEN)

        from django.contrib.auth import get_user_model
        from apps.categories.models import Category

        User = get_user_model()
        base_qs = Article.objects.all()
        if request.user.role == "author":
            base_qs = base_qs.filter(author=request.user)

        return Response({
            "total_articles": base_qs.count(),
            "published_articles": base_qs.filter(status="published").count(),
            "draft_articles": base_qs.filter(status="draft").count(),
            "total_views": sum(base_qs.values_list("views_count", flat=True)),
            "total_categories": Category.objects.filter(is_active=True).count(),
            "total_users": User.objects.count() if request.user.role == "admin" else None,
        })
