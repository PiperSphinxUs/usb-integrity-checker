import json
import socket
import getpass
from datetime import datetime
from pathlib import Path

def _current_actor() -> str:
    try:
        return f'{getpass.getuser()}@{socket.gethostname()}'
    except Exception:
        return 'unknown'

def append_audit_entry(logs_dir: Path, event_type: str, profile_name: str, summary: dict, extra: dict=None) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / 'audit_log.jsonl'
    entry = {'timestamp': datetime.now().isoformat(timespec='seconds'), 'event_type': event_type, 'actor': _current_actor(), 'profile_name': profile_name, 'summary': summary}
    if extra:
        entry['extra'] = extra
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return log_path

def read_audit_log(logs_dir: Path, limit: int=50) -> list:
    log_path = logs_dir / 'audit_log.jsonl'
    if not log_path.is_file():
        return []
    entries = []
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return list(reversed(entries))[:limit]
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Audit Log - view past scan/repair history')
    parser.add_argument('--logs-dir', required=True)
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    entries = read_audit_log(Path(args.logs_dir), limit=args.limit)
    if not entries:
        print('No scan/repair history yet')
    else:
        print(f'=== Last {len(entries)} entries ===\n')
        for e in entries:
            print(f'[{e['timestamp']}] {e['event_type']} | profile: {e['profile_name']} | by: {e['actor']} | summary: {e['summary']}')
