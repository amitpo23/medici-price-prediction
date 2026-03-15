# 🤖 MCP Servers Configuration - הגדרות שרתי MCP

פרויקט זה מוגדר עם שרתי MCP (Model Context Protocol) לשיפור יכולות ה-AI.

## 🧠 LSP - הבנה סמנטית (מהיר פי 900!)

### מה זה LSP?
**Language Server Protocol** - פרוטוקול שמאפשר לעורך הקוד "להבין" את הקוד שלך סמנטית, לא רק כטקסט רגיל.

### ההבדל בין חיפוש טקסטואלי ל-LSP

| קריטריון | ללא LSP (grep) | עם LSP |
|----------|---------------|--------|
| **מהירות** | ~45 שניות | ~50 אלפיות השניה |
| **דיוק** | נמוך (מצא שם טקסט) | גבוה (מבין הקשר) |
| **יכולות** | חיפוש בטקסט | Go to Definition, Find References, Rename |

### יכולות LSP בפרויקט

| קיצור | פעולה | תיאור |
|-------|-------|--------|
| `F12` | Go to Definition | קפיצה להגדרה של פונקציה/משתנה |
| `Shift+F12` | Find References | מציאת כל השימושים |
| `F2` | Rename Symbol | שינוי שם בכל הפרויקט |
| `Ctrl+Space` | IntelliSense | השלמה אוטומטית חכמה |
| `Ctrl+Shift+O` | Go to Symbol | ניווט לסימבול בקובץ |
| `Ctrl+T` | Go to Symbol in Workspace | חיפוש סימבול בכל הפרויקט |
| `Alt+F12` | Peek Definition | הצצה להגדרה בחלון קטן |
| `Ctrl+K F12` | Open Definition to Side | פתיחת ההגדרה בצד |

### Inlay Hints (רמזים בקוד)
הפרויקט מוגדר להציג:
- שמות פרמטרים בפונקציות
- סוגי ערכים חוזרים
- סוגי משתנים

---

## שרתי MCP פעילים

### 1. 📚 Context7
**מה עושה:** מחפש דוקומנטציות של ריפוזיטוריז בגיטהאב
**יתרון:** עוזר לסוכני AI לדעת איך מטמיעים כל דבר במקום לנחש
**שימוש:** כאשר צריך להבין איך להשתמש בספריה מסוימת

\`\`\`
# דוגמה - מציאת דוקומנטציה של Angular Material
context7: search angular/components button usage
\`\`\`

---

### 2. 🔍 DeepWiki
**מה עושה:** שואל שאילתות על דוקומנטציות ומבין הקשרים
**יתרון:** מבין קשרים בין קומפוננטות, APIs ופיצ'רים
**שימוש:** כאשר צריך להבין איך חלקים שונים עובדים יחד

\`\`\`
# דוגמה - הבנת ארכיטקטורה
deepwiki: explain how Angular services work with components
\`\`\`

---

### 3. 💻 OctoCode
**מה עושה:** רואה דוגמאות קוד ומבין איך להטמיע דברים
**יתרון:** לומד מדוגמאות אמיתיות בפרויקטים
**שימוש:** כאשר צריך לראות איך אחרים פתרו בעיה דומה

\`\`\`
# דוגמה - מציאת דוגמאות
octocode: find examples of Angular Material table with sorting
\`\`\`

---

### 4. 🔧 Ultracite
**מה עושה:** בודק ומזהה שגיאות lint בפרויקט
**יתרון:** מזהה בעיות קוד לפי חוקי ESLint, TypeScript ועוד
**שימוש:** לבדיקת איכות קוד ותיקון בעיות

\`\`\`bash
# הרצת lint
npm run lint

# בדיקת lint בלבד (בלי תיקון)
npm run lint:check
\`\`\`

---

### 5. 🌐 Chrome DevTools
**מה עושה:** בדיקות מקיפות לאתר
**יכולות:**
- ⚡ **ביצועים** - Lighthouse scores, Web Vitals
- 🔒 **אבטחה** - HTTPS, CSP, vulnerabilities
- 📡 **נטוורק** - API calls, load times, caching
- 🖥️ **קונסול** - errors, warnings, logs
- 🏗️ **DOM** - element inspection, accessibility

\`\`\`
# דוגמה - בדיקת ביצועים
chrome-devtools: run lighthouse on http://localhost:4200

# דוגמה - בדיקת נטוורק
chrome-devtools: monitor network requests on http://localhost:4200
\`\`\`

---

## ⚙️ הגדרת MCPs

קובץ ההגדרות נמצא ב: \`.vscode/mcp.json\`

### דרישות מערכת
- Node.js 18+
- npm/npx
- VS Code עם Copilot Chat

### הפעלת MCPs
1. פתח VS Code
2. ודא שהתוסף GitHub Copilot Chat מותקן
3. ה-MCPs יטענו אוטומטית מתוך \`mcp.json\`

---

## 📋 ESLint Rules

הפרויקט מוגדר עם חוקי ESLint הבאים:

### TypeScript
- \`@typescript-eslint/no-unused-vars\` - אזהרה על משתנים לא בשימוש
- \`@typescript-eslint/no-explicit-any\` - אזהרה על שימוש ב-any
- \`no-console\` - אזהרה על console.log (מותר warn/error)

### Angular
- \`@angular-eslint/component-selector\` - selector חייב להתחיל ב-app
- \`@angular-eslint/directive-selector\` - directive חייב להתחיל ב-app

### Templates (HTML)
- \`@angular-eslint/template/accessibility\` - בדיקות נגישות
- \`@angular-eslint/template/click-events-have-key-events\` - אירועי מקלדת

---

## 🚀 שימוש יומיומי

\`\`\`bash
# הרצת lint ותיקון אוטומטי
npm run lint

# בדיקת lint בלבד
npm run lint:check

# הרצת האפליקציה
npm start

# הרצת הבקאנד
cd medici-backend-node && node server.js
\`\`\`

---

## 📁 קבצי הגדרות

| קובץ | תיאור |
|------|--------|
| \`.vscode/mcp.json\` | הגדרות שרתי MCP |
| `.vscode/settings.json` | הגדרות VS Code + LSP |
| `.vscode/extensions.json` | הרחבות מומלצות |
| `eslint.config.mjs` | חוקי ESLint (פורמט חדש) |
| `tsconfig.json` | הגדרות TypeScript |

---

## 🔌 הרחבות מומלצות

הרחבות שמשפרות את חווית ה-LSP:

| הרחבה | תיאור |
|-------|--------|
| `Angular Language Service` | הבנה סמנטית לתבניות Angular |
| `TypeScript Next` | שרת TypeScript מעודכן |
| `ESLint` | ניתוח סטטי |
| `Prettier` | פורמט קוד |
| `GitLens` | Git insights |
| `Path Intellisense` | השלמת נתיבים |

להתקנת כל ההרחבות:
```bash
# VS Code יציע להתקין אוטומטית מ-extensions.json
```

