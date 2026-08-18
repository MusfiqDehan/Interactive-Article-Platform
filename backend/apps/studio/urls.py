"""Studio routes (``/api/v1/studio/``).

The whole authoring surface on one page. Two ordering rules are load-bearing
and now visible rather than implied by a router's internal sort:

* ``categories/tree/`` and ``tags/merge/`` precede their ``<slug>/`` patterns,
  or the slug pattern claims the literal segment.
* Every ``articles/<slug>/<verb>/`` route precedes ``articles/<str:slug>/``.
"""

from django.urls import path

from apps.editorial.views import (
    ArticleAuditView,
    ArticleRevisionDetailView,
    ArticleRevisionDiffView,
    ArticleRevisionListView,
    ArticleRevisionRestoreView,
    ArticleScheduleView,
    ArticleSnapshotView,
    ArticleTransitionListView,
    ArticleTransitionView,
    AuditLogListView,
    BulkTransitionView,
    ReviewAssignmentDetailView,
    ReviewAssignmentListView,
    ReviewAssignmentResolveView,
    ReviewCommentDetailView,
    ReviewCommentListView,
    ReviewCommentResolveView,
    ReviewInboxView,
)
from apps.analytics.views import (
    ArticleAnalyticsView,
    BufferHealthView,
    SiteAnalyticsView,
)
from apps.media_library.views import MediaUploadView
from apps.search.views import RebuildIndexView, SearchHealthView
from apps.seo.views import (
    AnalyzeSEOView,
    ArticleSEOView,
    RedirectDetailView,
    RedirectListView,
)
from apps.social.views import (
    CaptionPreviewView,
    PlatformSpecsView,
    SocialAccountConnectView,
    SocialAccountDetailView,
    SocialAccountListView,
    SocialPostDetailView,
    SocialPostListView,
    SocialTargetRetryView,
    SocialTemplateDetailView,
    SocialTemplateListView,
)
from apps.syndication.views import (
    DeliveryDetailView,
    DeliveryListView,
    DeliveryRetryView,
    DestinationDetailView,
    DestinationEnableView,
    DestinationListView,
)
from apps.taxonomy.views import TagDetailView, TagListView, TagMergeView

from .views import (
    StudioApiKeyDetailView,
    StudioApiKeyListView,
    StudioArticleDetailView,
    StudioArticleListView,
    StudioArticlePlacementsView,
    StudioCalendarView,
    StudioCategoryDetailView,
    StudioCategoryListView,
    StudioCategoryMoveView,
    StudioCategoryTreeView,
    StudioMediaDetailView,
    StudioMediaListView,
    StudioMembershipDetailView,
    StudioMembershipListView,
    StudioSiteListView,
    StudioSiteSettingsView,
)

# ---------------------------------------------------------------------------
# Articles. Sub-routes first; the bare `<str:slug>/` catch-all is last.
# ---------------------------------------------------------------------------
article_patterns = [
    path("articles/", StudioArticleListView.as_view(), name="studio-article-list"),
    path(
        "articles/bulk-transition/",
        BulkTransitionView.as_view(),
        name="studio-article-bulk-transition",
    ),
    path(
        "articles/<str:slug>/transition/",
        ArticleTransitionView.as_view(),
        name="studio-article-transition",
    ),
    path(
        "articles/<str:slug>/transitions/",
        ArticleTransitionListView.as_view(),
        name="studio-article-transitions",
    ),
    path(
        "articles/<str:slug>/schedule/",
        ArticleScheduleView.as_view(),
        name="studio-article-schedule",
    ),
    path(
        "articles/<str:slug>/revisions/",
        ArticleRevisionListView.as_view(),
        name="studio-article-revisions",
    ),
    path(
        "articles/<str:slug>/revisions/<int:number>/",
        ArticleRevisionDetailView.as_view(),
        name="studio-article-revision",
    ),
    path(
        "articles/<str:slug>/revisions/<int:number>/diff/",
        ArticleRevisionDiffView.as_view(),
        name="studio-article-revision-diff",
    ),
    path(
        "articles/<str:slug>/revisions/<int:number>/restore/",
        ArticleRevisionRestoreView.as_view(),
        name="studio-article-revision-restore",
    ),
    path(
        "articles/<str:slug>/snapshot/",
        ArticleSnapshotView.as_view(),
        name="studio-article-snapshot",
    ),
    path(
        "articles/<str:slug>/audit/",
        ArticleAuditView.as_view(),
        name="studio-article-audit",
    ),
    path(
        "articles/<str:slug>/placements/",
        StudioArticlePlacementsView.as_view(),
        name="studio-article-placements",
    ),
    path(
        "articles/<str:slug>/seo/",
        ArticleSEOView.as_view(),
        name="studio-article-seo",
    ),
    path(
        "articles/<str:slug>/analyze-seo/",
        AnalyzeSEOView.as_view(),
        name="studio-article-analyze-seo",
    ),
    path(
        "articles/<str:slug>/",
        StudioArticleDetailView.as_view(),
        name="studio-article-detail",
    ),
]

taxonomy_patterns = [
    # `tree/` is a literal that the `<str:slug>/` pattern below would
    # otherwise swallow, so it must come first.
    path(
        "categories/tree/",
        StudioCategoryTreeView.as_view(),
        name="studio-category-tree",
    ),
    path("categories/", StudioCategoryListView.as_view(), name="studio-category-list"),
    path(
        "categories/<str:slug>/move/",
        StudioCategoryMoveView.as_view(),
        name="studio-category-move",
    ),
    path(
        "categories/<str:slug>/",
        StudioCategoryDetailView.as_view(),
        name="studio-category-detail",
    ),
    # Same rule for tags: `merge/` before `<slug>/`.
    path("tags/merge/", TagMergeView.as_view(), name="studio-tag-merge"),
    path("tags/", TagListView.as_view(), name="studio-tag-list"),
    path("tags/<str:slug>/", TagDetailView.as_view(), name="studio-tag-detail"),
]

people_patterns = [
    path("sites/", StudioSiteListView.as_view(), name="studio-site-list"),
    path("people/", StudioMembershipListView.as_view(), name="studio-people-list"),
    path(
        "people/<int:pk>/",
        StudioMembershipDetailView.as_view(),
        name="studio-people-detail",
    ),
]

calendar_patterns = [
    path("calendar/", StudioCalendarView.as_view(), name="studio-calendar"),
]

distribution_patterns = [
    path(
        "destinations/", DestinationListView.as_view(), name="studio-destination-list"
    ),
    path(
        "destinations/<int:pk>/",
        DestinationDetailView.as_view(),
        name="studio-destination-detail",
    ),
    path(
        "destinations/<int:pk>/enable/",
        DestinationEnableView.as_view(),
        name="studio-destination-enable",
    ),
    path("deliveries/", DeliveryListView.as_view(), name="studio-delivery-list"),
    path(
        "deliveries/<int:pk>/", DeliveryDetailView.as_view(), name="studio-delivery-detail"
    ),
    path(
        "deliveries/<int:pk>/retry/",
        DeliveryRetryView.as_view(),
        name="studio-delivery-retry",
    ),
]

media_patterns = [
    # `upload/` before `<int:pk>/` -- the int converter would not match it, but
    # keeping literals first is the rule that holds when a converter changes.
    path("media/upload/", MediaUploadView.as_view(), name="studio-media-upload"),
    path("media/", StudioMediaListView.as_view(), name="studio-media-list"),
    path("media/<int:pk>/", StudioMediaDetailView.as_view(), name="studio-media-detail"),
]

editorial_patterns = [
    path("audit-log/", AuditLogListView.as_view(), name="studio-audit-list"),
    path("reviews/", ReviewAssignmentListView.as_view(), name="studio-review-list"),
    path(
        "reviews/<int:pk>/",
        ReviewAssignmentDetailView.as_view(),
        name="studio-review-detail",
    ),
    path(
        "reviews/<int:pk>/resolve/",
        ReviewAssignmentResolveView.as_view(),
        name="studio-review-resolve",
    ),
    path("comments/", ReviewCommentListView.as_view(), name="studio-comment-list"),
    path(
        "comments/<int:pk>/",
        ReviewCommentDetailView.as_view(),
        name="studio-comment-detail",
    ),
    path(
        "comments/<int:pk>/resolve/",
        ReviewCommentResolveView.as_view(),
        name="studio-comment-resolve",
    ),
    path("review-inbox/", ReviewInboxView.as_view(), name="studio-review-inbox"),
]

settings_patterns = [
    path("settings/", StudioSiteSettingsView.as_view(), name="studio-settings"),
    path("api-keys/", StudioApiKeyListView.as_view(), name="studio-apikey-list"),
    path(
        "api-keys/<int:pk>/",
        StudioApiKeyDetailView.as_view(),
        name="studio-apikey-detail",
    ),
    path("redirects/", RedirectListView.as_view(), name="studio-redirect-list"),
    path(
        "redirects/<int:pk>/",
        RedirectDetailView.as_view(),
        name="studio-redirect-detail",
    ),
]

analytics_patterns = [
    path("analytics/", SiteAnalyticsView.as_view(), name="studio-analytics"),
    path(
        "analytics/buffer/", BufferHealthView.as_view(), name="studio-analytics-buffer"
    ),
    path(
        "analytics/articles/<str:slug>/",
        ArticleAnalyticsView.as_view(),
        name="studio-article-analytics",
    ),
    path("search/health/", SearchHealthView.as_view(), name="studio-search-health"),
    path("search/rebuild/", RebuildIndexView.as_view(), name="studio-search-rebuild"),
]

social_patterns = [
    # Literal segments before the `<int:pk>/` patterns, as everywhere else.
    path(
        "social/platform-specs/",
        PlatformSpecsView.as_view(),
        name="studio-platform-specs",
    ),
    path("social/captions/", CaptionPreviewView.as_view(), name="studio-social-captions"),
    path(
        "social/accounts/connect/",
        SocialAccountConnectView.as_view(),
        name="studio-social-connect",
    ),
    path(
        "social/accounts/", SocialAccountListView.as_view(), name="studio-social-accounts"
    ),
    path(
        "social/accounts/<int:pk>/",
        SocialAccountDetailView.as_view(),
        name="studio-social-account",
    ),
    path(
        "social/templates/",
        SocialTemplateListView.as_view(),
        name="studio-social-templates",
    ),
    path(
        "social/templates/<int:pk>/",
        SocialTemplateDetailView.as_view(),
        name="studio-social-template",
    ),
    path("social/posts/", SocialPostListView.as_view(), name="studio-social-posts"),
    path(
        "social/posts/<int:pk>/",
        SocialPostDetailView.as_view(),
        name="studio-social-post",
    ),
    path(
        "social/targets/<int:pk>/retry/",
        SocialTargetRetryView.as_view(),
        name="studio-social-target-retry",
    ),
]

urlpatterns = [
    *article_patterns,
    *taxonomy_patterns,
    *media_patterns,
    *editorial_patterns,
    *people_patterns,
    *calendar_patterns,
    *distribution_patterns,
    *social_patterns,
    *analytics_patterns,
    *settings_patterns,
]
