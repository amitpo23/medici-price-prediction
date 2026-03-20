"""
Price Override Skill - Push override prices to Zenith/Noovy

Allows Price Predictor (or other authorized systems) to override
the price pushed to Zenith for specific SalesOffice Details,
without modifying the Detail itself (API price = source of truth).

Usage:
    # Write single override
    python override_push.py --write --detail-id 12345 --price 520.00 --by PricePredictor

    # Write from CSV
    python override_push.py --write-csv overrides.csv --by PricePredictor

    # Push all pending overrides to Zenith
    python override_push.py --push --connection-string "..."

    # Check status
    python override_push.py --status

    # Emergency rollback
    python override_push.py --rollback

    # Full cycle
    python override_push.py --write-csv overrides.csv --push --by PricePredictor
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pyodbc
import requests


# ═══════════════════════════════════════════════════════════════
# GUARDRAILS
# ═══════════════════════════════════════════════════════════════

ALLOWED_SYSTEMS = ["PricePredictor"]

MIN_PRICE = 1.0
MAX_PRICE = 10000.0
MAX_DEVIATION_PCT = 50  # ±50% from original price

MAX_OVERRIDES_PER_RUN = 5000
MAX_OVERRIDES_PER_HOTEL = 500
PUSH_DELAY_MS = 200
PUSH_TIMEOUT_SEC = 10
MAX_CONSECUTIVE_ERRORS = 5  # circuit breaker

# Table protection: ONLY these tables can be written to
ALLOWED_WRITE_TABLES = ["SalesOffice.PriceOverride"]

# Zenith credentials
ZENITH_URL = "https://hotel.tools/service/Medici%20new"
ZENITH_USERNAME = "APIMedici:Medici Live"
ZENITH_PASSWORD = "12345"


# ═══════════════════════════════════════════════════════════════
# ZENITH SOAP
# ═══════════════════════════════════════════════════════════════

def build_push_rates_soap(hotel_code, inv_type_code, rate_plan_code, start, end, amount):
    """Build SOAP XML for OTA_HotelRateAmountNotifRQ - identical to ApiInstantZenith.cs"""
    return f'''<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Header xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
    <wsse:Security soap:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <wsse:UsernameToken>
        <wsse:Username>{ZENITH_USERNAME}</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{ZENITH_PASSWORD}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </SOAP-ENV:Header>
  <SOAP-ENV:Body xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
    <OTA_HotelRateAmountNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05" TimeStamp="{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}" Version="1.0" EchoToken="override">
      <RateAmountMessages HotelCode="{hotel_code}">
        <RateAmountMessage>
          <StatusApplicationControl InvTypeCode="{inv_type_code}" RatePlanCode="{rate_plan_code}" Start="{start}" End="{end}"/>
          <Rates>
            <Rate>
              <BaseByGuestAmts>
                <BaseByGuestAmt AgeQualifyingCode="10" AmountAfterTax="{amount}"/>
                <BaseByGuestAmt AgeQualifyingCode="8" AmountAfterTax="{amount}"/>
              </BaseByGuestAmts>
            </Rate>
          </Rates>
        </RateAmountMessage>
      </RateAmountMessages>
    </OTA_HotelRateAmountNotifRQ>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>'''


def push_rate_to_zenith(hotel_code, inv_type_code, rate_plan_code, start, end, amount):
    """Push a single rate to Zenith. Returns (success, response_text)"""
    soap = build_push_rates_soap(hotel_code, inv_type_code, rate_plan_code, start, end, amount)
    try:
        resp = requests.post(
            ZENITH_URL,
            data=soap,
            headers={"Content-Type": "text/xml"},
            timeout=PUSH_TIMEOUT_SEC,
        )
        success = resp.status_code == 200 and "Error" not in resp.text
        return success, resp.text[:200]
    except Exception as e:
        return False, str(e)[:200]


# ═══════════════════════════════════════════════════════════════
# MAIN CLASS
# ═══════════════════════════════════════════════════════════════

class PriceOverrideSkill:
    def __init__(self, connection_string):
        self.conn = pyodbc.connect(connection_string)
        self.cursor = self.conn.cursor()
        self.audit_log = []

    def _audit(self, action, detail_id, data):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "detail_id": detail_id,
            **data,
        }
        self.audit_log.append(entry)

    # ── READ ──────────────────────────────────────────────────

    def get_active_details(self, hotel_id=None):
        """Get all active Details available for override"""
        sql = """
            SELECT d.Id, d.HotelId, h.[Name], d.RoomCategory, d.RoomBoard,
                   d.RoomPrice, d.SalesOfficeOrderId,
                   o.DateFrom, o.DateTo,
                   h.Innstant_ZenithId
            FROM [SalesOffice.Details] d
            JOIN [SalesOffice.Orders] o ON o.Id = d.SalesOfficeOrderId
            LEFT JOIN Med_Hotels h ON h.HotelId = d.HotelId
            WHERE d.IsDeleted = 0
        """
        if hotel_id:
            sql += f" AND d.HotelId = {int(hotel_id)}"
        sql += " ORDER BY d.HotelId, o.DateFrom, d.RoomCategory, d.RoomBoard"
        self.cursor.execute(sql)
        cols = [desc[0] for desc in self.cursor.description]
        return [dict(zip(cols, row)) for row in self.cursor.fetchall()]

    def get_detail_with_mapping(self, detail_id):
        """Get a single Detail with its Zenith mapping info"""
        self.cursor.execute("""
            SELECT d.Id, d.HotelId, d.RoomCategory, d.RoomBoard, d.RoomPrice,
                   d.IsDeleted, d.SalesOfficeOrderId,
                   o.DateFrom, o.DateTo,
                   h.Innstant_ZenithId,
                   r.RatePlanCode, r.InvTypeCode
            FROM [SalesOffice.Details] d
            JOIN [SalesOffice.Orders] o ON o.Id = d.SalesOfficeOrderId
            LEFT JOIN Med_Hotels h ON h.HotelId = d.HotelId
            LEFT JOIN MED_Board brd ON brd.BoardCode = d.RoomBoard
            LEFT JOIN MED_RoomCategory cat ON LOWER(cat.[Name]) = LOWER(d.RoomCategory)
            LEFT JOIN Med_Hotels_ratebycat r
                ON r.HotelId = d.HotelId AND r.BoardId = brd.BoardId AND r.CategoryId = cat.CategoryId
            WHERE d.Id = ?
        """, detail_id)
        row = self.cursor.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in self.cursor.description]
        return dict(zip(cols, row))

    # ── WRITE OVERRIDE ────────────────────────────────────────

    def set_override(self, detail_id, override_price, created_by):
        """Set a price override for a specific Detail"""
        # Guardrail 1: authorized system
        if created_by not in ALLOWED_SYSTEMS:
            return {"error": f"Unauthorized system: {created_by}. Allowed: {ALLOWED_SYSTEMS}"}

        # Guardrail 2: detail exists and is active
        detail = self.get_detail_with_mapping(detail_id)
        if not detail:
            return {"error": f"Detail {detail_id} not found"}
        if detail["IsDeleted"]:
            return {"error": f"Detail {detail_id} is deleted"}

        # Guardrail 3: price range
        if override_price < MIN_PRICE or override_price > MAX_PRICE:
            return {"error": f"Price {override_price} out of range [{MIN_PRICE}, {MAX_PRICE}]"}

        # Guardrail 4: deviation from original
        original = float(detail["RoomPrice"])
        if original > 0:
            deviation = abs(override_price - original) / original * 100
            if deviation > MAX_DEVIATION_PCT:
                return {"error": f"Price {override_price} deviates {deviation:.0f}% from original {original} (max {MAX_DEVIATION_PCT}%)"}

        # Guardrail 5: Zenith mapping exists
        if not detail.get("RatePlanCode") or not detail.get("InvTypeCode"):
            return {"error": f"Detail {detail_id} has no Zenith mapping (RPC/ITC missing)"}

        # Deactivate any existing override for this detail
        self.cursor.execute("""
            UPDATE [SalesOffice.PriceOverride]
            SET IsActive = 0
            WHERE DetailId = ? AND IsActive = 1
        """, detail_id)

        # Insert new override
        self.cursor.execute("""
            INSERT INTO [SalesOffice.PriceOverride]
            (DetailId, OriginalPrice, OverridePrice, CreatedBy, IsActive)
            VALUES (?, ?, ?, ?, 1)
        """, detail_id, original, override_price, created_by)
        self.conn.commit()

        self._audit("set_override", detail_id, {
            "original_price": original,
            "override_price": override_price,
            "created_by": created_by,
        })

        return {"success": True, "detail_id": detail_id, "original": original, "override": override_price}

    def write_csv(self, csv_path, created_by):
        """Write overrides from CSV file"""
        results = {"success": 0, "failed": 0, "errors": []}
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                if count >= MAX_OVERRIDES_PER_RUN:
                    results["errors"].append(f"Volume limit: stopped at {MAX_OVERRIDES_PER_RUN}")
                    break
                detail_id = int(row["detail_id"])
                price = float(row["override_price"])
                result = self.set_override(detail_id, price, created_by)
                if "error" in result:
                    results["failed"] += 1
                    results["errors"].append(f"Detail {detail_id}: {result['error']}")
                else:
                    results["success"] += 1
                count += 1
        return results

    # ── PUSH TO ZENITH ────────────────────────────────────────

    def push_overrides(self):
        """Push all active, unpushed overrides to Zenith"""
        self.cursor.execute("""
            SELECT po.Id, po.DetailId, po.OverridePrice, po.OriginalPrice
            FROM [SalesOffice.PriceOverride] po
            WHERE po.IsActive = 1 AND po.PushStatus IS NULL
        """)
        pending = self.cursor.fetchall()

        results = {"pushed": 0, "failed": 0, "errors": []}
        consecutive_errors = 0
        hotel_counts = {}

        for override_id, detail_id, override_price, original_price in pending:
            # Circuit breaker
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                results["errors"].append(f"CIRCUIT BREAKER: stopped after {MAX_CONSECUTIVE_ERRORS} consecutive errors")
                break

            # Volume limit
            if results["pushed"] + results["failed"] >= MAX_OVERRIDES_PER_RUN:
                results["errors"].append(f"Volume limit: {MAX_OVERRIDES_PER_RUN}")
                break

            # Get detail mapping
            detail = self.get_detail_with_mapping(detail_id)
            if not detail or not detail.get("RatePlanCode"):
                self._mark_push_status(override_id, "failed")
                results["failed"] += 1
                results["errors"].append(f"Detail {detail_id}: no mapping")
                consecutive_errors += 1
                continue

            # Hotel rate limit
            hotel_id = detail["HotelId"]
            hotel_counts[hotel_id] = hotel_counts.get(hotel_id, 0) + 1
            if hotel_counts[hotel_id] > MAX_OVERRIDES_PER_HOTEL:
                self._mark_push_status(override_id, "skipped")
                results["errors"].append(f"Hotel {hotel_id}: limit {MAX_OVERRIDES_PER_HOTEL}")
                continue

            # Build push params
            venue_id = str(detail["Innstant_ZenithId"])
            itc = detail["InvTypeCode"]
            rpc = detail["RatePlanCode"]
            date_from = detail["DateFrom"].strftime("%Y-%m-%d")
            date_to = detail["DateFrom"].strftime("%Y-%m-%d")  # same day

            # Push
            time.sleep(PUSH_DELAY_MS / 1000.0)
            success, response = push_rate_to_zenith(venue_id, itc, rpc, date_from, date_to, str(override_price))

            if success:
                self._mark_push_status(override_id, "success")
                results["pushed"] += 1
                consecutive_errors = 0
                self._audit("push_success", detail_id, {
                    "override_price": float(override_price),
                    "venue": venue_id, "rpc": rpc, "itc": itc, "date": date_from,
                })
            else:
                self._mark_push_status(override_id, "failed")
                results["failed"] += 1
                consecutive_errors += 1
                results["errors"].append(f"Detail {detail_id}: Zenith push failed - {response[:80]}")
                self._audit("push_failed", detail_id, {"response": response[:200]})

        return results

    def _mark_push_status(self, override_id, status):
        self.cursor.execute("""
            UPDATE [SalesOffice.PriceOverride]
            SET PushStatus = ?, PushedAt = GETDATE()
            WHERE Id = ?
        """, status, override_id)
        self.conn.commit()

    # ── RESET ─────────────────────────────────────────────────

    def reset_overrides(self):
        """Deactivate all active overrides (called after WebJob scan)"""
        self.cursor.execute("""
            UPDATE [SalesOffice.PriceOverride]
            SET IsActive = 0
            WHERE IsActive = 1
        """)
        count = self.cursor.rowcount
        self.conn.commit()
        return {"reset": count}

    # ── ROLLBACK ──────────────────────────────────────────────

    def emergency_rollback(self):
        """Push original prices back to Zenith for all active overrides"""
        self.cursor.execute("""
            SELECT po.Id, po.DetailId, po.OriginalPrice
            FROM [SalesOffice.PriceOverride] po
            WHERE po.IsActive = 1 AND po.PushStatus = 'success'
        """)
        to_rollback = self.cursor.fetchall()

        results = {"rolled_back": 0, "errors": []}
        for override_id, detail_id, original_price in to_rollback:
            detail = self.get_detail_with_mapping(detail_id)
            if not detail or not detail.get("RatePlanCode"):
                results["errors"].append(f"Detail {detail_id}: no mapping for rollback")
                continue

            venue_id = str(detail["Innstant_ZenithId"])
            itc = detail["InvTypeCode"]
            rpc = detail["RatePlanCode"]
            date_from = detail["DateFrom"].strftime("%Y-%m-%d")

            time.sleep(PUSH_DELAY_MS / 1000.0)
            success, _ = push_rate_to_zenith(venue_id, itc, rpc, date_from, date_from, str(original_price))

            if success:
                self._mark_push_status(override_id, "rolled_back")
                self.cursor.execute("UPDATE [SalesOffice.PriceOverride] SET IsActive=0 WHERE Id=?", override_id)
                self.conn.commit()
                results["rolled_back"] += 1
                self._audit("rollback", detail_id, {"restored_price": float(original_price)})
            else:
                results["errors"].append(f"Detail {detail_id}: rollback push failed")

        return results

    # ── STATUS ────────────────────────────────────────────────

    def get_status(self):
        """Get current override status"""
        self.cursor.execute("""
            SELECT
                COUNT(*) as Total,
                SUM(CASE WHEN IsActive=1 AND PushStatus IS NULL THEN 1 ELSE 0 END) as Pending,
                SUM(CASE WHEN IsActive=1 AND PushStatus='success' THEN 1 ELSE 0 END) as Pushed,
                SUM(CASE WHEN PushStatus='failed' THEN 1 ELSE 0 END) as Failed,
                SUM(CASE WHEN IsActive=0 THEN 1 ELSE 0 END) as Inactive
            FROM [SalesOffice.PriceOverride]
        """)
        row = self.cursor.fetchone()
        return {
            "total": row[0], "pending": row[1], "pushed": row[2],
            "failed": row[3], "inactive": row[4],
        }

    # ── SAVE AUDIT ────────────────────────────────────────────

    def save_audit(self, output_dir):
        if not self.audit_log:
            return
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"override-audit-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w") as f:
            json.dump(self.audit_log, f, indent=2, default=str)
        return path

    def close(self):
        self.conn.close()


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Price Override Skill")
    parser.add_argument("--connection-string", required=True)
    parser.add_argument("--write", action="store_true", help="Write single override")
    parser.add_argument("--detail-id", type=int)
    parser.add_argument("--price", type=float)
    parser.add_argument("--by", dest="created_by", default="PricePredictor")
    parser.add_argument("--write-csv", help="Write overrides from CSV")
    parser.add_argument("--push", action="store_true", help="Push pending overrides to Zenith")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--rollback", action="store_true", help="Emergency rollback")
    parser.add_argument("--reset", action="store_true", help="Reset all active overrides")
    parser.add_argument("--out", default="override-report", help="Output directory")
    args = parser.parse_args()

    skill = PriceOverrideSkill(args.connection_string)

    try:
        if args.status:
            status = skill.get_status()
            print(json.dumps(status, indent=2))

        if args.write and args.detail_id and args.price:
            result = skill.set_override(args.detail_id, args.price, args.created_by)
            print(json.dumps(result, indent=2, default=str))

        if args.write_csv:
            result = skill.write_csv(args.write_csv, args.created_by)
            print(f"CSV: {result['success']} success, {result['failed']} failed")
            if result["errors"]:
                for err in result["errors"]:
                    print(f"  ERROR: {err}")

        if args.push:
            result = skill.push_overrides()
            print(f"Push: {result['pushed']} success, {result['failed']} failed")
            if result["errors"]:
                for err in result["errors"]:
                    print(f"  ERROR: {err}")

        if args.rollback:
            result = skill.emergency_rollback()
            print(f"Rollback: {result['rolled_back']} restored")
            if result["errors"]:
                for err in result["errors"]:
                    print(f"  ERROR: {err}")

        if args.reset:
            result = skill.reset_overrides()
            print(f"Reset: {result['reset']} overrides deactivated")

        # Save audit
        audit_path = skill.save_audit(args.out)
        if audit_path:
            print(f"Audit: {audit_path}")

    finally:
        skill.close()


if __name__ == "__main__":
    main()
