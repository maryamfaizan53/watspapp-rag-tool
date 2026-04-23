#!/bin/sh
set -e

echo "=== PSX RAG Chatbot startup ==="

echo "Seeding admin user..."
python -m scripts.seed_admin || echo "Seed skipped (may already exist)"

echo "Starting API server on port 8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
