"""
Insert Opportunity Skill - Create purchase opportunities from Price Predictor

Replicates the exact logic of Backend's InsertOpp endpoint (BaseEF.cs lines 463-546)
but runs directly against the DB, bypassing the API proxy.

Usage:
    # Single opportunity
    python insert_opp.py --connection-string "..." \
      --hotel-id 32687 --start 2026-04-15 --end 2026-04-16 \
      --board-id 1 --category-id 1 \
      --buy-price 164.83 --push-price 189.00 \
      --max-rooms 3 --name "Jakob OCONNOR" --by PricePredictor

    # Bulk from CSV
    python insert_opp.py --connection-string "..." --csv opps.csv --by PricePredictor

    # Check status
    python insert_opp.py --connection-string "..." --status

    # Cancel opportunity
    python insert_opp.py --connection-string "..." --cancel --opp-id 12345
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta

import pyodbc


# ═══════════════════════════════════════════════════════════════
# GUARDRAILS
# ═══════════════════════════════════════════════════════════════

ALLOWED_SYSTEMS = ["PricePredictor"]

MIN_PRICE = 1.0
MAX_PRICE = 10000.0
MIN_MARGIN_PCT = 3          # pushPrice must be >= 103% of buyPrice
MAX_ROOMS = 30
MAX_DATE_SPAN_DAYS = 90
MAX_OPPS_PER_RUN = 50
MAX_OPPS_PER_HOTEL_PER_DAY = 10
FUTURE_DATES_ONLY = True
DUPLICATE_CHECK = True

ALLOWED_WRITE_TABLES = ["BackOfficeOPT", "MED_\u05b9O\u05b9\u05b9pportunities"]


# ═══════════════════════════════════════════════════════════════
# MAIN CLASS
# ═══════════════════════════════════════════════════════════════

class InsertOppSkill:
    def __init__(self, connection_string):
        self.conn = pyodbc.connect(connection_string)
        self.cursor = self.conn.cursor()
        self.audit_log = []
        self.opps_created_this_run = 0

    def _audit(self, action, data):
        self.audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            **data,
        })

    # ── VALIDATION ────────────────────────────────────────────

    def _validate(self, hotel_id, start_date, end_date, board_id, category_id,
                  buy_price, push_price, max_rooms, name, created_by):
        """Validate all inputs. Returns error string or None."""

        # 1. Authorized system
        if created_by not in ALLOWED_SYSTEMS:
            return f"Unauthorized: {created_by}. Allowed: {ALLOWED_SYSTEMS}"

        # 2. Hotel exists with ZenithId
        self.cursor.execute("""
            SELECT HotelId, [Name], Innstant_ZenithId, isActive
            FROM Med_Hotels WHERE HotelId = ?
        """, hotel_id)
        hotel = self.cursor.fetchone()
        if not hotel:
            return f"Hotel {hotel_id} not found"
        if not hotel[2] or hotel[2] <= 0:
            return f"Hotel {hotel_id} has no ZenithId"
        if not hotel[3]:
            return f"Hotel {hotel_id} is not active"

        # 3. ratebycat exists
        self.cursor.execute("""
            SELECT COUNT(*) FROM Med_Hotels_ratebycat
            WHERE HotelId = ? AND BoardId = ? AND CategoryId = ?
        """, hotel_id, board_id, category_id)
        if self.cursor.fetchone()[0] == 0:
            return f"No ratebycat for hotel={hotel_id} board={board_id} category={category_id}"

        # 4. Price range
        if buy_price < MIN_PRICE or buy_price > MAX_PRICE:
            return f"BuyPrice {buy_price} out of range [{MIN_PRICE}, {MAX_PRICE}]"
        if push_price < MIN_PRICE or push_price > MAX_PRICE:
            return f"PushPrice {push_price} out of range [{MIN_PRICE}, {MAX_PRICE}]"

        # 5. Margin check
        min_push = buy_price * (1 + MIN_MARGIN_PCT / 100.0)
        if push_price < min_push:
            return f"PushPrice {push_price} too low. Minimum {min_push:.2f} ({MIN_MARGIN_PCT}% margin on {buy_price})"

        # 6. Max rooms
        if max_rooms < 1 or max_rooms > MAX_ROOMS:
            return f"MaxRooms {max_rooms} out of range [1, {MAX_ROOMS}]"

        # 7. Date validation
        if FUTURE_DATES_ONLY and start_date.date() < datetime.now().date():
            return f"Start date {start_date.date()} is in the past"
        if end_date <= start_date:
            return f"End date must be after start date"
        span = (end_date - start_date).days
        if span > MAX_DATE_SPAN_DAYS:
            return f"Date span {span} days exceeds max {MAX_DATE_SPAN_DAYS}"

        # 8. Name validation
        if not name or len(name.strip().split()) < 2:
            return f"Name must be at least 2 words: '{name}'"

        # 9. Volume limit
        if self.opps_created_this_run >= MAX_OPPS_PER_RUN:
            return f"Volume limit: {MAX_OPPS_PER_RUN} per run"

        # 10. Duplicate check
        if DUPLICATE_CHECK:
            self.cursor.execute("""
                SELECT COUNT(*) FROM BackOfficeOPT
                WHERE HotelId = ? AND StartDate = ? AND EndDate = ?
                AND BordId = ? AND CatrgoryId = ? AND Status = 1
            """, hotel_id, start_date, end_date, board_id, category_id)
            if self.cursor.fetchone()[0] > 0:
                return f"Duplicate: active opportunity exists for hotel={hotel_id} {start_date.date()}-{end_date.date()} board={board_id} cat={category_id}"

        return None  # All good

    # ── GET RATEPLAN INFO ─────────────────────────────────────

    def _get_rateplan(self, hotel_id, board_id, category_id):
        """Get RatePlanCode and InvTypeCode from ratebycat"""
        self.cursor.execute("""
            SELECT RatePlanCode, InvTypeCode
            FROM Med_Hotels_ratebycat
            WHERE HotelId = ? AND BoardId = ? AND CategoryId = ?
        """, hotel_id, board_id, category_id)
        row = self.cursor.fetchone()
        if row:
            return row[0], row[1]
        return None, None

    # ── INSERT ────────────────────────────────────────────────

    def insert_opportunity(self, hotel_id, start_str, end_str, board_id, category_id,
                           buy_price, push_price, max_rooms, name, created_by):
        """Create opportunity - replicates BaseEF.cs InsertOpp logic exactly"""

        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")

        # Validate
        error = self._validate(hotel_id, start_date, end_date, board_id, category_id,
                               buy_price, push_price, max_rooms, name, created_by)
        if error:
            return {"error": error}

        # Get rateplan
        rpc, itc = self._get_rateplan(hotel_id, board_id, category_id)
        if not rpc or not itc:
            return {"error": f"No RatePlanCode/InvTypeCode for hotel={hotel_id} board={board_id} cat={category_id}"}

        # Step 1: Insert BackOfficeOPT (matches BaseEF.cs lines 475-491)
        self.cursor.execute("""
            INSERT INTO BackOfficeOPT
            (DateInsert, CountryId, HotelId, StartDate, EndDate, BordId, CatrgoryId,
             BuyPrice, PushPrice, MaxRooms, Status, InvTypeCode, RatePlanCode, ReservationFirstName)
            VALUES (GETDATE(), 1, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """, hotel_id, start_date, end_date, board_id, category_id,
             buy_price, push_price, max_rooms, itc, rpc, name)
        self.conn.commit()

        # Get the ID
        self.cursor.execute("SELECT SCOPE_IDENTITY()")
        row = self.cursor.fetchone()
        if row and row[0]:
            opp_ml_id = int(row[0])
        else:
            self.cursor.execute("SELECT MAX(id) FROM BackOfficeOPT")
            opp_ml_id = self.cursor.fetchone()[0]

        # Step 2: Insert MED_\u05b9O\u05b9\u05b9pportunities (matches BaseEF.cs lines 500-542)
        rooms_created = 0
        current_date = start_date
        while current_date < end_date:
            for room_num in range(max_rooms):
                self.cursor.execute("""
                    INSERT INTO MED_\u05b9O\u05b9\u05b9pportunities
                    (OpportunityMlId, DateCreate, DateForm, DateTo, NumberOfNights,
                     BoardId, CategoryId, Price, Operator, Currency,
                     FreeCancelation, CountryCode, PaxAdultsCount, PaxChildrenCount,
                     DestinationsType, DestinationsId, PushHotelCode, PushBookingLimit,
                     PushInvTypeCode, PushRatePlanCode, PushPrice, PushCurrency,
                     IsActive, IsPush, IsSale, ReservationFirstName)
                    VALUES (?, GETDATE(), ?, ?, 1,
                            ?, ?, ?, 'LTE', 'USD',
                            1, 'IL', 2, 0,
                            'hotel', ?, ?, 1,
                            ?, ?, ?, 'USD',
                            1, 0, 0, ?)
                """, opp_ml_id, current_date.date(), (current_date + timedelta(days=1)).date(),
                     board_id, category_id, buy_price,
                     hotel_id, hotel_id,
                     itc, rpc, push_price, name)
                rooms_created += 1
            current_date += timedelta(days=1)

        self.conn.commit()
        self.opps_created_this_run += 1

        result = {
            "success": True,
            "opp_id": opp_ml_id,
            "hotel_id": hotel_id,
            "dates": f"{start_str} to {end_str}",
            "rooms_created": rooms_created,
            "buy_price": buy_price,
            "push_price": push_price,
            "created_by": created_by,
        }

        self._audit("insert_opp", result)
        return result

    # ── BULK CSV ──────────────────────────────────────────────

    def insert_bulk_csv(self, csv_path, created_by):
        """Create opportunities from CSV"""
        results = {"success": 0, "failed": 0, "errors": [], "opp_ids": []}

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                result = self.insert_opportunity(
                    hotel_id=int(row["hotel_id"]),
                    start_str=row["start_date"],
                    end_str=row["end_date"],
                    board_id=int(row["board_id"]),
                    category_id=int(row["category_id"]),
                    buy_price=float(row["buy_price"]),
                    push_price=float(row["push_price"]),
                    max_rooms=int(row["max_rooms"]),
                    name=row["name"],
                    created_by=created_by,
                )
                if "error" in result:
                    results["failed"] += 1
                    results["errors"].append(result["error"])
                else:
                    results["success"] += 1
                    results["opp_ids"].append(result["opp_id"])

        return results

    # ── STATUS ────────────────────────────────────────────────

    def get_status(self, opp_id=None):
        """Get opportunity status"""
        if opp_id:
            self.cursor.execute("""
                SELECT bo.id, bo.HotelId, h.[Name], bo.StartDate, bo.EndDate,
                       bo.BuyPrice, bo.PushPrice, bo.MaxRooms, bo.Status,
                       (SELECT COUNT(*) FROM MED_\u05b9O\u05b9\u05b9pportunities WHERE OpportunityMlId = bo.id AND IsActive = 1) as ActiveOpps,
                       (SELECT COUNT(*) FROM MED_\u05b9O\u05b9\u05b9pportunities WHERE OpportunityMlId = bo.id AND IsPush = 1) as Pushed,
                       (SELECT COUNT(*) FROM MED_\u05b9O\u05b9\u05b9pportunities WHERE OpportunityMlId = bo.id AND IsSale = 1) as Sold
                FROM BackOfficeOPT bo
                LEFT JOIN Med_Hotels h ON h.HotelId = bo.HotelId
                WHERE bo.id = ?
            """, opp_id)
            row = self.cursor.fetchone()
            if not row:
                return {"error": f"Opportunity {opp_id} not found"}
            return {
                "opp_id": row[0], "hotel": f"{row[2]} ({row[1]})",
                "dates": f"{str(row[3])[:10]} to {str(row[4])[:10]}",
                "buy": float(row[5]), "push": float(row[6]),
                "max_rooms": row[7], "status": "active" if row[8] else "cancelled",
                "active_opps": row[9], "pushed": row[10], "sold": row[11],
            }
        else:
            self.cursor.execute("""
                SELECT COUNT(*) as Total,
                    SUM(CASE WHEN Status = 1 THEN 1 ELSE 0 END) as Active,
                    SUM(CASE WHEN Status = 0 THEN 1 ELSE 0 END) as Cancelled
                FROM BackOfficeOPT
            """)
            row = self.cursor.fetchone()
            return {"total": row[0], "active": row[1], "cancelled": row[2]}

    # ── CANCEL ────────────────────────────────────────────────

    def cancel_opportunity(self, opp_id):
        """Cancel opportunity - matches BaseEF.cs CancelOpportunity logic"""
        # Set BackOfficeOPT.Status = false
        self.cursor.execute("UPDATE BackOfficeOPT SET Status = 0 WHERE id = ?", opp_id)
        if self.cursor.rowcount == 0:
            return {"error": f"Opportunity {opp_id} not found"}

        # Set all MED_\u05b9O\u05b9\u05b9pportunities.IsActive = false
        self.cursor.execute("""
            UPDATE MED_\u05b9O\u05b9\u05b9pportunities SET IsActive = 0
            WHERE OpportunityMlId = ?
        """, opp_id)
        cancelled = self.cursor.rowcount
        self.conn.commit()

        self._audit("cancel_opp", {"opp_id": opp_id, "rows_cancelled": cancelled})
        return {"success": True, "opp_id": opp_id, "rows_cancelled": cancelled}

    # ── AUDIT ─────────────────────────────────────────────────

    def save_audit(self, output_dir):
        if not self.audit_log:
            return None
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"insert-opp-audit-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w") as f:
            json.dump(self.audit_log, f, indent=2, default=str)
        return path

    def close(self):
        self.conn.close()


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Insert Opportunity Skill")
    parser.add_argument("--connection-string", required=True)
    parser.add_argument("--hotel-id", type=int)
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--board-id", type=int)
    parser.add_argument("--category-id", type=int)
    parser.add_argument("--buy-price", type=float)
    parser.add_argument("--push-price", type=float)
    parser.add_argument("--max-rooms", type=int, default=1)
    parser.add_argument("--name", default="Price Predictor Guest")
    parser.add_argument("--by", dest="created_by", default="PricePredictor")
    parser.add_argument("--csv", help="Bulk insert from CSV")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--opp-id", type=int)
    parser.add_argument("--cancel", action="store_true")
    parser.add_argument("--out", default="opp-report")
    args = parser.parse_args()

    skill = InsertOppSkill(args.connection_string)

    try:
        if args.status:
            result = skill.get_status(args.opp_id)
            print(json.dumps(result, indent=2, default=str))

        elif args.cancel and args.opp_id:
            result = skill.cancel_opportunity(args.opp_id)
            print(json.dumps(result, indent=2, default=str))

        elif args.csv:
            result = skill.insert_bulk_csv(args.csv, args.created_by)
            print(f"Created: {result['success']} | Failed: {result['failed']}")
            if result["opp_ids"]:
                print(f"Opp IDs: {result['opp_ids']}")
            if result["errors"]:
                for err in result["errors"]:
                    print(f"  ERROR: {err}")

        elif args.hotel_id and args.start and args.end:
            result = skill.insert_opportunity(
                args.hotel_id, args.start, args.end,
                args.board_id, args.category_id,
                args.buy_price, args.push_price,
                args.max_rooms, args.name, args.created_by,
            )
            print(json.dumps(result, indent=2, default=str))

        else:
            parser.print_help()

        audit_path = skill.save_audit(args.out)
        if audit_path:
            print(f"Audit: {audit_path}")

    finally:
        skill.close()


if __name__ == "__main__":
    main()
