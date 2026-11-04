from unittest.mock import patch, Mock

from metaprobe.fetcher import Fetcher


def test_fetch_success():
    fetcher = Fetcher()

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "<html><title>Test</title></html>"

    with patch("metaprobe.fetcher.requests.get",
               return_value=mock_response):

        result = fetcher.fetch("https://example.com")

    assert result == "<html><title>Test</title></html>"

def test_fetch_not_found():
    fetcher = Fetcher()

    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.text = ""

    with patch("metaprobe.fetcher.requests.get",
               return_value=mock_response):

        result = fetcher.fetch("https://example.com")

    assert result is None