"""
노멀라이저 테스트 - D1에서 50개 데이터로 검증
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.db.d1 import D1Client
from scripts.normalize_policy import parse_policy_xml


def main():
    print("=== D1에서 50개 XML 가져와서 노멀라이저 검증 ===\n")

    d1 = D1Client()
    raw_policies = d1.fetch_raw_policies(limit=50)

    if not raw_policies:
        print("DB에서 데이터를 가져오지 못했습니다.")
        return

    print(f"총 {len(raw_policies)}개 정책 데이터 로드\n")

    success_count = 0
    error_count = 0
    errors = []

    for i, policy in enumerate(raw_policies, 1):
        policy_id = policy.get("policy_id")
        raw_xml = policy.get("raw_data")

        if not raw_xml:
            print(f"[{i}] {policy_id}: raw_data 비어있음")
            error_count += 1
            errors.append((policy_id, "raw_data가 비어있음"))
            continue

        try:
            normalized = parse_policy_xml(raw_xml)
            # 기본 필드 검증
            if normalized.get("serviceId") and normalized.get("serviceName"):
                print(f"[{i}] {policy_id}: ✓ 성공 - {normalized.get('serviceName')[:30]}...")
                success_count += 1
            else:
                print(f"[{i}] {policy_id}: ⚠ 필수 필드 누락 (serviceId/serviceName)")
                error_count += 1
                errors.append((policy_id, "필수 필드 누락"))
        except Exception as e:
            print(f"[{i}] {policy_id}: ✗ 파싱 에러 - {e}")
            error_count += 1
            errors.append((policy_id, str(e)))

    print("\n" + "=" * 50)
    print(f"결과: 성공 {success_count}개, 실패 {error_count}개")

    if errors:
        print("\n에러 목록:")
        for pid, err in errors:
            print(f"  - {pid}: {err}")
    else:
        print("\n✓ 모든 정책이 예외 없이 정상 처리됨!")


if __name__ == "__main__":
    main()
