import requests
import json
from config.settings import settings

class D1Client:
    def __init__(self):
        self.account_id = settings.CLOUDFLARE_ACCOUNT_ID
        self.api_token = settings.CLOUDFLARE_API_TOKEN
        self.database_id = settings.CLOUDFLARE_D1_DB_ID
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/d1/database/{self.database_id}/query"

    def execute_query(self, sql: str, params: list = None):
        """
        Executes a SQL query against Cloudflare D1.
        """
        if not self.account_id or not self.api_token or not self.database_id:
            print("Missing Cloudflare credentials. Skipping D1 execution.")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "sql": sql,
            "params": params or []
        }

        try:
            response = requests.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error executing D1 query: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None

    def execute_batch(self, queries: list):
        """
        Execute multiple SQL queries in one request.
        queries = [{"sql": "...", "params": [...]}, ...]
        """
        if not self.account_id or not self.api_token or not self.database_id:
            print("Missing Cloudflare credentials. Skipping D1 execution.")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(self.base_url, headers=headers, json=queries)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error executing D1 batch: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None

    def create_table_if_not_exists(self):
        """
        Creates the welfare_collections table if it doesn't exist.
        """
        sql = """
        CREATE TABLE IF NOT EXISTS welfare_collections (
            policy_id TEXT PRIMARY KEY,
            source_type TEXT,
            policy_title TEXT,
            raw_data TEXT,
            collected_at INTEGER
        );
        """
        result = self.execute_query(sql)
        if result and result.get("success"):
            print("D1: Table 'welfare_collections' verified/created.")
        else:
            print("D1: Failed to verify/create table.")
