# Lessons Learned

## Testing
- NEVER use mocks — all tests must use real objects
- Run py_compile before committing any Python file

## Noovy/Hotel.Tools
- Medici channel in HT Marketplace must be green (Connected) for Innstant to work
- Products need: Type=Room, Currency=USD, BasePrice>0, Quantity>=1
- Rate Plans need: Currency=USD, Products assigned
- Availability must be set explicitly via Bulk Update per date
- Noovy→Innstant sync takes 1-4 hours, not instant
- venue IDs are shared between Noovy and HT (same system)

## Innstant B2B
- Login: Account=Knowaa, Agent=Amit, Password=porat10 (NOT karpad66)
- Password field is readonly — must click first to remove readonly
- Search by city: Miami Beach = city-416633, Miami FL = city-3927
- Provider filter: Knowaa_Global_zenith shows our hotels

## Architecture
- Never write to medici-db — read-only enforced
- Decision Brain only — never execute trades or change prices
- Every AI feature needs rule-based fallback (no hard Claude dependency)

## Communication
- User communicates in Hebrew, code/docs in English
- FULL AUTONOMY — never ask for permission on any action
- Don't summarize what you just did — user can read the diff
