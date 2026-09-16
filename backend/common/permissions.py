from rest_framework.permissions import SAFE_METHODS, BasePermission


_MISSING = object()


def user_role(user):
    """Return a user's role, or ``""`` for anonymous/None.

    ``AnonymousUser`` has no ``role`` attribute, so reading it directly raises
    AttributeError and surfaces as a 500 rather than a 401/403. Every role check
    in this module goes through here.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return ""
    return getattr(user, "role", "") or ""


def is_admin(user):
    return user_role(user) == "admin"


def site_membership(request):
    """The caller's membership of ``request.site``, cached on the request.

    HasSiteRole, article scoping and the editorial state machine all need this
    row. Without a request-local cache they each issue the same SELECT, which
    on a studio page that fans out to several endpoints is wasted work -- and
    a place the answers can disagree if a membership changes mid-request.
    """
    cached = getattr(request, "_site_membership", _MISSING)
    if cached is not _MISSING:
        return cached

    site = getattr(request, "site", None)
    user = getattr(request, "user", None)
    if site is None or not getattr(user, "is_authenticated", False):
        request._site_membership = None
        return None

    from apps.tenancy.models import SiteMembership

    membership = (
        SiteMembership.objects.filter(site=site, user=user)
        .only("id", "role", "site_id", "user_id")
        .first()
    )
    request._site_membership = membership
    return membership


def view_required_site_role(view) -> str:
    """Minimum site role for this view.

    Defaults to ``author`` so a forgotten declaration fails closed (studio
    writers), not open (any viewer). Per-method ``@property`` declarations
    resolve here because ``getattr`` on the instance returns the computed
    string.
    """
    value = getattr(view, "required_site_role", "author")
    return value if isinstance(value, str) else "author"


class IsAdminUser(BasePermission):
    """Allow access only to admin users."""

    def has_permission(self, request, view):
        return is_admin(request.user)


class IsAdminOrAuthor(BasePermission):
    """Allow access to admin or author users."""

    def has_permission(self, request, view):
        return user_role(request.user) in ("admin", "author")


class IsAuthorOrReadOnly(BasePermission):
    """Read-only for everyone; writes only for the object's author or an admin."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if not getattr(request.user, "is_authenticated", False):
            return False
        return obj.author == request.user or is_admin(request.user)


class HasValidApiKey(BasePermission):
    """Require a valid ``X-API-Key`` resolving to an active site.

    The key is resolved by TenantResolutionMiddleware, which sets
    ``request.api_key``/``request.api_scopes``. Views declare the scope they
    need via ``required_scope``.
    """

    message = "A valid X-API-Key header is required."

    def has_permission(self, request, view):
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return False
        required = getattr(view, "required_scope", None)
        if required and required not in getattr(request, "api_scopes", []):
            return False
        return True


class HasSiteRole(BasePermission):
    """Require membership of ``request.site`` at or above a minimum role.

    Global admins bypass the check. Views set ``required_site_role``; the
    default of ``author`` means "can work in the studio", not merely view it.
    """

    ROLE_ORDER = {"viewer": 0, "author": 1, "editor": 2, "owner": 3}
    message = "You do not have access to this site."

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False
        if is_admin(user):
            return True

        membership = site_membership(request)
        if membership is None:
            return False

        required = view_required_site_role(view)
        return self.ROLE_ORDER.get(membership.role, -1) >= self.ROLE_ORDER.get(required, 0)


class CanEditSiteArticle(BasePermission):
    """Object-level write guard for articles.

    HasSiteRole is view-level: an ``author`` membership is enough to *reach*
    the endpoint. Without this, that author could PATCH another author's
    published article by slug -- the list hides others' drafts, but live
    pieces are intentionally visible, and visibility is not edit rights.
    Editors and owners may edit anyone's work on the site.
    """

    message = "You may only edit articles you authored."

    def has_permission(self, request, view):
        return bool(getattr(request.user, "is_authenticated", False))

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if not hasattr(obj, "author_id"):
            return True
        if is_admin(request.user):
            return True
        membership = site_membership(request)
        role = membership.role if membership else ""
        if HasSiteRole.ROLE_ORDER.get(role, -1) >= HasSiteRole.ROLE_ORDER["editor"]:
            return True
        return obj.author_id == getattr(request.user, "pk", None)


class IsOwnerOrAdmin(BasePermission):
    """Allow access only to the object's owner or an admin."""

    def has_permission(self, request, view):
        # Object-level checks below dereference request.user, so reject
        # anonymous callers here rather than letting them reach the object.
        return bool(getattr(request.user, "is_authenticated", False))

    def has_object_permission(self, request, view, obj):
        if is_admin(request.user):
            return True
        if hasattr(obj, "author"):
            return obj.author == request.user
        if hasattr(obj, "uploaded_by"):
            return obj.uploaded_by == request.user
        return False
