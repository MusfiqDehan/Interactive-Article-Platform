from rest_framework.pagination import CursorPagination, PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Legacy /api/* pagination.

    ``page_size = 12`` is a load-bearing contract: nine call sites in the
    current frontend read ``res.data.results || res.data``. Do not change it
    while the legacy surface is alive.
    """

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100


class StudioPagination(PageNumberPagination):
    """Authoring UI pagination -- denser pages than the public site."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


class PublicCursorPagination(CursorPagination):
    """Delivery API pagination.

    Cursor rather than page-number because offsets drift when content is
    published mid-pagination, and because ``OFFSET n`` degrades on large
    tables. Ordering must match an indexed column.
    """

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-published_at"
