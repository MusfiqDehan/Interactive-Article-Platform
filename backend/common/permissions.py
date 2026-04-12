from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminUser(BasePermission):
    """Allow access only to admin users."""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == "admin"


class IsAdminOrAuthor(BasePermission):
    """Allow access to admin or author users."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ("admin", "author")
        )


class IsAuthorOrReadOnly(BasePermission):
    """Allow read-only access to all, write access only to the author of the object."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.author == request.user or request.user.role == "admin"


class IsOwnerOrAdmin(BasePermission):
    """Allow access only to object owner or admin."""

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin":
            return True
        if hasattr(obj, "author"):
            return obj.author == request.user
        if hasattr(obj, "uploaded_by"):
            return obj.uploaded_by == request.user
        return False
