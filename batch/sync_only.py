"""
Sync-only script: D1 → PostgreSQL + Qdrant

기존 D1 데이터를 조회해서 PostgreSQL과 Qdrant에만 동기화
수집(Collection) 작업은 하지 않음

Note: D1을 한 번만 조회해서 PostgreSQL과 Qdrant에 동시 처리
"""

from batch.services.data_sync import DataSyncService
from shared.config.settings import settings


def main():
    """
    D1에 이미 저장된 데이터를 PostgreSQL + Qdrant로 동기화

    Efficient sync:
    - D1 조회 1회 (기존: 2회)
    - XML 파싱 1회 per policy (기존: 2회)
    - PostgreSQL과 Qdrant 동시 처리
    - USE_EMBEDDINGS 환경 변수로 임베딩 ON/OFF 제어
    """
    print("="*60)
    print("  D1 → PostgreSQL + Qdrant Sync Job")
    print("="*60)
    print(f"  Embeddings: {'Enabled (BGE-M3)' if settings.USE_EMBEDDINGS else 'Disabled (Placeholder)'}")
    print("="*60)

    sync_service = DataSyncService(use_embeddings=settings.USE_EMBEDDINGS)
    sync_service.sync_all(batch_size=100)

    print("\n✅ Sync job finished.")


if __name__ == "__main__":
    main()
