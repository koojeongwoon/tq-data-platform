# API 사용 가이드

## API 서버 시작

### 1. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# 필수 환경 변수 설정
# - POSTGRES_* : PostgreSQL 접속 정보
# - QDRANT_* : Qdrant 접속 정보
# - USE_EMBEDDINGS : multilingual-e5-large 사용 여부 (true/false)
```

### 2. 서버 시작

```bash
# 개발 모드 (자동 재시작)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 프로덕션 모드
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. 시작 시 로그

```
🚀 Starting TQ Data Platform API...
📦 Loading multilingual-e5-large embedding model...
Loading embedding model: BAAI/multilingual-e5-large...
✅ Model loaded successfully (dimension: 1024)
✅ Embedding model loaded successfully
✅ API server ready

INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**첫 실행 시**: multilingual-e5-large 모델 다운로드로 ~5-10분 소요 (이후 캐시 사용)

## API 엔드포인트

### 1. Health Check

```bash
# 서버 상태 확인
curl http://localhost:8000/health

# 응답
{
  "status": "healthy",
  "timestamp": "2025-12-27T12:00:00"
}
```

### 2. 검색 서비스 상태

```bash
# 임베딩 모델 및 Qdrant 상태 확인
curl http://localhost:8000/search/health

# 응답
{
  "embedding_service": "ready",
  "qdrant": "ready",
  "collection_count": 1500
}
```

### 3. 의미 검색 (Semantic Search)

> **사용 모델**: multilingual-e5-large (Dense) + BM25 (Sparse) 하이브리드 검색

#### 기본 검색

```bash
# 임신부 지원 정책 검색
curl "http://localhost:8000/search/semantic?q=임신부%20지원"

# 응답
{
  "query": "임신부 지원",
  "total": 10,
  "results": [
    {
      "policy_id": "WII00000123",
      "score": 0.89,
      "title": "임산부 건강관리 지원",
      "summary": "임신부 및 출산 가정 건강검진 및 영양 지원",
      "ministry": "보건복지부",
      "source_type": "central",
      "ctpv_nm": null,
      "sgg_nm": null,
      "phone": "1577-1234",
      "website": "http://example.com"
    },
    ...
  ]
}
```

#### 필터링 검색

```bash
# 중앙정부 정책만 검색
curl "http://localhost:8000/search/semantic?q=청년%20창업&source_type=central&limit=5"

# 응답
{
  "query": "청년 창업",
  "total": 5,
  "results": [...]
}
```

### 4. 검색 파라미터

| 파라미터 | 타입 | 필수 | 설명 | 기본값 | 예시 |
|---------|------|------|------|--------|------|
| `q` | string | ✅ | 검색 쿼리 (2자 이상) | - | `임신부 지원` |
| `source_type` | string | ❌ | 출처 필터 (`central` or `regional`) | null | `central` |
| `limit` | int | ❌ | 결과 개수 (1-100) | 10 | `20` |

## 검색 예시

### 1. 생애주기별 검색

```bash
# 영유아 지원
curl "http://localhost:8000/search/semantic?q=영유아%20보육"

# 청년 지원
curl "http://localhost:8000/search/semantic?q=청년%20주거%20지원"

# 노인 지원
curl "http://localhost:8000/search/semantic?q=어르신%20건강"
```

### 2. 주제별 검색

```bash
# 주거 지원
curl "http://localhost:8000/search/semantic?q=전세자금%20대출"

# 창업 지원
curl "http://localhost:8000/search/semantic?q=소상공인%20창업"

# 의료 지원
curl "http://localhost:8000/search/semantic?q=저소득층%20의료비"
```

### 3. 지역별 검색

```bash
# 서울시 정책
curl "http://localhost:8000/search/semantic?q=서울%20청년%20지원&source_type=regional"

# 전국 정책
curl "http://localhost:8000/search/semantic?q=전국%20육아%20지원&source_type=central"
```

## Python 클라이언트 예시

### 기본 사용

```python
import requests

# 검색 요청
response = requests.get(
    "http://localhost:8000/search/semantic",
    params={
        "q": "임신부 지원",
        "limit": 10
    }
)

results = response.json()

# 결과 출력
print(f"검색어: {results['query']}")
print(f"결과 수: {results['total']}")

for result in results['results']:
    print(f"\n제목: {result['title']}")
    print(f"점수: {result['score']:.2f}")
    print(f"요약: {result['summary']}")
```

### 필터링 검색

```python
# 중앙정부 청년 창업 정책
response = requests.get(
    "http://localhost:8000/search/semantic",
    params={
        "q": "청년 창업 자금",
        "source_type": "central",
        "limit": 5
    }
)

results = response.json()
```

## JavaScript 클라이언트 예시

### Fetch API

```javascript
// 검색 함수
async function searchPolicies(query, options = {}) {
  const params = new URLSearchParams({
    q: query,
    limit: options.limit || 10,
    ...(options.sourceType && { source_type: options.sourceType })
  });

  const response = await fetch(
    `http://localhost:8000/search/semantic?${params}`
  );

  return await response.json();
}

// 사용 예시
const results = await searchPolicies("임신부 지원", { limit: 5 });

results.results.forEach(result => {
  console.log(`제목: ${result.title}`);
  console.log(`점수: ${result.score}`);
});
```

### Axios

```javascript
import axios from 'axios';

const client = axios.create({
  baseURL: 'http://localhost:8000'
});

// 검색
const { data } = await client.get('/search/semantic', {
  params: {
    q: '청년 주거 지원',
    source_type: 'central',
    limit: 20
  }
});

console.log(`검색 결과: ${data.total}개`);
```

## 에러 처리

### 에러 응답 형식

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "검색어는 2자 이상이어야 합니다",
  "details": {
    "field": "q",
    "constraint": "min_length"
  }
}
```

### 주요 에러 코드

| 상태 코드 | 에러 코드 | 설명 | 해결 방법 |
|-----------|----------|------|----------|
| 400 | VALIDATION_ERROR | 파라미터 유효성 검사 실패 | 파라미터 확인 |
| 503 | SERVICE_UNAVAILABLE | 임베딩 서비스 미사용 가능 | 서버 재시작 대기 |
| 500 | INTERNAL_ERROR | 서버 내부 오류 | 로그 확인 |

## 성능 최적화

### 1. 서버 설정

```bash
# 워커 수 조정 (CPU 코어 수에 따라)
uvicorn app.main:app --workers 4

# 타임아웃 설정
uvicorn app.main:app --timeout-keep-alive 30
```

### 2. 클라이언트 설정

```python
# 연결 풀 사용
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=3, backoff_factor=0.3)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)

# 세션 사용
response = session.get("http://localhost:8000/search/semantic", ...)
```

## 모니터링

### 로그 확인

```bash
# 서버 로그 (표준 출력)
tail -f uvicorn.log

# 에러만 필터링
tail -f uvicorn.log | grep ERROR
```

### 헬스 체크

```bash
# 주기적 상태 확인
watch -n 5 'curl -s http://localhost:8000/search/health | jq'
```

## 배포 고려사항

### 1. 모델 사전 다운로드

```bash
# Dockerfile에서 모델 사전 다운로드
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/multilingual-e5-large')"
```

### 2. 환경 변수 설정

```bash
# 프로덕션 환경
ENVIRONMENT=production
USE_EMBEDDINGS=true
```

### 3. 리버스 프록시 (Nginx)

```nginx
upstream tq_api {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;  # 로드 밸런싱
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://tq_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 참고

- **API 문서**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI 스키마**: http://localhost:8000/openapi.json
