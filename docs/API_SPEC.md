# TQ Data Platform API 스펙

> **Version**: 0.1.0
> **Base URL**: `http://localhost:8000`
> **API 문서**: `/docs` (Swagger UI) | `/redoc` (ReDoc)

---

## 도메인별 API 문서

| 도메인                          | 문서          | Prefix        | 설명                           |
| ------------------------------- | ------------- | ------------- | ------------------------------ |
| [Auth](api/auth.md)             | 인증 API      | `/auth`       | 회원가입, 로그인, 토큰 갱신    |
| [Onboarding](api/onboarding.md) | 온보딩 API    | `/onboarding` | 대화형 회원가입 및 프로필 수집 |
| [Dashboard](api/dashboard.md)   | 대시보드 API  | `/dashboard`  | 맞춤 요약 정보 및 정책 피드    |
| [Welfare](api/welfare.md)       | 복지 정책 API | `/welfare`    | 정책 목록/상세 조회, 통계      |
| [Search](api/search.md)         | 검색 API      | `/search`     | 시맨틱 검색 (하이브리드)       |
| [Chat](api/chat.md)             | 챗봇 API      | `/chat`       | 멀티 에이전트 오케스트레이션   |
| [Core](api/core.md)             | Core 모듈     | `/`           | 헬스 체크, 에러 처리           |

---

## 프로젝트 구조

```
app/
├── main.py              # FastAPI 진입점
├── auth/                # 인증 도메인
│   ├── router.py        # /auth/* 엔드포인트
│   ├── service.py       # AuthService
│   └── schemas.py       # User 스키마
├── chat/                # 챗봇 도메인
│   ├── router.py        # /chat/* 엔드포인트
│   ├── service.py       # RAGService
│   ├── conversation.py  # ConversationFlow
│   └── schemas.py       # Chat 스키마
├── welfare/             # 복지정책 도메인
│   └── router.py        # /welfare/* 엔드포인트
├── search/              # 검색 도메인
│   ├── router.py        # /search/* 엔드포인트
│   └── schemas.py       # Search 스키마
├── core/                # 공통 모듈
│   ├── exceptions.py    # 커스텀 예외
│   └── health.py        # 헬스체크 라우터
└── middleware/          # 미들웨어
    └── error_handler.py # 전역 에러 핸들러
```

---

## 기술 스택

| 영역         | 기술                                  |
| ------------ | ------------------------------------- |
| Framework    | FastAPI                               |
| 인증         | JWT (Access + Refresh Token)          |
| 검색         | Qdrant + multilingual-e5-large + BM25 |
| LLM          | OpenAI GPT-4o-mini                    |
| 데이터베이스 | PostgreSQL                            |
| 대화 흐름    | LangGraph                             |

---

## 엔드포인트 요약

### Auth (`/auth`)

| Method | Endpoint         | 설명             |
| ------ | ---------------- | ---------------- |
| POST   | `/auth/register` | 회원가입         |
| POST   | `/auth/login`    | 로그인           |
| POST   | `/auth/refresh`  | 토큰 갱신        |
| GET    | `/auth/me`       | 현재 사용자 정보 |
| POST   | `/auth/logout`   | 로그아웃         |

### Welfare (`/welfare`)

| Method | Endpoint                        | 설명           |
| ------ | ------------------------------- | -------------- |
| GET    | `/welfare/policies`             | 정책 목록 조회 |
| GET    | `/welfare/policies/{policy_id}` | 정책 상세 조회 |
| GET    | `/welfare/stats`                | 정책 통계      |

### Search (`/search`)

| Method | Endpoint           | 설명             |
| ------ | ------------------ | ---------------- |
| GET    | `/search/semantic` | 시맨틱 검색      |
| GET    | `/search/health`   | 검색 서비스 상태 |

### Onboarding (`/onboarding`)

| Method | Endpoint                   | 설명                          |
| ------ | -------------------------- | ----------------------------- |
| POST   | `/onboarding/registration` | 대화형 게스트 회원가입        |
| POST   | `/onboarding/conversation` | 대화형 프로필 수집 (인증필요) |
| POST   | `/onboarding/complete`     | 온보딩 완료 및 데이터 저장    |

### Chat (`/chat`)

| Method | Endpoint                    | 설명                    |
| ------ | --------------------------- | ----------------------- |
| POST   | `/chat/conversation`        | 멀티 에이전트 복지 상담 |
| POST   | `/chat/conversation/stream` | 상담 스트리밍 (SSE)     |
| GET    | `/chat/conversations`       | 이전 대화 목록 조회     |
| PATCH  | `/chat/conversations/{id}`  | 대화방 제목/상태 수정   |
| GET    | `/chat/bookmarks`           | 북마크한 정책 목록      |

### Core (`/`)

| Method | Endpoint  | 설명      |
| ------ | --------- | --------- |
| GET    | `/`       | API 상태  |
| GET    | `/health` | 헬스 체크 |

---

## 공통 헤더

```http
Content-Type: application/json
Authorization: Bearer <access_token>  # 인증 필요 시
```

---

## 에러 응답 형식

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "에러 메시지",
    "details": {},
    "path": "/endpoint"
  }
}
```

자세한 내용은 [Core 모듈 문서](api/core.md)를 참조하세요.

---

## 참고

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI 스키마**: http://localhost:8000/openapi.json
