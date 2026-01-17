# TQ Data Platform API 연동 가이드

> 프론트엔드 개발자를 위한 API 연동 문서

## 빠른 시작

### Base URL
```
개발: http://localhost:8000
```

### 인증 흐름

```
1. POST /auth/login → access_token, refresh_token 획득
2. 요청 헤더에 Authorization: Bearer {access_token} 추가
3. 401 응답 시 → POST /auth/refresh로 토큰 갱신
```

### 회원가입 흐름

```
1. POST /auth/register → 계정 생성 + 토큰 발급 (onboarding_completed: false)
2. POST /onboarding/conversation → 온보딩 대화 (지역, 생애주기, 관심분야)
3. POST /onboarding/complete → 온보딩 완료 (onboarding_completed: true)
4. 이후 서비스 이용 가능
```

> **중요**: 로그인/회원가입 후 `user.onboarding_completed`가 `false`면 `/onboarding`으로 리다이렉트

---

## 도메인별 API 문서

| 도메인 | 문서 | 주요 기능 |
|--------|------|----------|
| [auth.md](auth.md) | 인증 | 로그인, 회원가입, 토큰 갱신 |
| [onboarding.md](onboarding.md) | 온보딩 | 대화형 프로필 수집 |
| [welfare.md](welfare.md) | 복지 정책 | 정책 목록/상세 조회 |
| [search.md](search.md) | 검색 | 시맨틱 검색 |
| [chat.md](chat.md) | 챗봇 | RAG 챗봇, 스트리밍 |
| [core.md](core.md) | Core | 헬스 체크, 에러 처리 |

---

## 핵심 연동 패턴

### 1. 인증 (JWT)

```typescript
// 로그인
const login = async (email: string, password: string) => {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  const data = await res.json();

  // 토큰 저장
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);

  return data.user;
};

// 인증된 요청
const authFetch = async (url: string, options: RequestInit = {}) => {
  const token = localStorage.getItem('access_token');

  const res = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });

  // 토큰 만료 시 갱신
  if (res.status === 401) {
    const refreshed = await refreshToken();
    if (refreshed) {
      return authFetch(url, options); // 재시도
    }
    throw new Error('인증 만료');
  }

  return res.json();
};

// 토큰 갱신
const refreshToken = async () => {
  const refresh = localStorage.getItem('refresh_token');

  const res = await fetch('/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh })
  });

  if (res.ok) {
    const data = await res.json();
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    return true;
  }

  // 갱신 실패 시 로그아웃 처리
  localStorage.clear();
  return false;
};
```

### 2. 검색

```typescript
interface SearchResult {
  policy_id: string;
  score: number;
  title: string;
  summary: string;
  ministry: string;
  source_type: 'central' | 'regional';
  phone?: string;
  website?: string;
}

const searchPolicies = async (
  query: string,
  options?: { source_type?: string; limit?: number }
) => {
  const params = new URLSearchParams({ q: query, ...options });
  const res = await fetch(`/search/semantic?${params}`);

  if (!res.ok) {
    if (res.status === 503) {
      throw new Error('검색 서비스 준비 중');
    }
    throw new Error('검색 실패');
  }

  return res.json() as Promise<{
    query: string;
    total: number;
    results: SearchResult[];
  }>;
};
```

### 3. 챗봇 스트리밍 (SSE)

```typescript
interface ChatSource {
  policy_id: string;
  title: string;
  score: number;
  summary: string;
  ministry: string;
  phone?: string;
  website?: string;
}

const chatStream = async (
  query: string,
  callbacks: {
    onSources?: (sources: ChatSource[]) => void;
    onChunk?: (text: string) => void;
    onDone?: () => void;
    onError?: (error: string) => void;
  }
) => {
  const res = await fetch('/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: 5 })
  });

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let currentEvent = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7);
      } else if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));

        switch (currentEvent) {
          case 'sources':
            callbacks.onSources?.(data);
            break;
          case 'answer':
            callbacks.onChunk?.(data.text);
            break;
          case 'done':
            callbacks.onDone?.();
            break;
          case 'error':
            callbacks.onError?.(data.error);
            break;
        }
      }
    }
  }
};

// 사용 예시
let answer = '';
const sources: ChatSource[] = [];

await chatStream('임신부 지원 정책 알려줘', {
  onSources: (s) => {
    sources.push(...s);
    renderSourceCards(s);  // UI에 정책 카드 표시
  },
  onChunk: (text) => {
    answer += text;
    updateAnswerUI(answer);  // 실시간 답변 업데이트
  },
  onDone: () => {
    console.log('완료');
  }
});
```

### 4. 대화형 챗봇

```typescript
interface ConversationResponse {
  response: string;
  session_id: string;
  intent: 'welfare_search' | 'policy_detail' | 'general_question' | 'chitchat';
  ready_to_search: boolean;
  user_profile: {
    region?: string;
    life_cycle?: string;
  };
  sources?: ChatSource[];
}

class ConversationClient {
  private sessionId: string | null = null;

  async send(message: string): Promise<ConversationResponse> {
    const res = await fetch('/chat/conversation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: this.sessionId
      })
    });

    const data = await res.json();
    this.sessionId = data.session_id;
    return data;
  }

  async close() {
    if (this.sessionId) {
      await fetch(`/chat/conversation/${this.sessionId}`, {
        method: 'DELETE'
      });
      this.sessionId = null;
    }
  }
}

// 사용 예시
const chat = new ConversationClient();

const r1 = await chat.send('정책 알려줘');
// → "어느 지역에 거주하고 계신가요?"

const r2 = await chat.send('서울');
// → "현재 상황에 해당하는 것이 있으신가요?"

const r3 = await chat.send('임신 중');
// → 검색 결과 + RAG 답변 (r3.sources에 정책 목록)

await chat.close();
```

---

## 에러 처리

### 에러 응답 형식

```typescript
interface ApiError {
  error: {
    code: string;      // 에러 코드 (프로그래밍용)
    message: string;   // 사용자에게 보여줄 메시지
    details?: object;  // 추가 정보 (개발 환경만)
    path: string;      // 요청 경로
  };
}
```

### 공통 에러 처리

```typescript
const handleApiError = async (res: Response) => {
  if (res.ok) return;

  const error = await res.json() as ApiError;

  switch (res.status) {
    case 400:
      throw new Error(error.error.message || '잘못된 요청입니다');
    case 401:
      // 로그인 페이지로 리다이렉트
      window.location.href = '/login';
      break;
    case 404:
      throw new Error('요청한 정보를 찾을 수 없습니다');
    case 503:
      throw new Error('서비스가 일시적으로 이용 불가합니다');
    default:
      throw new Error('오류가 발생했습니다');
  }
};
```

### 주요 에러 코드

| 코드 | HTTP | 설명 |
|------|------|------|
| VALIDATION_ERROR | 400/422 | 입력값 검증 실패 |
| AUTHENTICATION_ERROR | 401 | 인증 실패/토큰 만료 |
| NOT_FOUND | 404 | 리소스 없음 |
| SERVICE_UNAVAILABLE | 503 | 서비스 이용 불가 |

---

## TypeScript 타입 정의

```typescript
// 사용자
interface User {
  id: number;
  email: string;
  name: string;
  created_at: string;
  is_active: boolean;
  onboarding_completed: boolean;
  profile?: {
    region?: string;
    life_cycle?: string;
    interests?: string;
  };
}

// 정책
interface Policy {
  policy_id: string;
  title: string;
  summary?: string;
  ministry?: string;
  source_type: 'central' | 'regional';
  ctpv_nm?: string;  // 시/도
  sgg_nm?: string;   // 시/군/구
  support_content?: string;
  target_detail?: string;
  application_method?: string;
  phone?: string;
  website?: string;
}

// 검색 결과
interface SearchResult extends Policy {
  score: number;
}

// 토큰 응답
interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
  user?: User;
}
```

---

## 환경 설정

### React (Vite)

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/auth': 'http://localhost:8000',
      '/welfare': 'http://localhost:8000',
      '/search': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
    }
  }
});
```

### Next.js

```typescript
// next.config.js
module.exports = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*'
      }
    ];
  }
};
```

---

## API 테스트

### Swagger UI
http://localhost:8000/docs

### curl 예시

```bash
# 로그인
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"password123"}'

# 검색
curl "http://localhost:8000/search/semantic?q=임신부%20지원&limit=5"

# 챗봇
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"청년 주거 지원 정책 알려줘"}'
```

---

## 문의

API 관련 문의사항은 백엔드 팀에 연락해주세요.
