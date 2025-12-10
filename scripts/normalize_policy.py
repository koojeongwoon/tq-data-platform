"""
XML to JSON 정규화 모듈
복지 정책 raw XML을 정규화된 JSON으로 변환 및 LLM 요약 생성
"""
import xmltodict
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


def to_list(value):
    """단일 값이나 None을 리스트로 변환"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def parse_life_cycle(value: str) -> list:
    """생애주기 문자열을 리스트로 파싱 (예: '청년, 중장년, 노년')"""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def parse_policy_xml(xml_text: str) -> dict:
    """XML 텍스트를 정규화된 JSON 구조로 변환 (D1 welfare_policy 테이블 호환)"""
    data = xmltodict.parse(xml_text)

    root = data.get("wantedDtl", {})

    def extract_list(field):
        """리스트 필드 추출 (XML이 단일 항목을 리스트로 안 만들 수 있음)"""
        items = root.get(field)
        if not items:
            return []
        return to_list(items)

    # 연락처 리스트에서 첫 번째 값 추출
    def extract_first_contact(field, content_key="wlfareInfoReldCn"):
        items = extract_list(field)
        for item in items:
            if isinstance(item, dict) and item.get(content_key):
                return item.get(content_key)
        return None

    # 법률 리스트 추출 (이름만)
    def extract_law_names(field):
        items = extract_list(field)
        result = []
        for item in items:
            if isinstance(item, dict) and item.get("wlfareInfoReldNm"):
                result.append(item.get("wlfareInfoReldNm"))
        return result

    # 지원대상 내용에서 연령 정보 추출 시도
    target_content = root.get("sprtTrgtCn") or ""
    selection_criteria = root.get("slctCritCn") or ""

    normalized = {
        "serviceId": root.get("servId"),
        "serviceName": root.get("servNm"),
        "summary": root.get("servDgst"),  # 서비스 요약

        # 카테고리 (D1 호환 필드명)
        "category": {
            "lifeArray": parse_life_cycle(root.get("lifeNmArray")),
            "targetArray": parse_life_cycle(root.get("trgterIndvdlNmArray")),
            "themeArray": parse_life_cycle(root.get("intrsThemaNmArray"))
        },

        # 지역 (D1 호환 필드명)
        "region": {
            "sido": root.get("ctpvNm"),  # 시도명
            "sigungu": root.get("sggNm")  # 시군구명
        },

        # 주관기관
        "provider": {
            "orgName": root.get("bizChrDeptNm") or root.get("jurMnofNm")
        },

        # 지원 혜택
        "benefit": {
            "type": root.get("srvPvsnNm"),  # 제공유형명 (현금지급, 감면 등)
            "cycle": root.get("sprtCycNm"),  # 지원주기명
            "content": root.get("alwServCn"),  # 급여서비스 내용
            "amountSummary": None  # LLM이 채울 예정
        },

        # 자격조건
        "conditions": {
            "target": target_content,  # 지원대상 내용
            "selectionCriteria": selection_criteria,  # 선정기준
            "age": {
                "min": None,
                "max": None
            },
            "incomeSummary": None,  # LLM이 채울 예정
            "targetSummary": None,  # LLM이 채울 예정
            "regionSummary": None,  # LLM이 채울 예정
            "exclusions": None  # LLM이 채울 예정
        },

        # 신청 정보
        "apply": {
            "method": root.get("aplyMtdNm"),  # 신청방법명
            "process": root.get("aplyMtdCn")  # 신청방법 상세
        },

        # 연락처 (D1 호환: 첫 번째 값만)
        "contact": {
            "phone": extract_first_contact("inqplCtadrList"),
            "homepage": extract_first_contact("inqplHmpgReldList")
        },

        # 법령 (이름 리스트)
        "law": extract_law_names("baslawList"),

        # 메타 정보
        "effectivePeriod": {
            "start": root.get("enfcBgngYmd"),
            "end": root.get("enfcEndYmd")
        },
        "lastModified": root.get("lastModYmd"),
        "viewCount": root.get("inqNum"),

    }

    return normalized


def merge_policy_summaries(policy: dict, summaries: dict) -> dict:
    """
    정규화된 정책 JSON에 LLM 요약 정보를 병합합니다.

    Args:
        policy: parse_policy_xml로 생성된 정규화 정책 JSON
        summaries: generate_policy_summaries로 생성된 LLM 요약

    Returns:
        요약 정보가 병합된 정책 JSON
    """
    policy["short_summary"] = summaries.get("short_summary")
    policy["normalized_summary"] = summaries.get("normalized_summary")
    policy["long_summary"] = summaries.get("long_summary")
    policy["exclusion_summary"] = summaries.get("exclusion_summary")
    policy["embedding_text"] = summaries.get("embedding_text")
    return policy


def build_welfare_policy_upsert(policy: dict) -> tuple:
    """
    정규화된 정책 JSON(dict)을 받아서
    D1(welfare_policy 테이블)용 UPSERT SQL + 파라미터 튜플을 생성합니다.

    Args:
        policy: merge_policy_summaries로 요약이 병합된 정책 JSON

    Returns:
        (sql, params) 튜플
    """
    category = policy.get("category", {}) or {}
    region = policy.get("region", {}) or {}
    provider = policy.get("provider", {}) or {}
    conditions = policy.get("conditions", {}) or {}
    benefit = policy.get("benefit", {}) or {}
    contact = policy.get("contact", {}) or {}

    # 리스트 -> 콤마 구분 문자열
    def join_or_none(value):
        if isinstance(value, list):
            return ",".join([str(v) for v in value if v])
        return value

    life_stage = join_or_none(category.get("lifeArray"))
    target_group = join_or_none(category.get("targetArray"))
    theme = join_or_none(category.get("themeArray"))

    law_titles = join_or_none(policy.get("law"))

    age_info = conditions.get("age") or {}
    age_min = age_info.get("min")
    age_max = age_info.get("max")

    sql = """
    INSERT INTO welfare_policy (
        service_id,
        service_name,
        summary,
        short_summary,
        normalized_summary,
        long_summary,
        exclusion_summary,
        embedding_text,
        life_stage,
        target_group,
        theme,
        region_sido,
        region_sigungu,
        provider_org,
        support_type,
        support_cycle,
        age_min,
        age_max,
        contact_phone,
        contact_url,
        law_titles,
        raw_json,
        created_at,
        updated_at
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now')
    )
    ON CONFLICT(service_id) DO UPDATE SET
        service_name       = excluded.service_name,
        summary            = excluded.summary,
        life_stage         = excluded.life_stage,
        target_group       = excluded.target_group,
        theme              = excluded.theme,
        region_sido        = excluded.region_sido,
        region_sigungu     = excluded.region_sigungu,
        provider_org       = excluded.provider_org,
        support_type       = excluded.support_type,
        support_cycle      = excluded.support_cycle,
        age_min            = excluded.age_min,
        age_max            = excluded.age_max,
        contact_phone      = excluded.contact_phone,
        contact_url        = excluded.contact_url,
        law_titles         = excluded.law_titles,
        raw_json           = excluded.raw_json,
        updated_at         = datetime('now');
    """.strip()

    params = (
        policy.get("serviceId"),
        policy.get("serviceName"),
        policy.get("summary"),
        policy.get("short_summary"),
        policy.get("normalized_summary"),
        policy.get("long_summary"),
        policy.get("exclusion_summary"),
        policy.get("embedding_text"),
        life_stage,
        target_group,
        theme,
        region.get("sido"),
        region.get("sigungu"),
        provider.get("orgName"),
        benefit.get("type"),
        benefit.get("cycle"),
        age_min,
        age_max,
        contact.get("phone"),
        contact.get("homepage"),
        law_titles,
        json.dumps(policy, ensure_ascii=False),
    )

    return sql, params


def generate_policy_summaries(policy: dict, api_key: str, model: str = "gpt-4o-mini") -> dict:
    """
    OpenAI API를 사용하여 정책 요약 4개 필드를 생성합니다.

    Args:
        policy: parse_policy_xml로 생성된 정규화 정책 JSON
        api_key: OpenAI API 키
        model: 사용할 모델 (기본값: gpt-4o-mini)

    Returns:
        {
            "short_summary": "한 줄 요약",
            "normalized_summary": "정규화된 2-3문장 요약",
            "long_summary": "상세 요약",
            "exclusion_summary": "제외 대상 요약",
            "embedding_text": "임베딩용 핵심 정보 텍스트"
        }
    """
    client = OpenAI(api_key=api_key)

    # 정책 정보 텍스트 구성
    parts = []
    if policy.get("serviceName"):
        parts.append(f"정책명: {policy['serviceName']}")
    if policy.get("summary"):
        parts.append(f"요약: {policy['summary']}")

    conditions = policy.get("conditions", {})
    if conditions.get("target"):
        parts.append(f"지원대상: {conditions['target']}")
    if conditions.get("selectionCriteria"):
        parts.append(f"선정기준: {conditions['selectionCriteria']}")

    benefit = policy.get("benefit", {})
    if benefit.get("content"):
        parts.append(f"지원내용: {benefit['content']}")
    if benefit.get("cycle"):
        parts.append(f"지원주기: {benefit['cycle']}")
    if benefit.get("type"):
        parts.append(f"제공유형: {benefit['type']}")

    apply_info = policy.get("apply", {})
    if apply_info.get("method"):
        parts.append(f"신청방법: {apply_info['method']}")

    policy_text = "\n".join(parts)

    prompt = f"""아래 복지 정책 정보를 분석하여 JSON 형식으로 요약해주세요.

### 정책 정보:
{policy_text}

### 출력 형식 (JSON만 출력):
{{
  "short_summary": "한 문장으로 정책 핵심 요약 (50자 이내)",
  "normalized_summary": "대상자, 지원내용, 지원방식을 포함한 2-3문장 요약",
  "long_summary": "정책의 목적, 대상자, 지원내용, 신청방법 등을 포함한 상세 요약 (3-5문장)",
  "exclusion_summary": "지원 제외 대상 요약 (없으면 빈 문자열)",
  "embedding_text": "RAG 검색용 핵심 정보 텍스트"
}}

규칙:
- 반드시 JSON만 출력
- 정보가 없는 필드는 빈 문자열로 처리
- 한국어로 작성
- embedding_text 작성 규칙:
  * 정책명 제외
  * 반드시 포함: 자격조건(소득기준, 연령, 거주지역), 대상자 유형, 지원내용, 지원금액
  * 형식: 문장형으로 자연스럽게 연결
  * 예시: "중위소득 50% 이하 만19~34세 무주택 청년에게 월 최대 20만원 주거비 지원" """

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return {
            "short_summary": result.get("short_summary", ""),
            "normalized_summary": result.get("normalized_summary", ""),
            "long_summary": result.get("long_summary", ""),
            "exclusion_summary": result.get("exclusion_summary", ""),
            "embedding_text": result.get("embedding_text", "")
        }

    except Exception as e:
        logger.error(f"OpenAI API 호출 실패: {e}")
        return {
            "short_summary": "",
            "normalized_summary": "",
            "long_summary": "",
            "exclusion_summary": "",
            "embedding_text": ""
        }
