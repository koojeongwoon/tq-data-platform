import requests
from urllib.parse import unquote
from shared.config.settings import settings

class APIClient:
    def __init__(self):
        self.base_url = settings.API_BASE_URL
        # 여러 API 키 지원 (429 시 로테이션)
        self.api_keys = [unquote(k) for k in settings.API_KEYS] if settings.API_KEYS else []
        self.current_key_index = 0

    @property
    def api_key(self):
        if not self.api_keys:
            return None
        return self.api_keys[self.current_key_index]

    def rotate_key(self):
        """다음 API 키로 전환. 모두 소진 시 False 반환"""
        if len(self.api_keys) <= 1:
            return False
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f"API 키 전환: Key #{self.current_key_index + 1}/{len(self.api_keys)}")
        return True

    def _construct_url(self, endpoint: str) -> str:
        if endpoint.startswith("http"):
            return endpoint
        
        # Remove leading slash from endpoint if base_url has trailing slash, or handle consistently
        base = self.base_url.rstrip("/") if self.base_url else ""
        path = endpoint.lstrip("/")
        return f"{base}/{path}"

    def _get_xml_root(self, url: str, params: dict, retry_on_429: bool = True, _start_key_index: int = None):
        full_url = self._construct_url(url)
        # 현재 키로 params 업데이트
        params = params.copy()
        params["serviceKey"] = self.api_key

        # 시작 키 인덱스 기록 (한 바퀴 돌면 종료하기 위해)
        if _start_key_index is None:
            _start_key_index = self.current_key_index

        try:
            response = requests.get(
                full_url,
                params=params,
                timeout=settings.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.content.decode('utf-8')
        except requests.RequestException as e:
            # 429 에러 시 키 로테이션 후 재시도
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                if retry_on_429 and self.rotate_key():
                    # 한 바퀴 돌아서 원래 키로 돌아왔으면 종료
                    if self.current_key_index == _start_key_index:
                        print("모든 API 키가 rate limit 상태입니다. 수집을 종료합니다.")
                        raise SystemExit(1)
                    print("429 발생, 다른 키로 재시도...")
                    return self._get_xml_root(url, params, retry_on_429=True, _start_key_index=_start_key_index)
                else:
                    print("모든 API 키 소진됨")
                    raise SystemExit(1)
            print(f"Error fetching data from {full_url}: {e}")
            return None

    def fetch_central_list(self, page: int = 1, num_of_rows: int = 10):
        params = {
            "serviceKey": self.api_key,
            "callTp": "L",
            "pageNo": page,
            "numOfRows": num_of_rows,
            "srchKeyCode": "001"
        }
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

