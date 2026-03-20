# Price Override Skill

## Purpose
Allows Price Predictor (or other authorized systems) to override the price pushed to Zenith/Noovy for specific SalesOffice Details, without modifying the Detail itself.

**The Detail stays untouched** (API price = source of truth). Only the Zenith push price changes.

## How It Works

```
WebJob scans → Detail created ($485) → Push to Zenith ($485)
                                              ↓
Price Predictor → writes override ($520) → Skill pushes $520 to Zenith
                                              ↓
Next WebJob scan → Detail updated ($490) → Override resets → Push $490 to Zenith
```

Every scan cycle resets all overrides. Price Predictor must re-send if it wants to keep its price.

## Commands

```bash
# Write single override
python override_push.py --connection-string "..." \
  --write --detail-id 12345 --price 520.00 --by PricePredictor

# Write bulk from CSV
python override_push.py --connection-string "..." \
  --write-csv overrides.csv --by PricePredictor

# Push all pending overrides to Zenith
python override_push.py --connection-string "..." --push

# Full cycle (write + push)
python override_push.py --connection-string "..." \
  --write-csv overrides.csv --push --by PricePredictor

# Check status
python override_push.py --connection-string "..." --status

# Emergency: restore original prices to Zenith
python override_push.py --connection-string "..." --rollback

# Reset all active overrides without pushing
python override_push.py --connection-string "..." --reset
```

## CSV Format

```csv
detail_id,override_price
12345,520.00
12346,480.00
12347,610.00
```

## Guardrails

| Guard | Value | Description |
|-------|-------|-------------|
| Authorized systems | `PricePredictor` | Only listed systems can write overrides |
| Price range | $1 - $10,000 | Hard limits |
| Max deviation | ±50% | Override can't exceed 50% of original price |
| Max per run | 5,000 | Volume limit per execution |
| Max per hotel | 500 | Prevents flooding a single hotel |
| Push delay | 200ms | Rate limiting for Zenith API |
| Circuit breaker | 5 errors | Stops after 5 consecutive Zenith failures |
| Table protection | PriceOverride only | Script cannot write to any other table |
| Audit log | Always | Every action logged to JSON |
| Rollback | Always available | Original prices can be restored instantly |

## Database

### Table: `SalesOffice.PriceOverride`

| Column | Type | Description |
|--------|------|-------------|
| Id | INT (PK) | Auto-increment |
| DetailId | INT | FK to SalesOffice.Details |
| OriginalPrice | DECIMAL(9,2) | API price (for audit/rollback) |
| OverridePrice | DECIMAL(9,2) | Price to push to Zenith |
| CreatedBy | NVARCHAR(50) | System that created the override |
| CreatedAt | DATETIME | When override was created |
| PushedAt | DATETIME | When pushed to Zenith |
| PushStatus | NVARCHAR(20) | success / failed / rolled_back |
| IsActive | BIT | Resets to 0 after each scan cycle |

## Integration with Price Predictor

### Step 1: Read active Details
```python
import pyodbc

conn = pyodbc.connect("Driver={ODBC Driver 17 for SQL Server};...")
cursor = conn.cursor()
cursor.execute("""
    SELECT d.Id, d.HotelId, d.RoomCategory, d.RoomBoard, d.RoomPrice,
           o.DateFrom
    FROM [SalesOffice.Details] d
    JOIN [SalesOffice.Orders] o ON o.Id = d.SalesOfficeOrderId
    WHERE d.IsDeleted = 0
""")
details = cursor.fetchall()
```

### Step 2: Calculate optimal prices
```python
for detail in details:
    optimal_price = predict_price(detail)  # your ML model
    overrides.append({"detail_id": detail.Id, "override_price": optimal_price})
```

### Step 3: Write CSV and push
```python
import csv
with open("overrides.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["detail_id", "override_price"])
    writer.writeheader()
    writer.writerows(overrides)

# Then run:
# python override_push.py --connection-string "..." --write-csv overrides.csv --push --by PricePredictor
```

### Or: Direct API (Python)
```python
from override_push import PriceOverrideSkill

skill = PriceOverrideSkill(connection_string)
skill.set_override(detail_id=12345, override_price=520.00, created_by="PricePredictor")
skill.push_overrides()
skill.close()
```

## Zenith Push Details

Uses the same SOAP API as the WebJob:
- **URL:** `https://hotel.tools/service/Medici%20new`
- **Protocol:** OTA_HotelRateAmountNotifRQ
- **Auth:** WS-Security (APIMedici:Medici Live)
- **Rate:** 200ms delay between pushes
- **Capacity:** ~5 pushes/sec = 4,000 overrides in ~13 minutes

## Files

| File | Purpose |
|------|---------|
| `override_push.py` | Main skill script |
| `config.json` | Guardrails configuration |
| `SKILL.md` | This file |
