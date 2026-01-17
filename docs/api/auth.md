# 인증 API (Auth)

> **모듈**: `app/auth/`
> **Prefix**: `/auth`
> **Tags**: `Auth`

---

## 개요

JWT 기반 인증 시스템을 제공합니다.

- **Access Token**: 30분 유효
- **Refresh Token**: 7일 유효 (Rotation 방식)
- **비밀번호**: bcrypt 해싱

### 회원가입 흐름

```
1. POST /auth/register → 계정 생성 + 토큰 발급
2. POST /onboarding/conversation → 온보딩 대화 (지역, 생애주기, 관심분야 수집)
3. POST /onboarding/complete → 온보딩 완료 처리
4. 이후 서비스 이용 가능
```

> **중요**: 온보딩 미완료 사용자는 `user.onboarding_completed = false`로 표시됩니다.
> 프론트엔드에서 이 값을 확인하여 온보딩 페이지로 리다이렉트해야 합니다.

### 파일 구조

```
server/api/auth/
├── register.post.ts    # 회원가입
├── login.post.ts       # 로그인
├── refresh.post.ts     # 토큰 갱신
├── me.get.ts           # 내 정보 조회
└── logout.post.ts      # 로그아웃

server/api/onboarding/
├── conversation.post.ts  # 온보딩 대화
└── complete.post.ts      # 온보딩 완료
```

---

## 엔드포인트

### POST `/auth/register` - 회원가입

새 사용자 계정을 생성하고 자동 로그인합니다.

**Request Body**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "name": "홍길동"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| email | string (email) | ✅ | 이메일 주소 |
| password | string | ✅ | 비밀번호 (최소 8자) |
| name | string | ✅ | 이름 (2-50자) |

**Response** `201 Created`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "홍길동",
    "created_at": "2025-01-15T10:00:00",
    "is_active": true,
    "onboarding_completed": false
  }
}
```

> 회원가입 직후에는 `onboarding_completed: false`입니다.
> 프론트엔드는 이 값을 확인하여 `/onboarding` 페이지로 이동해야 합니다.

**Errors**
| 코드 | 설명 |
|------|------|
| 400 | 이미 등록된 이메일 |
| 422 | 유효성 검증 실패 |

---

### POST `/auth/login` - 로그인

**Request Body**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "홍길동",
    "created_at": "2025-01-15T10:00:00",
    "is_active": true,
    "onboarding_completed": true
  }
}
```

> `onboarding_completed`가 `false`인 경우 프론트엔드에서 `/onboarding`으로 리다이렉트해야 합니다.

**Errors**
| 코드 | 설명 |
|------|------|
| 401 | 이메일 또는 비밀번호 오류 |
| 401 | 비활성화된 계정 |

---

### POST `/auth/refresh` - 토큰 갱신

Refresh Token Rotation (RTR) 방식으로 새 토큰 쌍을 발급합니다.
기존 리프레시 토큰은 즉시 무효화됩니다.

**Request Body**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors**
| 코드 | 설명 |
|------|------|
| 401 | 유효하지 않거나 만료된 리프레시 토큰 |

---

### GET `/auth/me` - 현재 사용자 정보

**Headers**
```http
Authorization: Bearer <access_token>
```

**Response** `200 OK`
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "홍길동",
  "created_at": "2025-01-15T10:00:00",
  "is_active": true,
  "onboarding_completed": true,
  "profile": {
    "region": "서울",
    "life_cycle": "청년",
    "interests": "주거/임대, 취업/창업"
  }
}
```

**Errors**
| 코드 | 설명 |
|------|------|
| 401 | 유효하지 않거나 만료된 토큰 |

---

### POST `/auth/logout` - 로그아웃

**Headers**
```http
Authorization: Bearer <access_token>
```

**Response** `200 OK`
```json
{
  "message": "로그아웃 되었습니다",
  "user_id": 1
}
```

---

## 데이터 모델

### UserCreate (Request)

```python
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=2, max_length=50)
```

### UserResponse

```python
class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    created_at: datetime
    is_active: bool
```

### TokenResponse

```python
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: Optional[UserResponse] = None
```

---

## 사용 예시

### JavaScript

```javascript
// 회원가입
const register = async (email, password, name) => {
  const res = await fetch('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name })
  });
  return res.json();
};

// 토큰 갱신
const refreshToken = async (refreshToken) => {
  const res = await fetch('/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  });
  return res.json();
};

// 인증된 요청
const fetchWithAuth = async (url, token) => {
  const res = await fetch(url, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return res.json();
};
```

### Python

```python
import requests

class AuthClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token = None

    def login(self, email: str, password: str) -> dict:
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password}
        )
        data = response.json()
        self.token = data.get("access_token")
        return data

    def get_me(self) -> dict:
        response = requests.get(
            f"{self.base_url}/auth/me",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        return response.json()
```
