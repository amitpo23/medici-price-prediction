# 🏨 Medici Hotels - Professional Dashboard

## 📖 סקירה כללית

מערכת ניהול מלונות מקצועית עם דשבורדים אינטראקטיביים, תרשימים מתקדמים ותמיכה מלאה ב-Dark Mode.

## ✨ תכונות עיקריות

### 🎨 עיצוב מודרני
- **Material Design 3** - עיצוב עדכני ומקצועי
- **Tailwind CSS** - סטיילינג מהיר וגמיש
- **Dark Mode** - תמיכה מלאה במצב כהה/בהיר
- **אנימציות** - מעברים חלקים ואפקטים ויזואליים

### 📊 דשבורדים מתקדמים
- **KPI Cards** - כרטיסי מדדים עם אנימציות וגרדיאנטים
- **Revenue Charts** - תרשימי הכנסות אינטראקטיביים
- **Occupancy Trends** - מגמות תפוסה
- **Top Hotels** - מלונות מובילים ברווחיות

### 📱 Responsive Design
- תמיכה מלאה במובייל, טאבלט ודסקטופ
- Grid Layout אדפטיבי
- תפריטים נגישים

## 🚀 התקנה והרצה מקומית

### דרישות מקדימות
```bash
Node.js >= 16.x
npm >= 8.x
Angular CLI 16.x
```

### התקנת תלויות
```bash
npm install --legacy-peer-deps
```

### הרצה במצב Development
```bash
npm run dev
```

הפרויקט יפתח בכתובת: `http://localhost:4200`

### בניית הפרויקט
```bash
npm run build
```

## 🌐 Deployment ל-Vercel

### שיטה 1: שימוש בסקריפט האוטומטי

```bash
# הפיכת הסקריפט לקובץ הרצה
chmod +x deploy-vercel.sh

# הרצת הסקריפט
./deploy-vercel.sh
```

הסקריפט יבצע:
1. ✅ בדיקת Vercel CLI
2. ✅ התקנת תלויות
3. ✅ בנייה לייצור
4. ✅ העלאה ל-Vercel

### שיטה 2: Deployment ידני

#### שלב 1: התקן Vercel CLI
```bash
npm install -g vercel
```

#### שלב 2: התחבר ל-Vercel
```bash
vercel login
```

#### שלב 3: Deploy Preview
```bash
vercel
```

#### שלב 4: Deploy Production
```bash
vercel --prod
```

### הגדרות Environment Variables ב-Vercel

לאחר ה-Deploy, הגדר במסך ה-Dashboard של Vercel:

```env
PRODUCTION_API_URL=https://your-backend-url.vercel.app
NODE_ENV=production
```

## 📦 מבנה הפרויקט

```
medici_web03012026/
├── src/
│   ├── app/
│   │   ├── modules/
│   │   │   ├── dashboard/          # דשבורד ראשי
│   │   │   │   ├── components/
│   │   │   │   │   ├── kpi-cards/
│   │   │   │   │   ├── revenue-chart/
│   │   │   │   │   ├── occupancy-trend/
│   │   │   │   │   └── top-hotels/
│   │   │   ├── analytics/          # אנליטיקס
│   │   │   ├── hotels/             # ניהול מלונות
│   │   │   └── ...
│   │   ├── services/
│   │   │   ├── theme.service.ts    # שירות ערכות נושא
│   │   │   └── ...
│   │   └── core/
│   ├── assets/
│   └── styles.scss                 # סגנונות גלובליים
├── vercel.json                     # הגדרות Vercel
├── deploy-vercel.sh               # סקריפט deployment
└── package.json
```

## 🎨 תכונות UI מתקדמות

### KPI Cards
- אנימציות fadeIn ו-slideUp
- גרדיאנטים צבעוניים
- אינדיקטורים לשינויים (↑↓)
- Hover effects מתקדמים

### Charts
- תמיכה ב-Line ו-Bar charts
- בחירת תקופות (3/6/12 חודשים)
- Tooltips אינטראקטיביים
- סטטיסטיקות מסכמות

### Dark Mode
- מעבר חלק בין ערכות נושא
- שמירת העדפות ב-LocalStorage
- תמיכה ב-system preferences
- עיצוב מותאם לכל רכיב

## 🛠️ טכנולוגיות

- **Angular 16** - Framework
- **Angular Material** - UI Components
- **Tailwind CSS** - Utility-first CSS
- **Chart.js** - תרשימים
- **RxJS** - Reactive Programming
- **TypeScript** - Type Safety

## 📱 Browser Support

- Chrome (Latest)
- Firefox (Latest)
- Safari (Latest)
- Edge (Latest)

## 🔧 Scripts זמינים

```bash
npm start           # הרצה במצב development
npm run dev         # הרצה עם proxy
npm run build       # בנייה לייצור
npm run vercel-build # בנייה עבור Vercel
npm test            # הרצת טסטים
```

## 🐛 פתרון בעיות

### Build Errors
אם יש שגיאות בבנייה:
```bash
# נקה node_modules וnpm cache
rm -rf node_modules package-lock.json
npm cache clean --force
npm install --legacy-peer-deps
```

### Vercel Deployment Issues
1. ודא ש-`vercel-build` script מוגדר ב-package.json
2. בדוק ש-`distDir` ב-vercel.json מצביע לתיקייה הנכונה
3. ודא שאין שגיאות TypeScript

### Dark Mode לא עובד
1. בדוק ש-ThemeService מוזרק נכון
2. ודא שהסגנונות הגלובליים נטענים
3. נקה LocalStorage ונסה שוב

## 📄 License

This project is private and proprietary.

## 👥 Contact

For support or questions, please contact the development team.

---

Made with ❤️ by Medici Hotels Development Team

