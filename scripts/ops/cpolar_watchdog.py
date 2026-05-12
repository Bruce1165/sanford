import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _log(msg: str) -> None:
    sys.stdout.write(f"[{_now_iso()}] {msg}\n")
    sys.stdout.flush()


def _project_root() -> Path:
    env_root = (os.environ.get("NEOTRADE2_ROOT") or "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def _http_json_ok(url: str, timeout_sec: int) -> tuple[bool, str]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "neotrade2-cpolar-watchdog/1.0",
            "Cache-Control": "no-cache",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as resp:
            status = int(getattr(resp, "status", 0) or 0)
            body = resp.read(4096)
        if status != 200:
            return False, f"http_status={status}"
        try:
            data = json.loads(body.decode("utf-8", errors="replace") or "{}")
        except Exception:
            return False, "invalid_json"
        if str(data.get("status") or "").strip().lower() != "ok":
            return False, "json_status_not_ok"
        return True, "ok"
    except Exception as e:
        return False, f"error={type(e).__name__}:{e}"


def _read_tail_lines(path: Path, max_bytes: int = 200_000) -> list[str]:
    try:
        if not path.exists():
            return []
        data = path.read_bytes()
        if len(data) > max_bytes:
            data = data[-max_bytes:]
        text = data.decode("utf-8", errors="replace")
        return [x for x in text.splitlines() if x.strip()]
    except Exception:
        return []


def _parse_cpolar_last_established_at(lines: list[str], host: str) -> tuple[float, str]:
    needle = f"Tunnel established at https://{host}"
    for line in reversed(lines):
        if needle not in line:
            continue
        ts = 0.0
        try:
            prefix = line.split('time="', 1)[1]
            ts_str = prefix.split('"', 1)[0]
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
        except Exception:
            ts = 0.0
        return ts, line
    return 0.0, ""


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        combined = out if not err else (out + ("\n" if out else "") + err)
        return int(proc.returncode), combined
    except Exception as e:
        return 1, f"run_failed:{type(e).__name__}:{e}"


def _kickstart(label: str) -> tuple[bool, str]:
    uid = os.getuid()
    cmd = ["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"]
    code, out = _run(cmd)
    return code == 0, out


def _load_state(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8", errors="replace") or "{}")
    except Exception:
        return {}


def _save_state(path: Path, state: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external", required=True)
    parser.add_argument("--local", default="http://127.0.0.1:8765")
    parser.add_argument("--timeout-sec", type=int, default=6)
    parser.add_argument("--max-restart-every-sec", type=int, default=300)
    parser.add_argument("--cpolar-label", default="com.neotrade.cpolar")
    parser.add_argument("--flask-label", default="com.neotrade2.flask")
    parser.add_argument("--cpolar-log", default="/Users/mac/neotrade_cpolar.log")
    parser.add_argument("--tunnel-host", default="")
    parser.add_argument("--tunnel-established-window-sec", type=int, default=900)
    parser.add_argument("--alert-after-consecutive-failures", type=int, default=3)
    parser.add_argument("--alert-cooldown-sec", type=int, default=900)
    args = parser.parse_args()

    external = str(args.external).strip().rstrip("/")
    local_base = str(args.local).strip().rstrip("/")
    if not external.startswith("http://") and not external.startswith("https://"):
        _log("invalid external base url")
        return 0

    root = _project_root()
    state_path = root / "logs" / "cpolar_watchdog_state.json"
    state = _load_state(state_path)
    last_restart_at = float(state.get("last_restart_at") or 0.0)
    consecutive_failures = int(state.get("consecutive_failures") or 0)
    last_alert_at = float(state.get("last_alert_at") or 0.0)
    now_ts = time.time()
    can_restart = (now_ts - last_restart_at) >= int(args.max_restart_every_sec)

    local_url = f"{local_base}/api/health"
    external_url = f"{external}/api/health"

    local_ok, local_reason = _http_json_ok(local_url, int(args.timeout_sec))
    ext_ok, ext_reason = _http_json_ok(external_url, int(args.timeout_sec))

    tunnel_host = str(args.tunnel_host or "").strip()
    tunnel_ok = True
    tunnel_reason = "ok"
    if tunnel_host:
        lines = _read_tail_lines(Path(str(args.cpolar_log)))
        last_ts, last_line = _parse_cpolar_last_established_at(lines, tunnel_host)
        if not last_ts:
            tunnel_ok = False
            tunnel_reason = "no_established_log"
        else:
            age = now_ts - last_ts
            if age > int(args.tunnel_established_window_sec):
                tunnel_ok = False
                tunnel_reason = f"stale_established_log_age_sec={int(age)}"
            else:
                tunnel_ok = True
                tunnel_reason = f"ok_age_sec={int(age)}"
        state["last_tunnel_established_line"] = last_line

    _log(
        f"local={local_ok}({local_reason}) external={ext_ok}({ext_reason}) tunnel={tunnel_ok}({tunnel_reason}) external_url={external_url}"
    )

    if ext_ok and local_ok:
        state["consecutive_failures"] = 0
        state["last_ok_time"] = _now_iso()
        _save_state(state_path, state)
        return 0

    consecutive_failures += 1
    state["consecutive_failures"] = consecutive_failures
    state["last_fail_time"] = _now_iso()
    state["last_fail_reason"] = {"local": local_reason, "external": ext_reason, "tunnel": tunnel_reason}

    should_alert = (
        consecutive_failures >= int(args.alert_after_consecutive_failures)
        and (now_ts - last_alert_at) >= int(args.alert_cooldown_sec)
    )
    if should_alert:
        state["last_alert_at"] = now_ts
        state["last_alert_time"] = _now_iso()
        _log(f"ALERT consecutive_failures={consecutive_failures} local={local_reason} external={ext_reason} tunnel={tunnel_reason}")

    _save_state(state_path, state)

    if not can_restart:
        _log("skip restart: rate-limited")
        return 0

    state["last_restart_at"] = now_ts
    state["last_restart_reason"] = {"local": local_reason, "external": ext_reason}
    state["last_restart_time"] = _now_iso()
    _save_state(state_path, state)

    if not local_ok:
        ok, out = _kickstart(str(args.flask_label))
        _log(f"kickstart flask label={args.flask_label} ok={ok} out={out[:4000]}")

    ok, out = _kickstart(str(args.cpolar_label))
    _log(f"kickstart cpolar label={args.cpolar_label} ok={ok} out={out[:4000]}")

    time.sleep(2)
    ext_ok2, ext_reason2 = _http_json_ok(external_url, int(args.timeout_sec))
    _log(f"post_restart external={ext_ok2}({ext_reason2})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
