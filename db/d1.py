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
            response = requests.post(self.base_url, headers=headers, json={"batch": queries})
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error executing D1 batch: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None

    def init_db(self):
        """
        Creates all necessary tables if they don't exist.
        """
        queries = []
        
        # 1. Raw Collections Table
        queries.append({
            "sql": """
            CREATE TABLE IF NOT EXISTS welfare_collections (
                policy_id TEXT PRIMARY KEY,
                source_type TEXT,
                policy_title TEXT,
                raw_data TEXT,
                collected_at INTEGER
            );
            """,
            "params": []
        })

        # 2. Main Policy Table
        queries.append({
            "sql": """
            CREATE TABLE IF NOT EXISTS t_welfare_policies (
                policy_id TEXT PRIMARY KEY,
                title TEXT,
                ministry TEXT,
                summary TEXT,
                content TEXT,
                url TEXT,
                last_updated INTEGER
            );
            """,
            "params": []
        })

        # 3. Conditions Table
        queries.append({
            "sql": """
            CREATE TABLE IF NOT EXISTS t_welfare_conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id TEXT,
                age_min INTEGER,
                age_max INTEGER,
                gender TEXT,
                region TEXT,
                employment_status TEXT,
                disability_yn TEXT,
                pregnancy_birth_yn TEXT,
                childcare_yn TEXT,
                FOREIGN KEY(policy_id) REFERENCES t_welfare_policies(policy_id)
            );
            """,
            "params": []
        })

        # 4. Categories Table
        queries.append({
            "sql": """
            CREATE TABLE IF NOT EXISTS t_welfare_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id TEXT,
                category_name TEXT,
                FOREIGN KEY(policy_id) REFERENCES t_welfare_policies(policy_id)
            );
            """,
            "params": []
        })

        result = self.execute_batch(queries)
        if result and result.get("success"):
            print("D1: All tables verified/created.")
        else:
            print("D1: Failed to verify/create tables.")

    # Deprecated alias for backward compatibility if needed, but safe to remove if I update calls.
    # I will update the call site in welfare.py next.


    def get_existing_policy_ids(self, source_type: str = None) -> set:
        """
        Returns a set of policy_ids that already exist in the database.
        Optionally filter by source_type ('central' or 'regional').
        """
        if source_type:
            sql = "SELECT policy_id FROM welfare_collections WHERE source_type = ?"
            result = self.execute_query(sql, [source_type])
        else:
            sql = "SELECT policy_id FROM welfare_collections"
            result = self.execute_query(sql)

        if not result or not result.get("success"):
            return set()

        try:
            rows = result.get("result", [{}])[0].get("results", [])
            return {row["policy_id"] for row in rows}
        except (IndexError, KeyError, TypeError):
            return set()

    def fetch_raw_policies(self, limit: int = 1000):
        """
        Fetches raw policy data for processing.
        Returns a list of dicts: [{'policy_id': ..., 'raw_data': ...}, ...]
        """
        sql = "SELECT policy_id, raw_data FROM welfare_collections LIMIT ?"
        result = self.execute_query(sql, [limit])
        
        if not result or not result.get("success"):
            return []

        try:
            return result.get("result", [{}])[0].get("results", [])
        except (IndexError, KeyError, TypeError):
            return []
