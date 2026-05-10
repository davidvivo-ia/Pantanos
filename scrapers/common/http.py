import logging
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

log = logging.getLogger(__name__)

USER_AGENT = "Pantanos/0.1 (+https://github.com/davidvivo-ia/pantanos) data-aggregation"

_DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def make_client(headers: dict | None = None) -> httpx.Client:
    h = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate, br"}
    if headers:
        h.update(headers)
    return httpx.Client(timeout=_DEFAULT_TIMEOUT, headers=h, follow_redirects=True, http2=False)


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TransportError)),
    reraise=True,
)
def fetch_bytes(client: httpx.Client, url: str, params: dict | None = None) -> bytes:
    r = client.get(url, params=params)
    r.raise_for_status()
    return r.content


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TransportError)),
    reraise=True,
)
def fetch_json(client: httpx.Client, url: str, params: dict | None = None) -> dict | list:
    r = client.get(url, params=params)
    r.raise_for_status()
    return r.json()


def download_to(client: httpx.Client, url: str, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with client.stream("GET", url) as r:
        r.raise_for_status()
        with dst.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=64 * 1024):
                f.write(chunk)
    return dst
