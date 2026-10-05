import httpx

from providers.errors import ProviderError, RetryableProviderError


async def request(method: str, url: str, **kwargs) -> httpx.Response:
    """HTTP call that maps timeouts/5xx to retryable errors and 4xx to permanent ones."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(method, url, **kwargs)
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        raise RetryableProviderError(f"{type(e).__name__}: {e}") from e
    if resp.status_code >= 500:
        raise RetryableProviderError(f"HTTP {resp.status_code}", code=str(resp.status_code))
    if resp.status_code >= 400:
        raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}", code=str(resp.status_code))
    return resp
