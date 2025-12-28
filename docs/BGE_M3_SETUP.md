# BGE-M3 임베딩 설정 가이드

## 개요

BGE-M3 (BAAI General Embedding M3)는 다국어를 지원하는 고성능 임베딩 모델입니다.
- **크기**: 1024 차원
- **한국어 지원**: 우수
- **용도**: 의미 검색 (Semantic Search)

## 설치

### 1. 의존성 설치

```bash
# 프로젝트 의존성 설치 (BGE-M3 포함)
uv pip install -e ".[dev]"

# 또는 배치 작업용으로만 설치
uv pip install -e ".[batch]"
```

**패키지 크기 참고**:
- `sentence-transformers`: ~500MB
- `torch`: ~800MB
- BGE-M3 모델: ~2GB (첫 실행 시 자동 다운로드)

### 2. 첫 실행

첫 실행 시 모델이 자동으로 다운로드됩니다:

```python
from shared.services.embedding import get_embedding_service

# 모델 로딩 (최초 1회 다운로드, 이후 캐시 사용)
embedding_service = get_embedding_service()
```

**다운로드 위치**: `~/.cache/huggingface/hub/`

## 사용 방법

### 1. 단일 텍스트 임베딩

```python
from shared.services.embedding import get_embedding_service

embedding_service = get_embedding_service()

text = "서울시 거주 만 65세 이상 어르신 지원"
vector = embedding_service.encode_single(text)

print(len(vector))  # 1024
```

### 2. 배치 임베딩 (효율적)

```python
texts = [
    "임신부 및 출산 가정 지원",
    "청년 창업 자금 지원",
    "저소득층 주거 지원"
]

vectors = embedding_service.encode_batch(texts, batch_size=32)
print(len(vectors))  # 3
print(len(vectors[0]))  # 1024
```

### 3. 검색 쿼리 임베딩

```python
query = "임신부 지원 정책"
query_vector = embedding_service.encode_query(query)
```

## 데이터 동기화에서 사용

### 1. BGE-M3 사용 (기본값)

```python
from batch.services.data_sync import DataSyncService

# BGE-M3 임베딩 사용
sync_service = DataSyncService(use_embeddings=True)
sync_service.sync_all(batch_size=100)
```

**출력 예시**:
```
🔄 Initializing BGE-M3 embedding model...
✅ Embedding model ready

=== Starting Data Sync (D1 → PostgreSQL + Qdrant) ===

📊 Fetching policies from D1...
✅ Fetched 1500 policies from D1

...

📊 Sync Summary:
  PostgreSQL: 1500 synced, 0 failed
  Qdrant: 1500 synced
  Total processed: 1500 policies
  Embedding: BGE-M3 embeddings
============================================================

✅ Sync complete!
```

### 2. Placeholder 벡터 사용 (테스트용)

```python
# 임베딩 없이 테스트 (빠름, 검색 기능 없음)
sync_service = DataSyncService(use_embeddings=False)
sync_service.sync_all(batch_size=100)
```

**출력 예시**:
```
=== Starting Data Sync (D1 → PostgreSQL + Qdrant) ===

📊 Sync Summary:
  PostgreSQL: 1500 synced, 0 failed
  Qdrant: 1500 synced
  Total processed: 1500 policies
  Embedding: Placeholder vectors
============================================================

✅ Sync complete!
⚠️  Note: Using placeholder vectors. Enable embeddings for production.
```

## 성능 최적화

### 1. 배치 크기 조정

```python
# 메모리가 충분한 경우 배치 크기를 늘려서 속도 향상
sync_service = DataSyncService(use_embeddings=True)
sync_service.sync_all(batch_size=200)  # 기본값: 100
```

### 2. GPU 사용 (선택사항)

PyTorch가 CUDA를 지원하는 경우 자동으로 GPU 사용:

```bash
# GPU 사용 확인
python -c "import torch; print(torch.cuda.is_available())"
```

### 3. 싱글톤 패턴

모델은 자동으로 싱글톤으로 관리되어 메모리 효율적:

```python
# 여러 번 호출해도 모델은 1번만 로딩됨
service1 = get_embedding_service()
service2 = get_embedding_service()  # 동일한 인스턴스 반환
```

## 벡터 검색 사용

### 1. Qdrant에서 유사 정책 검색

```python
from shared.db.qdrant_client import QdrantClient
from shared.services.embedding import get_embedding_service

# 1. 검색 쿼리 임베딩
embedding_service = get_embedding_service()
query = "임신부 지원 정책"
query_vector = embedding_service.encode_single(query)

# 2. Qdrant에서 검색
qdrant = QdrantClient()
results = qdrant.search(
    query_vector=query_vector,
    filters={'source_type': 'central'},  # 선택적 필터
    limit=10
)

# 3. 결과 출력
for result in results:
    print(f"Score: {result['score']}")
    print(f"Title: {result['metadata']['title']}")
    print(f"Summary: {result['metadata']['summary']}")
    print("---")
```

### 2. 하이브리드 검색 (키워드 + 벡터)

```python
from shared.db.postgres import PostgresClient
from shared.db.qdrant_client import QdrantClient
from shared.services.embedding import get_embedding_service

def hybrid_search(query: str, limit: int = 10):
    """
    1단계: PostgreSQL 키워드 검색 (빠름)
    2단계: Qdrant 벡터 검색으로 재순위화 (정확함)
    """
    # 1. 키워드 검색으로 후보 추출 (100개)
    postgres = PostgresClient()
    candidates = postgres.keyword_search(query, limit=100)

    # 2. 벡터 검색으로 최종 순위 결정
    embedding_service = get_embedding_service()
    query_vector = embedding_service.encode_single(query)

    qdrant = QdrantClient()
    # 후보 ID 필터 적용
    candidate_ids = [c['policy_id'] for c in candidates]
    results = qdrant.search(
        query_vector=query_vector,
        filters={'policy_id': {'$in': candidate_ids}},
        limit=limit
    )

    return results
```

## 문제 해결

### 모델 다운로드 실패

```bash
# 수동으로 모델 다운로드
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```

### 메모리 부족

```python
# 배치 크기를 줄여서 메모리 사용량 감소
sync_service = DataSyncService(use_embeddings=True)
sync_service.sync_all(batch_size=50)  # 기본값 100에서 감소
```

### 느린 속도

1. **GPU 사용**: CUDA 설치 확인
2. **배치 크기 증가**: 메모리가 허용하는 한 늘리기
3. **Placeholder 사용**: 개발/테스트 시 임베딩 비활성화

## 모델 정보

- **모델명**: BAAI/bge-m3
- **출처**: https://huggingface.co/BAAI/bge-m3
- **라이센스**: MIT
- **논문**: https://arxiv.org/abs/2402.03216
- **지원 언어**: 100+ (한국어 포함)

## 참고

- 첫 실행 시 모델 다운로드로 인해 시간이 걸릴 수 있습니다 (~5-10분)
- 모델은 캐시되므로 이후 실행은 빠릅니다 (~2-3초)
- 프로덕션 환경에서는 반드시 `use_embeddings=True` 사용
