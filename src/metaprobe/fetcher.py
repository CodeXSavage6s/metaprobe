import requests

class Fetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) MetadataFetcher/1.0'
        }

    def fetch(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return response.text
            
            print(f"Failed to fetch {url}. Status code: {response.status_code}")
            return None
            
        except requests.RequestException as e:
            print(f"An error occurred: {e}")
            return None
