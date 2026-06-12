#!/usr/bin/env python3
"""Load sanity test: concurrent client-portal sessions + admin activity.

Zero external deps (pure asyncio + httpx, already in requirements).
Run against a LOCAL or STAGING server — never production with real clients.

Usage:
    # terminal 1:
    SECRET_KEY=loadtest uvicorn backend.main:app --port 8000
    # terminal 2:
    SECRET_KEY=loadtest python3 scripts/load_test.py --base http://127.0.0.1:8000 \
        --sessions 50 --duration 600
"""
import argparse
import asyncio
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx  # noqa: E402


async def portal_session(client, base, token, latencies, errors, stop_at):
    """A portal tab: fetch /me every ~10s (worst-case pre-SSE behavior, so
    results are an upper bound vs. the SSE reality)."""
    while time.monotonic() < stop_at:
        t0 = time.perf_counter()
        try:
            r = await client.get(f"{base}/api/client/me",
                                 headers={"Authorization": f"Bearer {token}"})
            latencies.append((time.perf_counter() - t0) * 1000)
            if r.status_code >= 500:
                errors.append(r.status_code)
        except Exception as e:
            errors.append(str(e)[:80])
        await asyncio.sleep(10)


async def admin_session(client, base, token, latencies, errors, stop_at):
    """The operator: board + digest + clients every ~15s."""
    while time.monotonic() < stop_at:
        for path in ("/api/admin/board", "/api/admin/digest", "/api/admin/clients"):
            t0 = time.perf_counter()
            try:
                r = await client.get(f"{base}{path}",
                                     headers={"Authorization": f"Bearer {token}"})
                latencies.append((time.perf_counter() - t0) * 1000)
                if r.status_code >= 500:
                    errors.append(r.status_code)
            except Exception as e:
                errors.append(str(e)[:80])
        await asyncio.sleep(15)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--sessions", type=int, default=50)
    ap.add_argument("--duration", type=int, default=600, help="seconds")
    args = ap.parse_args()

    from backend.main import make_token  # needs same SECRET_KEY as the server
    client_token = make_token("test-alice@example.com", "client")
    admin_token = make_token("admin@districtawardtravel.com", "admin")

    latencies, errors = [], []
    stop_at = time.monotonic() + args.duration

    async with httpx.AsyncClient(timeout=30) as client:
        # sanity: server up?
        r = await client.get(f"{args.base}/healthz")
        print(f"healthz: {r.status_code} {r.text[:100]}")

        tasks = [portal_session(client, args.base, client_token, latencies, errors, stop_at)
                 for _ in range(args.sessions)]
        tasks.append(admin_session(client, args.base, admin_token, latencies, errors, stop_at))
        await asyncio.gather(*tasks)

    if not latencies:
        print("NO SAMPLES — server unreachable?")
        sys.exit(1)
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    p99 = latencies[int(len(latencies) * 0.99) - 1]
    print(f"\n=== RESULTS ({args.sessions} portal sessions + 1 admin, {args.duration}s) ===")
    print(f"requests: {len(latencies)}  errors: {len(errors)} "
          f"({100 * len(errors) / max(len(latencies) + len(errors), 1):.2f}%)")
    print(f"latency ms — p50: {p50:.0f}  p95: {p95:.0f}  p99: {p99:.0f}  max: {latencies[-1]:.0f}")
    if errors[:5]:
        print("sample errors:", errors[:5])


if __name__ == "__main__":
    asyncio.run(main())
