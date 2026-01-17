# 임베딩 모델 설정 가이드

## 개요

TQ Data Platform은 **하이브리드 검색**을 사용합니다:

| 모델 | 타입 | 차원 | 용도 |
|------|------|------|------|
| `intfloat/multilingual-e5-large` | Dense | 1024 | 의미 기반 검색 |
| `Qdrant/bm25` | Sparse | - | 키워드 기반 검색 |

두 모델의 결과를 결합하여 더 정확한 검색 결과를 제공합니다.

## 모델 정보

### multilingual-e5-large (Dense)

- **출처**: https://huggingface.co/intfloat/multilingual-e5-large
- **크기**: ~2GB
- **차원**: 1024
- **특징**:
  - 다국어 지원 (한국어 포함 100+ 언어)
  - 쿼리에 `query: ` 접두사, 문서에 `passage: ` 접두사 필요
  - 의미적 유사도 검색에 최적화

### BM25 (Sparse)

- **출처**: Qdrant FastEmbed
- **특징**:
  - 전통적인 키워드 매칭
  - 정확한 용어 매칭에 강점
  - Dense 검색과 상호 보완

## 설치

### 1. 의존성 설치

```bash
# 프로젝트 의존성 설치
uv pip install -e ".[dev]"
```

**패키지 크기 참고**:
- `fastembed`: ~100MB
- multilingual-e5-large 모델: ~2GB (첫 실행 시 자동 다운로드)

### 2. 첫 실행

첫 실행 시 모델이 자동으로 다운로드됩니다:

```python
from shared.services.qdrant_service import QdrantService

# 모델 로딩 (최초 1회 다운로드, 이후 캐시 사용)
service = QdrantService()
service._get_dense_model()   # multilingual-e5-large
service._get_sparse_model()  # BM25
```

**다운로드 위치**: `~/.cache/fastembed/`

## 사용 방법

### 1. 하이브리드 검색 (권장)

```python
from shared.services.qdrant_service import QdrantService

service = QdrantService(host="localhost", port=6333)

# 하이브리드 검색 (Dense + Sparse)
results = service.hybrid_search(
    query="임신부 지원 정책",
    limit=10,
    chunk_type="benefit",      # 선택적 필터
    province="서울특별시"       # 선택적 필터
)

for result in results:
    print(f"Score: {result['score']}")
    print(f"Title: {result['title']}")
    print(f"Content: {result['content'][:100]}")
    print("---")
```

### 2. Dense 검색만 사용

```python
# Dense 벡터만으로 검색
results = service.search_dense(
    query="청년 창업 지원",
    limit=10
)
```

### 3. 문서 인덱싱

```python
# 청크 데이터 준비
chunks = [
    {
        "id": "chunk_001",
        "content": "임신부 건강관리 지원 정책입니다...",
        "policy_id": "WLF00000123",
        "title": "임산부 건강관리",
        "chunk_type": "benefit"
    }
]

# Qdrant에 업로드 (Dense + Sparse 벡터 자동 생성)
service.upsert_chunks(chunks)
```

## API 서버에서 사용

API 서버는 시작 시 모델을 미리 로드합니다:

```python
# app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 모델 로드
    qdrant_service = QdrantService()
    qdrant_service._get_dense_model()   # multilingual-e5-large
    qdrant_service._get_sparse_model()  # BM25

    app.state.qdrant_service = qdrant_service
    yield
```

**시작 로그**:
```
🚀 Starting TQ Data Platform API...
📦 Loading embedding models...
✅ Embedding models loaded successfully
✅ API server ready
```

## 성능 최적화

### 1. 배치 인코딩

```python
# 여러 텍스트를 한 번에 인코딩 (더 효율적)
texts = ["텍스트1", "텍스트2", "텍스트3"]
vectors = service._encode_dense(texts)
```

### 2. GPU 사용 (선택사항)

ONNX Runtime이 CUDA를 지원하는 경우 자동으로 GPU 사용

### 3. 모델 캐싱

모델은 lazy loading으로 첫 사용 시 로드되고 이후 재사용됩니다:

```python
service = QdrantService()
# 첫 검색 시 모델 로드 (~2-3초)
results1 = service.hybrid_search("검색어1")
# 이후 검색은 빠름 (~0.1초)
results2 = service.hybrid_search("검색어2")
```

## 문제 해결

### 모델 다운로드 실패

```bash
# 수동으로 모델 다운로드
python -c "from fastembed import TextEmbedding; TextEmbedding('intfloat/multilingual-e5-large')"
```

### 메모리 부족

Dense 모델은 약 2GB 메모리가 필요합니다. 메모리가 부족한 경우:
- 다른 프로세스 종료
- 서버 메모리 증설

### Qdrant 연결 오류

```bash
# Qdrant 서버 상태 확인
curl http://localhost:6333/health

# Docker로 Qdrant 실행
docker run -p 6333:6333 qdrant/qdrant
```

## 레거시: BGE-M3 (더 이상 사용하지 않음)

이전에 사용하던 `BAAI/bge-m3` 모델은 `shared/services/embedding.py`에 있지만,
현재는 `QdrantService`의 `multilingual-e5-large` + BM25 하이브리드 검색을 사용합니다.

## 참고

- 첫 실행 시 모델 다운로드로 인해 시간이 걸릴 수 있습니다 (~3-5분)
- 모델은 캐시되므로 이후 실행은 빠릅니다 (~2-3초)
- 프로덕션 환경에서는 서버 시작 시 모델을 미리 로드하는 것을 권장
