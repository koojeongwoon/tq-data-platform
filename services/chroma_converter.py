import json
import sys
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

# Add project root to Python path when running as script
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

from db.d1 import D1Client


class ChromaConverter:
    """
    D1에서 복지정책 데이터를 가져와 ChromaDB 저장용 JSON으로 변환
    """

    def __init__(self):
        self.d1 = D1Client()

    def fetch_policies(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        D1에서 복지정책 데이터를 가져옴

        Args:
            limit: 가져올 정책 개수 (기본값: 5)

        Returns:
            List of raw policy data dictionaries
        """
        sql = """
        SELECT policy_id, source_type, policy_title, raw_data, collected_at
        FROM welfare_collections
        LIMIT ?
        """
        result = self.d1.execute_query(sql, [limit])

        if not result or not result.get("success"):
            print("Failed to fetch policies from D1")
            return []

        try:
            policies = result.get("result", [{}])[0].get("results", [])
            print(f"Fetched {len(policies)} policies from D1")
            return policies
        except (IndexError, KeyError, TypeError) as e:
            print(f"Error parsing D1 response: {e}")
            return []

    def _extract_text(self, root: ET.Element, tag_name: str) -> str:
        """XML에서 텍스트 추출"""
        elem = root.find(f".//{tag_name}")
        return elem.text if elem is not None and elem.text else ""

    def _extract_all_texts(self, root: ET.Element, tag_name: str) -> List[str]:
        """XML에서 같은 태그의 모든 텍스트 추출"""
        return [elem.text for elem in root.findall(f".//{tag_name}") if elem.text]

    def parse_xml_to_json(self, policy_id: str, raw_xml: str, source_type: str) -> Optional[Dict[str, Any]]:
        """
        XML 데이터를 ChromaDB용 JSON으로 변환

        ChromaDB 저장 형식:
        {
            "id": "policy_id",
            "document": "전체 텍스트 내용 (검색용)",
            "metadata": {
                "title": "정책명",
                "ministry": "부처명",
                "source_type": "central/regional",
                "category": "카테고리",
                "target": "대상",
                "support_type": "지원유형",
                "url": "URL"
            }
        }
        """
        if not raw_xml:
            return None

        try:
            root = ET.fromstring(raw_xml)

            # 기본 정보 추출
            title = self._extract_text(root, "servNm")
            ministry = self._extract_text(root, "bizChrDeptNm") or self._extract_text(root, "jurMnofNm")
            summary = self._extract_text(root, "servDgst")

            # 대상 정보
            target = self._extract_text(root, "trgterIndvdlNmArray")
            target_detail = self._extract_text(root, "sprtTrgtCn")
            selection_criteria = self._extract_text(root, "slctCritCn")

            # 카테고리 (생애주기)
            life_cycle = self._extract_text(root, "lifeNmArray")
            interest_theme = self._extract_text(root, "intrsThemaNmArray")

            # 지원 정보
            support_content = self._extract_text(root, "alwServCn")  # 지원내용 (상세)
            support_cycle = self._extract_text(root, "sprtCycNm")  # 지원주기
            support_provision = self._extract_text(root, "srvPvsnNm")  # 제공방법
            application_method_type = self._extract_text(root, "aplyMtdNm")  # 신청방법
            application_method_detail = self._extract_text(root, "aplyMtdCn")  # 신청방법 상세

            # URL 및 연락처 정보 (wlfareInfoReldCn과 wlfareInfoReldNm 쌍으로 추출)
            phone = ""
            website = ""

            # 모든 wlfareInfo 관련 요소를 순서대로 읽기
            welfare_info_elements = list(root.iter())
            for i, elem in enumerate(welfare_info_elements):
                if elem.tag == "wlfareInfoDtlCd" and elem.text:
                    detail_code = elem.text
                    # 다음 2개 요소 찾기 (wlfareInfoReldCn, wlfareInfoReldNm)
                    if i + 2 < len(welfare_info_elements):
                        next_elem = welfare_info_elements[i + 1]
                        if detail_code == "010" and next_elem.tag == "wlfareInfoReldCn":
                            phone = next_elem.text or ""
                        elif detail_code == "020" and next_elem.tag == "wlfareInfoReldCn":
                            website = next_elem.text or ""

            # 전체 텍스트 (ChromaDB 검색용 document)
            document_parts = [
                title,
                summary,
                target_detail,
                selection_criteria,
                support_content,
                application_method_detail,
                life_cycle,
                interest_theme
            ]
            document = " ".join([part for part in document_parts if part])

            # ChromaDB 형식으로 변환
            chroma_data = {
                "id": policy_id,
                "document": document,
                "metadata": {
                    "title": title,
                    "ministry": ministry,
                    "source_type": source_type,
                    "category": life_cycle,
                    "interest_theme": interest_theme,
                    "target": target,
                    "target_detail": target_detail,
                    "selection_criteria": selection_criteria,
                    "support_content": support_content,
                    "support_cycle": support_cycle,
                    "support_provision": support_provision,
                    "application_method": application_method_type,
                    "application_method_detail": application_method_detail,
                    "phone": phone,
                    "website": website
                }
            }

            return chroma_data

        except ET.ParseError as e:
            print(f"XML parsing error for policy {policy_id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error parsing policy {policy_id}: {e}")
            return None

    def convert_policies_to_chroma_format(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        D1에서 정책을 가져와 ChromaDB 형식으로 변환

        Args:
            limit: 가져올 정책 개수

        Returns:
            List of ChromaDB-formatted policy dictionaries
        """
        # D1에서 정책 가져오기
        raw_policies = self.fetch_policies(limit)

        if not raw_policies:
            return []

        # XML → JSON 변환
        chroma_documents = []
        for policy in raw_policies:
            policy_id = policy.get("policy_id")
            raw_xml = policy.get("raw_data")
            source_type = policy.get("source_type")

            chroma_data = self.parse_xml_to_json(policy_id, raw_xml, source_type)

            if chroma_data:
                chroma_documents.append(chroma_data)

        print(f"Successfully converted {len(chroma_documents)}/{len(raw_policies)} policies")
        return chroma_documents

    def save_to_json_file(self, output_path: str = "chroma_policies.json", limit: int = 5):
        """
        변환된 데이터를 JSON 파일로 저장

        Args:
            output_path: 저장할 파일 경로
            limit: 가져올 정책 개수
        """
        chroma_documents = self.convert_policies_to_chroma_format(limit)

        if not chroma_documents:
            print("No documents to save")
            return

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chroma_documents, f, ensure_ascii=False, indent=2)

        print(f"Saved {len(chroma_documents)} policies to {output_path}")


def main():
    """Example usage"""
    converter = ChromaConverter()

    # D1에서 5개 정책 가져와서 ChromaDB 형식으로 변환
    chroma_documents = converter.convert_policies_to_chroma_format(limit=5)

    # 결과 출력
    for i, doc in enumerate(chroma_documents, 1):
        print(f"\n=== Policy {i} ===")
        print(f"ID: {doc['id']}")
        print(f"Title: {doc['metadata']['title']}")
        print(f"Ministry: {doc['metadata']['ministry']}")
        print(f"Category: {doc['metadata']['category']}")
        print(f"Document preview: {doc['document'][:200]}...")

    # JSON 파일로 저장
    converter.save_to_json_file("chroma_policies.json", limit=5)


if __name__ == "__main__":
    main()
