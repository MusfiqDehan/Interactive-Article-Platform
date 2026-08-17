"""Public delivery routes (``/api/v1/public/``).

Every path is declared. `articles/slugs/` and `articles/featured/` come before
`articles/<str:slug>/` so the slug pattern cannot claim them -- with a router
these were `@action(detail=False)` decorators whose precedence you had to know
the router's sorting rules to predict.
"""

from django.urls import path

from apps.analytics.views import EventIngestView
from apps.search.views import PublicSearchView, SearchTokenView

from .views import (
    PublicArticleDetailView,
    PublicArticleListView,
    PublicArticleSlugsView,
    PublicCategoryDetailView,
    PublicCategoryListView,
    PublicFeaturedArticlesView,
    PublicHealthView,
    PublicRedirectsView,
    PublicRelatedArticlesView,
    PublicSitemapIndexView,
    PublicSitemapShardView,
    PublicSiteView,
    PublicTagDetailView,
    PublicTagListView,
)

urlpatterns = [
    # Articles
    path("articles/", PublicArticleListView.as_view(), name="public-article-list"),
    path(
        "articles/slugs/",
        PublicArticleSlugsView.as_view(),
        name="public-article-slugs",
    ),
    path(
        "articles/featured/",
        PublicFeaturedArticlesView.as_view(),
        name="public-article-featured",
    ),
    path(
        "articles/<str:slug>/",
        PublicArticleDetailView.as_view(),
        name="public-article-detail",
    ),
    path(
        "articles/<str:slug>/related/",
        PublicRelatedArticlesView.as_view(),
        name="public-article-related",
    ),
    # Taxonomy
    path("categories/", PublicCategoryListView.as_view(), name="public-category-list"),
    path(
        "categories/<str:slug>/",
        PublicCategoryDetailView.as_view(),
        name="public-category-detail",
    ),
    path("tags/", PublicTagListView.as_view(), name="public-tag-list"),
    path("tags/<str:slug>/", PublicTagDetailView.as_view(), name="public-tag-detail"),
    # Site-level
    path("site/", PublicSiteView.as_view(), name="public-site"),
    path("redirects/", PublicRedirectsView.as_view(), name="public-redirects"),
    path(
        "sitemap-index/",
        PublicSitemapIndexView.as_view(),
        name="public-sitemap-index",
    ),
    path(
        "sitemap/<int:index>/",
        PublicSitemapShardView.as_view(),
        name="public-sitemap-shard",
    ),
    # Search. `token/` before the bare `search/` is not required by the
    # resolver, but keeping literals first is the rule everywhere else.
    path("search/token/", SearchTokenView.as_view(), name="public-search-token"),
    path("search/", PublicSearchView.as_view(), name="public-search"),
    # Analytics beacon.
    path("events/", EventIngestView.as_view(), name="public-events"),
    path("health/", PublicHealthView.as_view(), name="public-health"),
]
