from db.database import engine, Base
from services.welfare import WelfareService

def init_db():
    Base.metadata.create_all(bind=engine)

def main():
    # Initialize Database (optional for now as we don't save yet)
    # init_db()
    
    service = WelfareService()
    
    
    # Batch Job Execution
    from batch.core import Job
    from batch.steps import CentralWelfareStep, RegionalWelfareStep, NormalizationStep

    job = Job(
        name="Welfare Data Enhancement Job",
        steps=[
            CentralWelfareStep(service),
            RegionalWelfareStep(service),
            NormalizationStep(service)
        ]
    )
    
    job.run()

    print("\nJob execution finished.")

if __name__ == "__main__":
    main()
