# Tests

테스트 디렉토리 구조 및 실행 방법

## 디렉토리 구조

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures 및 설정
├── unit/                    # 단위 테스트
│   ├── __init__.py
│   ├── test_api.py          # API 엔드포인트 테스트
│   ├── test_services.py     # 서비스 레이어 테스트
│   └── test_processing.py   # 데이터 처리 테스트
├── integration/             # 통합 테스트
│   ├── __init__.py
│   └── test_api_integration.py
└── fixtures/                # 테스트 데이터
    └── __init__.py
```

## 테스트 실행

### 모든 테스트 실행
```bash
pytest
```

### 특정 디렉토리만 실행
```bash
# 단위 테스트만
pytest tests/unit

# 통합 테스트만
pytest tests/integration
```

### 마커로 필터링
```bash
# API 테스트만
pytest -m api

# 단위 테스트만
pytest -m unit

# 느린 테스트 제외
pytest -m "not slow"
```

### 커버리지 리포트
```bash
# 터미널에 출력
pytest --cov=app --cov-report=term-missing

# HTML 리포트 생성
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

### 특정 테스트 파일 실행
```bash
pytest tests/unit/test_api.py
```

### 특정 테스트 함수 실행
```bash
pytest tests/unit/test_api.py::TestAPIEndpoints::test_root_endpoint
```

### Verbose 모드
```bash
pytest -v
pytest -vv  # 더 상세하게
```

## 테스트 작성 가이드

### 단위 테스트 (Unit Tests)
- 개별 함수나 메서드를 독립적으로 테스트
- Mock을 사용하여 외부 의존성 제거
- 빠르게 실행되어야 함

```python
import pytest

@pytest.mark.unit
def test_example(mock_d1_client):
    # 테스트 코드
    pass
```

### 통합 테스트 (Integration Tests)
- 여러 컴포넌트가 함께 동작하는지 테스트
- 실제 API 호출이나 DB 연결 포함 가능
- 실행 시간이 더 오래 걸릴 수 있음

```python
import pytest

@pytest.mark.integration
@pytest.mark.slow
def test_full_flow(client):
    # 테스트 코드
    pass
```

### Fixtures 사용
conftest.py에 정의된 fixtures 사용:

- `client`: FastAPI TestClient
- `mock_d1_client`: Mock D1Client
- `sample_policy_data`: 샘플 정책 데이터
- `sample_xml_response`: 샘플 XML 응답

## CI/CD 통합

GitHub Actions에서 자동으로 테스트 실행:

```yaml
- name: Run tests
  run: |
    pytest --cov=app --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```
