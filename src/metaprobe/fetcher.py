import httpx

class Fetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) MetadataFetcher/1.0'
        }

    async def fetch(self, url):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, headers=self.headers, timeout=10, follow_redirects=True
                )
                
                if response.status_code == 200:
                    return response.text
                
                print(f"Failed to fetch {url}. Status code: {response.status_code}")
                return None
                
            except (httpx.RequestError, httpx.InvalidURL) as e:
                print(f"An error occurred: {e}")
                return None
