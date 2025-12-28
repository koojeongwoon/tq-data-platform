#!/bin/bash
# Development environment setup script

set -e  # Exit on error

echo "============================================================"
echo "  TQ Data Platform - Development Environment Setup"
echo "============================================================"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Install dependencies
echo -e "\n${GREEN}[1/4] Installing Python dependencies...${NC}"
uv pip install -e ".[dev]"

# 2. Setup environment file
echo -e "\n${GREEN}[2/4] Setting up environment file...${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠️  .env file created. Please update with your credentials:${NC}"
    echo "   - API_KEYS (Public Data Portal)"
    echo "   - CLOUDFLARE_* (D1 database)"
    echo "   - POSTGRES_* (PostgreSQL)"
else
    echo "✅ .env file already exists"
fi

# 3. Download BGE-M3 model
echo -e "\n${GREEN}[3/4] Downloading BGE-M3 embedding model...${NC}"
echo "   Model: BAAI/bge-m3 (~2GB)"
echo "   Location: ~/.cache/huggingface/hub/"
echo ""

python3 << 'EOF'
import sys
try:
    print("🔄 Starting model download...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('BAAI/bge-m3')
    print("✅ Model downloaded successfully!")
    print(f"   Dimension: {model.get_sentence_embedding_dimension()}")
except Exception as e:
    print(f"❌ Failed to download model: {e}")
    sys.exit(1)
EOF

# 4. Start Docker services
echo -e "\n${GREEN}[4/4] Starting Docker services...${NC}"
if command -v docker &> /dev/null; then
    if docker compose ps &> /dev/null; then
        echo "✅ Docker Compose is available"
        echo ""
        echo "Start services with:"
        echo "  docker compose up -d postgres qdrant"
    else
        echo "⚠️  Docker is installed but compose is not available"
    fi
else
    echo "⚠️  Docker is not installed"
    echo "   Install from: https://docs.docker.com/get-docker/"
fi

# Summary
echo ""
echo "============================================================"
echo -e "${GREEN}✅ Development environment setup complete!${NC}"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Update .env file with your credentials"
echo "  2. Start Docker services:"
echo "     docker compose up -d postgres qdrant"
echo "  3. Run database migration:"
echo "     docker exec -it tq-data-platform-postgres-1 psql -U welfare_user -d welfare_db -f /docker-entrypoint-initdb.d/init_db.sql"
echo "  4. Start API server:"
echo "     uvicorn app.main:app --reload"
echo "  5. Run batch sync:"
echo "     python batch/sync_only.py"
echo ""
