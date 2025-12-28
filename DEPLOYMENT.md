# Deployment Guide

## 프로젝트 구조

이 프로젝트는 두 가지 실행 환경으로 분리되어 있습니다:

### 1. 배치 작업 (GitHub Actions)
- **위치**: `batch/`, `main.py`
- **실행**: GitHub Actions에서 자동 실행 (매일 02:00 KST)
- **용도**: 공공데이터 API에서 복지 정보 수집 및 D1 저장

### 2. 애플리케이션 (배포용)
- **위치**: `app/`, `shared/`
- **배포**: 실제 서비스 환경에 배포
- **용도**: API 서버 또는 웹 애플리케이션

## 의존성 관리

### 로컬 개발 (모든 기능 포함)
```bash
# 전체 의존성 설치
uv pip install -e ".[dev,batch]"
```

### 배포 환경 (배치 제외)
```bash
# 배포용 의존성만 설치 (batch 제외)
uv pip install -e .
```

### GitHub Actions (배치만)
```bash
# 배치 작업용 의존성만 설치
uv pip install -e ".[batch]"
```

## GitHub Actions 설정

### Secrets 설정
기존 `schedule.yaml` 워크플로우가 이미 설정되어 있습니다.

GitHub 저장소의 Settings → Secrets and variables → Actions에서 다음 secrets가 설정되어 있어야 합니다:

- `API_KEYS`: Public Data Portal API 키들
- `CLOUDFLARE_ACCOUNT_ID`: Cloudflare 계정 ID
- `CLOUDFLARE_API_TOKEN`: Cloudflare API 토큰
- `CLOUDFLARE_D1_DB_ID`: Cloudflare D1 데이터베이스 ID

### 수동 실행
1. GitHub 저장소의 Actions 탭으로 이동
2. "Scheduled Data Collection" 워크플로우 선택
3. "Run workflow" 버튼 클릭

### 자동 실행
- 매일 00:00 KST (15:00 UTC 전날) 자동 실행

## 배포 빌드

배포용 패키지를 빌드할 때 `batch/` 디렉토리는 자동으로 제외됩니다:

```bash
# 배포용 wheel 패키지 빌드 (batch 제외됨)
uv build

# 생성된 파일: dist/tq_data_platform-0.1.0-py3-none-any.whl
```

빌드된 패키지에는 다음만 포함됩니다:
- `app/` (API 서버 및 비즈니스 로직)
- `shared/` (공통 코드: config, db, external clients)

다음은 제외됩니다:
- `batch/` ❌
- `scripts/` ❌
- `tests/` ❌
- 테스트 파일 ❌

## 환경 변수

### 배치 작업 (GitHub Actions)
모든 환경 변수는 GitHub Secrets로 관리됩니다.

### 애플리케이션 (배포 환경)
필요한 환경 변수를 배포 환경에 설정하세요:
```bash
# 예: Cloudflare Workers, Railway, Fly.io 등
export CLOUDFLARE_ACCOUNT_ID="..."
export CLOUDFLARE_API_TOKEN="..."
export CLOUDFLARE_D1_DB_ID="..."
```

## 디렉토리 구조

```
tq-data-platform/
├── app/              ✅ 배포에 포함 (애플리케이션 코드)
│   ├── main.py       → FastAPI 서버 진입점
│   └── services/     → 비즈니스 로직 (WelfareService, Processor 등)
├── shared/           ✅ 배포에 포함 (공통 코드)
│   ├── clients/      → 외부 서비스 클라이언트 (Public Data Portal, LLM)
│   ├── config/       → 설정 (환경변수 관리)
│   └── db/           → 데이터베이스 (D1Client, SQLAlchemy)
├── batch/            ❌ 배포에서 제외 (GitHub Actions 전용)
│   ├── core.py       → 배치 작업 프레임워크
│   ├── steps.py      → 작업 단계 정의
│   └── main.py       → 배치 작업 진입점
├── scripts/          ❌ 배포에서 제외 (개발 유틸리티)
├── tests/            ❌ 배포에서 제외 (테스트)
├── pyproject.toml    📝 의존성 및 빌드 설정
└── .github/
    └── workflows/
        └── schedule.yaml  🤖 배치 작업 자동화 (매일 00:00 KST)
```

### 구조 설명

**app/** - 배포용 애플리케이션 코드
- FastAPI 서버 및 비즈니스 로직
- 배포 시 이 디렉토리가 패키징됨
- `from app.services.welfare import WelfareService` 형태로 import

**shared/** - 공통 코드 (app과 batch 모두 사용)
- clients: 외부 서비스 클라이언트 (Public Data Portal, LLM)
- config: 환경변수 및 설정 관리
- db: D1Client, SQLAlchemy 설정
- `from shared.config.settings import settings` 형태로 import
- 배포 시 함께 패키징됨

**batch/** - 배치 작업 전용 (완전히 분리됨)
- GitHub Actions에서 `python batch/main.py` 실행
- 배포 패키지에서 완전히 제외
- shared/ 코드를 import하여 사용
- 배치 관련 모든 코드가 한 곳에 모여있음

**scripts/** - 개발/테스트 유틸리티
- 로컬 개발 및 디버깅용
- 배포 패키지에서 제외

**tests/** - 테스트 코드
- pytest 기반 단위/통합 테스트
- 배포 패키지에서 제외

## 개발 워크플로우

1. **로컬 개발**: 모든 기능 사용 가능
   ```bash
   cd tq-data-platform
   # direnv가 자동으로 .venv 활성화
   uv pip install -e ".[dev,batch]"
   ```

2. **배치 테스트**: 로컬에서 배치 작업 테스트
   ```bash
   python batch/main.py
   ```

3. **API 서버 개발**: FastAPI 서버 실행
   ```bash
   # 개발 모드 (핫 리로드)
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

   # 프로덕션 모드
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

   API 문서:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

4. **배포**: 배치 코드 없이 배포
   ```bash
   uv build  # batch/ 자동 제외
   ```

## Docker 실행

### 개발 (기본)
```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 파일 편집하여 Cloudflare 자격증명 추가

# 2. 빌드 (BGE-M3 모델 포함)
docker-compose build
# ⏱️ 첫 빌드 시 BGE-M3 모델 다운로드 (~2GB, 5-10분 소요)
# ✅ 이후 재빌드/재배포 시 모델 즉시 사용 가능

# 3. 실행
docker-compose up

# 4. 백그라운드 실행
docker-compose up -d

# 5. 로그 확인
docker-compose logs -f api

# 6. 중지
docker-compose down
```

**특징:**
- 🔥 코드 변경 시 자동 리로드 (핫 리로드)
- 📁 app/, shared/ 디렉토리가 컨테이너에 마운트됨
- 🧠 BGE-M3 모델이 이미지에 포함되어 즉시 사용 가능
- 🌐 http://localhost:8000 접속
- 📚 API 문서: http://localhost:8000/docs

### 프로덕션 배포

Docker 이미지는 BGE-M3 모델을 포함하고 있어 재배포 시에도 즉시 실행됩니다:

```bash
# 이미지 빌드
docker build -t tq-data-platform:latest .

# 실행
docker run -p 8000:8000 \
  -e CLOUDFLARE_ACCOUNT_ID="..." \
  -e CLOUDFLARE_API_TOKEN="..." \
  -e CLOUDFLARE_D1_DB_ID="..." \
  -e POSTGRES_HOST="..." \
  -e QDRANT_HOST="..." \
  -e USE_EMBEDDINGS=true \
  tq-data-platform:latest
```

**이미지 사양:**
- 전체 이미지 크기: ~4-5GB (BGE-M3 모델 2GB 포함)
- 첫 빌드 시간: 10-15분 (모델 다운로드 포함)
- 재빌드 시간: 1-2분 (캐시 활용)
- 재배포 시: 모델 다운로드 없이 즉시 실행

## API 서버 엔드포인트

### 기본
- `GET /` - API 상태 확인
- `GET /health` - 헬스 체크

### 복지 정책
- `GET /welfare/policies` - 복지 정책 목록 조회
  - Query params: `limit` (기본: 100), `offset` (기본: 0)
- `GET /welfare/policies/{policy_id}` - 특정 정책 상세 조회
- `GET /welfare/stats` - 복지 정책 통계 정보

## 테스트

### 테스트 실행
```bash
# 모든 테스트 실행
pytest

# 커버리지 포함
pytest --cov=app --cov-report=html

# 특정 마커만 실행
pytest -m unit          # 단위 테스트만
pytest -m integration   # 통합 테스트만
pytest -m "not slow"    # 느린 테스트 제외
```

### 테스트 구조
```
tests/
├── conftest.py              # Fixtures 및 설정
├── unit/                    # 단위 테스트
│   ├── test_api.py          # API 엔드포인트
│   ├── test_services.py     # 서비스 레이어
│   └── test_processing.py   # 데이터 처리
└── integration/             # 통합 테스트
    └── test_api_integration.py
```

### CI/CD에서 테스트
```yaml
- name: Run tests
  run: |
    pytest --cov=app --cov-report=xml
```

더 자세한 내용은 [tests/README.md](tests/README.md) 참고
