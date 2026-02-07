#!/bin/bash
set -e

echo "🚀 Stock Knowledge Graph Setup"

# Install UV if not present
if ! command -v uv &> /dev/null; then
    echo "Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Create venv and install deps
uv venv
uv pip install pydantic-ai pydantic yfinance python-dotenv httpx ddgs pyyaml

# Setup env
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Please edit .env and add your NVIDIA_API_KEY"
fi

echo "✅ Setup complete!"
echo "Run: source .venv/bin/activate && python knowledge_graph/scripts/extract_relationships.py"
