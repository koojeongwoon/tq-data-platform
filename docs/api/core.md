# Core 모듈 API

> **모듈**: `app/core/`
> **Prefix**: `/` (루트)
> **Tags**: `Health`

---

## 개요

애플리케이션의 공통 기능을 제공합니다.

- 헬스 체크 엔드포인트
- 커스텀 예외 클래스
- 공통 유틸리티

### 파일 구조

```
app/core/
├── __init__.py       # health_router export
├── health.py         # 헬스 체크 라우터
└── exceptions.py     # 커스텀 예외 클래스
```

---

## 엔드포인트

### GET `/` - API 상태

API 서버의 기본 정보를 반환합니다.

**Response** `200 OK`
```json
{
  "message": "TQ Data Platform API",
  "version": "0.1.0",
  "status": "running"
}
```

---

### GET `/health` - 헬스 체크

서버 상태를 확인합니다. 로드밸런서나 컨테이너 오케스트레이션에서 사용합니다.

**Response** `200 OK`
```json
{
  "status": "healthy"
}
```

---

## 커스텀 예외 (`app/core/exceptions.py`)

### TQBaseException

모든 커스텀 예외의 기본 클래스입니다.

```python
class TQBaseException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details
        super().__init__(message)
```

### 파생 예외 클래스

| 예외 클래스 | 상태 코드 | 에러 코드 | 용도 |
|------------|----------|-----------|------|
| NotFoundError | 404 | NOT_FOUND | 리소스 없음 |
| ValidationError | 400 | VALIDATION_ERROR | 유효성 검증 실패 |
| AuthenticationError | 401 | AUTHENTICATION_ERROR | 인증 실패 |
| AuthorizationError | 403 | AUTHORIZATION_ERROR | 권한 없음 |
| ServiceUnavailableError | 503 | SERVICE_UNAVAILABLE | 서비스 이용 불가 |

### 사용 예시

```python
from app.core.exceptions import NotFoundError, ValidationError

# 정책을 찾을 수 없을 때
raise NotFoundError(
    message="정책을 찾을 수 없습니다",
    details={"policy_id": "WLF00000123"}
)

# 유효성 검증 실패
raise ValidationError(
    message="검색어는 2자 이상이어야 합니다",
    details={"field": "q", "value": "a"}
)
```

---

## 에러 응답 형식

`app/middleware/error_handler.py`에서 모든 예외를 일관된 형식으로 변환합니다.

### 응답 구조

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "정책을 찾을 수 없습니다",
    "details": {
      "policy_id": "WLF00000123"
    },
    "path": "/welfare/policies/WLF00000123"
  }
}
```

### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| code | string | 에러 코드 (프로그래밍용) |
| message | string | 사람이 읽을 수 있는 메시지 |
| details | object | 추가 정보 (개발 환경에서만) |
| path | string | 요청 경로 |

### 환경별 동작

- **Development**: `details` 포함, 전체 스택 트레이스
- **Production**: `details` 제외, 일반화된 메시지

---

## HTTP 상태 코드

| 코드 | 설명 | 사용 상황 |
|------|------|----------|
| 200 | OK | 성공 |
| 201 | Created | 리소스 생성 성공 |
| 400 | Bad Request | 잘못된 요청 파라미터 |
| 401 | Unauthorized | 인증 실패 |
| 403 | Forbidden | 권한 없음 |
| 404 | Not Found | 리소스 없음 |
| 422 | Unprocessable Entity | 유효성 검증 실패 |
| 500 | Internal Server Error | 서버 내부 오류 |
| 503 | Service Unavailable | 서비스 이용 불가 |

---

## 사용 예시

### JavaScript

```javascript
// 헬스 체크
const checkHealth = async () => {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    return data.status === 'healthy';
  } catch {
    return false;
  }
};

// 에러 처리
const handleError = (error) => {
  if (error.error) {
    console.error(`[${error.error.code}] ${error.error.message}`);
    if (error.error.details) {
      console.error('Details:', error.error.details);
    }
  }
};
```

### Python

```python
import requests

def check_health(base_url: str) -> bool:
    try:
        response = requests.get(f"{base_url}/health")
        return response.json().get("status") == "healthy"
    except:
        return False

def handle_api_error(response: requests.Response):
    if not response.ok:
        error = response.json().get("error", {})
        print(f"[{error.get('code')}] {error.get('message')}")
        raise Exception(error.get("message"))
```
