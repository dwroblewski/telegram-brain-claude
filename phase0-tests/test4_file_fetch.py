#!/usr/bin/env python3
"""
Phase 0 - Test 4: File Fetch Performance (Local Simulation)

Simulates R2 fetch by reading vault files from disk.
R2 should be faster (edge, SSD) so this is a conservative estimate.
"""
import time
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
from datetime import datetime


def load_vault_files_sync(vault_path: Path, max_files: int = 130) -> tuple[list, int, int]:
    """Load vault files synchronously, return contents and stats."""
    contents = []
    total_bytes = 0
    file_count = 0

    priority_folders = ["Daily", "0-Inbox", "Projects", "Areas", "Resources", "Archive"]

    for folder in priority_folders:
        folder_path = vault_path / folder
        if not folder_path.exists():
            continue
        for md_file in folder_path.rglob("*.md"):
            if file_count >= max_files:
                break
            try:
                text = md_file.read_text(encoding="utf-8")
                contents.append(text)
                total_bytes += len(text.encode("utf-8"))
                file_count += 1
            except Exception:
                pass
        if file_count >= max_files:
            break

    return contents, file_count, total_bytes


async def load_vault_files_async(vault_path: Path, max_files: int = 130) -> tuple[list, int, int]:
    """Load vault files with asyncio thread pool (simulates parallel fetch)."""
    priority_folders = ["Daily", "0-Inbox", "Projects", "Areas", "Resources", "Archive"]
    file_paths = []

    for folder in priority_folders:
        folder_path = vault_path / folder
        if not folder_path.exists():
            continue
        for md_file in folder_path.rglob("*.md"):
            if len(file_paths) >= max_files:
                break
            file_paths.append(md_file)
        if len(file_paths) >= max_files:
            break

    def read_file(path):
        try:
            return path.read_text(encoding="utf-8")
        except:
            return ""

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=50) as executor:
        contents = await asyncio.gather(
            *[loop.run_in_executor(executor, read_file, p) for p in file_paths]
        )

    total_bytes = sum(len(c.encode("utf-8")) for c in contents if c)
    return [c for c in contents if c], len(file_paths), total_bytes


def main():
    vault_path = Path.home() / "projects/second-brain"

    print(f"\n{'='*60}")
    print("PHASE 0 - TEST 4: FILE FETCH PERFORMANCE")
    print(f"{'='*60}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Vault path: {vault_path}")
    print("\nNote: Local disk is likely SLOWER than R2 edge storage")
    print("      This provides a conservative upper bound estimate\n")

    results = {}

    # Test 1: Sequential fetch
    print("--- Sequential Fetch ---")
    start = time.time()
    contents, count, total_bytes = load_vault_files_sync(vault_path, max_files=130)
    elapsed = time.time() - start

    results["sequential"] = {
        "elapsed_ms": round(elapsed * 1000, 2),
        "file_count": count,
        "total_bytes": total_bytes,
        "bytes_per_ms": round(total_bytes / (elapsed * 1000), 2),
    }
    print(f"  Files: {count}")
    print(f"  Size: {total_bytes:,} bytes ({total_bytes/1024:.1f} KB)")
    print(f"  Time: {elapsed*1000:.2f} ms")
    print(f"  Rate: {total_bytes/(elapsed*1024):.1f} KB/s")

    # Test 2: Parallel fetch (simulates Promise.all in JS)
    print("\n--- Parallel Fetch (50 workers) ---")
    start = time.time()
    contents, count, total_bytes = asyncio.run(
        load_vault_files_async(vault_path, max_files=130)
    )
    elapsed = time.time() - start

    results["parallel"] = {
        "elapsed_ms": round(elapsed * 1000, 2),
        "file_count": count,
        "total_bytes": total_bytes,
        "bytes_per_ms": round(total_bytes / (elapsed * 1000), 2),
    }
    print(f"  Files: {count}")
    print(f"  Size: {total_bytes:,} bytes ({total_bytes/1024:.1f} KB)")
    print(f"  Time: {elapsed*1000:.2f} ms")
    print(f"  Rate: {total_bytes/(elapsed*1024):.1f} KB/s")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    parallel_ms = results["parallel"]["elapsed_ms"]

    if parallel_ms < 100:
        verdict = "✓ EXCELLENT: <100ms parallel fetch"
    elif parallel_ms < 500:
        verdict = "✓ GOOD: 100-500ms parallel fetch"
    elif parallel_ms < 1000:
        verdict = "⚠ ACCEPTABLE: 500ms-1s parallel fetch"
    else:
        verdict = "✗ SLOW: >1s parallel fetch - consider concatenation"

    print(f"Sequential: {results['sequential']['elapsed_ms']:.2f} ms")
    print(f"Parallel:   {results['parallel']['elapsed_ms']:.2f} ms")
    print(f"Verdict:    {verdict}")

    print("\n--- Decision ---")
    if parallel_ms < 500:
        print("✓ PASS: File fetch fast enough for R2")
        print("  R2 (edge SSD) should be similar or faster")
    else:
        print("⚠ CONSIDER: May need to concatenate files in R2")
        print("  Or use single pre-built vault object")

    # Save results
    output_file = Path(__file__).parent / "test4_results.json"
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "verdict": verdict,
        }, f, indent=2)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
