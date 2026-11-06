from unittest.mock import patch

from metaprobe.extractor import MetadataExtractor


def test_extract_metadata():
    html = """
    <html>
        <head>
            <title>MetaProbe Test</title>
            <meta name="description" content="Testing metadata">
            <meta property="og:title" content="Open Graph Title">
        </head>
    </html>
    """

    extractor = MetadataExtractor()

    with patch.object(
        extractor.fetcher,
        "fetch",
        return_value=html
    ):
        result = extractor.get_metadata("https://example.com")

    assert result["title"] == "MetaProbe Test"
    assert result["description"] == "Testing metadata"
    assert result["og:title"] == "Open Graph Title"