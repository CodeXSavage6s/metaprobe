# MetaProbe

A lightweight Python library for fetching webpages and extracting their metadata, including page titles, descriptions, Open Graph and Twitter Card information.

## Installation

```bash
pip install metaprobe
```

## Usage

```python
import asyncio
from metaprobe import MetadataExtractor

async def main():
    extractor = MetadataExtractor()

    metadata = await extractor.get_metadata(
        "https://example.com"
    )

    print(metadata)

if __name__ == "__main__":
    asyncio.run(main())
```

## CLI Usage

You can also use MetaProbe directly from your terminal:

```bash
metaprobe https://example.com
```

## How It Works

MetaProbe is built with Python and uses:

- **HTTPX** – for asynchronous HTTP requests and webpage fetching.
- **BeautifulSoup4** – for parsing HTML and extracting metadata.

The library separates webpage fetching from metadata extraction, making its components easier to maintain and extend.

## Built With

- Python
- HTTPX
- BeautifulSoup4

## License

See the [LICENSE](LICENSE) file for licensing information.

