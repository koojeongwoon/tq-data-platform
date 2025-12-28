"""
Cloudflare Workers AI LLM Client
"""
import requests

from shared.config.settings import settings


class CloudflareLLM:
    """Cloudflare Workers AI를 사용하는 LLM 클라이언트"""

    # 사용 가능한 모델들
    MODELS = {
        "qwen-14b": "@cf/qwen/qwen1.5-14b-chat-awq",
        "qwen-7b": "@cf/qwen/qwen1.5-7b-chat-awq",
        "qwq-32b": "@cf/qwen/qwq-32b",  # 추론 모델
        "llama-8b": "@cf/meta/llama-3.1-8b-instruct",
    }

    def __init__(self, model: str = "qwen-14b"):
        self.account_id = settings.CLOUDFLARE_ACCOUNT_ID
        self.api_token = settings.CLOUDFLARE_API_TOKEN
        self.model = self.MODELS.get(model, model)  # 별칭 또는 직접 모델명
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{self.model}"

    def run(self, prompt: str, max_tokens: int = 2048) -> dict:
        """
        프롬프트를 실행하고 응답을 반환

        Args:
            prompt: 실행할 프롬프트
            max_tokens: 최대 토큰 수

        Returns:
            {"response": "...", "success": True/False}
        """
        if not self.account_id or not self.api_token:
            return {"response": "", "success": False, "error": "Missing Cloudflare credentials"}

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                result = data.get("result", {})
                return {
                    "response": result.get("response", ""),
                    "success": True
                }
            else:
                return {
                    "response": "",
                    "success": False,
                    "error": data.get("errors", [])
                }

        except requests.Timeout:
            return {"response": "", "success": False, "error": "Request timeout"}
        except requests.RequestException as e:
            return {"response": "", "success": False, "error": str(e)}
