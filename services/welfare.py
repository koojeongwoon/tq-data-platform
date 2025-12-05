import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from api.client import APIClient
from config.settings import settings

class WelfareService:
    def __init__(self):
        self.client = APIClient()

    def _parse_ids_from_xml(self, xml_content, tag_name="servId"):
        if not xml_content:
            return []
        try:
            root = ET.fromstring(xml_content)
            return [elem.text for elem in root.iter(tag_name)]
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
            return []

    def process_central_welfare(self):
        print("\n--- Central Government Welfare Service ---")
        print("Fetching Central List (Page 1)...")
        list_xml = self.client.fetch_central_list(page=1, num_of_rows=500)
        
        if not list_xml:
            print("Failed to fetch Central List.")
            return

        ids = self._parse_ids_from_xml(list_xml, "servId")
        print(f"Found {len(ids)} items in Central List.")
        
        print(f"Fetching Details for {len(ids)} items concurrently...")
        start_time = time.time()
        
        results = []
        # 'thread_name_prefix' helps in debugging by tagging threads
        with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS, thread_name_prefix="CentralFetcher") as executor:
            future_to_id = {executor.submit(self.client.fetch_central_detail, serv_id): serv_id for serv_id in ids}
            
            for future in as_completed(future_to_id):
                serv_id = future_to_id[future]
                try:
                    # Enforce a timeout for each task result to prevent hanging indefinitely
                    data = future.result(timeout=settings.REQUEST_TIMEOUT)
                    if data:
                        results.append(data)
                except TimeoutError:
                    print(f"ID {serv_id} timed out.")
                except Exception as exc:
                    print(f"ID {serv_id} generated an exception: {exc}")
        
        elapsed = time.time() - start_time
        print(f"Fetched {len(results)} details in {elapsed:.2f} seconds.")

    def process_regional_welfare(self):
        print("\n--- Regional Government Welfare Service ---")
        print("Fetching Regional List (Page 1)...")
        list_xml = self.client.fetch_regional_list(page=1, num_of_rows=500)
        
        if not list_xml:
            print("Failed to fetch Regional List.")
            return

        ids = self._parse_ids_from_xml(list_xml, "servId")
        print(f"Found {len(ids)} items in Regional List.")
        
        if not ids:
            return

        print(f"Fetching Details for {len(ids)} items concurrently...")
        start_time = time.time()

        results = []
        with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS, thread_name_prefix="RegionalFetcher") as executor:
            future_to_id = {executor.submit(self.client.fetch_regional_detail, serv_id): serv_id for serv_id in ids}
            
            for future in as_completed(future_to_id):
                serv_id = future_to_id[future]
                try:
                    data = future.result(timeout=settings.REQUEST_TIMEOUT)
                    if data:
                        results.append(data)
                except TimeoutError:
                    print(f"ID {serv_id} timed out.")
                except Exception as exc:
                    print(f"ID {serv_id} generated an exception: {exc}")

        elapsed = time.time() - start_time
        print(f"Fetched {len(results)} details in {elapsed:.2f} seconds.")
