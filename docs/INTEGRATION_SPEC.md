# אפיון אינטגרציה: Medici Price Prediction (Decision Brain)

> **מסמך אפיון בלבד** — לא כולל מימוש
> תאריך: 2026-02-26
> גרסה: 2.0

---

## עיקרון מרכזי

```
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║   המערכת הזו היא מוח בלבד.                                        ║
║                                                                    ║
║   • לא קונה                                                       ║
║   • לא מוכרת                                                      ║
║   • לא מבטלת                                                      ║
║   • לא משנה מחירים                                                 ║
║   • לא מבצעת שום פעולה במערכת המסחר                                ║
║                                                                    ║
║   היא מקבלת מידע → מנתחת → מחזירה המלצות ותובנות.                  ║
║   ההחלטה לפעול נשארת תמיד בידי מערכת המסחר או המפעיל.             ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
```

---

## תוכן עניינים

1. [ארכיטקטורה כללית](#1-ארכיטקטורה-כללית)
2. [גישה לנתונים — מה המערכת קוראת](#2-גישה-לנתונים--מה-המערכת-קוראת)
3. [ממשק כניסה — איך שואלים את המערכת](#3-ממשק-כניסה--איך-שואלים-את-המערכת)
4. [ממשק יציאה — מה המערכת מחזירה](#4-ממשק-יציאה--מה-המערכת-מחזירה)
5. [איך המערכת מנתחת את המידע](#5-איך-המערכת-מנתחת-את-המידע)
6. [סוגי המלצות](#6-סוגי-המלצות)
7. [מודל הנתונים](#7-מודל-הנתונים)
8. [ארכיטקטורת תקשורת](#8-ארכיטקטורת-תקשורת)
9. [Feedback Loop — למידה מתוצאות](#9-feedback-loop--למידה-מתוצאות)
10. [שאלות פתוחות](#10-שאלות-פתוחות)

---

## 1. ארכיטקטורה כללית

```
┌─────────────────────────────────────────────────────────────┐
│              MEDICI HOTELS (מערכת המסחר - .NET)              │
│                                                             │
│  BuyRooms │ PushRates │ AutoCancel │ BackOffice │ Dashboard │
│                                                             │
│  ★ מקבלת החלטות ומבצעת פעולות ★                             │
│                                                             │
│         │ שואלת                          ▲ מקבלת תשובה      │
│         │ "מה אתה חושב?"                 │ "הנה הניתוח שלי" │
│         ▼                                │                  │
└─────────┼────────────────────────────────┼──────────────────┘
          │                                │
    ══════╪════════════════════════════════╪══════════════════
          │           API / DB             │
    ══════╪════════════════════════════════╪══════════════════
          │                                │
┌─────────▼────────────────────────────────┼──────────────────┐
│                                                             │
│          PREDICTION ENGINE — Decision Brain                 │
│          (Python, עצמאי לחלוטין, Read-Only)                 │
│                                                             │
│  ┌────────────────────────────────────────────────────┐     │
│  │ DATA LAYER (Read-Only)                             │     │
│  │                                                    │     │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────────┐  │     │
│  │  │medici-db │  │ External     │  │ Local       │  │     │
│  │  │(read     │  │ Sources      │  │ prediction  │  │     │
│  │  │ only)    │  │ (weather,    │  │ DB          │  │     │
│  │  │          │  │  holidays,   │  │ (models,    │  │     │
│  │  │ Books    │  │  events,     │  │  cache,     │  │     │
│  │  │ Opps     │  │  competitors)│  │  history)   │  │     │
│  │  │ Hotels   │  │              │  │             │  │     │
│  │  │ Reserv.  │  │              │  │             │  │     │
│  │  └──────────┘  └──────────────┘  └─────────────┘  │     │
│  └────────────────────────┬───────────────────────────┘     │
│                           │                                 │
│  ┌────────────────────────▼───────────────────────────┐     │
│  │ ANALYSIS LAYER                                     │     │
│  │                                                    │     │
│  │  Feature Engineering (49+ features)                │     │
│  │  Price Forecaster (LightGBM / XGBoost / NBEATS)    │     │
│  │  Occupancy Predictor (Gradient Boosting)           │     │
│  │  Dynamic Pricer (Revenue Optimization)             │     │
│  │  Demand Elasticity (Price Sensitivity)             │     │
│  │  Seasonality Analysis (STL Decomposition)          │     │
│  └────────────────────────┬───────────────────────────┘     │
│                           │                                 │
│  ┌────────────────────────▼───────────────────────────┐     │
│  │ OUTPUT LAYER                                       │──────►
│  │                                                    │  המלצות
│  │  Recommendations (BUY/PASS/HOLD/REPRICE/CANCEL)    │  בלבד
│  │  Price Forecasts + Confidence Intervals             │
│  │  Risk Assessments                                  │
│  │  Portfolio Analysis                                │
│  │  Daily Reports                                     │
│  └────────────────────────────────────────────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**הבהרה חשובה:** חץ היציאה מחזיר **מידע בלבד** — לא פקודות ביצוע. מערכת המסחר (או המפעיל האנושי) מחליטה אם לפעול לפי ההמלצה.

---

## 2. גישה לנתונים — מה המערכת קוראת

### 2.1 גישה ישירה ל-medici-db (Read-Only)

המערכת צריכה **גישת קריאה בלבד** לבסיס הנתונים של מערכת המסחר. אפשרויות:

| אפשרות | תיאור | יתרונות | חסרונות |
|---------|--------|---------|---------|
| **A. Direct Read** | SQLAlchemy connection ישיר ל-medici-db עם user read-only | פשוט, real-time, אין sync lag | תלות ב-DB, load על production |
| **B. DB Replica** | Azure SQL Read Replica | אפס load על production | עלות נוספת, lag קטן |
| **C. Scheduled Import** | Job שמעתיק טבלאות רלוונטיות ל-prediction-db כל X דקות | עצמאות מלאה, אין load | lag, צריך לתחזק sync |
| **D. Hybrid** | Import יומי מלא + Direct Read לשאילתות on-demand | איזון טוב | מורכבות |

**המלצה:** אפשרות **D (Hybrid)** — import יומי של היסטוריה + קריאה ישירה ל-queries נקודתיים.

### 2.2 מה קוראים מ-medici-db

#### טבלה: `MED_Book` — מלאי חדרים שנרכשו

| שדה | טיפוס | שימוש בניתוח |
|------|--------|-------------|
| `PreBookId` | int (PK) | מזהה ייחודי |
| `OpportunityId` | int (FK) | קישור להזדמנות |
| `HotelId` | int (FK) | מזהה מלון |
| `BuyPrice` | decimal | **מחיר קנייה — קריטי לחישוב מרווח** |
| `Price` | decimal | **מחיר מכירה נוכחי (PushPrice)** |
| `LastPrice` | decimal | מחיר קודם — לזיהוי שינויי מחיר |
| `IsActive` | bool | האם עדיין במלאי |
| `IsSold` | bool | **האם נמכר — feedback loop** |
| `SoldId` | string | מזהה מכירה |
| `CancellationTo` | DateTime | **מועד אחרון לביטול חינם** |
| `DateFrom` / `DateTo` | DateTime | תאריכי שהייה |
| `SourceId` | int | 1=Innstant, 2=GoGlobal |
| `Adults` / `Children` | int | הרכב אורחים |
| `Created` | DateTime | תאריך קנייה |
| `ContentBookingId` | string | מזהה הזמנה אצל הספק |

**שימוש:** חישוב מרווח, זיהוי מגמות, feedback loop (נמכר? לא נמכר? באיזה מחיר?)

#### טבלה: `MED_Opportunities` — הזדמנויות קנייה

| שדה | טיפוס | שימוש בניתוח |
|------|--------|-------------|
| `OppId` | int (PK) | מזהה |
| `HotelId` | int (FK) | מלון |
| `DateFrom` / `DateTo` | DateTime | תאריכים |
| `BuyPrice` | decimal | **מחיר קנייה מתוכנן** |
| `PushPrice` | decimal | **מחיר מכירה מתוכנן** |
| `CategoryId` | int (FK) | סוג חדר |
| `BoardId` | int (FK) | סוג ארוחה |
| `IsBought` | bool | האם בוצע |
| `IsCancel` | bool | האם בוטל |

**שימוש:** הבנת אסטרטגיית התמחור הקיימת, חישוב שיעור הצלחה היסטורי

#### טבלה: `BackOfficeOPT` — הזדמנויות מ-BackOffice

| שדה | טיפוס | שימוש בניתוח |
|------|--------|-------------|
| `id` | int (PK) | מזהה |
| `HotelId` | int | מלון |
| `DateFrom` / `DateTo` | DateTime | תאריכים |
| `BuyPrice` | decimal | מחיר קנייה |
| `PushPrice` | decimal | מחיר מכירה |
| `CategoryId` / `BoardId` | int | סוג חדר + ארוחה |
| `IsBought` / `IsSold` / `IsCanceled` | bool | סטטוס |
| `Created` | DateTime | תאריך יצירה |

**שימוש:** היסטוריה מלאה של החלטות + תוצאות → אימון המודל

#### טבלה: `Med_Hotels` — רשימת מלונות

| שדה | טיפוס | שימוש |
|------|--------|-------|
| `HotelId` | int (PK) | מזהה פנימי |
| `Name` | string | שם המלון |
| `Innstant_ZenithId` | string | מזהה ב-Zenith |
| `InnstantId` | string | מזהה בספק |
| `IsActive` | bool | פעיל |
| `RatePlanCode` | string | קוד תעריף |
| `InvTypeCode` | string | קוד סוג חדר |

#### טבלה: `Med_Reservations` — הזמנות אורחים

| שדה | טיפוס | שימוש |
|------|--------|-------|
| `Id` | int (PK) | מזהה |
| `UniqueId` | string | מזהה ייחודי |
| `SoldId` | string | מזהה מכירה — לחיבור ל-MED_Book |
| `Status` | string | Commit/Modify/Cancel |
| `Created` | DateTime | תאריך |

**שימוש:** מדידת קצב ביקוש (booking velocity), שיעור ביטולים

#### טבלאות עזר:
- `Med_Board` — סוגי ארוחה (RO=1, BB=2, HB=3, FB=4, AI=5, CB=6, BD=7)
- `Med_RoomCategories` — סוגי חדר (Standard=1, Superior=2, Dormitory=3, Deluxe=4, Suite=12)
- `Med_Source` — ספקים (Innstant=1, GoGlobal=2)
- `Queue` — תור עבודות (סטטוס עיבוד)
- `Med_Log` — לוגים תפעוליים

#### טבלאות שגיאות (לניתוח כשלונות):
- `MED_BookError` — כשלונות קנייה
- `MED_CancelBookError` — כשלונות ביטול

### 2.3 מקורות חיצוניים (כבר קיימים במערכת)

| מקור | מידע | תדירות | עלות |
|------|-------|---------|------|
| **Open-Meteo** | מזג אוויר (טמפ', גשם) 8 ערים | כל 6 שעות | חינם |
| **Hebcal** | חגים עבריים + חופשות | יומי | חינם |
| **PredictHQ** | אירועים, כנסים, פסטיבלים | יומי | API key |
| **SerpApi** | מחירי מתחרים (Google Hotels) | יומי | API key |
| **CBS** | סטטיסטיקות תיירות ישראל | שבועי | חינם |

---

## 3. ממשק כניסה — איך שואלים את המערכת

המערכת חושפת **REST API** שמערכת המסחר (או כל צרכן אחר) יכולה לקרוא לו.

### 3.1 שאילתה: "האם כדאי לקנות?"

```
POST /api/v1/analyze/opportunity
```

**מי קורא:** BuyRooms WebJob / BackOffice / מפעיל אנושי
**מתי:** לפני כל החלטת קנייה

**Request:**
```json
{
  "opportunity_id": "OPP-12345",
  "hotel_id": 42,
  "city": "Tel Aviv",
  "star_rating": 5,
  "date_from": "2026-04-10",
  "date_to": "2026-04-12",
  "nights": 2,
  "category_id": 4,
  "board_id": 2,
  "adults": 2,
  "children": 0,

  "supplier_options": [
    {
      "source_id": 1,
      "source_name": "Innstant",
      "buy_price_per_night": 420.0,
      "total_buy_price": 840.0,
      "currency": "USD",
      "cancellation_deadline": "2026-04-03",
      "is_free_cancellation": true
    },
    {
      "source_id": 2,
      "source_name": "GoGlobal",
      "buy_price_per_night": 395.0,
      "total_buy_price": 790.0,
      "currency": "USD",
      "cancellation_deadline": "2026-04-05",
      "is_free_cancellation": true
    }
  ],

  "current_push_price": 650.0
}
```

### 3.2 שאילתה: "מה המצב של חדר שכבר קנינו?"

```
GET /api/v1/analyze/booking/{pre_book_id}
```

**מי קורא:** UpdatePrices WebJob / Dashboard / מפעיל
**מתי:** באופן מחזורי (כל 30 דקות) או on-demand

### 3.3 שאילתה: "מה המצב של כל התיק שלנו?"

```
GET /api/v1/analyze/portfolio
```

**מי קורא:** Dashboard / דוח יומי
**מתי:** on-demand או מתוזמן

### 3.4 שאילתה: "מה החיזוי לתאריך/מלון ספציפי?"

```
GET /api/v1/forecast/{hotel_id}?date_from=2026-04-10&date_to=2026-04-12&category_id=4&board_id=2
```

**מי קורא:** כל מי שרוצה חיזוי מחיר
**מתי:** on-demand

### 3.5 שאילתה: "תן לי דוח יומי"

```
GET /api/v1/report/daily?date=2026-02-26
```

### 3.6 שאילתה: "מה ההמלצות הפעילות?"

```
GET /api/v1/recommendations/active
```

**מחזיר:** כל ההמלצות שהמערכת חישבה מסבב הניתוח האחרון (כולל הזדמנויות, אזהרות, שינויי מחיר מומלצים)

---

## 4. ממשק יציאה — מה המערכת מחזירה

### 4.1 תשובה: ניתוח הזדמנות (response ל-3.1)

```json
{
  "opportunity_id": "OPP-12345",
  "analysis_timestamp": "2026-02-26T10:35:00Z",
  "model_version": "lightgbm_v2.1",

  "recommendation": "BUY",
  "confidence": 0.85,
  "reasoning": [
    "GoGlobal זול ב-$50/לילה לעומת Innstant",
    "מחיר שוק צפוי $595 — מרווח של 50% מעל מחיר קנייה",
    "פסח בעוד 45 יום — ביקוש גבוה צפוי",
    "תפוסה צפויה 82% — לחץ מחירים כלפי מעלה",
    "ביטול חינם עד 03/04 — סיכון נמוך"
  ],

  "price_analysis": {
    "best_buy_option": {
      "source": "GoGlobal",
      "source_id": 2,
      "price_per_night": 395.0,
      "total_price": 790.0,
      "why": "cheapest + later cancellation deadline"
    },
    "predicted_market_price": 595.0,
    "confidence_80": [545.0, 645.0],
    "confidence_95": [505.0, 685.0],
    "recommended_push_price": 620.0,
    "expected_margin_pct": 56.9,

    "price_trajectory": {
      "today": 540.0,
      "in_7_days": 560.0,
      "in_14_days": 585.0,
      "in_30_days": 610.0,
      "at_checkin": 630.0,
      "direction": "rising"
    }
  },

  "occupancy_analysis": {
    "predicted_occupancy": 0.82,
    "confidence": [0.76, 0.88],
    "trend": "rising",
    "demand_level": "high"
  },

  "risk_assessment": {
    "risk_level": "low",
    "sell_probability": 0.72,
    "cancellation_safety": {
      "free_until": "2026-04-05",
      "buffer_days": 5,
      "max_loss_if_unsold": 0.0
    },
    "downside_scenario": {
      "probability": 0.15,
      "worst_case_price": 450.0,
      "note": "ביטול חינם — הפסד מקסימלי $0"
    }
  },

  "market_context": {
    "competitor_avg_price": 610.0,
    "our_price_percentile": 55,
    "seasonal_index": 1.22,
    "demand_elasticity": -1.35
  },

  "impact_factors": [
    {"factor": "pessach_proximity", "impact_pct": 18.0, "confidence": "high"},
    {"factor": "high_occupancy_forecast", "impact_pct": 12.0, "confidence": "medium"},
    {"factor": "beach_season", "impact_pct": 5.0, "confidence": "high"},
    {"factor": "weekend_premium", "impact_pct": 10.0, "confidence": "high"}
  ]
}
```

### 4.2 תשובה: ניתוח חדר קיים (response ל-3.2)

```json
{
  "pre_book_id": 8834,
  "hotel_id": 42,
  "analysis_timestamp": "2026-02-26T11:00:00Z",

  "current_status": {
    "buy_price": 395.0,
    "current_push_price": 620.0,
    "current_margin_pct": 56.9,
    "days_to_checkin": 43,
    "days_to_cancel_deadline": 36,
    "is_sold": false
  },

  "recommendation": "HOLD",
  "confidence": 0.78,
  "reasoning": [
    "מחיר המכירה הנוכחי ($620) תואם את התחזית ($595-$645)",
    "עדיין 43 ימים לצ'ק-אין — אין לחץ",
    "ביקוש עולה לקראת פסח",
    "אין צורך בשינוי מחיר כרגע"
  ],

  "price_recommendation": {
    "suggested_push_price": 620.0,
    "change_from_current": 0.0,
    "action": "no_change",
    "optimal_range": [600.0, 640.0]
  },

  "alerts": [],

  "next_review": "2026-02-27T11:00:00Z"
}
```

**אם המצב היה שונה (למשל מחיר שוק ירד):**

```json
{
  "recommendation": "REPRICE",
  "confidence": 0.71,
  "reasoning": [
    "מחיר השוק ירד ל-$520 — מחיר המכירה שלנו ($620) גבוה ב-19%",
    "תפוסה צפויה ירדה ל-58%",
    "נותרו 12 ימים לצ'ק-אין — לחץ למכור"
  ],
  "price_recommendation": {
    "suggested_push_price": 545.0,
    "change_from_current": -75.0,
    "change_pct": -12.1,
    "action": "reduce_price",
    "optimal_range": [530.0, 560.0]
  }
}
```

**או אם צריך לשקול ביטול:**

```json
{
  "recommendation": "CONSIDER_CANCEL",
  "confidence": 0.65,
  "reasoning": [
    "מחיר השוק ($380) מתחת למחיר הקנייה ($395)",
    "תפוסה צפויה רק 32% — ביקוש נמוך",
    "סיכוי מכירה 22% בלבד",
    "מועד ביטול חינם בעוד 3 ימים בלבד"
  ],
  "cancel_analysis": {
    "cost_of_holding": 0.0,
    "probability_of_sale": 0.22,
    "expected_value_if_hold": -15.0,
    "expected_value_if_cancel": 0.0,
    "cancel_deadline": "2026-04-05",
    "days_remaining": 3
  }
}
```

### 4.3 תשובה: ניתוח תיק (response ל-3.3)

```json
{
  "snapshot_timestamp": "2026-02-26T11:00:00Z",

  "portfolio_summary": {
    "total_active_rooms": 45,
    "total_sold_rooms": 128,
    "total_invested_usd": 28500.0,
    "total_expected_revenue_usd": 38700.0,
    "expected_overall_margin_pct": 35.8,
    "portfolio_health": "good"
  },

  "breakdown": {
    "by_recommendation": {
      "hold": 30,
      "reprice_down": 5,
      "reprice_up": 7,
      "consider_cancel": 3
    },
    "by_risk": {
      "low": 32,
      "medium": 10,
      "high": 3
    },
    "by_city": [
      {"city": "Tel Aviv", "rooms": 18, "avg_margin": 42.0, "health": "good"},
      {"city": "Jerusalem", "rooms": 12, "avg_margin": 35.0, "health": "good"},
      {"city": "Eilat", "rooms": 8, "avg_margin": 28.0, "health": "attention"},
      {"city": "Dead Sea", "rooms": 7, "avg_margin": 38.0, "health": "good"}
    ]
  },

  "attention_items": [
    {
      "pre_book_id": 9012,
      "hotel": "Isrotel Dead Sea",
      "issue": "cancel_deadline_in_2_days",
      "recommendation": "CONSIDER_CANCEL",
      "details": "מחיר שוק $380 < מחיר קנייה $395. סיכוי מכירה 22%."
    },
    {
      "pre_book_id": 8756,
      "hotel": "Royal Beach Eilat",
      "issue": "overpriced_vs_market",
      "recommendation": "REPRICE",
      "details": "Push=$720, שוק=$590. ממליץ להוריד ל-$615."
    }
  ],

  "opportunities_detected": [
    {
      "hotel_id": 42,
      "hotel_name": "Dan Panorama Tel Aviv",
      "dates": "2026-04-10 to 2026-04-12",
      "current_supplier_price": 380.0,
      "predicted_sell_price": 620.0,
      "expected_margin_pct": 63.2,
      "confidence": 0.81,
      "note": "מחיר ספק ירד 12% מאתמול. הזדמנות קנייה."
    }
  ]
}
```

### 4.4 תשובה: חיזוי מחיר (response ל-3.4)

```json
{
  "hotel_id": 42,
  "hotel_name": "Dan Panorama Tel Aviv",
  "category": "Deluxe",
  "board": "BB",
  "forecast_generated": "2026-02-26T11:05:00Z",

  "predictions": [
    {
      "date": "2026-04-10",
      "predicted_price": 595.0,
      "confidence_80": [545.0, 645.0],
      "confidence_95": [505.0, 685.0],
      "factors": ["pessach +18%", "weekend +10%", "high_demand +12%"]
    },
    {
      "date": "2026-04-11",
      "predicted_price": 610.0,
      "confidence_80": [558.0, 662.0],
      "confidence_95": [518.0, 702.0],
      "factors": ["pessach +18%", "high_demand +12%", "beach_weather +5%"]
    }
  ],

  "market_context": {
    "competitor_avg": 610.0,
    "seasonal_index": 1.22,
    "occupancy_forecast": 0.82,
    "demand_trend": "rising"
  }
}
```

### 4.5 תשובה: דוח יומי (response ל-3.5)

```json
{
  "report_date": "2026-02-26",

  "performance_yesterday": {
    "rooms_sold": 6,
    "revenue_usd": 4200.0,
    "avg_margin_pct": 32.5,
    "rooms_bought": 3,
    "rooms_cancelled": 1
  },

  "predictions_accuracy": {
    "predictions_made": 156,
    "mape_7d": 8.5,
    "mape_30d": 9.1,
    "recommendations_given": 45,
    "recommendations_followed": 32,
    "outcome_when_followed": {
      "avg_margin": 38.2,
      "success_rate": 0.78
    },
    "outcome_when_ignored": {
      "avg_margin": 24.1,
      "success_rate": 0.61
    }
  },

  "top_recommendations_today": [
    {
      "type": "opportunity",
      "hotel": "Dan Panorama Tel Aviv",
      "dates": "2026-04-10–12",
      "potential_margin": 63.2,
      "confidence": 0.81
    },
    {
      "type": "reprice",
      "hotel": "Royal Beach Eilat",
      "pre_book_id": 8756,
      "current_price": 720.0,
      "suggested_price": 615.0,
      "reason": "overpriced vs market by 22%"
    },
    {
      "type": "cancel_warning",
      "hotel": "Isrotel Dead Sea",
      "pre_book_id": 9012,
      "cancel_deadline": "2026-02-28",
      "sell_probability": 0.22
    }
  ],

  "market_trends": {
    "tel_aviv": {"trend": "rising", "avg_price_change_7d": "+4.2%"},
    "jerusalem": {"trend": "stable", "avg_price_change_7d": "+0.8%"},
    "eilat": {"trend": "falling", "avg_price_change_7d": "-3.1%"},
    "dead_sea": {"trend": "rising", "avg_price_change_7d": "+2.5%"}
  }
}
```

---

## 5. איך המערכת מנתחת את המידע

### 5.1 Pipeline — מקבלת שאלה עד שמחזירה תשובה

```
שאלה נכנסת (API request)
    │
    ▼
┌──────────────────────────────────────────────────┐
│ STEP 1: אסוף נתונים רלוונטיים                    │
│                                                  │
│ FROM medici-db:                                  │
│   • היסטוריית מחירים של המלון (MED_Book)         │
│   • הזדמנויות קודמות (BackOfficeOPT)             │
│   • הזמנות אחרונות (Med_Reservations)            │
│   • מלאי פעיל (MED_Book WHERE IsActive=1)        │
│                                                  │
│ FROM external sources (cached):                   │
│   • מזג אוויר ל-30 יום (Open-Meteo)              │
│   • חגים קרובים (Hebcal)                         │
│   • אירועים באזור (PredictHQ)                    │
│   • מחירי מתחרים (SerpApi)                       │
│   • נתוני תיירות (CBS)                           │
│                                                  │
│ Time: ~2-5 seconds                               │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│ STEP 2: הנדסת Features                           │
│                                                  │
│ EXISTING (40 features):                          │
│   • Calendar: day_of_week, month, is_weekend     │
│   • Lags: price_lag_1/7/14/28                    │
│   • Rolling: mean/std/min/max @ 7/14/30d         │
│   • Holidays: is_holiday, days_to_next           │
│   • Events: event_count, impact_score            │
│   • Weather: temperature, beach_score            │
│   • Hotel: star_rating, is_coastal               │
│   • Seasonality: STL decomposition               │
│                                                  │
│ NEW from trading data (9 features):              │
│   • buy_sell_spread — מרווח קנייה/מכירה          │
│   • inventory_depth — כמה חדרים במלאי            │
│   • sell_through_rate — מהירות מכירה             │
│   • avg_days_to_sell — ימי מכירה ממוצעים         │
│   • cancellation_pressure — לחץ ביטולים          │
│   • booking_velocity — קצב הזמנות               │
│   • price_revision_count — שינויי מחיר          │
│   • supplier_price_gap — פער בין ספקים           │
│   • opportunity_conversion — שיעור המרה          │
│                                                  │
│ Time: ~1-2 seconds                               │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│ STEP 3: הרצת מודלים                              │
│                                                  │
│ A. Price Forecaster (LightGBM default)           │
│    Input: 49 features × time series              │
│    Output: price forecast 30 days + CI           │
│    Time: ~5-8 seconds                            │
│                                                  │
│ B. Occupancy Predictor (Gradient Boosting)       │
│    Input: calendar + holidays + events + weather │
│    Output: occupancy rate + CI                   │
│    Time: ~2-3 seconds                            │
│                                                  │
│ C. Dynamic Pricer (rule-based + ML)              │
│    Input: forecast + occupancy + market           │
│    Adjustments:                                  │
│      Star rating    → ×0.7 to ×2.2              │
│      Occupancy      → -15% to +100%             │
│      Weekend        → +10%                       │
│      Holiday        → +20%                       │
│      Events         → up to +15%                 │
│      Weather        → up to +3%                  │
│      Competitors    → ±5%                        │
│    Output: recommended push price                │
│    Time: ~1 second                               │
│                                                  │
│ Total model inference: ~10-15 seconds            │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│ STEP 4: ייצור המלצה                              │
│                                                  │
│ Compare:                                         │
│   fair_value vs buy_price → margin               │
│   push_price vs market → competitiveness         │
│   occupancy vs threshold → demand                │
│   cancel_deadline vs today → urgency             │
│   sell_probability vs threshold → risk           │
│                                                  │
│ Generate recommendation:                         │
│   BUY / PASS / HOLD / REPRICE / CONSIDER_CANCEL  │
│   + confidence score (0-1)                       │
│   + human-readable reasoning                     │
│   + supporting data                              │
│                                                  │
│ Time: ~1 second                                  │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│ STEP 5: שמירה והחזרה                             │
│                                                  │
│ 1. שמור בprediction-db:                          │
│    • ההמלצה + נתוני הניתוח                        │
│    • (לצורך audit trail + feedback loop)          │
│                                                  │
│ 2. החזר response ל-caller                        │
│                                                  │
│ Total end-to-end: 15-25 seconds                  │
└──────────────────────────────────────────────────┘
```

### 5.2 ניתוח מחזורי (Background Analysis)

בנוסף לתשובות on-demand, המערכת מריצה ניתוח מחזורי באופן עצמאי:

```
┌─────────────────────────────────────────────────────┐
│ SCHEDULED ANALYSIS (runs independently)             │
│                                                     │
│ Every 30 minutes:                                   │
│   • סרוק את כל MED_Book WHERE IsActive=1           │
│   • הרץ ניתוח על כל חדר                             │
│   • עדכן טבלת recommendations ב-prediction-db       │
│   • אם זוהתה המלצה דחופה → הוסף ל-alerts            │
│                                                     │
│ Every hour:                                         │
│   • סרוק מחירי ספקים (via Innstant/GoGlobal cache)  │
│   • זהה הזדמנויות קנייה חדשות                       │
│   • עדכן טבלת opportunities ב-prediction-db         │
│                                                     │
│ Every 6 hours:                                      │
│   • עדכן נתוני מזג אוויר                            │
│   • עדכן אירועים                                    │
│   • חשב מחדש seasonal indices                       │
│                                                     │
│ Daily:                                              │
│   • ייצר דוח יומי                                   │
│   • חשב דיוק חיזויים (MAPE)                         │
│   • בדוק אם צריך retrain                            │
│   • Import מלא של נתוני medici-db                    │
│                                                     │
│ כל התוצאות נשמרות ב-prediction-db וזמינות            │
│ דרך GET /api/v1/recommendations/active              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**מערכת המסחר לא צריכה לחכות לניתוח** — היא יכולה תמיד לקרוא ל-`/recommendations/active` ולקבל את ההמלצות העדכניות ביותר שחושבו ברקע.

---

## 6. סוגי המלצות

```
┌──────────────────────────────────────────────────────────────────┐
│                        RECOMMENDATION TYPES                      │
│                                                                  │
│  כל המלצה היא מידע בלבד — ההחלטה תמיד בידי מערכת המסחר         │
│                                                                  │
├──────────┬───────────────────────────────────────────────────────┤
│          │                                                       │
│  BUY     │  "כדאי לקנות"                                        │
│          │                                                       │
│          │  When: fair_value > buy_price × 1.15                  │
│          │    AND occupancy_forecast > 0.60                      │
│          │    AND free_cancellation = true                       │
│          │    AND confidence > 0.60                              │
│          │                                                       │
│          │  Returns: recommended source, buy price,              │
│          │           suggested push price, expected margin       │
│          │                                                       │
├──────────┼───────────────────────────────────────────────────────┤
│          │                                                       │
│  PASS    │  "לא כדאי לקנות"                                     │
│          │                                                       │
│          │  When: expected_margin < 15%                          │
│          │    OR sell_probability < 0.40                         │
│          │    OR market_trend = "falling"                        │
│          │                                                       │
│          │  Returns: why not, what would change the answer       │
│          │                                                       │
├──────────┼───────────────────────────────────────────────────────┤
│          │                                                       │
│  HOLD    │  "אל תשנה כלום — המצב טוב"                           │
│          │                                                       │
│          │  When: push_price within ±10% of fair_value           │
│          │    AND no urgent deadlines                            │
│          │    AND stable market                                  │
│          │                                                       │
├──────────┼───────────────────────────────────────────────────────┤
│          │                                                       │
│  REPRICE │  "שקול לשנות מחיר"                                    │
│          │                                                       │
│          │  REPRICE_UP: push_price < fair_value × 0.90          │
│          │    → "אפשר להעלות מחיר, ביקוש תומך"                  │
│          │                                                       │
│          │  REPRICE_DOWN: push_price > fair_value × 1.15        │
│          │    → "מחיר גבוה מדי ביחס לשוק"                       │
│          │                                                       │
│          │  Returns: suggested new price, expected impact        │
│          │                                                       │
├──────────┼───────────────────────────────────────────────────────┤
│          │                                                       │
│  CONSIDER│  "שקול ביטול"                                         │
│  _CANCEL │                                                       │
│          │  When: market_price < buy_price                       │
│          │    AND sell_probability < 0.30                        │
│          │    AND cancel_deadline approaching (< 5 days)         │
│          │                                                       │
│          │  Returns: expected loss if hold, cancel deadline,     │
│          │           probability of recovery                     │
│          │                                                       │
├──────────┼───────────────────────────────────────────────────────┤
│          │                                                       │
│  ALERT   │  "שים לב — משהו השתנה"                               │
│          │                                                       │
│          │  When: price moved > 15% in 24h                       │
│          │    OR new holiday/event detected                      │
│          │    OR model confidence dropped significantly          │
│          │    OR competitor changed pricing strategy              │
│          │                                                       │
│          │  Returns: what changed, potential impact               │
│          │                                                       │
└──────────┴───────────────────────────────────────────────────────┘
```

**שוב — כל אלו המלצות בלבד.** ה-`BUY` לא קונה. ה-`CONSIDER_CANCEL` לא מבטל. מערכת המסחר מקבלת את המידע ומחליטה מה לעשות.

---

## 7. מודל הנתונים

### 7.1 מיפוי ישויות

```
MEDICI HOTELS (medici-db)              PREDICTION (prediction-db)
══════════════════════════             ═══════════════════════════

Med_Hotels.HotelId           ←→       hotel_id
Med_Hotels.Name              →        hotel_name (cached)
Med_Board.ID (1-7)           ←→       board_id
Med_RoomCategories.Id        ←→       category_id
MED_Book.PreBookId           ←→       booking_reference
MED_Book.BuyPrice            →        acquisition_cost
MED_Book.Price               →        current_push_price
BackOfficeOPT.id             ←→       opportunity_reference
```

### 7.2 טבלאות prediction-db (של מערכת החיזוי)

```
prediction_recommendations    ← כל המלצה שיוצרת
├── id (PK)
├── timestamp
├── type (BUY/PASS/HOLD/REPRICE/CONSIDER_CANCEL/ALERT)
├── hotel_id (FK → Med_Hotels)
├── booking_reference (FK → MED_Book.PreBookId, nullable)
├── opportunity_reference (nullable)
├── confidence
├── reasoning (JSON)
├── price_data (JSON)
├── risk_data (JSON)
├── status (active/expired/superseded)
└── outcome (null → filled later by feedback loop)

prediction_forecasts          ← כל חיזוי מחיר
├── id (PK)
├── timestamp
├── hotel_id
├── date_from / date_to
├── category_id / board_id
├── predicted_price
├── confidence_80_low / confidence_80_high
├── confidence_95_low / confidence_95_high
├── model_version
└── features_snapshot (JSON)

prediction_outcomes           ← feedback — מה באמת קרה
├── id (PK)
├── recommendation_id (FK)
├── was_followed (bool)
├── actual_outcome (sold/cancelled/expired)
├── actual_sell_price (nullable)
├── actual_sell_date (nullable)
├── prediction_error_pct
└── notes

prediction_model_metrics      ← דיוק המודל לאורך זמן
├── id (PK)
├── date
├── model_version
├── mape_7d / mape_30d
├── total_predictions
├── recommendations_given
├── recommendations_followed
├── success_rate
└── avg_margin_when_followed
```

### 7.3 Features חדשים מנתוני המסחר

| Feature | חישוב | מקור |
|---------|--------|------|
| `buy_sell_spread` | (PushPrice - BuyPrice) / BuyPrice | MED_Book |
| `inventory_depth` | COUNT(active rooms) per hotel per date | MED_Book |
| `sell_through_rate` | sold / (sold + active) rolling 7d | MED_Book |
| `avg_days_to_sell` | AVG(sold_date - created) per hotel | MED_Book |
| `cancellation_pressure` | rooms with deadline < 7d / total active | MED_Book |
| `booking_velocity` | COUNT(reservations) per day per hotel | Med_Reservations |
| `price_revision_count` | times Price != LastPrice per room | MED_Book |
| `supplier_price_gap` | Innstant_price - GoGlobal_price | Search results |
| `opportunity_conversion` | bought / total opportunities per hotel | BackOfficeOPT |

---

## 8. ארכיטקטורת תקשורת

### 8.1 תרשים

```
┌────────────────────────────────────────────────────────────────┐
│                      AZURE                                     │
│                                                                │
│  ┌────────────────────┐         ┌───────────────────────────┐  │
│  │ MEDICI HOTELS      │         │ PREDICTION ENGINE         │  │
│  │ (.NET App Service)  │         │ (Python App Service)      │  │
│  │                    │         │                           │  │
│  │                    │  HTTP   │ ┌───────────────────┐     │  │
│  │  WebJob/Dashboard ─┼────────►│ │ FastAPI           │     │  │
│  │  "מה אתה חושב?"   │  POST   │ │ /api/v1/analyze   │     │  │
│  │                    │         │ │ /api/v1/forecast   │     │  │
│  │                    │◄────────┼─│ /api/v1/portfolio  │     │  │
│  │ מקבל JSON response │  JSON   │ │ /api/v1/report    │     │  │
│  │                    │         │ │ /api/v1/recommend  │     │  │
│  │                    │         │ └──────────┬────────┘     │  │
│  └──────────┬─────────┘         │            │              │  │
│             │                   │  ┌─────────▼──────────┐   │  │
│             │                   │  │ Analysis Engine     │   │  │
│             │                   │  │ • Feature Engine    │   │  │
│             │                   │  │ • Price Forecaster  │   │  │
│             │                   │  │ • Occupancy Model   │   │  │
│             │                   │  │ • Dynamic Pricer    │   │  │
│             │                   │  │ • Analytics Suite   │   │  │
│             │                   │  └─────────┬──────────┘   │  │
│             │                   │            │              │  │
│             │                   └────────────┼──────────────┘  │
│             │                                │                 │
│             │   ┌────────────────────────┐    │                 │
│             └──►│    AZURE SQL SERVER     │◄──┘                 │
│                 │                        │                     │
│                 │  medici-db             │  ← R/W by Hotels    │
│                 │  (Hotels, Books,       │  ← READ ONLY by     │
│                 │   Opportunities,       │    Prediction       │
│                 │   Reservations)        │                     │
│                 │                        │                     │
│                 │  prediction-db         │  ← R/W by Predict   │
│                 │  (recommendations,     │  ← READ by Hotels   │
│                 │   forecasts,           │    (optional)       │
│                 │   outcomes, metrics)   │                     │
│                 └────────────────────────┘                     │
│                                                                │
│                 ┌────────────────────────┐                     │
│                 │ EXTERNAL DATA SOURCES  │                     │
│                 │ (Weather, Holidays,    │ ← Prediction only   │
│                 │  Events, Competitors,  │                     │
│                 │  CBS Tourism Stats)    │                     │
│                 └────────────────────────┘                     │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 8.2 פרוטוקולי תקשורת

| ערוץ | כיוון | פרוטוקול | מתי | הערה |
|------|--------|----------|------|------|
| **Hotels → Prediction API** | שאלה | HTTP POST/GET | on-demand | Hotels שואלת, Prediction עונה |
| **Prediction → medici-db** | קריאת נתונים | SQLAlchemy (read-only) | כל 5-30 דקות | גישה ישירה ל-DB |
| **Prediction → prediction-db** | כתיבה/קריאה | SQLAlchemy (full) | כל הזמן | DB עצמאי של המערכת |
| **Hotels → prediction-db** | קריאה (optional) | Direct SQL / API | on-demand | Dashboard קורא המלצות |

### 8.3 Authentication

| ערוץ | שיטה |
|------|-------|
| Hotels → Prediction API | API Key ב-header: `X-API-Key: <shared-secret>` |
| Prediction → medici-db | Azure SQL read-only user: `prediction_readonly` |
| Prediction → prediction-db | Azure SQL full access: `prediction_admin` |

### 8.4 מה לא קיים (ולא צריך לקיום)

- **אין** WebSocket/SignalR מ-Prediction ל-Hotels — המערכת לא "דוחפת" פעולות
- **אין** write access ל-medici-db — המערכת לא משנה כלום
- **אין** ביצוע פעולות — לא קנייה, לא מכירה, לא ביטול, לא שינוי מחיר
- **אין** תקשורת ישירה עם Innstant/GoGlobal/Zenith — רק דרך הנתונים ב-DB

---

## 9. Feedback Loop — למידה מתוצאות

### 9.1 איך המערכת לומדת אם היא צדקה

```
┌─────────────────────────────────────────────────────────┐
│                   FEEDBACK CYCLE                         │
│                                                         │
│  T=0: המערכת נותנת המלצה                                │
│    recommendation = BUY, confidence = 0.85               │
│    predicted_sell_price = $620                           │
│    stored in: prediction_recommendations                │
│                                                         │
│  T+X: מערכת המסחר מחליטה (ללא מעורבות שלנו)            │
│    action_taken = bought at $395                         │
│    push_price_set = $620                                │
│                                                         │
│  T+Y: התוצאה מתבררת (from medici-db)                    │
│    outcome = sold at $598                               │
│    actual_margin = 51.4%                                │
│    prediction_error = -3.7%                             │
│    stored in: prediction_outcomes                       │
│                                                         │
│  Daily: מערכת החיזוי קוראת את medici-db                  │
│    → מוצאת bookings שנמכרו / בוטלו / פגו               │
│    → משווה לחיזוי המקורי                                │
│    → מעדכנת prediction_outcomes                         │
│    → מחשבת accuracy metrics                             │
│    → אם MAPE > 12% ל-7 ימים → flag for retrain         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 9.2 מטריקות ביצוע שהמערכת עוקבת אחריהן

| מטריקה | תיאור | Target |
|--------|--------|--------|
| **MAPE** | Mean Absolute Percentage Error של חיזוי מחיר | < 10% |
| **Signal Accuracy** | % המלצות BUY שהובילו למכירה רווחית | > 70% |
| **Margin Lift** | מרווח ממוצע כש-following recommendations vs לא | > +10pp |
| **CANCEL Saves** | כמה הפסדים נמנעו ע"י CONSIDER_CANCEL | track |
| **Confidence Calibration** | ב-80% CI, 80% מהתוצאות באמת בטווח | ~80% |

---

## 10. שאלות פתוחות

| # | שאלה | למה חשוב |
|---|-------|---------|
| 1 | **מי צורך את ההמלצות?** WebJob אוטומטי? Dashboard אנושי? שניהם? | משפיע על UI/UX של ה-response |
| 2 | **היקף אוטומציה:** האם ה-BuyRooms WebJob ישתמש ב-API שלנו אוטומטית, או שמפעיל אנושי מסתכל על ההמלצות? | משפיע על latency requirements ו-confidence thresholds |
| 3 | **כמה חודשי data היסטורי** יש ב-medici-db? | מינימום 6 חודשים לאימון סביר |
| 4 | **גישה ל-medici-db:** צריך ליצור read-only user? יש כבר? | prerequisite טכני |
| 5 | **Deploy:** איפה מריצים את ה-Prediction service? Azure App Service? Container? | ארכיטקטורה |
| 6 | **Budget:** מה ה-budget לשירותי ענן נוספים? | Azure SQL costs, App Service tier |
| 7 | **Stored Procedures:** יש ~90 SPs — האם אפשר לקרוא אותם? יש SPs שמחזירים נתונים שימושיים? | אולי יש aggregated views שכבר קיימים |
| 8 | **SLA:** מה קורה אם המערכת לא זמינה? מה acceptable downtime? | redundancy planning |

---

## סיכום

```
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║  Prediction Engine = מערכת ייעוץ עצמאית                    ║
║                                                            ║
║  IN:  קוראת מ-medici-db (read-only)                       ║
║       + מקורות חיצוניים (מזג אוויר, חגים, מתחרים)         ║
║       + שאלות מ-API (מערכת המסחר שואלת)                    ║
║                                                            ║
║  PROCESS: 49 features → ML models → analysis               ║
║                                                            ║
║  OUT: המלצות (BUY/PASS/HOLD/REPRICE/CONSIDER_CANCEL)      ║
║       + חיזויי מחיר עם רווחי ביטחון                        ║
║       + ניתוח תיק                                         ║
║       + דוחות יומיים                                       ║
║       + מטריקות דיוק                                       ║
║                                                            ║
║  NOT: לא קונה. לא מוכרת. לא מבטלת. לא משנה מחירים.       ║
║       לא מבצעת שום פעולה. מוח בלבד.                        ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```
