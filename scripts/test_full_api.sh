#!/bin/bash
echo "========================================="
echo "🧪 FULL API TEST SUITE"
echo "========================================="
echo ""

echo "1️⃣  Health Check:"
curl -s http://localhost:8000/health | jq -c '{status, dependencies}'
echo ""

echo "2️⃣  Pricing:"
curl -s http://localhost:8000/api/v1/pricing | jq -c '.tiers | keys'
echo ""

echo "3️⃣  Event Types:"
curl -s http://localhost:8000/api/v1/events/types | jq -c '.event_types | keys'
echo ""

echo "4️⃣  Company Search (AAPL):"
curl -s "http://localhost:8000/api/v1/company/search?query=AAPL" | jq -c '.[0] | {name, ticker, cik, exchange}'
echo ""

echo "5️⃣  Events (AAPL, limit=3):"
echo "   ⏳ This takes ~20 seconds..."
curl -s "http://localhost:8000/api/v1/events?query=AAPL&limit=3" | jq -c '{total}'
echo ""

echo "========================================="
echo "✅ TEST SUITE COMPLETE"
echo "========================================="
