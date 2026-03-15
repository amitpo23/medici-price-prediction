# 🎯 איך לגשת למערכת Sales Room

## ✅ המערכת רצה!

### 🌐 כתובות:
- **Frontend (Angular):** http://localhost:4200
- **Backend (Node.js):** http://localhost:8080
- **Sales Room:** http://localhost:4200/sales-room

---

## 📍 איפה למצוא את Sales Room?

### דרך 1: ניווט בתפריט
1. פתח את האפליקציה: http://localhost:4200
2. לחץ על **"Rooms"** בתפריט הצד (השורה עם אייקון מיטה 🛏️)
3. התפריט יתרחב ותראה:
   - ✅ Active
   - ❌ Cancelled
   - 💰 **Sales** ← לחץ כאן!

### דרך 2: גישה ישירה
פשוט פתח את הכתובת:
```
http://localhost:4200/sales-room
```

---

## 🖥️ מה תראה במערכת?

```
┌─────────────────────────────────────────────────────┐
│ Sales Room                                    🔄 ⚙️ │
├─────────────────────────────────────────────────────┤
│ 🔍 Search hotel...                      [Clear] 🔄  │
├─────────────────────────────────────────────────────┤
│ Sold Id │ Hotel Name │ Start Date │ Price │ ...    │
│─────────┼────────────┼────────────┼───────┼────────│
│   123   │ Hotel ABC  │ 2026-01-20 │ €250  │ [Edit] │
│   124   │ Hotel XYZ  │ 2026-01-22 │ €180  │ [Edit] │
└─────────────────────────────────────────────────────┘
```

**תכונות:**
- 📊 טבלה מתקדמת עם AG Grid
- 🔍 חיפוש מלונות
- 📤 ייצוא לExcel
- 🔄 רענון נתונים
- ✏️ עריכת מכירות
- 🔢 Pagination (10/50/100/500)

---

## 🚀 הפעלת המערכת

### Backend (כבר רץ):
```powershell
cd "c:\Users\97250\Desktop\booking engine\medici_web03012026\medici-backend-node"
$env:PORT=8080
node server.js
```

### Frontend (כבר רץ):
```powershell
cd "c:\Users\97250\Desktop\booking engine\medici_web03012026"
npx ng serve --port 4200 --open
```

---

## 🔍 בדיקה מהירה

### 1. בדוק ש-Backend רץ:
```powershell
Invoke-RestMethod "http://localhost:8080/SalesRoom/Sales"
```

### 2. פתח את הדפדפן:
```
http://localhost:4200/sales-room
```

### 3. אם יש שגיאה:
- בדוק שה-Backend רץ על 8080
- בדוק שה-Frontend רץ על 4200
- בדוק את ה-Console בדפדפן (F12)

---

## 📱 מבנה התפריט המלא:

```
📊 Dashboard
🏨 Hotels
🛏️ Rooms
   ├── ✅ Active
   ├── ❌ Cancelled
   └── 💰 Sales       ← כאן!
📖 Reservations
🔍 Search & Price
⚙️ Options
📈 Analytics
🤖 AI Prediction
```

---

## ✅ בדיקה שהמערכת עובדת:

1. **התפריט מופיע?** ✓
   - לחץ על "Rooms" → אמור לראות "Sales"

2. **הנתיב עובד?** ✓
   - נווט ל: `/sales-room`

3. **הנתונים נטענים?** ✓
   - אמורים להופיע שורות בטבלה

4. **החיפוש עובד?** ✓
   - הקלד שם מלון בחיפוש

---

## 🎉 זהו!

המערכת רצה ב:
- ✅ http://localhost:4200/sales-room

**תהנה!** 🚀

