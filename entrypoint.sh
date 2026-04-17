#!/bin/sh
set -e

echo "=== PSX RAG Chatbot startup ==="

# Seed admin user (idempotent — safe to run every time)
echo "Seeding admin user..."
python -m scripts.seed_admin || echo "Seed skipped (may already exist)"

echo "Starting API server on port 7860..."
exec uvicorn app.main:app --host 0.0.0.0 --port 7860 --workers 1
