"""Social provider implementations.

Importing this package registers every provider. ``apps.SocialConfig.ready()``
does that once at startup, so ``get_provider()`` never has to know which
module a key lives in.
"""

from .base import (  # noqa: F401
    AccountInfo,
    AuthorizationStart,
    Capabilities,
    ProviderAuthError,
    ProviderError,
    ProviderNotReady,
    PublishResult,
    SocialProvider,
)
from .registry import (  # noqa: F401
    get_provider,
    provider_for_key,
    providers_for_platform,
    register,
    registered,
)

# Imported for the side effect of registering. Direct per-platform providers
# arrive in Phase 8; nothing above this line changes when they do.
from . import aggregator  # noqa: F401,E402
from . import direct  # noqa: F401,E402
