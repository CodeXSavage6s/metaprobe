"""Tests for the command line interface (python -m metaprobe / metaprobe)."""

import json
import subprocess
import sys

import httpx
import pytest

#from metaprobe import __version__
from metaprobe.__main__ import main

URL = "https://example.com/"
HTML = (
    "<html><head><title>CLI</title>"
    '<meta name="description" content="d">'
    '<meta property="og:title" content="O"></head></html>'
)
ERROR_JSON = {"error": "Could not retrieve page content."}

# These tests are deliberately synchronous: main() calls asyncio.run() itself.


def test_prints_json_and_exits_zero(respx_mock, capsys):
    respx_mock.get(URL).mock(return_value=httpx.Response(200, text=HTML))
    assert main([URL]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "title": "CLI",
        "open_graph": {"og:title": "O"},
        "twitter_card": {},
        "description": "d",
    }


@pytest.mark.parametrize("status", [404, 500])
def test_http_failure_exits_one_with_valid_json(respx_mock, capsys, status):
    respx_mock.get(URL).mock(return_value=httpx.Response(status))
    assert main([URL]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == ERROR_JSON
    assert str(status) in captured.err


def test_network_failure_exits_one_with_valid_json(respx_mock, capsys):
    respx_mock.get(URL).mock(side_effect=httpx.ConnectError("refused"))
    assert main([URL]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == ERROR_JSON
    assert "refused" in captured.err


def test_malformed_url_exits_one_without_traceback(capsys):
    assert main(["http://example.com:abc/"]) == 1
    assert json.loads(capsys.readouterr().out) == ERROR_JSON


def test_page_with_meta_named_error_is_still_success(respx_mock, capsys):
    html = '<title>T</title><meta name="error" content="x">'
    respx_mock.get(URL).mock(return_value=httpx.Response(200, text=html))
    assert main([URL]) == 0
    assert json.loads(capsys.readouterr().out)["title"] == "T"


def test_non_ascii_output_is_ascii_safe_json(respx_mock, capsys):
    html = "<title>café ✓</title>"
    respx_mock.get(URL).mock(return_value=httpx.Response(200, text=html))
    assert main([URL]) == 0
    raw = capsys.readouterr().out
    assert raw.isascii()
    assert json.loads(raw)["title"] == "café ✓"


def test_stdout_contains_only_json(respx_mock, capsys):
    respx_mock.get(URL).mock(return_value=httpx.Response(200, text=HTML))
    main([URL])
    json.loads(capsys.readouterr().out)  # raises if anything else was printed


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_missing_url_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "url" in capsys.readouterr().err.lower()


def test_python_dash_m_entry_point():
    proc = subprocess.run(
        [sys.executable, "-m", "metaprobe", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    assert __version__ in proc.stdout
