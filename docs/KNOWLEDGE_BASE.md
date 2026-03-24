# Medici Knowledge Base — Complete Data Source Reference

> This document serves as the single source of truth for all data sources,
> tables, access patterns, and historical pricing capabilities available
> to the Medici Price Prediction system.
>
> Last updated: 2026-03-24

---

## 1. Azure SQL Tables (medici-db)

### 1.1 Price Discovery & Scanning

#### SalesOffice.Orders
- **Purpose**: Search requests sent to Innstant Switch
- **Key columns**: Id, DateFrom, DateTo, DateInsert, IsActive, WebJobStatus, DestinationId
- **Frequency**: Real-time (per booking request from OTAs)
- **Retention**: All history
- **Access**: `collector.py` QUERY, MCP `medici_query`

#### SalesOffice.Details
- **Purpose**: Room prices returned from Innstant API per search
- **Key columns**: Id, SalesOfficeOrderId, HotelId, RoomCategory, RoomBoard, RoomPrice, RoomCode, DateCreated, IsDeleted
- **Frequency**: Updated every 3h scan cycle
- **Volume**: ~4,050 active rooms (IsDeleted=0)
- **Access**: `collector.py` QUERY, `load_active_bookings()`
- **Historical use**: LAG(RoomPrice) for velocity, DateCreated for timeline

#### SalesOffice.Log
- **Purpose**: Complete audit trail of every price change, API call, push event
- **Key columns**: Id, DateCreated, ActionId, Message, SalesOfficeOrderId, SalesOfficeDetailId
- **Volume**: 1.2M+ rows
- **Retention**: All history
- **Price pattern**: `DbRoomPrice: X -> API RoomPrice: Y` in Message field
- **ActionId values**: 3=UpdateDetail, 5=PushAvailability, 6=UpdateRate
- **Access**: MCP `medici_price_drops`, skill `salesoffice-price-drop`
- **Value**: THE primary source for inter-scan price change detection

#### RoomPriceUpdateLog
- **Purpose**: Every price change event with exact timestamp
- **Key columns**: Id, DateInsert, PreBookId, Price
- **Volume**: 82K+ rows
- **Access**: MCP `medici_price_change_log`, `load_price_updates()`
- **Value**: Price momentum/acceleration tracking

### 1.2 Market Intelligence

#### AI_Search_HotelData
- **Purpose**: Competitor pricing from OTA searches
- **Volume**: 8.5M rows
- **Key columns**: HotelId, PriceAmount, UpdatedAt, CityName, Stars, RoomType, Board
- **Access**: MCP `medici_market_pressure`, `load_ai_search_data()`
- **Value**: "Is our price above or below market?" per hotel/star/room type

#### SearchResultsSessionPollLog
- **Purpose**: Per-provider price granularity (129 OTA providers)
- **Volume**: 8.3M rows
- **Key columns**: HotelId, PriceAmount, NetPriceAmount, DateInsert, ProviderId, RoomCategory
- **Access**: MCP `medici_provider_pressure`, `medici_provider_trends`
- **Value**: Which provider is dropping prices fastest? Provider spread analysis.

#### MED_SearchHotels (Archive)
- **Purpose**: 3 years of historical hotel search data (2020-2023)
- **Volume**: 7M rows
- **Key columns**: HotelId, DateFrom, DateTo, Price, providerId, source
- **Access**: MCP `medici_historical_patterns`, `load_med_search_hotels()`
- **Value**: Seasonal baseline — "what was this room's price in March 2022?"

### 1.3 Booking Pipeline

#### MED_Book
- **Purpose**: Purchased rooms — active inventory
- **Volume**: 10.7K rows
- **Key columns**: id, PreBookId, HotelId, price (BuyPrice), lastPrice (market), DateLastPrice, IsActive, IsSold, startDate, endDate
- **Access**: `load_active_bookings()`, `load_med_book_for_prediction()`
- **Value**: lastPrice vs price = market movement. Track margin erosion over time.

#### MED_PreBook
- **Purpose**: Pre-booked (tentative) rooms before purchase
- **Volume**: 10.7K rows
- **Key columns**: PreBookId, HotelId, DateFrom, DateTo, Price, ProviderName
- **Access**: `load_prebooks()`

#### MED_CancelBook
- **Purpose**: Cancellation events — demand collapse signal
- **Volume**: 4.7K rows
- **Key columns**: Id, PreBookId, CancellationDate, CancellationReason, DateInsert
- **Access**: MCP `medici_cancellation_spikes`, `load_cancellations()`
- **Value**: Cancellation spikes (>2x avg) predict price drops

#### BackOfficeOPT
- **Purpose**: Opportunity headers — rooms we plan to buy
- **Key columns**: id, HotelID, StartDate, EndDate, BuyPrice, PushPrice, Status
- **Access**: `load_backoffice_opportunities()`, skill `insert-opp`

#### MED_Opportunities
- **Purpose**: Room-night detail records for selling
- **Key columns**: OpportunityId, DateFrom, DateTo, Price, PushPrice, DestinationsId
- **Access**: `load_opportunities()`

### 1.4 Reference Data

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| Med_Hotels | Master hotel list (23+) | HotelId, InnstantId, ZenithId, name, isActive |
| Med_Hotels_ratebycat | Zenith rate plan mappings | HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode |
| MED_Board | Board types (7) | BoardId, BoardCode (RO, BB, HB, FB, AI, CB, BD) |
| MED_RoomCategory | Room types (5) | CategoryId, Name (Standard, Superior, Deluxe, Suite, Dormitory) |
| Med_Source | OTA providers (129) | Id, Name, IsActive |
| Destinations | Cities/areas (40K+) | Id, Name, Latitude, Longitude |
| tprice | Historical monthly baselines | price, month, HotelId |

### 1.5 Execution Tables (WRITE access)

| Table | Purpose | Who Writes |
|-------|---------|-----------|
| SalesOffice.PriceOverride | PUT signal execution — price reductions | prediction_reader (override system) |
| BackOfficeOPT | CALL signal — opportunity headers | prediction_reader (opportunity system) |
| MED_Opportunities | CALL signal — room-night details | prediction_reader (opportunity system) |

---

## 2. Local SQLite Databases

### salesoffice_prices.db
- **Location**: `data/salesoffice_prices.db`
- **Tables**: `price_snapshots`, `analysis_runs`
- **Purpose**: Hourly price snapshots from every 3h scan cycle
- **Schema**:
  ```
  price_snapshots: snapshot_ts, detail_id, order_id, hotel_id, hotel_name,
                   room_category, room_board, room_price, room_code,
                   date_from, date_to, UNIQUE(snapshot_ts, detail_id)
  ```
- **Access**: `price_store.py` — `load_all_snapshots()`, `load_price_history(detail_id)`
- **Value**: Reconstruct exact price at any scan checkpoint

### prediction_tracker.db
- **Tables**: `prediction_log`
- **Purpose**: Closed-loop accuracy — every prediction vs actual
- **Schema**:
  ```
  prediction_log: room_id, hotel_id, prediction_ts, checkin_date, t_at_prediction,
                  predicted_price, predicted_signal, actual_price, error_pct, signal_correct
  ```
- **Access**: `accuracy_tracker.py` — `load_prediction_logs()`

### override_queue.db / opportunity_queue.db
- **Purpose**: Execution queue history (PUT/CALL signals acted upon)
- **Value**: Track which signals led to action and their outcomes

### fred_data.db
- **Purpose**: FRED macroeconomic indicators (Hotel PPI, Employment, CPI)
- **Access**: `FREDCollector.collect()` persists here

---

## 3. MCP Tools (medici-db server)

| Tool | Best For | Tables Used |
|------|----------|-------------|
| `medici_price_drops` | Find price drops by hotel, min %, time window | SalesOffice.Log + Details |
| `medici_scan_velocity` | Inter-scan price momentum (velocity %) | SalesOffice.Details (LAG window) |
| `medici_market_pressure` | Hotel vs competitor positioning | AI_Search_HotelData |
| `medici_price_change_log` | Every price update event | RoomPriceUpdateLog |
| `medici_provider_pressure` | Which providers are dropping prices | SearchResultsPollLog |
| `medici_provider_trends` | Per-provider trend over 14 days | SearchResultsPollLog |
| `medici_booking_intelligence` | Booking pipeline analysis | MED_Book + PreBook + CancelBook |
| `medici_cancellation_spikes` | Anomaly detection in cancellations | MED_CancelBook |
| `medici_historical_patterns` | 2020-2023 seasonal/weekly patterns | MED_SearchHotels |
| `medici_combined_put_analysis` | Unified PUT score (all sources) | All of above |
| `medici_mapping_status` | Hotel configuration status | Med_Hotels + Orders |
| `medici_query` | Custom read-only SQL | Any table (SELECT only) |

---

## 4. Skills (medici-price-prediction/skills/)

| Skill | Purpose | Data Sources |
|-------|---------|-------------|
| **next-scan-drop** | Predict ≥5% drop in next 3h scan | Details + Log + RoomPriceUpdateLog + AI_Search |
| **salesoffice-price-drop** | Analyze Log for drop statistics | SalesOffice.Log (regex parsing) |
| **hotel-data-explorer** | Full DB exploration (--prices, --scans, --logs, --sql) | All tables |
| **price-prediction** | Time-series forecasting (ARIMA/ETS/Prophet) | price_snapshots |
| **price-visualization** | Advanced charts (candlestick, heatmap, waterfall) | Any DataFrame |
| **insert-opp** | Execute CALL signals (buy rooms) | BackOfficeOPT + MED_Opportunities |
| **price-override** | Execute PUT signals (push lower price) | SalesOffice.PriceOverride + Zenith SOAP |

---

## 5. External Data Sources

| Source | Data | Volume | Frequency | Access |
|--------|------|--------|-----------|--------|
| Kiwi.com Flights | Miami flight demand/prices | Variable | Daily | API (flights.db cache) |
| Ticketmaster/SeatGeek | Miami events + attendance | 8 major + dynamic | Weekly | API (events.db cache) |
| Open-Meteo | Weather history + 14-day forecast | Daily | Daily | API (weather_cache.db) |
| GMCVB | Official Miami ADR/RevPAR by zone | Weekly | Weekly | Manual/scraper |
| FRED St. Louis Fed | Hotel PPI, Lodging CPI, Employment | Monthly | Monthly | API (fred_data.db) |
| Statista | Miami ADR benchmarks | Annual | Annual | Manual |
| BrightData | Live OTA prices (Booking/Expedia) | On demand | On demand | MCP scraper |

---

## 6. How to Answer Historical Price Questions

### "What was the price for hotel X, room Y, on check-in Z at T days before check-in?"

1. **SQLite snapshots** (fastest): `price_store.load_price_history(detail_id)` → find snapshot_ts ≈ checkin - T days
2. **Azure SQL Log** (most complete): MCP `medici_price_drops(hotel_id, hours_back)` → parse DbRoomPrice changes
3. **RoomPriceUpdateLog** (every change): MCP `medici_price_change_log(hotel_id)` → exact timestamps
4. **Historical archive** (2020-2023): MCP `medici_historical_patterns(hotel_id, group_by="month")`

### "How fast is the price dropping?"

1. **Scan velocity**: MCP `medici_scan_velocity(hotel_id, direction="DROP")` → % change per 3h scan
2. **Acceleration**: `next-scan-drop` skill → velocity_3h, acceleration, drop_frequency features
3. **Provider trends**: MCP `medici_provider_trends(hotel_id)` → which OTAs are cutting fastest

### "Is this a good price vs market?"

1. **Competitor comparison**: MCP `medici_market_pressure(hotel_id)` → vs AI_Search 8.5M rows
2. **Provider spread**: MCP `medici_provider_pressure(hotel_id)` → 129 provider prices
3. **Official benchmark**: GMCVB ADR by zone → `vote_official_benchmark()` voter
4. **Historical baseline**: MCP `medici_historical_patterns(hotel_id)` → 2020-2023 seasonal avg

### "Is demand collapsing?"

1. **Cancellations**: MCP `medici_cancellation_spikes(hotel_id)` → anomaly detection
2. **Booking intelligence**: MCP `medici_booking_intelligence(hotel_id)` → conversion rates
3. **Flight demand**: Kiwi.com flights → `vote_flight_demand()` voter
4. **Events**: `MIAMI_MAJOR_EVENTS` → `vote_events()` voter (upcoming = demand boost)

---

## 7. Database Connection

| Property | Value |
|----------|-------|
| Server | medici-sql-server.database.windows.net |
| Database | medici-db |
| Read user | prediction_reader |
| Write tables | PriceOverride, BackOfficeOPT, MED_Opportunities only |
| Enforcement | SQLAlchemy event listener blocks all other writes |
| MCP transport | stdio (stdin/stdout) |

---

## 8. Consensus Signal Engine — 11 Voters

| Voter | Category | Data Source | Connected |
|-------|----------|-------------|-----------|
| Forward Curve | Lagging | FC change_pct | Yes |
| Scan Velocity | Coincident | momentum.velocity_24h | Yes |
| Competitors | Coincident | Zone avg price (same tier) | Yes |
| Events | Leading | MIAMI_MAJOR_EVENTS (v2.6.0) | Yes |
| Seasonality | Leading | FC season_adj_pct | Yes |
| Flight Demand | Leading | FC demand_adj_pct | Yes |
| Weather | Leading | FC weather_adj_pct | Yes |
| Peers | Coincident | Peer hotel directions (v2.6.0) | Yes |
| Booking Momentum | Lagging | FC cancellation_adj_pct | Yes |
| Historical | Lagging | probability.up/down | Yes |
| Official Benchmark | Lagging | GMCVB ADR by zone | Yes |

**Rules**: Equal weight, probability = agreeing/voting × 100%, ≥66% = signal, MIN_VOTING=4

---

## 9. Prediction Pipeline

```
Price Scan (every 3h)
  → SalesOffice.Details query → SQLite snapshot
  → Build Forward Curve (Bayesian smoothed, 9 enrichments)
  → Combine: FC 50% + Historical 30% + ML 20%
  → 11-voter Consensus Signal (CALL/PUT/NEUTRAL)
  → Rule Matcher → Override Queue / Opportunity Queue
  → Zenith Push (if enabled) / BuyRoom (if approved)
```

### Enrichments (applied to Forward Curve)
1. Events: +0.03% to +0.40%
2. Seasonality: ×3.0 multiplier, Feb peak +9.9%, Sep trough -15.5%
3. Demand (flights): HIGH +0.15%, LOW -0.15%
4. Weather: rain -0.05%, clear +0.02%, hurricane -0.15%
5. Competitor pressure: ±0.20%
6. Cancellation risk: -0.25% max
7. Market benchmark: from AI_Search_HotelData
8. Price velocity: from RoomPriceUpdateLog
9. Booking momentum: from MED_Book pipeline
