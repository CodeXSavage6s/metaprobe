from bs4 import BeautifulSoup
from .fetcher import Fetcher

class MetadataExtractor:
    def __init__(self):
        self.fetcher = Fetcher()

    def get_metadata(self, url):
        
        html_content = self.fetcher.fetch(url)
        
        if not html_content:
            return {"error": "Could not retrieve page content."}

        soup = BeautifulSoup(html_content, 'html.parser')
        metadata = {
          'title': None,
          'open_graph': {},
          'twitter_card': {}
        }

        title_tag = soup.find('title')
        metadata['title'] = title_tag.string.strip() if title_tag and title_tag.string else None

        for tag in soup.find_all('meta'):
            name = tag.get('name') or tag.get('property')
            content = tag.get('content')
            if name and content:
              if name.startswith('og'):
                metadata['open_graph'][name] = content.strip()
              elif name.startswith('twitter:'):
                metadata['twitter_card'][name] = content.strip()
              else:
                metadata[name] = content.strip()
                

        
        return metadata

