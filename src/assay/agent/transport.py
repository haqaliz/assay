"""Shared HTTP transport rules for model adapters.

Environment proxies are disabled: a "local" loopback call must not silently become a remote one.
Redirects are refused: a 30x must not forward an Authorization header to another host.
"""

from __future__ import annotations

import urllib.request

MAX_RESPONSE_BYTES = 4_000_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), _NoRedirect()
)


def urlopen_bounded(request: urllib.request.Request) -> bytes:
    with _OPENER.open(request, timeout=60) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("response is too large")
    return data


def redact(text: str, secret: str | None) -> str:
    return text.replace(secret, "***") if secret else text
