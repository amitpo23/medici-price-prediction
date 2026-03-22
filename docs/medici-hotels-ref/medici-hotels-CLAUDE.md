# medici hotels — Agent Instructions

## Shared Knowledge Base
Cross-project knowledge is available at `.knowledge/` (symlink to `/Users/mymac/Desktop/coding/ceo/knowledge/`).
- `.knowledge/apis/` — API catalogs for all Medici systems
- `.knowledge/shared/connections.md` — How projects connect to each other
- `.knowledge/projects/` — Status and profiles of sibling projects

## Daily Dev Log
At the end of each work session, run `./dev-log.sh` to log what was done today.
This creates a `.dev-logs/YYYY-MM-DD.md` file, commits and pushes it.
A central collector agent aggregates all logs across machines and projects.
