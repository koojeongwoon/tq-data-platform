"""
D1에서 복지 정책 1건 샘플 데이터를 가져와서 파일로 저장
"""
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shared.db.d1 import D1Client


def fetch_sample_policy():
    """D1에서 복지 정책 1건을 가져와서 파일로 저장"""

    print("D1 클라이언트 초기화 중...")
    d1 = D1Client()

    # welfare_collections 테이블에서 1건 조회
    query = """
    SELECT policy_id, source_type, policy_title, raw_data, collected_at
    FROM welfare_collections
    LIMIT 1
    """

    print("D1에서 데이터 조회 중...")
    result = d1.execute_query(query)

    if not result or not result.get("success"):
        print("❌ D1 조회 실패")
        return

    try:
        # D1 응답 구조: {"result": [{"results": [...]}], "success": true}
        policies = result.get("result", [{}])[0].get("results", [])

        if not policies:
            print("❌ 데이터가 없습니다.")
            return

        policy = policies[0]
        policy_id = policy.get("policy_id")

        print(f"\n✅ 정책 ID: {policy_id}")
        print(f"   정책명: {policy.get('policy_title')}")
        print(f"   출처: {policy.get('source_type')}")
        print(f"   수집일시: {policy.get('collected_at')}")

        # 파일로 저장
        output_dir = project_root / "data"
        output_dir.mkdir(exist_ok=True)

        # 1. 전체 정보 JSON으로 저장
        json_path = output_dir / f"sample_policy_{policy_id}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(policy, f, ensure_ascii=False, indent=2)
        print(f"\n📄 JSON 저장: {json_path}")

        # 2. Raw XML 데이터만 따로 저장
        xml_path = output_dir / f"sample_policy_{policy_id}.xml"
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(policy.get('raw_data', ''))
        print(f"📄 XML 저장: {xml_path}")

        print("\n✅ 샘플 데이터 저장 완료!")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print(f"응답 내용: {result}")


if __name__ == "__main__":
    fetch_sample_policy()
