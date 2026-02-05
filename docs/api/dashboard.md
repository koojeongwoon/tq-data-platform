# Dashboard API Specification

The Dashboard provides a high-level summary of the user's welfare status and personalized policy lists for UI-centric browsing.

## 1. Summary Overview

### [GET] `/dashboard/summary`

Returns aggregated statistics for the main dashboard landing page.

**Authorization**: `Bearer <access_token>`

**Response Body**:

```json
{
  "total_matches": 12, // 전체 매칭된 정책 수
  "new_matches": 2, // 지난 7일 내 새로 매칭된 정책 수
  "profile_completion_score": 85, // 프로필 완성도 (0~100)
  "next_deadline": "2026-03-15", // 가장 임박한 신청 마감일 (해당 시)
  "recent_activities_count": 5 // 최근 정책 조회 활동 수
}
```

---

## 2. Personalized Feed

### [GET] `/dashboard/personalized`

Returns a list of recommended policies optimized for UI card rendering.

**Authorization**: `Bearer <access_token>`

**Response Body**:

```json
{
  "total_count": 5,
  "recommendations": [
    {
      "id": "policy_uuid",
      "title": "청년 월세 지원금",
      "category": "housing",
      "region": "서울특별시",
      "deadline": "2026-04-30",
      "match_score": 0.98 // 매칭 정확도
    }
  ]
}
```

---

## 3. Synergy Features (Dashboard -> Chat)

### Contextual Pivot

When a user clicks a policy on the dashboard, the frontend should navigate to the Chat and use the following payload:

**[POST] `/chat/conversation`**

```json
{
  "message": "",
  "pre_load_policy_id": "policy_uuid"
}
```

_Effect: The assistant will skip general greeting and immediately ask if the user needs help with requirements or application documents for the specific policy._
