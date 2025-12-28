"""Batch job entry point for welfare data collection and synchronization"""

from batch.core import Job
from batch.steps import CentralWelfareStep, PostgresSyncStep, QdrantSyncStep, RegionalWelfareStep


def main():
    """
    Welfare data collection and synchronization batch job

    Steps:
    1. Collect central government welfare policies (D1)
    2. Collect regional government welfare policies (D1)
    3. Sync to PostgreSQL for keyword search
    4. Sync to Qdrant for vector search
    """
    job = Job(
        name="Welfare Data Collection & Sync Job",
        steps=[
            CentralWelfareStep(),
            RegionalWelfareStep(),
            PostgresSyncStep(batch_size=100),
            QdrantSyncStep(batch_size=100)
        ]
    )

    job.run()

    print("\n✅ Job execution finished.")


if __name__ == "__main__":
    main()
