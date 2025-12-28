#!/usr/bin/env python3
"""Development environment setup script (Cross-platform)"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def print_section(title: str):
    """Print section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_step(step: str, current: int, total: int):
    """Print step header"""
    print(f"\n[{current}/{total}] {step}...")


def run_command(cmd: list[str], description: str = "") -> bool:
    """Run shell command and return success status"""
    try:
        if description:
            print(f"  Running: {description}")
        subprocess.run(cmd, check=True, capture_output=False)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Command failed: {e}")
        return False


def main():
    """Main setup function"""
    print_section("TQ Data Platform - Development Environment Setup")

    # Get project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # 1. Install dependencies
    print_step("Installing Python dependencies", 1, 4)
    success = run_command(
        ["uv", "pip", "install", "-e", ".[dev]"],
        "uv pip install -e .[dev]"
    )
    if not success:
        print("  ⚠️  Try using pip instead:")
        print("     pip install -e .[dev]")
        return 1

    # 2. Setup environment file
    print_step("Setting up environment file", 2, 4)
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"

    if not env_file.exists():
        shutil.copy(env_example, env_file)
        print("  ✅ .env file created")
        print("  ⚠️  Please update with your credentials:")
        print("     - API_KEYS (Public Data Portal)")
        print("     - CLOUDFLARE_* (D1 database)")
        print("     - POSTGRES_* (PostgreSQL)")
    else:
        print("  ✅ .env file already exists")

    # 3. Download BGE-M3 model
    print_step("Downloading BGE-M3 embedding model", 3, 4)
    print("  Model: BAAI/bge-m3 (~2GB)")
    print("  Location: ~/.cache/huggingface/hub/")
    print()

    try:
        print("  🔄 Starting model download...")
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("BAAI/bge-m3")
        print("  ✅ Model downloaded successfully!")
        print(f"     Dimension: {model.get_sentence_embedding_dimension()}")
    except Exception as e:
        print(f"  ❌ Failed to download model: {e}")
        print()
        print("  You can download it later by running:")
        print('     python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer(\'BAAI/bge-m3\')"')
        return 1

    # 4. Check Docker
    print_step("Checking Docker services", 4, 4)
    docker_available = shutil.which("docker") is not None

    if docker_available:
        print("  ✅ Docker is available")
        print()
        print("  Start services with:")
        print("     docker compose up -d postgres qdrant")
    else:
        print("  ⚠️  Docker is not installed")
        print("     Install from: https://docs.docker.com/get-docker/")

    # Summary
    print()
    print_section("✅ Development environment setup complete!")
    print()
    print("Next steps:")
    print("  1. Update .env file with your credentials")
    print("  2. Start Docker services:")
    print("     docker compose up -d postgres qdrant")
    print()
    print("  3. Initialize PostgreSQL:")
    print("     docker exec -it tq-data-platform-postgres-1 \\")
    print("       psql -U welfare_user -d welfare_db \\")
    print("       -f /docker-entrypoint-initdb.d/init_db.sql")
    print()
    print("  4. Start API server:")
    print("     uvicorn app.main:app --reload")
    print()
    print("  5. Run batch sync:")
    print("     python batch/sync_only.py")
    print()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
