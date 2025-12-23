"""
Unit tests for service layer
"""
import pytest
import xml.etree.ElementTree as ET

from app.services.welfare import WelfareService


@pytest.mark.unit
class TestWelfareService:
    """Test WelfareService functionality"""

    def test_parse_ids_from_xml(self, sample_xml_response):
        """Test XML parsing for service IDs"""
        service = WelfareService()
        ids = service._parse_ids_from_xml(sample_xml_response, "servId")
        assert len(ids) > 0
        assert "TEST001" in ids

    def test_parse_ids_empty_xml(self):
        """Test XML parsing with empty content"""
        service = WelfareService()
        ids = service._parse_ids_from_xml("", "servId")
        assert ids == []

    def test_parse_ids_invalid_xml(self):
        """Test XML parsing with invalid XML"""
        service = WelfareService()
        ids = service._parse_ids_from_xml("not valid xml", "servId")
        assert ids == []


@pytest.mark.unit
class TestXMLParsing:
    """Test XML parsing utilities"""

    def test_parse_welfare_policy_xml(self, sample_xml_response):
        """Test parsing welfare policy from XML"""
        root = ET.fromstring(sample_xml_response)
        items = root.findall(".//item")
        assert len(items) == 1

        item = items[0]
        policy_id = item.findtext("servId")
        policy_name = item.findtext("servNm")

        assert policy_id == "TEST001"
        assert policy_name == "테스트 복지 정책"

    def test_parse_empty_fields(self):
        """Test parsing XML with missing fields"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <response>
            <body>
                <items>
                    <item>
                        <servId>TEST001</servId>
                    </item>
                </items>
            </body>
        </response>'''

        root = ET.fromstring(xml)
        item = root.find(".//item")
        policy_name = item.findtext("servNm")

        assert policy_name is None
