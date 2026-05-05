"""Fetch a manifest from a URL or local path.

Returns (manifest_dict, raw_bytes) on success. The raw bytes are returned
alongside the parsed dict so callers can hash them for the install record
without a re-fetch.

Supports:
  * file paths (absolute or relative)
  * file:// URLs
  * http:// and https:// URLs

Anything else raises FetchError. We deliberately do not pull in `requests`
or `httpx`; urllib + json are the entire dependency footprint.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse

from .errors import FetchError

# A reasonable cap on manifest size. Manifests should be small documents —
# anything multi-megabyte is almost certainly an error or an attack surface
# we don't want to load into memory.
MAX_MANIFEST_BYTES = 1_048_576  # 1 MiB
DEFAULT_TIMEOUT_S = 30
USER_AGENT = "install-manifest/0.1.0 (+https://github.com/drknowhow/install-manifest-spec)"


def fetch_manifest(
    url_or_path: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_S,
    max_bytes: int = MAX_MANIFEST_BYTES,
) -> Tuple[dict, bytes]:
    """Fetch and JSON-parse the manifest at the given URL or local path.

    Returns:
        (manifest_dict, raw_bytes)

    Raises:
        FetchError: on network failure, non-2xx response, oversized body,
            invalid JSON, unsupported scheme, or unreadable local file.
    """
    if not isinstance(url_or_path, str) or not url_or_path:
        raise FetchError("manifest URL or path is empty")

    # Detect Windows drive letters (e.g., 'C:\path') before urlparse: it
    # interprets the drive letter as a scheme. Heuristic: a single-letter
    # "scheme" followed by ':\' or ':/' is a local path, not a URL.
    if (
        len(url_or_path) >= 3
        and url_or_path[0].isalpha()
        and url_or_path[1] == ":"
        and url_or_path[2] in ("\\", "/")
    ):
        raw = _fetch_local(url_or_path, urlparse(""), max_bytes=max_bytes)
    else:
        parsed = urlparse(url_or_path)
        scheme = parsed.scheme.lower()
        if scheme in ("", "file"):
            raw = _fetch_local(url_or_path, parsed, max_bytes=max_bytes)
        elif scheme in ("http", "https"):
            raw = _fetch_http(url_or_path, timeout=timeout, max_bytes=max_bytes)
        else:
            raise FetchError(f"unsupported scheme: {parsed.scheme!r}")

    try:
        manifest = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as e:
        raise FetchError(f"manifest is not valid UTF-8: {e}") from e
    except json.JSONDecodeError as e:
        raise FetchError(f"manifest is not valid JSON: {e}") from e

    if not isinstance(manifest, dict):
        raise FetchError(
            f"manifest top-level must be a JSON object, got {type(manifest).__name__}"
        )

    return manifest, raw


def _fetch_local(url_or_path: str, parsed, *, max_bytes: int) -> bytes:
    if parsed.scheme == "file":
        # urlparse gives netloc + path; for cross-platform local paths we
        # use the urllib helper rather than reconstructing by hand.
        from urllib.request import url2pathname
        local_path = Path(url2pathname(parsed.path))
    else:
        local_path = Path(url_or_path)

    try:
        size = local_path.stat().st_size
    except FileNotFoundError as e:
        raise FetchError(f"manifest not found: {local_path}") from e
    except OSError as e:
        raise FetchError(f"cannot stat manifest at {local_path}: {e}") from e

    if size > max_bytes:
        raise FetchError(
            f"manifest at {local_path} is {size} bytes; exceeds limit of {max_bytes}"
        )

    try:
        return local_path.read_bytes()
    except OSError as e:
        raise FetchError(f"cannot read manifest at {local_path}: {e}") from e


def _fetch_http(url: str, *, timeout: float, max_bytes: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            status = getattr(resp, "status", None) or resp.getcode()
            if status is None or not (200 <= int(status) < 300):
                raise FetchError(f"HTTP {status} fetching {url}")

            # Read with a hard cap. urlopen + .read(n) will return up to n
            # bytes; we read max_bytes + 1 and reject if we got more.
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise FetchError(
                    f"manifest at {url} exceeds size limit of {max_bytes} bytes"
                )
            return raw
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code} fetching {url}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise FetchError(f"network error fetching {url}: {e.reason}") from e
    except TimeoutError as e:
        raise FetchError(f"timeout after {timeout}s fetching {url}") from e
