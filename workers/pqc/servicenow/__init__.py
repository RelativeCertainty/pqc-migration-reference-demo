"""ServiceNow ``x_pba_pqc`` scoped-app adapter.

The package deliberately does not expose a generic request method.  Callers can
only invoke the allowlisted operations represented by :class:`ServiceNowClient`.
"""

from .client import RequestContext, ServiceNowClient
from .oauth import (
    OAuthAuthorizerError,
    ServiceNowOAuthClientCredentialsAuthorizer,
)
from .transport import (
    AuthenticatedHTTPTransport,
    HTTPRequest,
    HTTPResponse,
    NoRedirectHandler,
    RequestAuthorizer,
    UrllibAuthenticatedTransport,
)

__all__ = [
    "AuthenticatedHTTPTransport",
    "HTTPRequest",
    "HTTPResponse",
    "NoRedirectHandler",
    "OAuthAuthorizerError",
    "RequestAuthorizer",
    "RequestContext",
    "ServiceNowClient",
    "ServiceNowOAuthClientCredentialsAuthorizer",
    "UrllibAuthenticatedTransport",
]
