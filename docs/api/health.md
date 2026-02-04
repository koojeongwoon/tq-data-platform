# Health API

API 서버의 작동 여부 및 기본 연결 상태를 확인합니다.

## Root Endpoint

현재 API 서버의 상태를 기본적으로 확인합니다.

- **URL**: `/`
- **Method**: `GET`
- **Description**: API 상태 확인 (Hello World)
- **Response**: `200 OK`

## Health Check

상세 헬스 체크 엔드포인트입니다.

- **URL**: `/health`
- **Method**: `GET`
- **Description**: 헬스 체크 엔드포인트
- **Response**: `200 OK`
