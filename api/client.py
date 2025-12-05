import requests
from config.settings import settings

class APIClient:
    def __init__(self):
        # self.base_url is no longer used as we have specific URLs for each endpoint
        self.api_key = settings.API_KEY

    def _get_xml_root(self, url: str, params: dict):
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            # The API returns XML, so we need to parse it
            # We can return the raw content or parse it here. 
            # For now, let's return the text and parse in the specific methods or helper
            return response.content
        except requests.RequestException as e:
            print(f"Error fetching data from {url}: {e}")
            return None

    def fetch_central_list(self, page: int = 1, num_of_rows: int = 10):
        params = {
            "serviceKey": self.api_key,
            "callTp": "L",
            "pageNo": page,
            "numOfRows": num_of_rows
        }
        # Note: The API key in .env might need decoding if it's already encoded, 
        # or encoding if it's raw. usually requests handles encoding, but public data portal keys 
        # often come pre-encoded. If it fails, we might need to use unquote.
        
        return self._get_xml_root(settings.CENTRAL_LIST_URL, params)

    def fetch_central_detail(self, serv_id: str):
        params = {
            "serviceKey": self.api_key,
            "callTp": "D",
            "servId": serv_id
        }
        return self._get_xml_root(settings.CENTRAL_DETAILED_URL, params)

    def fetch_regional_list(self, page: int = 1, num_of_rows: int = 10):
        params = {
            "serviceKey": self.api_key,
            "pageNo": page,
            "numOfRows": num_of_rows
        }
        return self._get_xml_root(settings.REGIONAL_LIST_URL, params)

    def fetch_regional_detail(self, serv_id: str):
        params = {
            "serviceKey": self.api_key,
            "servId": serv_id
        }
        return self._get_xml_root(settings.REGIONAL_DETAILED_URL, params)

