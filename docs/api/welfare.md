# 복지 정책 API (Welfare)

> **모듈**: `app/welfare/`
> **Prefix**: `/welfare`
> **Tags**: `Welfare`

---

## 개요

PostgreSQL에 저장된 복지 정책 데이터를 조회합니다.

- 중앙정부 정책 (central)
- 지방정부 정책 (regional)

### 파일 구조

```
app/welfare/
├── __init__.py
└── router.py      # 엔드포인트 정의
```

### 데이터 소스

- **PostgreSQL**: `welfare_policies` 테이블
- **데이터 수집**: `batch/` 모듈에서 공공데이터포털 API로 수집

---

## 엔드포인트

### GET `/welfare/policies` - 정책 목록 조회

페이지네이션을 지원하는 정책 목록 조회

**Query Parameters**

| 파라미터 | 타입    | 필수 | 기본값 | 설명             |
| -------- | ------- | ---- | ------ | ---------------- |
| limit    | integer | ❌   | 100    | 조회할 정책 개수 |
| offset   | integer | ❌   | 0      | 시작 위치        |

**예시**

```http
GET /welfare/policies?limit=10&offset=0
```

**Response** `200 OK`

```json
{
  "total": 50,
  "limit": 100,
  "offset": 0,
  "policies": [
    {
      "policy_id": "WLF00000123",
      "title": "청년 주거 지원",
      "summary": "청년층 주거비 지원 정책",
      "ministry": "국토교통부",
      "source_type": "central",
      "ctpv_nm": null,
      "sgg_nm": null,
      "support_provision": "월 최대 50만원",
      "phone": "1599-0001",
      "website": "https://example.go.kr"
    }
  ]
}
```

**Errors**
| 코드 | 설명 |
|------|------|
| 500 | 데이터베이스 조회 실패 |

---

### GET `/welfare/policies/{policy_id}` - 정책 상세 조회

특정 정책의 상세 정보를 조회합니다.

**Path Parameters**

| 파라미터  | 타입   | 설명                      |
| --------- | ------ | ------------------------- |
| policy_id | string | 정책 ID (예: WLF00000123) |

**예시**

```http
GET /welfare/policies/WLF00000123
```

**Response** `200 OK`

```json
{
  "policy_id": "WLF00000123",
  "title": "청년 주거 지원",
  "summary": "청년층 주거비 지원 정책",
  "ministry": "국토교통부",
  "source_type": "central",
  "ctpv_nm": null,
  "sgg_nm": null,
  "support_content": "월세 지원금 최대 50만원 지급",
  "target_detail": "만 19-34세 무주택 청년",
  "application_method": "온라인 신청",
  "application_detail": "복지로 홈페이지에서 신청",
  "phone": "1599-0001",
  "website": "https://example.go.kr"
}
```

**Errors**
| 코드 | 설명 |
|------|------|
| 404 | 정책을 찾을 수 없음 |
| 500 | 데이터베이스 조회 실패 |

---

## 데이터 모델

### Policy

```python
class Policy(BaseModel):
    policy_id: str              # 정책 고유 ID
    title: str                  # 정책명
    summary: Optional[str]      # 정책 요약
    ministry: Optional[str]     # 담당부처/기관
    source_type: str            # "central" | "regional"
    ctpv_nm: Optional[str]      # 시/도 (지역정책)
    sgg_nm: Optional[str]       # 시/군/구 (지역정책)
    support_content: Optional[str]      # 지원 내용
    support_provision: Optional[str]    # 지원 조건
    target_detail: Optional[str]        # 지원 대상 상세
    application_method: Optional[str]   # 신청 방법
    application_detail: Optional[str]   # 신청 방법 상세
    phone: Optional[str]        # 문의 전화
    website: Optional[str]      # 관련 웹사이트
```

### source_type 값

| 값       | 설명                                      |
| -------- | ----------------------------------------- |
| central  | 중앙정부 정책 (보건복지부, 국토교통부 등) |
| regional | 지방정부 정책 (시/도, 시/군/구)           |

---

## 사용 예시

### JavaScript

```javascript
// 정책 목록 조회
const getPolicies = async (limit = 10, offset = 0) => {
  const res = await fetch(`/welfare/policies?limit=${limit}&offset=${offset}`);
  return res.json();
};

// 정책 상세 조회
const getPolicy = async (policyId) => {
  const res = await fetch(`/welfare/policies/${policyId}`);
  if (!res.ok) throw new Error("Policy not found");
  return res.json();
};

// 통계 조회
const getStats = async () => {
  const res = await fetch("/welfare/stats");
  return res.json();
};
```

### Python

```python
import requests

def get_policies(limit: int = 10, offset: int = 0) -> dict:
    response = requests.get(
        "http://localhost:8000/welfare/policies",
        params={"limit": limit, "offset": offset}
    )
    return response.json()

def get_policy(policy_id: str) -> dict:
    response = requests.get(
        f"http://localhost:8000/welfare/policies/{policy_id}"
    )
    response.raise_for_status()
    return response.json()
```
