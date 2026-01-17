# 검색 API (Search)

> **모듈**: `app/search/`
> **Prefix**: `/search`
> **Tags**: `Search`

---

## 개요

Qdrant 벡터 데이터베이스를 활용한 하이브리드 시맨틱 검색을 제공합니다.

### 검색 방식

- **Dense Embedding**: `multilingual-e5-large` (의미 기반 검색)
- **Sparse Embedding**: `BM25` (키워드 기반 검색)
- **Hybrid Search**: Dense + Sparse 결합으로 정확도 향상

### 파일 구조

```
app/search/
├── __init__.py
├── router.py      # 엔드포인트 정의
└── schemas.py     # Pydantic 모델
```

---

## 엔드포인트

### GET `/search/semantic` - 시맨틱 검색

의미 기반 복지 정책 검색

**Query Parameters**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| q | string | ✅ | - | 검색어 (최소 2자) |
| source_type | string | ❌ | null | `central` 또는 `regional` |
| limit | integer | ❌ | 10 | 결과 개수 (1-100) |

**예시**
```http
GET /search/semantic?q=임신부%20지원&limit=5
GET /search/semantic?q=청년%20주거&source_type=central
```

**Response** `200 OK`
```json
{
  "query": "임신부 지원",
  "total": 5,
  "results": [
    {
      "policy_id": "WLF00000456",
      "score": 0.89,
      "title": "임산부 건강관리 지원",
      "summary": "임신부 및 출산 가정 건강검진 및 영양 지원",
      "ministry": "보건복지부",
      "source_type": "central",
      "ctpv_nm": null,
      "sgg_nm": null,
      "phone": "1577-1234",
      "website": "https://example.go.kr"
    }
  ]
}
```

**Errors**
| 코드 | 설명 |
|------|------|
| 400 | source_type 값 오류 (`central` 또는 `regional`만 허용) |
| 422 | 검색어 유효성 검증 실패 (2자 미만) |
| 500 | 검색 실패 (Qdrant 오류) |
| 503 | 임베딩 서비스 미사용 가능 (서버 로딩 중) |

---

### GET `/search/health` - 검색 서비스 상태

검색 서비스의 상태를 확인합니다.

**Response** `200 OK`
```json
{
  "embedding_service": "ready",
  "qdrant": "ready",
  "collection_count": 1500
}
```

**상태 값**

| 필드 | 가능한 값 | 설명 |
|------|-----------|------|
| embedding_service | `ready` / `not_loaded` | 임베딩 모델 로드 상태 |
| qdrant | `ready` / `unavailable` | Qdrant 연결 상태 |
| collection_count | integer | 인덱싱된 정책 청크 수 |

---

## 데이터 모델

### SearchResult

```python
class SearchResult(BaseModel):
    policy_id: str              # 정책 ID
    score: float                # 관련도 점수 (0-1)
    title: str                  # 정책명
    summary: Optional[str]      # 정책 요약
    ministry: Optional[str]     # 담당부처
    source_type: str            # "central" | "regional"
    ctpv_nm: Optional[str]      # 시/도
    sgg_nm: Optional[str]       # 시/군/구
    phone: Optional[str]        # 문의 전화
    website: Optional[str]      # 웹사이트
```

### SearchResponse

```python
class SearchResponse(BaseModel):
    query: str                  # 검색어
    total: int                  # 결과 개수
    results: List[SearchResult] # 검색 결과
```

---

## 검색 동작 원리

### 1. 쿼리 임베딩 생성

```
사용자 쿼리 "임신부 지원"
    ↓
multilingual-e5-large → Dense Vector (1024 dim)
    ↓
BM25 Tokenizer → Sparse Vector
```

### 2. 하이브리드 검색

```
Qdrant Collection
    ↓
Dense Search (의미 유사도) + Sparse Search (키워드 매칭)
    ↓
RRF (Reciprocal Rank Fusion) 점수 결합
    ↓
상위 N개 결과 반환
```

### 3. 결과 반환

검색 점수(score)는 0-1 범위로 정규화됩니다.
- **0.8 이상**: 매우 관련성 높음
- **0.6-0.8**: 관련성 있음
- **0.4-0.6**: 약간 관련 있음
- **0.4 미만**: 관련성 낮음

---

## 사용 예시

### JavaScript

```javascript
// 시맨틱 검색
const search = async (query, options = {}) => {
  const params = new URLSearchParams({ q: query, ...options });
  const res = await fetch(`/search/semantic?${params}`);

  if (!res.ok) {
    if (res.status === 503) {
      throw new Error('검색 서비스가 아직 준비되지 않았습니다.');
    }
    throw new Error('검색 실패');
  }

  return res.json();
};

// 사용 예
const results = await search('임신부 지원', {
  source_type: 'central',
  limit: 5
});
```

### Python

```python
import requests

def semantic_search(
    query: str,
    source_type: str = None,
    limit: int = 10
) -> dict:
    params = {"q": query, "limit": limit}
    if source_type:
        params["source_type"] = source_type

    response = requests.get(
        "http://localhost:8000/search/semantic",
        params=params
    )
    response.raise_for_status()
    return response.json()

# 사용 예
results = semantic_search("청년 주거 지원", source_type="central", limit=5)
for r in results["results"]:
    print(f"{r['title']} (score: {r['score']:.2f})")
```

---

## 관련 서비스

- **QdrantService**: `shared/services/qdrant_service.py`
- **임베딩 모델**: multilingual-e5-large (Hugging Face)
- **Qdrant 설정**: `shared/config/settings.py` (`QDRANT_HOST`, `QDRANT_PORT`)
