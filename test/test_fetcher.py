"""Tests for metaprobe.fetcher.Fetcher (network mocked with respx)."""
import httpx
import pytest

from metaprobe.fetcher import Fetcher

URL = "https://example.com/page"
HTML = "<html><title>Test</title></html>"


# --------------------------------------------------------------------------
# Success
# --------------------------------------------------------------------------


async def test_200_returns_body_text(respx_mock):
    respx_mock.get(URL).mock(return_value=httpx.Response(200, text=HTML))
    assert await Fetcher().fetch(URL) == HTML


async def test_200_with_empty_body_returns_empty_string(respx_mock):
    respx_mock.get(URL).mock(return_value=httpx.Response(200, text=""))
    assert await Fetcher().fetch(URL) == ""


async def test_utf8_body_decoded(respx_mock):
    respx_mock.get(URL).mock(
        return_value=httpx.Response(
            200,
            content="<title>café ✓</title>".encode("utf-8"),
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    assert await Fetcher().fetch(URL) == "<title>café ✓</title>"


async def test_declared_latin1_charset_respected(respx_mock):
    respx_mock.get(URL).mock(
        return_value=httpx.Response(
            200,
            content="<title>café</title>".encode("latin-1"),
            headers={"content-type": "text/html; charset=iso-8859-1"},
        )
    )
    assert await Fetcher().fetch(URL) == "<title>café</title>"


async def test_url_with_query_string_requested_verbatim(respx_mock):
    url = "https://example.com/p?a=1&b=two%20words"
    route = respx_mock.get(url).mock(return_value=httpx.Response(200, text=HTML))
    assert await Fetcher().fetch(url) == HTML
    assert route.call_count == 1


# --------------------------------------------------------------------------
# Request shape
# --------------------------------------------------------------------------


async def test_sends_default_user_agent(respx_mock):
    route = respx_mock.get(URL).mock(return_value=httpx.Response(200, text=HTML))
    await Fetcher().fetch(URL)
    ua = route.calls.last.request.headers["user-agent"]
    assert "MetadataFetcher" in ua


async def test_headers_are_per_instance():
    a, b = Fetcher(), Fetcher()
    a.headers["User-Agent"] = "custom"
    assert b.headers["User-Agent"] != "custom"


async def test_mutated_instance_headers_are_sent(respx_mock):
    route = respx_mock.get(URL).mock(return_value=httpx.Response(200, text=HTML))
    fetcher = Fetcher()
    fetcher.headers["User-Agent"] = "custom/1.0"
    await fetcher.fetch(URL)
    assert route.calls.last.request.headers["user-agent"] == "custom/1.0"


async def test_timeout_is_ten_seconds(respx_mock):
    route = respx_mock.get(URL).mock(return_value=httpx.Response(200, text=HTML))
    await Fetcher().fetch(URL)
    timeout = route.calls.last.request.extensions["timeout"]
    assert set(timeout.values()) == {10}


async def test_uses_get_only(respx_mock):
    route = respx_mock.route().mock(return_value=httpx.Response(200, text=HTML))
    await Fetcher().fetch(URL)
    assert route.calls.last.request.method == "GET"


# --------------------------------------------------------------------------
# Failure handling: always None, never raises for transport problems
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status", [201, 204, 301, 302, 400, 401, 403, 404, 410, 429, 500, 502, 503]
)
async def test_non_200_returns_none(respx_mock, status):
    respx_mock.get(URL).mock(return_value=httpx.Response(status, text="body"))
    assert await Fetcher().fetch(URL) is None


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ConnectTimeout("connect timed out"),
        httpx.ReadTimeout("read timed out"),
        httpx.PoolTimeout("pool timed out"),
        httpx.ConnectError("refused"),
        httpx.ReadError("reset"),
        httpx.RemoteProtocolError("bad response"),
        httpx.UnsupportedProtocol("ftp not supported"),
        httpx.TooManyRedirects("loop"),
    ],
)
async def test_request_errors_return_none(respx_mock, exc):
    respx_mock.get(URL).mock(side_effect=exc)
    assert await Fetcher().fetch(URL) is None


async def test_non_httpx_exceptions_are_not_swallowed(respx_mock):
    respx_mock.get(URL).mock(side_effect=RuntimeError("bug"))
    with pytest.raises(RuntimeError):
        await Fetcher().fetch(URL)


async def test_fetcher_is_reusable_after_failure(respx_mock):
    route = respx_mock.get(URL)
    route.side_effect = [httpx.ConnectError("x"), httpx.Response(200, text=HTML)]
    fetcher = Fetcher()
    assert await fetcher.fetch(URL) is None
    assert await fetcher.fetch(URL) == HTML


async def test_concurrent_fetches_are_independent(respx_mock):
    import asyncio

    urls = [f"https://example.com/{i}" for i in range(20)]
    for i, u in enumerate(urls):
        respx_mock.get(u).mock(return_value=httpx.Response(200, text=f"page{i}"))
    fetcher = Fetcher()
    results = await asyncio.gather(*(fetcher.fetch(u) for u in urls))
    assert results == [f"page{i}" for i in range(20)]


# --------------------------------------------------------------------------
# Gaps a published library should close (strict xfail = fix, then delete mark)
# --------------------------------------------------------------------------


@pytest.mark.respx(assert_all_called=False)
@pytest.mark.xfail(
    strict=True,
    reason="httpx does not follow redirects by default (requests did)",
)
async def test_follows_redirects(respx_mock):
    respx_mock.get("http://example.com/").mock(
        return_value=httpx.Response(301, headers={"location": "https://example.com/"})
    )
    respx_mock.get("https://example.com/").mock(
        return_value=httpx.Response(200, text=HTML)
    )
    assert await Fetcher().fetch("http://example.com/") == HTML


@pytest.mark.xfail(strict=True, reason="library code prints instead of logging")
async def test_failures_do_not_print_to_stdout(respx_mock, capsys):
    respx_mock.get(URL).mock(return_value=httpx.Response(500))
    await Fetcher().fetch(URL)
    assert capsys.readouterr().out == ""


@pytest.mark.xfail(strict=True, reason="non-HTML 200 responses are returned as text")
@pytest.mark.parametrize(
    ("content_type", "body"),
    [("application/json", b'{"a": 1}'), ("application/pdf", b"%PDF-1.7 \x00\x01")],
)
async def test_non_html_content_type_returns_none(respx_mock, content_type, body):
    respx_mock.get(URL).mock(
        return_value=httpx.Response(
            200, content=body, headers={"content-type": content_type}
        )
    )
    assert await Fetcher().fetch(URL) is None


@pytest.mark.xfail(
    strict=True, raises=TypeError, reason="timeout/headers are hard-coded"
)
@pytest.mark.parametrize("kwargs", [{"timeout": 3}, {"headers": {"X-A": "b"}}])
def test_constructor_is_configurable(kwargs):
    Fetcher(**kwargs)


@pytest.mark.xfail(
    strict=True, raises=TypeError, reason="no way to inject a shared AsyncClient"
)
async def test_accepts_shared_client():
    async with httpx.AsyncClient() as client:
        Fetcher(client=client)
