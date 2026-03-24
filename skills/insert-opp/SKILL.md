# Insert Opportunity Skill

## Purpose
Allows Price Predictor to create purchase opportunities when it identifies a good price. Replicates the exact logic of the Backend's InsertOpp API endpoint, writing directly to the database.

## How It Works

```
Price Predictor identifies $164 price (worth buying)
    │
    ├── Skill creates BackOfficeOPT record (opportunity header)
    ├── Skill creates MED_Opportunities records (1 per room per night)
    │
    └── BuyRoom WebJob picks up → purchases from Innstant → pushes to Zenith
```

## Commands

```bash
# Single opportunity
python insert_opp.py --connection-string "..." \
  --hotel-id 32687 --start 2026-05-15 --end 2026-05-16 \
  --board-id 1 --category-id 1 \
  --buy-price 164.83 --push-price 189.00 \
  --max-rooms 3 --name "Guest Name Here" \
  --by PricePredictor

# Bulk from CSV
python insert_opp.py --connection-string "..." \
  --csv opportunities.csv --by PricePredictor

# Check status
python insert_opp.py --connection-string "..." --status
python insert_opp.py --connection-string "..." --status --opp-id 3866

# Cancel opportunity
python insert_opp.py --connection-string "..." --cancel --opp-id 3866
```

## CSV Format

```csv
hotel_id,start_date,end_date,board_id,category_id,buy_price,push_price,max_rooms,name
32687,2026-05-15,2026-05-16,1,1,164.83,189.00,3,Jakob OCONNOR
22034,2026-05-20,2026-05-21,2,4,450.00,520.00,2,Test Guest
```

## Parameters

| Parameter | Type | Required | Validation |
|-----------|------|----------|------------|
| hotel_id | int | Yes | Must exist in Med_Hotels with ZenithId |
| start_date | YYYY-MM-DD | Yes | Must be future date |
| end_date | YYYY-MM-DD | Yes | Must be after start, max 90 days span |
| board_id | int | Yes | 1=RO, 2=BB. Must have ratebycat entry |
| category_id | int | Yes | 1=Standard, 2=Superior, 4=Deluxe, 12=Suite |
| buy_price | float | Yes | $1-$10,000 |
| push_price | float | Yes | Must be ≥ 103% of buy_price |
| max_rooms | int | Yes | 1-30 |
| name | string | Yes | At least 2 words (first + last name) |

## Guardrails

| Guard | Value | Description |
|-------|-------|-------------|
| Authorized systems | `PricePredictor` | Only listed systems can create |
| Price range | $1 - $10,000 | Hard limits |
| Min margin | 3% | push_price ≥ 103% of buy_price |
| Max rooms | 30 | Per opportunity |
| Max date span | 90 days | Single opportunity |
| Future dates only | Yes | Cannot create for past dates |
| Volume limit | 50 per run | Prevents mass creation |
| Per hotel/day limit | 10 | Prevents flooding a hotel |
| Duplicate check | Yes | No active opp for same hotel+date+board+cat |
| Hotel validation | Yes | Must be active with ZenithId |
| ratebycat validation | Yes | Mapping must exist |
| Table protection | BackOfficeOPT, MED_Opportunities only | Cannot write elsewhere |

## Database Tables

### BackOfficeOPT (1 row per opportunity)

| Column | Description |
|--------|-------------|
| id | Auto PK |
| DateInsert | Creation time |
| HotelId | Hotel |
| StartDate / EndDate | Date range |
| BordId / CatrgoryId | Board + Category |
| BuyPrice / PushPrice | Buy and sell prices |
| MaxRooms | Rooms per night |
| Status | 1=active, 0=cancelled |
| RatePlanCode / InvTypeCode | Zenith mapping |

### MED_Opportunities (MaxRooms × nights rows)

Each row = 1 room for 1 night. Created in loop:
- Outer: each day from Start to End
- Inner: MaxRooms times per day

## Integration with Price Predictor

```python
from insert_opp import InsertOppSkill

skill = InsertOppSkill(connection_string)

# Create opportunity
result = skill.insert_opportunity(
    hotel_id=32687,
    start_str="2026-05-15",
    end_str="2026-05-16",
    board_id=1,
    category_id=1,
    buy_price=164.83,
    push_price=189.00,
    max_rooms=3,
    name="Guest Name",
    created_by="PricePredictor"
)
# result = {"success": True, "opp_id": 3866, "rooms_created": 3, ...}

# Check status
status = skill.get_status(opp_id=3866)

# Cancel if needed
skill.cancel_opportunity(opp_id=3866)

skill.close()
```

## Files

| File | Purpose |
|------|---------|
| `insert_opp.py` | Main skill script |
| `config.json` | Guardrails configuration |
| `SKILL.md` | This file |

## Gotchas

<!-- Add entries immediately after errors occur. Format: [date] what happened; rule -->
<!-- Each entry prevents the same mistake from recurring in future sessions -->

- [2026-03-20] Opportunity created with push_price < 103% of buy_price causing BuyRoom WebJob rejection; rule: Always validate push_price >= buy_price * 1.03 before submission
- [2026-03-20] Duplicate opportunity created for same hotel+date+board+category while previous was still active; rule: Always query active opportunities first and skip if duplicate exists
- [2026-03-21] Used predicted_checkin_price field name but endpoint expected buy_price; rule: Always use field names from the Parameters table above, never from internal analytics models
