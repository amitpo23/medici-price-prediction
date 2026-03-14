import argparse
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def append_entry(memory_path: Path, changed: str, evidence: str, blocker: str, next_step: str) -> None:
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    if not memory_path.exists():
        memory_path.write_text('# MEMORY LOG — Medici Price Prediction\n\n', encoding='utf-8')

    lines = [
        f'## Run Snapshot — {utc_now_iso()}',
        f'- What changed: {changed.strip()}',
        f'- Evidence: {evidence.strip()}',
        f'- Blocker: {blocker.strip()}',
        f'- Next step: {next_step.strip()}',
        '',
    ]

    with memory_path.open('a', encoding='utf-8') as file:
        file.write('\n'.join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description='Append one structured entry to docs/MEMORY_LOG.md')
    parser.add_argument('--changed', required=True, help='What changed in this run/session')
    parser.add_argument('--evidence', required=True, help='Evidence file paths under data/reports/')
    parser.add_argument('--blocker', required=True, help='Current blocker, or "none"')
    parser.add_argument('--next-step', required=True, help='Explicit next action')
    parser.add_argument(
        '--memory-file',
        default='docs/MEMORY_LOG.md',
        help='Path to memory log file (default: docs/MEMORY_LOG.md)',
    )

    args = parser.parse_args()
    append_entry(
        memory_path=Path(args.memory_file),
        changed=args.changed,
        evidence=args.evidence,
        blocker=args.blocker,
        next_step=args.next_step,
    )

    print(f'memory_log_appended {args.memory_file}')


if __name__ == '__main__':
    main()
