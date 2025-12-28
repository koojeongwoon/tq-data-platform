# TQ Data Platform

한국 정부 복지 정보 수집 및 제공 플랫폼

## 빠른 시작

### 개발 환경 설정 (최초 1회)

```bash
# 1. 의존성 설치
uv sync --extra dev

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일을 열어서 API 키와 DB 정보 입력
```

**BGE-M3 모델 다운로드**:
- **자동**: API 서버나 배치 작업 첫 실행 시 자동 다운로드 (~2GB, 5-10분)
- **수동** (미리 받으려면): `uv run setup-dev` 실행

**참고**: 모델은 `~/.cache/huggingface/hub/`에 저장되며, 한 번만 다운로드됩니다.

### 개발 환경 실행

```bash
# 1. Docker 서비스 시작
docker compose up -d postgres qdrant

# 2. API 서버 시작 (자동으로 BGE-M3 모델 로딩)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. API 접속
# - API 서버: http://localhost:8000
# - API 문서: http://localhost:8000/docs
# - Health Check: http://localhost:8000/health
# - 검색: http://localhost:8000/search/semantic?q=임신부%20지원
```

### 배치 작업 실행

```bash
# 데이터 수집 + 동기화
python batch/main.py

# 동기화만 (D1 → PostgreSQL + Qdrant)
python batch/sync_only.py
```

### 중지

```bash
docker compose down
```

## 프로젝트 구조

```
tq-data-platform/
├── app/              # FastAPI 서버 (배포용)
│   ├── main.py       # API 진입점
│   └── services/     # 비즈니스 로직
├── shared/           # 공통 코드 (app/batch 공유)
│   ├── clients/      # 외부 API 클라이언트
│   ├── config/       # 설정
│   └── db/           # 데이터베이스
├── batch/            # 배치 작업 (GitHub Actions)
└── tests/            # 테스트
```

## 주요 기능

- 🏛️ 공공데이터포털 API 연동 (중앙/지역정부 복지 서비스)
- ☁️ Cloudflare D1 원본 데이터 저장 (XML)
- 🗄️ PostgreSQL 키워드 검색 (전문 검색, 필터링)
- 🔍 Qdrant 벡터 검색 (BGE-M3 의미 기반 검색)
- 🤖 BGE-M3 임베딩 모델 (한국어 최적화)
- 🔄 자동 스케줄 배치 작업 (매일 새벽 2시)
- 🚀 FastAPI 기반 REST API 제공
- 🐳 Docker 개발 환경

## API 엔드포인트

### 기본
- `GET /health` - 헬스 체크

### 검색 (NEW!)
- `GET /search/semantic?q=임신부 지원` - 의미 기반 검색 (BGE-M3)
- `GET /search/health` - 검색 서비스 상태

### 복지 정책
- `GET /welfare/policies` - 복지 정책 목록
- `GET /welfare/policies/{id}` - 정책 상세 정보
- `GET /welfare/stats` - 통계 정보

자세한 내용: http://localhost:8000/docs

## 검색 예시

```bash
# 임신부 지원 정책 검색
curl "http://localhost:8000/search/semantic?q=임신부%20지원&limit=5"

# 청년 창업 정책 (중앙정부만)
curl "http://localhost:8000/search/semantic?q=청년%20창업&source_type=central"

# 어르신 건강 정책 (지역정부만)
curl "http://localhost:8000/search/semantic?q=어르신%20건강&source_type=regional"
```

## 자세한 문서

- **[docs/BGE_M3_SETUP.md](docs/BGE_M3_SETUP.md)** - BGE-M3 임베딩 모델 설정
- **[docs/API_USAGE.md](docs/API_USAGE.md)** - API 사용 가이드
- [DEPLOYMENT.md](DEPLOYMENT.md) - 배포 및 설정 가이드
- [CLAUDE.md](CLAUDE.md) - 프로젝트 개요 및 아키텍처
- [tests/README.md](tests/README.md) - 테스트 가이드
