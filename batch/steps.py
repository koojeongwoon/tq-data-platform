"""Batch job steps for welfare data processing"""

from batch.services.welfare import WelfareCollector

from .core import JobContext, Step


class CentralWelfareStep(Step):
    """Collect central government welfare policies"""

    def __init__(self):
        super().__init__("Central Welfare Collection")
        self.collector = WelfareCollector()

    def execute(self, context: JobContext):
        self.collector.collect_central_policies()


class RegionalWelfareStep(Step):
    """Collect regional government welfare policies"""

    def __init__(self):
        super().__init__("Regional Welfare Collection")
        self.collector = WelfareCollector()

    def execute(self, context: JobContext):
        self.collector.collect_regional_policies()


class PostgresSyncStep(Step):
    """Sync D1 data to PostgreSQL for keyword search"""

    def __init__(self, batch_size: int = 100):
        super().__init__("PostgreSQL Sync")
        self.batch_size = batch_size

    def execute(self, context: JobContext):
        from batch.services.data_sync import DataSyncService

        sync_service = DataSyncService()
        sync_service.sync_to_postgres(batch_size=self.batch_size)


class QdrantSyncStep(Step):
    """Sync D1 data to Qdrant for vector search"""

    def __init__(self, batch_size: int = 100):
        super().__init__("Qdrant Sync")
        self.batch_size = batch_size

    def execute(self, context: JobContext):
        from batch.services.data_sync import DataSyncService

        sync_service = DataSyncService()
        sync_service.sync_to_qdrant(batch_size=self.batch_size)
