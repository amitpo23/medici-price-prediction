# מדריך שימוש מהיר – SalesOffice Price Drop Skill

## מה הכלי עושה
הכלי מנתח לוגים של `SalesOffice.Log` ומוציא:
- כמה שינויים היו במחיר
- כמה מהם היו ירידות מחיר
- איפה בדיוק הייתה ירידה (מלון/קטגוריה/Board)
- כמה ירידות היו בכל חלון סריקה (ברירת מחדל: 10 דקות)
- מה המחיר הכי נמוך שנצפה
- הערכת הסתברות לירידת מחיר בסריקה הבאה

## התקנה
```powershell
cd skills/salesoffice-price-drop-skill
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## הרצה עם חיבור ישיר ל-DB
```powershell
python analyzer.py --connection-string "Driver={ODBC Driver 18 for SQL Server};Server=<SERVER>;Database=<DB>;Uid=<USER>;Pwd=<PASS>;TrustServerCertificate=yes" --scan-minutes 10 --out report
```

## הרצה עם CSV
```powershell
python analyzer.py --input-csv price_changes.csv --scan-minutes 10 --out report
```

## קבצי פלט
- `report/price_drop_events.csv` – כל אירועי ירידת מחיר
- `report/price_drop_by_scan.csv` – סיכום לפי חלון סריקה
- `report/price_drop_by_hotel.csv` – סיכום לפי מלון/קטגוריה/board
- `report/summary.json` – תקציר כללי + הסתברות ירידה בסריקה הבאה

## שאילתות SQL מוכנות
- `queries/01_extract_price_changes.sql`
- `queries/02_price_drop_summary.sql`
- `queries/03_price_drop_by_scan.sql`

## הערות חשובות
- זיהוי מחיר מבוסס על פורמט הודעה מהקוד:  
  `DbRoomPrice: X -> API RoomPrice: Y`
- ActionIds מרכזיים:
  - `3` = Detail Updated
  - `6` = Zenith Push - Update Rate
- אם פורמט ההודעה ישתנה, צריך לעדכן את regex בקובץ `analyzer.py`.

