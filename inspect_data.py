
import os
import sys
from shared.clients.client import APIClient
from shared.config.settings import settings

# Verify settings are loaded
print(f"Base URL: {settings.API_BASE_URL}")

client = APIClient()

print("Fetching Central List (1 item)...")
list_xml = client.fetch_central_list(page=1, num_of_rows=1)
print(f"List XML: {list_xml[:500]}...")

if list_xml:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(list_xml)
        serv_id = root.find(".//servId").text
        print(f"Fetching Detail for {serv_id}...")
        detail_xml = client.fetch_central_detail(serv_id)
        print(f"Detail XML:\n{detail_xml}")
    except Exception as e:
        print(f"Error parsing: {e}")
