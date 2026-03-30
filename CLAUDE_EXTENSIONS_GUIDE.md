# Claude Code Extensions — Medici Price Prediction

## מה הותקן

חמישה ריפואים פתוחים שולבו בפרויקט תחת `.claude/`:

| # | Repo | Stars | מה נלקח |
|---|------|-------|---------|
| 1 | [Everything Claude Code](https://github.com/affaan-m/everything-claude-code) | ~108K ⭐ | 10 agents, 6 commands |
| 2 | [Awesome Claude Code](https://github.com/hesreallyhim/awesome-claude-code) | ~33.7K ⭐ | Reference & index |
| 3 | [Ruflo](https://github.com/ruvnet/ruflo) | ~28K ⭐ | 5 YAML agent definitions |
| 4 | [Claude Code MCP](https://github.com/steipete/claude-code-mcp) | ~1.2K ⭐ | MCP server (built & ready) |
| 5 | [Awesome Claude Code Toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit) | ~936 ⭐ | 10 agents, 8 skills, 15 rules, hooks |

---

## מבנה התיקיות

```
.claude/
├── agents/          ← 25 סוכני משנה מתמחים
│   ├── architect.md          # ארכיטקט מערכת
│   ├── python-reviewer.md    # Code review ל-Python
│   ├── code-reviewer.md      # Code review כללי
│   ├── security-reviewer.md  # סקירת אבטחה
│   ├── performance-optimizer.md  # אופטימיזציית ביצועים
│   ├── planner.md            # תכנון פיצ'רים
│   ├── tdd-guide.md          # מדריך TDD
│   ├── database-reviewer.md  # סקירת DB
│   ├── doc-updater.md        # עדכון תיעוד
│   ├── refactor-cleaner.md   # ריפקטורינג
│   ├── data-engineer.md      # הנדסת נתונים
│   ├── data-scientist.md     # Data Science
│   ├── ml-engineer.md        # ML Engineering
│   ├── llm-architect.md      # ארכיטקטורת LLM
│   ├── feature-engineer.md   # Feature Engineering
│   ├── multi-agent-coordinator.md  # תיאום רב-סוכני
│   ├── task-coordinator.md   # תיאום משימות
│   ├── workflow-director.md  # ניהול Workflow
│   ├── backend-developer.md  # Backend dev
│   ├── api-designer.md       # עיצוב API
│   ├── architect.yaml        # Ruflo architect
│   ├── coder.yaml            # Ruflo coder
│   ├── reviewer.yaml         # Ruflo reviewer
│   ├── security-architect.yaml # Ruflo security
│   └── tester.yaml           # Ruflo tester
│
├── commands/        ← 6 פקודות slash
│   ├── code-review.md   # /code-review
│   ├── build-fix.md     # /build-fix
│   ├── checkpoint.md    # /checkpoint
│   ├── docs.md          # /docs
│   ├── eval.md          # /eval
│   └── learn.md         # /learn
│
├── skills/          ← 8 מיומנויות מתמחות
│   ├── api-design-patterns/
│   ├── ci-cd-pipelines/
│   ├── data-engineering/
│   ├── database-optimization/
│   ├── llm-integration/
│   ├── monitoring-observability/
│   ├── python-best-practices/
│   └── security-hardening/
│
├── rules/           ← 15 כללי קוד
│   ├── coding-style.md
│   ├── error-handling.md
│   ├── security.md
│   ├── testing.md
│   ├── performance.md
│   └── ... (10 more)
│
├── hooks/           ← אוטומציה
│   ├── hooks.json
│   └── scripts/
│
└── mcp-configs/     ← תצורות MCP
    └── (ready for claude-code-mcp)
```

---

## איך להשתמש — מה להגיד ל-Claude Code

### סוכני משנה (Agents)

```bash
# הפעלת סוכן ספציפי
claude "use the @architect agent to review the prediction pipeline architecture"
claude "use @python-reviewer to review my last commit"
claude "use @security-reviewer to audit src/api/"
claude "use @performance-optimizer to optimize the forward curve calculation"
claude "use @data-scientist to analyze prediction accuracy trends"
claude "use @ml-engineer to improve the ensemble model"
claude "use @multi-agent-coordinator to plan Sprint TD-1"
```

### פקודות Slash

```bash
# בתוך Claude Code session:
/code-review          # סקירת קוד אוטומטית
/build-fix            # תיקון שגיאות build
/checkpoint           # שמירת מצב נוכחי
/docs                 # עדכון תיעוד
/eval                 # הרצת הערכה
/learn                # למידה מטעויות
```

### Claude Code MCP (סוכן-בתוך-סוכן)

להוסיף ל-`~/.claude/mcp_config.json`:

```json
{
  "mcpServers": {
    "claude-code-mcp": {
      "command": "node",
      "args": ["/path/to/claude-code-mcp/dist/index.js"],
      "env": {
        "CLAUDE_MCP_ALLOWED_PATHS": "/path/to/medici-price-prediction"
      }
    }
  }
}
```

### פרומפטים חזקים למדיצ'י

```
# תכנון ספרינט עם סוכני משנה
"Plan Sprint TD-1 using @architect for design, @planner for task breakdown,
and @python-reviewer to identify which files need the most cleanup"

# סקירת קוד מקיפה
"Run a full code review: use @security-reviewer on src/api/,
@python-reviewer on src/analytics/, and @database-reviewer on src/data/"

# אופטימיזציה
"Use @performance-optimizer to profile the prediction pipeline,
then @data-engineer to suggest data flow improvements"

# ML שיפור
"Use @ml-engineer to evaluate the 50/30/20 ensemble weights,
@feature-engineer to suggest new features from existing data sources,
and @data-scientist to run backtesting analysis"

# Multi-agent workflow
"Use @workflow-director to orchestrate: first @architect reviews the
scenario_engine.py design, then @code-reviewer checks implementation,
then @tdd-guide writes missing tests"
```

---

---

## גל 2 — Superpowers + GSD + LightRAG

| # | Repo | Stars | מה הותקן |
|---|------|-------|---------|
| 6 | [Superpowers](https://github.com/obra/superpowers) | ~42K ⭐ | 12 skills, 1 agent, 3 commands, hooks |
| 7 | [GSD (Get Shit Done)](https://github.com/gsd-build/gsd-2) | ~32K ⭐ | CLI tool (gsd-pi v2.58.0) |
| 8 | [LightRAG](https://github.com/HKUDS/LightRAG) | ~31K ⭐ | Python package (v1.4.13) + config |

### Superpowers Skills (מותקנים ב-.claude/skills/)

```
brainstorming/                  ← סיעור מוחות מובנה לפני כל משימה
writing-plans/                  ← כתיבת תוכניות עבודה מפורטות
executing-plans/                ← ביצוע תוכניות צעד-אחר-צעד
subagent-driven-development/    ← פיתוח מבוסס סוכני משנה
dispatching-parallel-agents/    ← שליחת סוכנים מקבילים
test-driven-development/        ← TDD מובנה
systematic-debugging/           ← דיבאג שיטתי
verification-before-completion/ ← אימות לפני סיום
requesting-code-review/         ← בקשת code review
receiving-code-review/          ← קבלת code review
using-git-worktrees/            ← עבודה עם git worktrees
finishing-a-development-branch/ ← סגירת branch
```

### Superpowers Commands

```bash
/brainstorm       # סיעור מוחות מובנה — תכנון לפני קוד
/write-plan       # כתיבת תוכנית מפורטת עם צעדים
/execute-plan     # הרצת תוכנית עם סוכני משנה
```

### GSD — פקודות CLI

```bash
# התקנה מלאה על המכונה שלך:
npm install -g gsd-pi@latest

# הרצה על פרויקט Medici:
gsd init                    # אתחול פרויקט GSD
gsd plan "Sprint TD-1"     # יצירת תוכנית עבודה
gsd auto                    # הרצה אוטונומית — walk away!
gsd auto --yolo             # ללא אינטראקציה בכלל
gsd status                  # בדיקת מצב
gsd discuss "milestone-1"   # דיון על milestone
```

**איך GSD עובד:**
1. שובר את הפרויקט למשימות קטנות (slices)
2. כל משימה רצה בחלון context נקי של 200K tokens
3. סוכן משנה נפרד לכל משימה
4. ניהול git אוטומטי (branches, commits)
5. זיהוי loops תקועים + recovery אוטומטי

### LightRAG — בניית Knowledge Base

```python
# קונפיגורציה: config/lightrag_config.py
# שימוש בסיסי:

import asyncio
from lightrag import LightRAG, QueryParam

async def setup_medici_rag():
    rag = LightRAG(working_dir="./data/lightrag_store")
    await rag.initialize_storages()

    # הזנת מסמכים
    await rag.ainsert("Art Basel Miami 2026 increases hotel demand by 40%...")
    await rag.ainsert("Forward curve shows upward trend for Q1...")

    # שאילתה חכמה
    result = await rag.aquery(
        "What events drive the highest price increases?",
        param=QueryParam(mode="hybrid")
    )
    return result

asyncio.run(setup_medici_rag())
```

**Query Modes:**
- `local` — חיפוש ממוקד (entity-based)
- `global` — סקירה רחבה (community-based)
- `hybrid` — שילוב local+global (מומלץ)
- `naive` — vector search ישיר
- `mix` — KG + vector (הכי מדויק)

---

## פרומפטים מתקדמים (Superpowers + GSD)

```
# תכנון ספרינט עם Superpowers
/brainstorm "Sprint TD-1: Extract Jinja2 from remaining HTML generators"
/write-plan
/execute-plan

# Subagent-driven development
"Use subagent-driven-development to implement the TD-1 plan.
Dispatch parallel agents for terminal_page.py, alerts_page.py,
and _options_html_gen.py extraction"

# Systematic debugging
"Use systematic-debugging to investigate why forward curve
predictions are off by >5% for weekend dates"

# Verification workflow
"Use verification-before-completion to validate all changes
from Sprint 5.2 before merging to main"

# GSD autonomous mode
gsd plan "Implement data quality scoring improvements"
gsd auto

# LightRAG-powered analysis
"Query the LightRAG knowledge base: which combination of
events and weather patterns produces the highest price signals?"
```

---

## Sources

- [Everything Claude Code](https://github.com/affaan-m/everything-claude-code) — 108K+ ⭐
- [Superpowers](https://github.com/obra/superpowers) — 42K+ ⭐
- [Awesome Claude Code](https://github.com/hesreallyhim/awesome-claude-code) — 33.7K+ ⭐
- [GSD (Get Shit Done)](https://github.com/gsd-build/gsd-2) — 32K+ ⭐
- [LightRAG](https://github.com/HKUDS/LightRAG) — 31K+ ⭐
- [Ruflo](https://github.com/ruvnet/ruflo) — 28K+ ⭐
- [Claude Code MCP](https://github.com/steipete/claude-code-mcp) — 1.2K+ ⭐
- [Awesome Claude Code Toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit) — 936+ ⭐
