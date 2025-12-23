# TQ Data Platform

한국 정부 복지 정보 수집 및 제공 플랫폼

## 빠른 시작

### 개발 환경 실행

```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 편집하여 API 키와 Cloudflare 자격증명 입력

# 2. Docker로 실행
docker-compose up

# 3. API 접속
# - API 서버: http://localhost:8000
# - API 문서: http://localhost:8000/docs
# - Health Check: http://localhost:8000/health
```

### 중지

```bash
docker-compose down
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
- ☁️ Cloudflare D1 데이터 저장
- 🔄 자동 스케줄 배치 작업 (매일 새벽 2시)
- 🚀 FastAPI 기반 REST API 제공
- 🐳 Docker 개발 환경

## API 엔드포인트

- `GET /` - API 상태 확인
- `GET /health` - 헬스 체크
- `GET /welfare/policies` - 복지 정책 목록
- `GET /welfare/policies/{id}` - 정책 상세 정보
- `GET /welfare/stats` - 통계 정보

## 자세한 문서

- [DEPLOYMENT.md](DEPLOYMENT.md) - 배포 및 설정 가이드
- [CLAUDE.md](CLAUDE.md) - 프로젝트 개요 및 아키텍처
- [tests/README.md](tests/README.md) - 테스트 가이드
