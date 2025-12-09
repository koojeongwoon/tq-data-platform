import time
import json
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from api.client import APIClient
from config.settings import settings
from db.d1 import D1Client

class WelfareService:
    def __init__(self):
        self.client = APIClient()
        self.d1 = D1Client()
        self.d1.create_table_if_not_exists()

    def _parse_ids_from_xml(self, xml_content, tag_name="servId"):
        if not xml_content:
            return []
        try:
            root = ET.fromstring(xml_content)
            return [elem.text for elem in root.iter(tag_name)]
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
            return []

    def _extract_text(self, xml_content, tag_name):
        try:
            root = ET.fromstring(xml_content)
            node = root.find(f".//{tag_name}")
            return node.text if node is not None else ""
        except:
            return ""

    def _get_total_count(self, xml_content):
        try:
            root = ET.fromstring(xml_content)
            node = root.find(".//totalCount")
            return int(node.text) if node is not None else 0
        except:
            return 0

    def _save_to_d1_batch(self, items):
        """Batch insert to D1. items = [(serv_id, source, data), ...]"""
        if not items:
            return

        collected_at = int(time.time())
        queries = []

        for serv_id, source, data in items:
            title = self._extract_text(data, "servNm")
            sql = """INSERT INTO welfare_collections (policy_id, source_type, policy_title, raw_data, collected_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(policy_id) DO UPDATE SET
                policy_title=excluded.policy_title,
                raw_data=excluded.raw_data,
                collected_at=excluded.collected_at;"""
            queries.append({"sql": sql, "params": [serv_id, source, title, data, collected_at]})

        self.d1.execute_batch(queries)
        print(f"Batch saved {len(items)} items to D1.")

    def process_central_welfare(self):
        print("\n--- Central Government Welfare Service ---")

        # First, get total count
        num_of_rows = 500
        first_page = self.client.fetch_central_list(page=1, num_of_rows=num_of_rows)
        if not first_page:
            print("Failed to fetch Central List.")
            return

        total_count = self._get_total_count(first_page)
        total_pages = (total_count + num_of_rows - 1) // num_of_rows
        print(f"Total: {total_count} items, {total_pages} pages")

        # Collect IDs from all pages
        all_ids = self._parse_ids_from_xml(first_page, "servId")
        print(f"Page 1: {len(all_ids)} items")

        for page in range(2, total_pages + 1):
            list_xml = self.client.fetch_central_list(page=page, num_of_rows=num_of_rows)
            if list_xml:
                ids = self._parse_ids_from_xml(list_xml, "servId")
                all_ids.extend(ids)
                print(f"Page {page}: {len(ids)} items")
            time.sleep(0.1)

        # Filter out already collected IDs
        existing_ids = self.d1.get_existing_policy_ids("central")
        ids = [id for id in all_ids if id not in existing_ids]
        skipped = len(all_ids) - len(ids)

        if skipped > 0:
            print(f"Skipping {skipped} already collected items.")

        if not ids:
            print("No new items to fetch.")
            return

        print(f"Fetching Details for {len(ids)} new items sequentially (rate limited)...")
        start_time = time.time()

        results = []
        batch = []
        batch_size = 50

        for i, serv_id in enumerate(ids):
            try:
                data = self.client.fetch_central_detail(serv_id)
                if data:
                    results.append(data)
                    batch.append((serv_id, "central", data))

                # Save batch every 50 items
                if len(batch) >= batch_size:
                    self._save_to_d1_batch(batch)
                    batch = []

                if (i + 1) % 50 == 0:
                    print(f"Progress: {i + 1}/{len(ids)}")
                time.sleep(0.1)  # 100ms delay (10 req/sec)
            except Exception as exc:
                print(f"ID {serv_id} error: {exc}")

        # Save remaining items
        if batch:
            self._save_to_d1_batch(batch)

        elapsed = time.time() - start_time
        print(f"Fetched {len(results)} details in {elapsed:.2f} seconds.")

    def process_regional_welfare(self):
        print("\n--- Regional Government Welfare Service ---")

        # First, get total count
        num_of_rows = 500
        first_page = self.client.fetch_regional_list(page=1, num_of_rows=num_of_rows)
        if not first_page:
            print("Failed to fetch Regional List.")
            return

        total_count = self._get_total_count(first_page)
        total_pages = (total_count + num_of_rows - 1) // num_of_rows
        print(f"Total: {total_count} items, {total_pages} pages")

        # Collect IDs from all pages
        all_ids = self._parse_ids_from_xml(first_page, "servId")
        print(f"Page 1: {len(all_ids)} items")

        for page in range(2, total_pages + 1):
            list_xml = self.client.fetch_regional_list(page=page, num_of_rows=num_of_rows)
            if list_xml:
                ids = self._parse_ids_from_xml(list_xml, "servId")
                all_ids.extend(ids)
                print(f"Page {page}: {len(ids)} items")
            time.sleep(0.1)

        # Filter out already collected IDs
        existing_ids = self.d1.get_existing_policy_ids("regional")
        ids = [id for id in all_ids if id not in existing_ids]
        skipped = len(all_ids) - len(ids)

        if skipped > 0:
            print(f"Skipping {skipped} already collected items.")

        if not ids:
            print("No new items to fetch.")
            return

        print(f"Fetching Details for {len(ids)} new items sequentially (rate limited)...")
        start_time = time.time()

        results = []
        batch = []
        batch_size = 50

        for i, serv_id in enumerate(ids):
            try:
                data = self.client.fetch_regional_detail(serv_id)
                if data:
                    results.append(data)
                    batch.append((serv_id, "regional", data))

                # Save batch every 50 items
                if len(batch) >= batch_size:
                    self._save_to_d1_batch(batch)
                    batch = []

                if (i + 1) % 50 == 0:
                    print(f"Progress: {i + 1}/{len(ids)}")
                time.sleep(0.1)  # 100ms delay (10 req/sec)
            except Exception as exc:
                print(f"ID {serv_id} error: {exc}")

        # Save remaining items
        if batch:
            self._save_to_d1_batch(batch)

        elapsed = time.time() - start_time
        print(f"Fetched {len(results)} details in {elapsed:.2f} seconds.")
