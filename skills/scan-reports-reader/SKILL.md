# Scan Reports Reader — Skill Definition

## Purpose
Read Knowaa competitive scan reports from the medici-price-prediction project.
These reports show where Knowaa_Global_zenith appears on Innstant B2B, whether we're the cheapest, and where we're missing.

## How To Fetch Reports

Reports are on GitHub. Fetch via raw URL:

### Full 55-Hotel Report (latest):
```bash
curl -s https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/2026-03-31_full_55_hotels_report.md
```

### Detailed Competitive Report:
```bash
curl -s https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/2026-03-31_knowaa_competitive_report.md
```

### Raw JSON Data:
```bash
curl -s https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/2026-03-31_07-10.json
```

### List All Available Reports:
```bash
curl -s https://api.github.com/repos/amitpo23/medici-price-prediction/contents/shared-reports | python3 -c "import sys,json; [print(f['name']) for f in json.load(sys.stdin)]"
```

### Get Latest Report (auto-detect filename):
```bash
LATEST=$(curl -s https://api.github.com/repos/amitpo23/medici-price-prediction/contents/shared-reports | python3 -c "import sys,json; files=[f['name'] for f in json.load(sys.stdin) if f['name'].endswith('_full_55_hotels_report.md')]; print(sorted(files)[-1] if files else '')")
curl -s "https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/$LATEST"
```

## URL Pattern
```
https://raw.githubusercontent.com/amitpo23/medici-price-prediction/main/shared-reports/{filename}
```

## Report Structure

Each scan report contains 5 sections:

| Section | Description |
|---------|-------------|
| **A** | Hotels where Knowaa is #1 (cheapest) |
| **B** | Hotels where Knowaa is #2 |
| **C** | Hotels where Knowaa is #3+ |
| **D** | Hotels with offers from others but NOT from Knowaa |
| **E** | Hotels with no refundable offers at all |

Per hotel data: VenueId, InnstantId, category, board, Knowaa price, cheapest price, cheapest provider, rank.

## Schedule
New reports are pushed approximately every 8 hours by the medici-price-prediction agent.
File naming: `YYYY-MM-DD_HH-MM_*.md` / `*.json`

## When To Use
- When asked about Knowaa competitive position
- When checking if we appear on Innstant for a specific hotel
- When comparing our prices vs competitors
- When investigating why a hotel has no Knowaa offers
- Before/after price pushes to verify visibility
