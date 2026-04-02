"""Zenith SOAP push utility — single source of truth for rate pushes.

All Zenith credentials and SOAP XML construction centralized here.
Credentials read from environment variables, not hardcoded.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

ZENITH_URL = os.getenv("ZENITH_SOAP_URL", "https://hotel.tools/service/Medici%20new")
ZENITH_USERNAME = os.getenv("ZENITH_SOAP_USERNAME")
ZENITH_PASSWORD = os.getenv("ZENITH_SOAP_PASSWORD")
ZENITH_TIMEOUT = 10


def _require_zenith_creds() -> tuple[str, str]:
    """Return (username, password) or raise if not configured."""
    if not ZENITH_USERNAME or not ZENITH_PASSWORD:
        raise RuntimeError(
            "ZENITH_SOAP_USERNAME and ZENITH_SOAP_PASSWORD env vars required for Zenith push"
        )
    return ZENITH_USERNAME, ZENITH_PASSWORD


def build_soap_envelope(hotel_code: str, inv_type_code: str, rate_plan_code: str,
                        start: str, end: str, amount: float, echo_token: str = "override") -> str:
    """Build OTA_HotelRateAmountNotifRQ SOAP envelope."""
    username, password = _require_zenith_creds()
    return f'''<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Header>
    <wsse:Security soap:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <wsse:UsernameToken>
        <wsse:Username>{username}</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{password}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </SOAP-ENV:Header>
  <SOAP-ENV:Body>
    <OTA_HotelRateAmountNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05" TimeStamp="{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")}" Version="1.0" EchoToken="{echo_token}">
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


def push_rate_to_zenith(hotel_code: str, inv_type_code: str, rate_plan_code: str,
                        start: str, end: str, amount: float,
                        echo_token: str = "override") -> tuple[bool, str]:
    """Push a single rate to Zenith. Returns (success, response_preview)."""
    soap = build_soap_envelope(hotel_code, inv_type_code, rate_plan_code, start, end, amount, echo_token)
    try:
        resp = requests.post(
            ZENITH_URL,
            data=soap,
            headers={"Content-Type": "text/xml"},
            timeout=ZENITH_TIMEOUT,
        )
        success = resp.status_code == 200 and "Error" not in resp.text
        return success, resp.text[:200]
    except Exception as exc:
        logger.error("Zenith push failed: %s", exc)
        return False, str(exc)[:200]


def get_pyodbc_connection():
    """Create pyodbc connection from MEDICI_DB_URL env var. Returns connection or raises."""
    import pyodbc
    from urllib.parse import urlparse, parse_qs, unquote

    db_url = os.getenv("MEDICI_DB_URL", "")
    if not db_url:
        raise ValueError("MEDICI_DB_URL not configured")

    parsed = urlparse(db_url)
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    server = parsed.hostname or ""
    database = parsed.path.lstrip("/")
    qs_params = parse_qs(parsed.query)
    driver = qs_params.get("driver", ["ODBC Driver 18 for SQL Server"])[0]

    conn_str = (
        f"DRIVER={{{driver}}};Server={server};Database={database};"
        f"Uid={user};Pwd={password};Encrypt=yes;TrustServerCertificate=no;"
        f"Connection Timeout=15"
    )
    return pyodbc.connect(conn_str, timeout=15)
