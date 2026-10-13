"""Benchmarking and Load Generation Script for Scalable URL Shortener.

Measures throughput (Requests/sec) and latency percentiles (p50, p95, p99)
across both URL Creation and Read-Through Cache Redirection endpoints.
"""

import asyncio
import time
from typing import List
import httpx

TARGET_BASE_URL = "http://localhost:8000"
TOTAL_REQUESTS = 1000
CONCURRENCY = 50


async def benchmark_endpoint(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    json_data: dict = None,
) -> float:
    start = time.perf_counter()
    if method == "POST":
        resp = await client.post(url, json=json_data)
    else:
        resp = await client.get(url, follow_redirects=False)
    elapsed = (time.perf_counter() - start) * 1000.0  # ms
    return elapsed


async def run_benchmark():
    print(f"🚀 Initializing Benchmark on {TARGET_BASE_URL}")
    print(f"Total Requests: {TOTAL_REQUESTS} | Concurrency: {CONCURRENCY}\n")

    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=CONCURRENCY)
    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        # Pre-seed a short URL for read benchmark
        seed_res = await client.post(
            f"{TARGET_BASE_URL}/api/v1/urls",
            json={"original_url": "https://example.com/target", "custom_code": "bench-target"},
        )
        if seed_res.status_code not in (201, 409):
            print("⚠️ Target server not reachable at localhost:8000. Please start the app before benchmarking.")
            return

        print("⚡ Benchmarking Read-Through Cache Redirects (GET /bench-target)...")
        tasks = []
        sem = asyncio.Semaphore(CONCURRENCY)

        async def worker():
            async with sem:
                return await benchmark_endpoint(client, "GET", f"{TARGET_BASE_URL}/bench-target")

        start_time = time.perf_counter()
        latencies: List[float] = await asyncio.gather(*(worker() for _ in range(TOTAL_REQUESTS)))
        total_time = time.perf_counter() - start_time

        latencies.sort()
        qps = TOTAL_REQUESTS / total_time
        avg_lat = sum(latencies) / len(latencies)
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print("-" * 50)
        print("📊 BENCHMARK RESULTS")
        print("-" * 50)
        print(f"Total Time:      {total_time:.2f} s")
        print(f"Throughput:      {qps:.2f} req/sec")
        print(f"Average Latency: {avg_lat:.2f} ms")
        print(f"p50 Latency:     {p50:.2f} ms")
        print(f"p95 Latency:     {p95:.2f} ms")
        print(f"p99 Latency:     {p99:.2f} ms")
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
