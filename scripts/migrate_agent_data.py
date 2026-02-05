from shared.db.postgres import PostgresClient

def run_migration():
    client = PostgresClient()
    
    # Add agent_data column to conversations table if it doesn't exist
    sql = """
    ALTER TABLE conversations 
    ADD COLUMN IF NOT EXISTS agent_data JSONB DEFAULT '{}'::jsonb;
    """
    
    print("🚀 Running DB Migration: Adding 'agent_data' to 'conversations'...")
    success = client.execute_ddl(sql)
    
    if success:
        print("✅ Migration SUCCESS: 'agent_data' column added.")
    else:
        print("❌ Migration FAILED.")

if __name__ == "__main__":
    run_migration()
