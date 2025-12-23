"""
D1에서 복지 정책 10건을 가져와서 청킹 처리 후 파일로 저장
"""
import sys
import json
import re
import html
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shared.db.d1 import D1Client


def normalize_text(text: str) -> str:
    """텍스트 정규화 (Markdown 친화적, 줄바꿈 최적화)"""
    if not text:
        return ""

    # HTML 엔티티 디코딩
    text = html.unescape(text)

    # 불필요한 특수문자 제거 및 마크다운 리스트로 변환
    text = text.replace('ㅇ ', '- ')
    text = text.replace('• ', '- ')
    text = text.replace('· ', '- ')
    
    # 연속된 공백/줄바꿈 제거
    # 1. 3개 이상의 줄바꿈을 2개로 줄임 (섹션 구분용)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 2. 불필요한 공백 제거
    text = re.sub(r'[ \t]+', ' ', text)

    # 앞뒤 공백 제거
    text = text.strip()

    return text


def normalize_date(date_str: str) -> str:
    """YYYYMMDD → YYYY-MM-DD"""
    if not date_str:
        return ""
    if date_str == "99991231":
        return "상시운영"

    try:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    except (IndexError, ValueError):
        return date_str


def parse_xml_to_dict(xml_string: str) -> Dict:
    """XML을 파싱하여 딕셔너리로 변환"""
    try:
        root = ET.fromstring(xml_string)

        def get_text(elem, tag):
            """XML 요소에서 텍스트 추출"""
            child = elem.find(tag)
            return child.text if child is not None and child.text else ""

        # 연락처 정보 추출
        contact_list = root.find("inqplCtadrList")
        contact_phone = ""
        contact_name = ""
        if contact_list is not None:
            contact_phone = get_text(contact_list, "wlfareInfoReldCn")
            contact_name = get_text(contact_list, "wlfareInfoReldNm")

        # 홈페이지 정보 추출
        homepage_list = root.find("inqplHmpgReldList")
        homepage_url = ""
        if homepage_list is not None:
            homepage_url = get_text(homepage_list, "wlfareInfoReldCn")

        return {
            "serv_id": get_text(root, "servId"),
            "serv_nm": get_text(root, "servNm"),
            "enfc_bgng_ymd": get_text(root, "enfcBgngYmd"),
            "enfc_end_ymd": get_text(root, "enfcEndYmd"),
            "biz_chr_dept_nm": get_text(root, "bizChrDeptNm"),
            "ctpv_nm": get_text(root, "ctpvNm"),
            "sgg_nm": get_text(root, "sggNm"),
            "serv_dgst": get_text(root, "servDgst"),
            "life_nm_array": get_text(root, "lifeNmArray"),
            "trgter_indvdl_nm_array": get_text(root, "trgterIndvdlNmArray"),
            "intrs_thema_nm_array": get_text(root, "intrsThemaNmArray"),
            "sprt_cyc_nm": get_text(root, "sprtCycNm"),
            "srv_pvsn_nm": get_text(root, "srvPvsnNm"),
            "aply_mtd_nm": get_text(root, "aplyMtdNm"),
            "sprt_trgt_cn": get_text(root, "sprtTrgtCn"),
            "slct_crit_cn": get_text(root, "slctCritCn"),
            "alw_serv_cn": get_text(root, "alwServCn"),
            "aply_mtd_cn": get_text(root, "aplyMtdCn"),
            "contact_phone": contact_phone,
            "contact_name": contact_name,
            "homepage_url": homepage_url,
        }
    except ET.ParseError as e:
        print(f"⚠️ XML 파싱 오류: {e}")
        return {}


def extract_metadata(policy: Dict) -> Dict:
    """정책에서 메타데이터 추출 (기존 버전 - 하위 호환)"""
    return {
        "policy_id": policy.get("serv_id", ""),
        "policy_name": policy.get("serv_nm", ""),
        "region_province": policy.get("ctpv_nm", ""),
        "region_city": policy.get("sgg_nm", ""),
        "department": policy.get("biz_chr_dept_nm", ""),
        "life_cycle": [x.strip() for x in policy.get("life_nm_array", "").split(",")] if policy.get("life_nm_array") else [],
        "target_group": [x.strip() for x in policy.get("trgter_indvdl_nm_array", "").split(",")] if policy.get("trgter_indvdl_nm_array") else [],
        "interest_theme": [x.strip() for x in policy.get("intrs_thema_nm_array", "").split(",")] if policy.get("intrs_thema_nm_array") else [],
        "support_type": policy.get("srv_pvsn_nm", ""),
        "support_cycle": policy.get("sprt_cyc_nm", ""),
        "start_date": normalize_date(policy.get("enfc_bgng_ymd", "")),
        "end_date": normalize_date(policy.get("enfc_end_ymd", "")),
    }


def extract_tags_rule_based(policy: Dict) -> List[str]:
    """규칙 기반 태그 추출 (LLM 불필요)"""
    tags = []

    # 대상자 정보
    if policy.get('trgter_indvdl_nm_array'):
        tags.extend([x.strip() for x in policy['trgter_indvdl_nm_array'].split(',') if x.strip()])

    # 생애주기 정보
    if policy.get('life_nm_array'):
        tags.extend([x.strip() for x in policy['life_nm_array'].split(',') if x.strip()])

    # 지원형태
    if policy.get('srv_pvsn_nm'):
        tags.append(policy['srv_pvsn_nm'])

    # 관심사
    if policy.get('intrs_thema_nm_array'):
        tags.extend([x.strip() for x in policy['intrs_thema_nm_array'].split(',') if x.strip()])

    # 지역 정보
    if policy.get('ctpv_nm'):
        tags.append(policy['ctpv_nm'])
    if policy.get('sgg_nm'):
        tags.append(policy['sgg_nm'])

    # 중복 제거 및 빈 문자열 제거
    return list({tag for tag in tags if tag})


def create_optimized_metadata(policy: Dict) -> Dict:
    """최적화된 메타데이터 생성 (중복 최소화)"""
    region_parts = []
    if policy.get('ctpv_nm'):
        region_parts.append(policy['ctpv_nm'])
    if policy.get('sgg_nm'):
        region_parts.append(policy['sgg_nm'])

    return {
        "policy_id": policy.get("serv_id", ""),
        "policy_name": policy.get("serv_nm", ""),
        "region": "_".join(region_parts) if region_parts else "",
        "tags": extract_tags_rule_based(policy),
        "period": f"{normalize_date(policy.get('enfc_bgng_ymd', ''))}~{normalize_date(policy.get('enfc_end_ymd', ''))}"
    }


def create_natural_overview(policy: Dict) -> str:
    """템플릿 기반 자연어 개요 생성 (LLM 불필요)"""
    sentences = []

    # 정책명과 지역
    region_parts = []
    if policy.get('ctpv_nm'):
        region_parts.append(policy['ctpv_nm'])
    if policy.get('sgg_nm'):
        region_parts.append(policy['sgg_nm'])
    region = " ".join(region_parts) if region_parts else "전국"

    support_type = policy.get('srv_pvsn_nm', '지원')
    policy_name = policy.get('serv_nm', '')

    sentences.append(
        f"{policy_name}은(는) {region}에서 시행하는 {support_type} 프로그램입니다."
    )

    # 대상 및 생애주기
    target = policy.get('trgter_indvdl_nm_array', '')
    life_cycle = policy.get('life_nm_array', '')

    if target and life_cycle:
        sentences.append(
            f"이 정책은 {target}을(를) 대상으로 하며, {life_cycle} 생애주기에 적용됩니다."
        )
    elif target:
        sentences.append(f"이 정책은 {target}을(를) 대상으로 합니다.")
    elif life_cycle:
        sentences.append(f"이 정책은 {life_cycle} 생애주기에 적용됩니다.")

    # 간략 설명
    summary = normalize_text(policy.get('serv_dgst', ''))
    if summary:
        sentences.append(summary)

    # 지원 주기
    support_cycle = policy.get('sprt_cyc_nm', '')
    if support_cycle:
        sentences.append(f"지원 주기는 {support_cycle}입니다.")

    # 담당 부서
    department = policy.get('biz_chr_dept_nm', '')
    if department:
        sentences.append(f"담당 부서: {department}")

    return "\n\n".join(sentences)


def create_single_chunk_per_policy(policy: Dict) -> List[Dict]:
    """
    정책당 1개 청크 생성 (Best Practice: Single Doc Strategy)
    
    장점:
    - 문맥 단절 없음: 자격요건과 혜택이 한 번에 보임
    - 검색 로직 단순화: 상위 문서 검색(Parent Retrieval) 불필요
    - 요즘 LLM Context Window가 커서 이 정도 길이는 한 번에 처리하는 게 더 효율적
    """
    policy_id = policy.get('serv_id', '')
    policy_name = policy.get('serv_nm', '')
    
    # 지역 정보
    region_parts = []
    if policy.get('ctpv_nm'): region_parts.append(policy['ctpv_nm'])
    if policy.get('sgg_nm'): region_parts.append(policy['sgg_nm'])
    region_str = " ".join(region_parts) if region_parts else "전국"

    # Context Header (임베딩 성능 향상용)
    header = f"정책명: {policy_name} | 지역: {region_str} | 항목: 전체 정책 통합 정보"

    content_parts = []
    content_parts.append(header)
    content_parts.append("") # 공백 라인

    # 1. 개요
    content_parts.append("## 1. 정책 개요")
    content_parts.append(create_natural_overview(policy))

    # 2. 지원 대상 및 선정 기준
    if policy.get('sprt_trgt_cn') or policy.get('slct_crit_cn'):
        content_parts.append("## 2. 지원 대상 및 기준")
        if policy.get('sprt_trgt_cn'):
            content_parts.append(f"### 지원대상\n{normalize_text(policy['sprt_trgt_cn'])}")
        if policy.get('slct_crit_cn'):
            content_parts.append(f"### 선정기준\n{normalize_text(policy['slct_crit_cn'])}")

    # 3. 지원 내용
    if policy.get('alw_serv_cn'):
        content_parts.append("## 3. 지원 내용")
        content_parts.append(normalize_text(policy['alw_serv_cn']))

    # 4. 신청 방법
    if policy.get('aply_mtd_cn') or policy.get('aply_mtd_nm'):
        content_parts.append("## 4. 신청 방법")
        if policy.get('aply_mtd_nm'):
            content_parts.append(f"- 신청기간/방법: {policy.get('aply_mtd_nm', '')}")
        if policy.get('aply_mtd_cn'):
            content_parts.append(f"- 상세절차:\n{normalize_text(policy['aply_mtd_cn'])}")

    # 5. 문의처 정보
    contact_info = []
    if policy.get('biz_chr_dept_nm'): contact_info.append(f"- 담당부서: {policy.get('biz_chr_dept_nm')}")
    if policy.get('contact_name'): contact_info.append(f"- 담당자: {policy.get('contact_name')}")
    if policy.get('contact_phone'): contact_info.append(f"- 전화번호: {policy.get('contact_phone')}")
    if policy.get('homepage_url'): contact_info.append(f"- 홈페이지: {policy.get('homepage_url')}")

    if contact_info:
        content_parts.append("## 5. 문의처")
        content_parts.append("\n".join(contact_info))

    # 단일 청크 생성
    # 마지막으로 전체 텍스트에 대해 정규화 실행 (중복 줄바꿈 제거)
    final_content = normalize_text("\n\n".join(content_parts))
    
    chunk = {
        "chunk_id": policy_id, # ID도 간결하게 정책 ID로
        "chunk_type": "full_document",
        "content": final_content,
        "metadata": create_optimized_metadata(policy)
    }

    return [chunk]


def fetch_and_chunk_policies():
    """D1에서 10개 정책을 가져와서 청킹 처리"""

    print("D1 클라이언트 초기화 중...")
    d1 = D1Client()

    # welfare_collections 테이블에서 10건 조회
    query = """
    SELECT policy_id, source_type, policy_title, raw_data
    FROM welfare_collections
    LIMIT 10
    """

    print("D1에서 데이터 조회 중...")
    result = d1.execute_query(query)

    if not result or not result.get("success"):
        print("❌ D1 조회 실패")
        return

    try:
        # D1 응답 구조: {"result": [{"results": [...]}], "success": true}
        raw_policies = result.get("result", [{}])[0].get("results", [])

        if not raw_policies:
            print("❌ 데이터가 없습니다.")
            return

        print(f"✅ {len(raw_policies)}개 정책 조회 완료\n")

        # 청킹 처리
        all_chunks = []
        policy_summaries = []

        for raw_policy in raw_policies:
            policy_id = raw_policy.get("policy_id", "")
            policy_title = raw_policy.get("policy_title", "")
            raw_xml = raw_policy.get("raw_data", "")

            print(f"📋 처리 중: {policy_id} - {policy_title}")

            # XML 파싱
            policy = parse_xml_to_dict(raw_xml)
            if not policy:
                print("   ⚠️ XML 파싱 실패, 건너뜀")
                continue

            # Best Practice: Single Chunk
            chunks = create_single_chunk_per_policy(policy)
            all_chunks.extend(chunks)

            # 요약 정보
            policy_summaries.append({
                "policy_id": policy_id,
                "policy_title": policy_title,
                "chunks_count": len(chunks)
            })

            print(f"   ✅ {len(chunks)}개 청크 생성")

        # 결과 저장
        output_dir = project_root / "data"
        output_dir.mkdir(exist_ok=True)

        # 1. 전체 청크 저장
        chunks_path = output_dir / "chunks_output.json"
        with open(chunks_path, 'w', encoding='utf-8') as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=2)
        print(f"\n📄 전체 청크 저장: {chunks_path}")
        print(f"   총 {len(all_chunks)}개 청크")

        # 2. 정책별 요약 저장
        summary_path = output_dir / "chunks_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump({
                "total_policies": len(raw_policies),
                "total_chunks": len(all_chunks),
                "policies": policy_summaries
            }, f, ensure_ascii=False, indent=2)
        print(f"📄 요약 정보 저장: {summary_path}")

        print("\n📊 청킹 통계:")
        print(f"   정책 수: {len(raw_policies)}개")
        print(f"   총 청크 수: {len(all_chunks)}개")
        print(f"   정책당 청크: {len(all_chunks) / len(raw_policies):.1f}개")

        print("\n✅ 청킹 처리 완료 (Best Practices Applied)")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    fetch_and_chunk_policies()
