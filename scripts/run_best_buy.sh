#!/bin/bash
# Best Buy Scan — runs every 2 hours via cron
# Calls the API, saves JSON, checks for new STRONG BUY alerts

cd /Users/mymac/Desktop/coding/medici-price-prediction

TIMESTAMP=$(date -u +%Y-%m-%d_%H-%M)
OUTFILE="scan-reports/best-buy-${TIMESTAMP}.json"

# Call the API
curl -s "https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/best-buy?top=30" > "$OUTFILE" 2>/dev/null

# Check if valid JSON
if ! python3 -c "import json; json.load(open('$OUTFILE'))" 2>/dev/null; then
    echo "[${TIMESTAMP}] ERROR: Invalid API response" >> scan-reports/best-buy.log
    rm -f "$OUTFILE"
    exit 1
fi

# Count by label
COUNTS=$(python3 -c "
import json
data = json.load(open('$OUTFILE'))
opps = data.get('opportunities', [])
labels = {}
for o in opps:
    l = o.get('label', 'UNKNOWN')
    labels[l] = labels.get(l, 0) + 1
strong = [o['hotel_name'] + ' ' + o['category'] + '/' + o['board'] + ' \$' + str(o['price']) for o in opps if o['label'] == 'STRONG BUY']
print(f'Total: {len(opps)} | ' + ' | '.join(f'{k}: {v}' for k,v in sorted(labels.items())))
if strong:
    print('ALERT — New STRONG BUY: ' + ', '.join(strong))
")

echo "[${TIMESTAMP}] ${COUNTS}" >> scan-reports/best-buy.log

# Git commit
git add "$OUTFILE" scan-reports/best-buy.log 2>/dev/null
git commit -m "chore: best-buy scan ${TIMESTAMP}" --quiet 2>/dev/null
