# 챗봇 API (Chat)

> **모듈**: `app/chat/`
> **Prefix**: `/chat`
> **Tags**: `Chat`

---

## 개요

RAG(Retrieval-Augmented Generation) 기반 복지 정책 챗봇을 제공합니다.

### 주요 기능

- **일반 챗봇**: 단일 질문 → 정책 검색 → LLM 답변
- **대화형 챗봇**: 멀티턴 대화로 사용자 정보 수집 후 맞춤 검색
- **스트리밍**: SSE(Server-Sent Events)로 실시간 응답

### 파일 구조

```
app/chat/
├── __init__.py
├── router.py         # 엔드포인트 정의
├── service.py        # RAGService (검색 + LLM)
├── conversation.py   # ConversationFlow (LangGraph 멀티턴)
└── schemas.py        # Pydantic 모델
```

---

## 엔드포인트

### POST `/chat` - 일반 챗봇

단일 질문에 대해 정책 검색 후 LLM 답변을 생성합니다.

**Request Body**
```json
{
  "query": "임신부가 받을 수 있는 혜택이 뭐가 있어?",
  "session_id": "optional-session-id",
  "filters": {
    "chunk_type": "benefit",
    "province": "서울특별시"
  },
  "top_k": 5,
  "model": "gpt-4o-mini"
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| query | string | ✅ | - | 질문 (2-500자) |
| session_id | string | ❌ | null | 세션 ID |
| filters | object | ❌ | null | 검색 필터 |
| filters.chunk_type | string | ❌ | null | 청크 타입 필터 |
| filters.province | string | ❌ | null | 시/도 필터 |
| top_k | integer | ❌ | 5 | 검색 정책 수 (1-10) |
| model | string | ❌ | gpt-4o-mini | LLM 모델 |

**chunk_type 값**

| 값 | 설명 |
|----|------|
| basic_info | 기본 정보 |
| eligibility | 자격 요건 |
| benefit | 혜택/지원 내용 |
| application | 신청 방법 |

**Response** `200 OK`
```json
{
  "answer": "임신부가 받을 수 있는 주요 혜택으로는...",
  "sources": [
    {
      "policy_id": "WLF00000456",
      "title": "임산부 건강관리 지원",
      "score": 0.89,
      "chunk_type": "benefit",
      "chunk_content": "...",
      "ministry": "보건복지부",
      "summary": "...",
      "support_content": "...",
      "target_detail": "...",
      "application_method": "...",
      "phone": "1577-1234",
      "website": "https://example.go.kr",
      "source_type": "central",
      "ctpv_nm": null,
      "sgg_nm": null
    }
  ],
  "query": "임신부가 받을 수 있는 혜택이 뭐가 있어?",
  "context_used": true
}
```

---

### POST `/chat/stream` - 스트리밍 챗봇

SSE(Server-Sent Events)로 실시간 응답을 스트리밍합니다.

**Request Body**: `/chat`와 동일

**Response**: `text/event-stream`

```
event: sources
data: [{"policy_id": "WLF00000456", "title": "임산부 건강관리 지원", ...}]

event: answer
data: {"text": "임신부가 "}

event: answer
data: {"text": "받을 수 있는 "}

event: answer
data: {"text": "주요 혜택으로는..."}

event: done
data: {"query": "임신부 혜택", "context_used": true}
```

**SSE 이벤트**

| 이벤트 | 데이터 | 설명 |
|--------|--------|------|
| sources | PolicySource[] | 참조 정책 목록 (먼저 전송) |
| answer | {text: string} | 답변 텍스트 청크 |
| done | {query, context_used} | 완료 신호 |
| error | {error: string} | 오류 발생 |

---

### POST `/chat/conversation` - 대화형 챗봇

LangGraph 기반 멀티턴 대화로 사용자 정보를 수집하고 맞춤 정책을 검색합니다.

**Request Body**
```json
{
  "message": "지원받을 수 있는 정책 알려줘",
  "session_id": "optional-session-id"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| message | string | ✅ | 사용자 메시지 (1-500자) |
| session_id | string | ❌ | 세션 ID (없으면 새 세션 생성) |

**Response** `200 OK`
```json
{
  "response": "어느 지역에 거주하고 계신가요?",
  "session_id": "abc123-def456",
  "intent": "welfare_search",
  "ready_to_search": false,
  "user_profile": {
    "region": "",
    "life_cycle": ""
  },
  "sources": null
}
```

**대화 흐름 예시**

```
[Turn 1]
User: "지원받을 수 있는 정책 알려줘"
AI: "어느 지역에 거주하고 계신가요?"
→ intent: welfare_search, ready_to_search: false

[Turn 2]
User: "서울이요"
AI: "현재 상황에 해당하는 것이 있으신가요? (임신/출산, 육아, 취업 등)"
→ intent: welfare_search, ready_to_search: false

[Turn 3]
User: "임신 중이에요"
AI: "서울, 임신/출산 조건으로 검색합니다. [검색 결과 + RAG 답변]"
→ intent: welfare_search, ready_to_search: true, sources: [...]
```

**Intent 타입**

| Intent | 설명 | 동작 |
|--------|------|------|
| welfare_search | 복지 정책 검색 | 슬롯 수집 → 검색 |
| policy_detail | 특정 정책 상세 조회 | 정책 ID로 조회 |
| general_question | 일반 복지 관련 질문 | RAG 답변 생성 |
| chitchat | 인사, 잡담 | 간단한 응답 |
| unknown | 인식 불가 | 안내 메시지 |

---

### POST `/chat/conversation/stream` - 대화형 스트리밍

**Request Body**: `/chat/conversation`과 동일

**Response**: `text/event-stream`

```
event: session
data: {"session_id": "abc123-def456"}

event: intent
data: {"intent": "welfare_search"}

event: message
data: {"text": "서울, 임신/출산 조건으로 검색합니다."}

event: profile
data: {"region": "서울특별시", "life_cycle": "임신/출산"}

event: sources
data: [{"policy_id": "WLF00000456", ...}]

event: answer
data: {"text": "임신부를 위한 "}

event: answer
data: {"text": "주요 정책으로는..."}

event: done
data: {"ready_to_search": true}
```

**SSE 이벤트**

| 이벤트 | 데이터 | 설명 |
|--------|--------|------|
| session | {session_id} | 세션 ID |
| intent | {intent} | 감지된 의도 |
| message | {text} | AI 응답 (슬롯 질문 등) |
| profile | object | 수집된 사용자 정보 |
| sources | PolicySource[] | 검색 결과 |
| answer | {text} | RAG 답변 청크 |
| done | {ready_to_search} | 완료 신호 |
| error | {error} | 오류 발생 |

---

### DELETE `/chat/conversation/{session_id}` - 세션 삭제

대화 세션을 삭제합니다.

**Path Parameters**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| session_id | string | 세션 ID |

**Response** `200 OK`
```json
{
  "message": "세션이 삭제되었습니다."
}
```

**Errors**
| 코드 | 설명 |
|------|------|
| 404 | 세션을 찾을 수 없음 |

---

### GET `/chat/health` - 챗봇 서비스 상태

**Response** `200 OK`
```json
{
  "qdrant": "ready",
  "postgres": "ready",
  "openai": "configured",
  "embedding_models": "pre-loaded",
  "active_sessions": 5,
  "policy_count": {
    "qdrant_chunks": 15000,
    "postgres": 1500
  }
}
```

---

## 데이터 모델

### ChatRequest

```python
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    session_id: Optional[str] = None
    filters: Optional[ChatFilters] = None
    top_k: int = Field(default=5, ge=1, le=10)
    model: str = "gpt-4o-mini"
```

### ConversationRequest

```python
class ConversationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = None
```

### UserProfile

```python
class UserProfile(BaseModel):
    region: Optional[str] = None      # 시/도
    life_cycle: Optional[str] = None  # 생애주기
    age_group: Optional[str] = None   # 연령대
    interest: Optional[str] = None    # 관심분야
```

---

## 사용 예시

### JavaScript - 스트리밍

```javascript
const chatStream = async (query, onEvent) => {
  const res = await fetch('/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        const eventType = line.slice(7);
        continue;
      }
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        onEvent(eventType, data);
      }
    }
  }
};

// 사용 예
chatStream('임신부 지원', (event, data) => {
  switch (event) {
    case 'sources':
      console.log('참조 정책:', data);
      break;
    case 'answer':
      process.stdout.write(data.text);
      break;
    case 'done':
      console.log('\n완료');
      break;
  }
});
```

### Python - 대화형

```python
import requests
import uuid

class ConversationClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id = str(uuid.uuid4())

    def send(self, message: str) -> dict:
        response = requests.post(
            f"{self.base_url}/chat/conversation",
            json={
                "message": message,
                "session_id": self.session_id
            }
        )
        return response.json()

    def close(self):
        requests.delete(
            f"{self.base_url}/chat/conversation/{self.session_id}"
        )

# 사용 예
client = ConversationClient("http://localhost:8000")

print(client.send("정책 알려줘"))
# → "어느 지역에 거주하고 계신가요?"

print(client.send("서울"))
# → "현재 상황에 해당하는 것이 있으신가요?"

print(client.send("임신 중"))
# → 검색 결과 + RAG 답변

client.close()
```

---

## 관련 서비스

- **RAGService**: `app/chat/service.py` - 검색 + LLM 통합
- **ConversationFlow**: `app/chat/conversation.py` - LangGraph 대화 흐름
- **QdrantService**: `shared/services/qdrant_service.py` - 하이브리드 검색
- **프롬프트**: `shared/prompts/welfare.py` - 시스템 프롬프트
