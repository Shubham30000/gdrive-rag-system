#!/usr/bin/env bash
# sample_requests.sh
# Run these after starting the server with: uvicorn api.main:app --reload
# Base URL (change if deployed remotely)
BASE="http://localhost:8000"

echo "=== 1. Health Check ==="
curl -s "$BASE/" | python3 -m json.tool

echo ""
echo "=== 2. Index Status ==="
curl -s "$BASE/status" | python3 -m json.tool

echo ""
echo "=== 3. Sync Google Drive ==="
curl -s -X POST "$BASE/sync-drive" | python3 -m json.tool

echo ""
echo "=== 4. Ask a Question ==="
curl -s -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our refund policy?"}' \
  | python3 -m json.tool

echo ""
echo "=== 5. Ask with top_k override ==="
curl -s -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "How is user data stored?", "top_k": 3}' \
  | python3 -m json.tool

echo ""
echo "=== 6. Ask with document filter ==="
curl -s -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the compliance requirements?", "doc_filter": "compliance_policy.pdf"}' \
  | python3 -m json.tool

echo ""
echo "=== 7. Clear Index (dev only) ==="
curl -s -X DELETE "$BASE/clear" | python3 -m json.tool