"""Welfare policy chunker for semantic search"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional


class WelfareChunker:
    """
    Chunks welfare policy XML data into semantic units for RAG

    Chunk types:
    - basic_info: 서비스명, 요약, 담당부서, 지역, 시행기간
    - eligibility: 지원대상 + 선정기준 ("누가 받을 수 있나요?")
    - benefit: 지원내용 ("무엇을 받을 수 있나요?")
    - application: 신청방법 + 문의처 ("어떻게 신청하나요?")
    """

    CHUNK_TYPES = ["basic_info", "eligibility", "benefit", "application"]

    def __init__(self):
        pass

    def _get_text(self, root: ET.Element, tag: str) -> str:
        """Extract text from XML tag"""
        node = root.find(f".//{tag}")
        return node.text.strip() if node is not None and node.text else ""

    def _get_contacts(self, root: ET.Element) -> List[str]:
        """Extract contact information list"""
        contacts = []
        for contact in root.findall(".//inqplCtadrList"):
            name = contact.find("wlfareInfoReldNm")
            phone = contact.find("wlfareInfoReldCn")
            if name is not None and phone is not None and name.text and phone.text:
                contacts.append(f"{name.text}: {phone.text}")
        return contacts

    def chunk_policy(self, policy_id: str, raw_xml: str) -> List[Dict[str, Any]]:
        """
        Chunk a single welfare policy into semantic units

        Args:
            policy_id: Unique policy ID
            raw_xml: Raw XML string from API

        Returns:
            List of chunk dictionaries with chunk_id, chunk_type, content, metadata
        """
        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError as e:
            return [{"error": f"XML parsing error: {e}", "policy_id": policy_id}]

        chunks = []

        # Extract common fields
        title = self._get_text(root, "servNm")

        # === Chunk 1: Basic Info ===
        basic_metadata = {
            "policy_id": policy_id,
            "title": title,
            "summary": self._get_text(root, "servDgst"),
            "department": self._get_text(root, "bizChrDeptNm"),
            "province": self._get_text(root, "ctpvNm"),
            "city": self._get_text(root, "sggNm"),
            "start_date": self._get_text(root, "enfcBgngYmd"),
            "end_date": self._get_text(root, "enfcEndYmd"),
            "life_cycle": self._get_text(root, "lifeNmArray"),
            "target_type": self._get_text(root, "trgterIndvdlNmArray"),
            "theme": self._get_text(root, "intrsThemaNmArray"),
            "support_cycle": self._get_text(root, "sprtCycNm"),
            "support_type": self._get_text(root, "srvPvsnNm"),
            "last_modified": self._get_text(root, "lastModYmd"),
        }

        basic_content = f"""[{title}]
요약: {basic_metadata['summary']}
담당부서: {basic_metadata['department']}
지역: {basic_metadata['province']} {basic_metadata['city']}
시행기간: {basic_metadata['start_date']} ~ {basic_metadata['end_date']}
생애주기: {basic_metadata['life_cycle']}
대상유형: {basic_metadata['target_type']}
주제: {basic_metadata['theme']}
지원주기: {basic_metadata['support_cycle']}
지원형태: {basic_metadata['support_type']}"""

        chunks.append({
            "chunk_id": f"{policy_id}_basic",
            "chunk_type": "basic_info",
            "policy_id": policy_id,
            "title": title,
            "content": basic_content,
            "metadata": basic_metadata,
        })

        # === Chunk 2: Eligibility ===
        target = self._get_text(root, "sprtTrgtCn")
        criteria = self._get_text(root, "slctCritCn")

        # Deduplicate if same
        if target == criteria:
            eligibility_text = f"지원대상 및 선정기준:\n{target}"
        else:
            eligibility_text = f"지원대상:\n{target}\n\n선정기준:\n{criteria}"

        chunks.append({
            "chunk_id": f"{policy_id}_eligibility",
            "chunk_type": "eligibility",
            "policy_id": policy_id,
            "title": title,
            "content": f"[{title}] - 누가 받을 수 있나요?\n\n{eligibility_text}",
            "metadata": {
                "policy_id": policy_id,
                "target": target,
                "criteria": criteria,
                "province": basic_metadata["province"],
                "city": basic_metadata["city"],
            },
        })

        # === Chunk 3: Benefit ===
        benefit = self._get_text(root, "alwServCn")

        chunks.append({
            "chunk_id": f"{policy_id}_benefit",
            "chunk_type": "benefit",
            "policy_id": policy_id,
            "title": title,
            "content": f"[{title}] - 무엇을 받을 수 있나요?\n\n지원내용:\n{benefit}",
            "metadata": {
                "policy_id": policy_id,
                "benefit": benefit,
                "support_cycle": basic_metadata["support_cycle"],
                "support_type": basic_metadata["support_type"],
                "province": basic_metadata["province"],
                "city": basic_metadata["city"],
            },
        })

        # === Chunk 4: Application ===
        apply_method = self._get_text(root, "aplyMtdCn")
        apply_type = self._get_text(root, "aplyMtdNm")
        contacts = self._get_contacts(root)

        apply_content = f"신청방법: {apply_type}\n\n{apply_method}"
        if contacts:
            apply_content += f"\n\n문의처:\n" + "\n".join(contacts)

        chunks.append({
            "chunk_id": f"{policy_id}_application",
            "chunk_type": "application",
            "policy_id": policy_id,
            "title": title,
            "content": f"[{title}] - 어떻게 신청하나요?\n\n{apply_content}",
            "metadata": {
                "policy_id": policy_id,
                "apply_method": apply_method,
                "apply_type": apply_type,
                "contacts": contacts,
                "province": basic_metadata["province"],
                "city": basic_metadata["city"],
            },
        })

        return chunks

    def chunk_policies(self, policies: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Chunk multiple policies

        Args:
            policies: List of {"policy_id": str, "raw_data": str}

        Returns:
            List of all chunks from all policies
        """
        all_chunks = []
        for policy in policies:
            chunks = self.chunk_policy(policy["policy_id"], policy["raw_data"])
            all_chunks.extend(chunks)
        return all_chunks
