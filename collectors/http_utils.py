"""Minimal retrying HTTP GET using the Python standard library only."""
import json
import time
import urllib.request
import urllib.error

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (PollenSentinel; +https://github.com/pollen-sentinel) pollen-monitor/1.0",
    "Accept": "application/json,text/javascript,*/*",
}


def http_get(url, extra_headers=None, timeout=20, retries=3, backoff=1.5):
    """GET a URL with retries; returns decoded text. Raises after exhausting retries."""
    headers = dict(DEFAULT_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    last_err = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            # The pollen endpoint is utf-8; Open-Meteo is always utf-8.
            return raw.decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise RuntimeError("GET failed after %d attempts: %s (%s)" % (retries, url, last_err))


def http_json(url, extra_headers=None, timeout=20, retries=3):
    return json.loads(http_get(url, extra_headers, timeout, retries))
