"""Runs a fixed search against the configured SearXNG instance and prints
the raw results. Run with:
python -m backend.scripts.smoke_searxng --query "distributed rate limiter design interview"
"""

import argparse

from backend.searxng_client import SearXNGError, search


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--num-results", type=int, default=5)
    args = parser.parse_args()

    try:
        results = search(args.query, num_results=args.num_results)
    except SearXNGError as e:
        print(f"FAILED: {e}")
        raise SystemExit(1)

    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet'][:200]}\n")


if __name__ == "__main__":
    main()
