# 온보딩 API (Onboarding)

> **모듈**: `server/api/onboarding/`
> **Prefix**: `/onboarding`
> **Tags**: `Onboarding`

---

## 개요

회원가입 후 사용자 프로필을 수집하는 대화형 온보딩 시스템입니다.

### 온보딩 흐름

```
1. 회원가입 완료 (onboarding_completed: false)
2. POST /onboarding/conversation → 대화 시작
3. 지역 → 생애주기 → 관심분야 순서로 수집
4. POST /onboarding/complete → 온보딩 완료 처리
5. 이후 서비스 이용 가능 (onboarding_completed: true)
```

### 수집 정보

| 필드 | 설명 | 예시 |
|------|------|------|
| region | 거주 지역 (시/도) | 서울, 경기, 부산 등 |
| life_cycle | 생애주기 | 임신/출산, 영유아 양육, 청년 등 |
| interests | 관심 분야 (복수 선택) | 주거/임대, 취업/창업, 교육/장학 등 |

### 파일 구조

```
server/api/onboarding/
├── conversation.post.ts  # 온보딩 대화
└── complete.post.ts      # 온보딩 완료
```

---

## 엔드포인트

### POST `/onboarding/conversation` - 온보딩 대화

대화형으로 사용자 프로필 정보를 수집합니다.

**Headers**
```http
Authorization: Bearer <access_token>
```

**Request Body**
```json
{
  "message": "서울이요",
  "session_id": "onb_abc123..."
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| message | string | ✅ | 사용자 메시지 (첫 요청 시 빈 문자열 가능) |
| session_id | string | ❌ | 세션 ID (없으면 새 세션 생성) |

**Response** `200 OK`
```json
{
  "response": "서울에 사시는군요! 👍\n\n현재 상황에 해당하는 것이 있으신가요?",
  "session_id": "onb_abc123...",
  "step": "collect_life_cycle",
  "profile": {
    "region": "서울"
  },
  "is_completed": false,
  "quick_replies": ["임신/출산", "영유아 양육", "아동/청소년", "청년", "중장년", "노년"]
}
```

**Response 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| response | string | AI 응답 메시지 |
| session_id | string | 세션 ID |
| step | string | 현재 단계 |
| profile | object | 수집된 프로필 정보 |
| is_completed | boolean | 온보딩 완료 여부 |
| quick_replies | string[] | 빠른 응답 버튼 목록 |

**온보딩 단계 (step)**

| Step | 설명 |
|------|------|
| greeting | 인사 (첫 요청 시) |
| collect_region | 지역 수집 |
| collect_life_cycle | 생애주기 수집 |
| collect_interests | 관심분야 수집 |
| completed | 완료 |

**대화 흐름 예시**

```
[Turn 1] 첫 요청 (message: "")
AI: "홍길동님, 가입을 축하해요! 🎉 어느 지역에 거주하고 계신가요?"
Quick Replies: [서울, 부산, 대구, 인천, ...]

[Turn 2]
User: "서울"
AI: "서울에 사시는군요! 👍 현재 상황에 해당하는 것이 있으신가요?"
Quick Replies: [임신/출산, 영유아 양육, 청년, ...]

[Turn 3]
User: "청년"
AI: "청년 관련 정책을 찾아드릴게요! 관심 있는 분야를 선택해주세요."
Quick Replies: [🏠 주거/임대, 💼 취업/창업, 📚 교육/장학, ...]

[Turn 4]
User: "주거, 취업"
AI: "완료됐어요! 입력해주신 정보를 바탕으로 맞춤 혜택을 찾아드릴게요."
is_completed: true
```

**Errors**
| 코드 | 설명 |
|------|------|
| 401 | 인증 필요 |

---

### POST `/onboarding/complete` - 온보딩 완료

온보딩을 완료 처리하고 프로필을 저장합니다.

**Headers**
```http
Authorization: Bearer <access_token>
```

**Request Body**
```json
{
  "session_id": "onb_abc123...",
  "profile": {
    "region": "서울",
    "life_cycle": "청년",
    "interests": "주거/임대, 취업/창업"
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| session_id | string | ✅ | 온보딩 세션 ID |
| profile | object | ✅ | 수집된 프로필 정보 |

**Response** `200 OK`
```json
{
  "message": "온보딩이 완료되었습니다.",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "홍길동",
    "onboarding_completed": true,
    "profile": {
      "region": "서울",
      "life_cycle": "청년",
      "interests": "주거/임대, 취업/창업"
    }
  }
}
```

**Errors**
| 코드 | 설명 |
|------|------|
| 400 | 잘못된 세션 ID |
| 401 | 인증 필요 |

---

### DELETE `/onboarding/conversation/{session_id}` - 세션 삭제

온보딩 세션을 삭제합니다. (건너뛰기 시 사용)

**Headers**
```http
Authorization: Bearer <access_token>
```

**Path Parameters**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| session_id | string | 세션 ID |

**Response** `200 OK`
```json
{
  "message": "온보딩 세션이 삭제되었습니다."
}
```

---

## 데이터 모델

### UserProfile

```typescript
interface UserProfile {
  region?: string;      // 거주 지역 (시/도)
  life_cycle?: string;  // 생애주기
  interests?: string;   // 관심 분야 (쉼표 구분)
}
```

### OnboardingResponse

```typescript
interface OnboardingResponse {
  response: string;
  session_id: string;
  step: 'greeting' | 'collect_region' | 'collect_life_cycle' | 'collect_interests' | 'completed';
  profile: UserProfile;
  is_completed: boolean;
  quick_replies?: string[];
}
```

---

## 사용 예시

### JavaScript

```javascript
class OnboardingClient {
  constructor(token) {
    this.token = token;
    this.sessionId = null;
  }

  async send(message = '') {
    const res = await fetch('/onboarding/conversation', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`
      },
      body: JSON.stringify({
        message,
        session_id: this.sessionId
      })
    });

    const data = await res.json();
    this.sessionId = data.session_id;
    return data;
  }

  async complete(profile) {
    const res = await fetch('/onboarding/complete', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`
      },
      body: JSON.stringify({
        session_id: this.sessionId,
        profile
      })
    });
    return res.json();
  }

  async skip() {
    await fetch(`/onboarding/conversation/${this.sessionId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${this.token}`
      }
    });
  }
}

// 사용 예시
const onboarding = new OnboardingClient(accessToken);

// 시작
const r1 = await onboarding.send('');
console.log(r1.response); // "홍길동님, 가입을 축하해요! ..."
console.log(r1.quick_replies); // ["서울", "부산", ...]

// 지역 선택
const r2 = await onboarding.send('서울');
console.log(r2.response); // "서울에 사시는군요! ..."

// 생애주기 선택
const r3 = await onboarding.send('청년');

// 관심분야 선택
const r4 = await onboarding.send('주거, 취업');
if (r4.is_completed) {
  await onboarding.complete(r4.profile);
}
```

---

## 프론트엔드 가이드

### 온보딩 필요 여부 확인

```javascript
// 로그인/회원가입 후
const checkOnboarding = (user) => {
  if (!user.onboarding_completed) {
    router.push('/onboarding');
  } else {
    router.push('/chat');
  }
};
```

### 온보딩 건너뛰기

사용자가 "건너뛰기"를 선택한 경우:

```javascript
const skipOnboarding = async () => {
  // 세션 삭제
  await onboarding.skip();

  // 빈 프로필로 완료 처리
  await onboarding.complete({});

  // 채팅으로 이동
  router.push('/chat');
};
```
