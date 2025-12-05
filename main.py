from db.database import engine, Base
from services.welfare import WelfareService

def init_db():
    Base.metadata.create_all(bind=engine)

def main():
    # Initialize Database (optional for now as we don't save yet)
    # init_db()
    
    service = WelfareService()
    
    service.process_central_welfare()
    service.process_regional_welfare()

    print("\nNote: Database save is skipped as requested.")

if __name__ == "__main__":
    main()
