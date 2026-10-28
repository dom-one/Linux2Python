"""工作区互斥锁。

两个 cron 任务共用一把锁，避免同时写 git 索引撞 index.lock。

用法:
    python AI/脚本/_t10_lock.py acquire --owner 开发
    python AI/脚本/_t10_lock.py release --owner 开发
"""

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOCK_DIR = os.path.join(ROOT, "AI", "锁")
LOCK_PATH = os.path.join(LOCK_DIR, "git.lock")
STALE_SECONDS = 1800


def read_state():
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_state(payload):
    os.makedirs(LOCK_DIR, exist_ok=True)
    tmp_path = LOCK_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, LOCK_PATH)


def acquire(owner):
    now = time.time()
    state = read_state()
    if state and state.get("released_ts") is None:
        age = now - float(state.get("acquired_ts") or 0)
        if age < STALE_SECONDS and state.get("owner") != owner:
            print(json.dumps(
                {"ok": False, "reason": "锁被占用", "owner": state.get("owner"),
                 "age_seconds": int(age)},
                ensure_ascii=False))
            return 1
    write_state({"owner": owner, "acquired_ts": now, "released_ts": None})
    print(json.dumps({"ok": True, "acquired_ts": now, "stale_seconds": STALE_SECONDS},
                     ensure_ascii=False))
    return 0


def release(owner):
    state = read_state() or {}
    if state.get("owner") != owner and state.get("released_ts") is None:
        print(json.dumps({"ok": False, "reason": "锁不属于本任务",
                          "owner": state.get("owner")}, ensure_ascii=False))
        return 1
    write_state({"owner": owner, "acquired_ts": state.get("acquired_ts"),
                 "released_ts": time.time()})
    print(json.dumps({"ok": True, "owner": owner}, ensure_ascii=False))
    return 0


def status():
    state = read_state()
    print(json.dumps(state or {"locked": False}, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description="工作区互斥锁")
    parser.add_argument("action", choices=["acquire", "release", "status"])
    parser.add_argument("--owner", default="未知")
    args = parser.parse_args()
    if args.action == "acquire":
        return acquire(args.owner)
    if args.action == "release":
        return release(args.owner)
    return status()


if __name__ == "__main__":
    sys.exit(main())
