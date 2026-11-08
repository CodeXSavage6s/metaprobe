"""Tests for metaprobe.extractor.MetadataExtractor.

Layout
------
* Plain tests pin down behaviour that works today (regression safety net).
* ``@pytest.mark.xfail(strict=True)`` tests describe behaviour a published
  library should have but the current code does not. When you fix one, the
  test flips to XPASS and (because of strict mode) fails the run, which is
  your cue to delete the marker.
"""
import inspect
from unittest.mock import AsyncMock

import httpx
import pytest

from metaprobe.extractor import MetadataExtractor

URL = "https://example.com/page"
ERROR_RESULT = {"error": "Could not retrieve page content."}
EMPTY = {"title": None, "open_graph": {}, "twitter_card": {}}


def page(head: str = "") -> str:
    return f"<html><head>{head}</head><body></body></html>"


def meta(name: str, content: str, attr: str = "name") -> str:
    return f'<meta {attr}="{name}" content="{content}">'


@pytest.fixture
def extract():
    """Run get_metadata against canned HTML without touching the network."""

    async def _extract(html):
        extractor = MetadataExtractor()
        extractor.fetcher.fetch = AsyncMock(return_value=html)
        return await extractor.get_metadata(URL)

    return _extract


# --------------------------------------------------------------------------
# API shape
# --------------------------------------------------------------------------


def test_get_metadata_is_a_coroutine_function():
    # Guards the "forgot to await" mistake the old sync tests made.
    assert inspect.iscoroutinefunction(MetadataExtractor().get_metadata)


async def test_fetcher_called_once_with_exact_url():
    extractor = MetadataExtractor()
    extractor.fetcher.fetch = AsyncMock(return_value=page())
    await extractor.get_metadata(URL)
    extractor.fetcher.fetch.assert_awaited_once_with(URL)


async def test_each_extractor_owns_its_fetcher():
    assert MetadataExtractor().fetcher is not MetadataExtractor().fetcher


# --------------------------------------------------------------------------
# Happy path
# --------------------------------------------------------------------------


async def test_full_page(extract):
    html = page(
        "<title>MetaProbe</title>"
        + meta("description", "A library")
        + meta("keywords", "a,b")
        + meta("author", "me")
        + meta("og:title", "OG Title", "property")
        + meta("og:image", "https://example.com/i.png", "property")
        + meta("twitter:card", "summary")
        + meta("twitter:title", "TW Title")
    )
    result = await extract(html)
    assert result == {
        "title": "MetaProbe",
        "open_graph": {
            "og:title": "OG Title",
            "og:image": "https://example.com/i.png",
        },
        "twitter_card": {"twitter:card": "summary", "twitter:title": "TW Title"},
        "description": "A library",
        "keywords": "a,b",
        "author": "me",
    }


async def test_og_and_twitter_keys_do_not_leak_to_top_level(extract):
    result = await extract(
        page(meta("og:title", "x", "property") + meta("twitter:card", "s"))
    )
    assert not any(k.startswith(("og:", "twitter:")) for k in result)


@pytest.mark.parametrize(
    ("tag", "bucket", "key"),
    [
        (meta("og:title", "x", "property"), "open_graph", "og:title"),
        (meta("og:title", "x", "name"), "open_graph", "og:title"),  # name= variant
        (meta("twitter:card", "x", "name"), "twitter_card", "twitter:card"),
        (meta("twitter:card", "x", "property"), "twitter_card", "twitter:card"),
    ],
)
async def test_name_and_property_attributes_both_accepted(extract, tag, bucket, key):
    result = await extract(page(tag))
    assert result[bucket] == {key: "x"}


# --------------------------------------------------------------------------
# <title>
# --------------------------------------------------------------------------


async def test_title_missing_is_none(extract):
    assert (await extract(page(meta("description", "d"))))["title"] is None


async def test_title_surrounding_whitespace_stripped(extract):
    assert (await extract(page("<title>\n   Hello  \n</title>")))["title"] == "Hello"


async def test_title_html_entities_decoded(extract):
    assert (await extract(page("<title>Tom &amp; Jerry</title>")))["title"] == (
        "Tom & Jerry"
    )


async def test_title_unicode(extract):
    assert (await extract(page("<title>日本語 ✓</title>")))["title"] == "日本語 ✓"


async def test_first_title_wins(extract):
    assert (await extract(page("<title>A</title><title>B</title>")))["title"] == "A"


async def test_meta_named_title_does_not_override_real_title(extract):
    result = await extract(page("<title>Real</title>" + meta("title", "Fake")))
    assert result["title"] == "Real"


@pytest.mark.xfail(strict=True, reason="inner whitespace is not collapsed")
async def test_title_inner_whitespace_collapsed(extract):
    assert (await extract(page("<title>Hello \n   World</title>")))["title"] == (
        "Hello World"
    )


@pytest.mark.xfail(strict=True, reason="empty <title> yields '' instead of None")
async def test_empty_title_is_none(extract):
    assert (await extract(page("<title></title>")))["title"] is None


@pytest.mark.xfail(strict=True, reason="soup.find('title') matches <svg><title>")
async def test_svg_title_is_not_the_page_title(extract):
    html = (
        "<html><body><svg><title>icon label</title></svg></body>"
        "<head><title>Page</title></head></html>"
    )
    assert (await extract(html))["title"] == "Page"


# --------------------------------------------------------------------------
# <meta> handling
# --------------------------------------------------------------------------


async def test_meta_content_is_stripped(extract):
    assert (await extract(page(meta("description", "  hi  "))))["description"] == "hi"


@pytest.mark.parametrize(
    "tag",
    [
        '<meta name="description">',  # no content
        '<meta content="orphan">',  # no name/property
        '<meta name="description" content="">',  # empty content
        '<meta charset="utf-8">',
        '<meta http-equiv="refresh" content="0;url=/x">',
        '<meta itemprop="name" content="x">',
        '<link rel="canonical" href="https://example.com/">',
    ],
)
async def test_irrelevant_or_incomplete_tags_ignored(extract, tag):
    assert await extract(page(tag)) == EMPTY


@pytest.mark.parametrize(
    "name", ["organization", "ogg:foo", "twitterfoo", "og", "twitter"]
)
async def test_prefix_match_is_strict(extract, name):
    # Regression: the old check was name.startswith('og'), which swallowed
    # "organization" into open_graph.
    result = await extract(page(meta(name, "v")))
    assert result["open_graph"] == {}
    assert result["twitter_card"] == {}
    assert result[name] == "v"


@pytest.mark.parametrize("reserved", ["title", "open_graph", "twitter_card"])
async def test_reserved_names_cannot_clobber_result_structure(extract, reserved):
    result = await extract(page(meta(reserved, "x")))
    assert result == EMPTY


async def test_duplicate_keys_last_value_wins_currently(extract):
    # Characterisation test: lossy for multi-value tags like og:image.
    result = await extract(
        page(meta("og:image", "a", "property") + meta("og:image", "b", "property"))
    )
    assert result["open_graph"] == {"og:image": "b"}


async def test_many_meta_tags(extract):
    tags = "".join(meta(f"k{i}", f"v{i}") for i in range(5000))
    result = await extract(page(tags))
    assert len(result) == 5003  # 5000 + title/open_graph/twitter_card
    assert result["k4999"] == "v4999"


@pytest.mark.xfail(strict=True, reason="og:/twitter: matching is case-sensitive")
@pytest.mark.parametrize(
    ("tag", "bucket"),
    [
        (meta("OG:Title", "x", "property"), "open_graph"),
        (meta("Twitter:Card", "x"), "twitter_card"),
    ],
)
async def test_prefixes_are_case_insensitive(extract, tag, bucket):
    assert (await extract(page(tag)))[bucket] != {}


@pytest.mark.xfail(strict=True, reason="name wins over property; og data is lost")
async def test_tag_with_both_name_and_property(extract):
    html = page('<meta name="description" property="og:description" content="x">')
    result = await extract(html)
    assert result["open_graph"] == {"og:description": "x"}


@pytest.mark.xfail(strict=True, reason="whitespace-only content stored as ''")
async def test_whitespace_only_content_ignored(extract):
    assert "description" not in await extract(page(meta("description", "   ")))


@pytest.mark.xfail(
    strict=True, reason="in-band 'error' key can collide with a page's own meta"
)
async def test_page_meta_named_error_is_not_mistaken_for_failure(extract):
    result = await extract(page("<title>T</title>" + meta("error", "oops")))
    assert "error" not in result


# --------------------------------------------------------------------------
# Failure paths and hostile input
# --------------------------------------------------------------------------


@pytest.mark.parametrize("fetched", [None, ""])
async def test_no_content_returns_error_dict(extract, fetched):
    assert await extract(fetched) == ERROR_RESULT


@pytest.mark.parametrize("html", ["   ", "<html></html>", "just text, no tags"])
async def test_content_without_metadata_returns_empty_skeleton(extract, html):
    assert await extract(html) == EMPTY


@pytest.mark.parametrize(
    "html",
    ["<<<>>><meta name=", "\x00", "<title>unclosed", "<meta " * 100, "&#xZZ;"],
)
async def test_garbage_html_does_not_raise(extract, html):
    result = await extract(html)
    assert isinstance(result, dict)
    assert "title" in result or result == ERROR_RESULT


async def test_fetcher_exceptions_currently_propagate():
    # Characterisation test: only httpx.RequestError is caught in Fetcher.
    extractor = MetadataExtractor()
    extractor.fetcher.fetch = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        await extractor.get_metadata(URL)


# --------------------------------------------------------------------------
# End to end: real Fetcher + real parser, network mocked at transport level
# --------------------------------------------------------------------------


async def test_end_to_end_success(respx_mock):
    respx_mock.get(URL).mock(
        return_value=httpx.Response(
            200, text=page("<title>E2E</title>" + meta("og:title", "O", "property"))
        )
    )
    result = await MetadataExtractor().get_metadata(URL)
    assert result["title"] == "E2E"
    assert result["open_graph"] == {"og:title": "O"}


@pytest.mark.parametrize("status", [301, 403, 404, 429, 500, 503])
async def test_end_to_end_http_error_gives_error_dict(respx_mock, status):
    respx_mock.get(URL).mock(return_value=httpx.Response(status))
    assert await MetadataExtractor().get_metadata(URL) == ERROR_RESULT


@pytest.mark.parametrize(
    "exc",
    [httpx.ConnectTimeout("t"), httpx.ConnectError("c"), httpx.ReadError("r")],
)
async def test_end_to_end_network_error_gives_error_dict(respx_mock, exc):
    respx_mock.get(URL).mock(side_effect=exc)
    assert await MetadataExtractor().get_metadata(URL) == ERROR_RESULT
