#!/usr/bin/env python3
"""Utility to cancel every scheduled Upload-Post job for a given profile."""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Tuple

import requests


DEFAULT_BASE_URL = "https://api.upload-post.com"
SCHEDULE_ENDPOINT = "/api/uploadposts/schedule"


def fetch_scheduled_jobs(base_url: str, headers: dict) -> List[dict]:
    """Return all scheduled jobs visible to the API key."""
    resp = requests.get(f"{base_url}{SCHEDULE_ENDPOINT}", headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("scheduled_posts"), list):
            return data["scheduled_posts"]
        if isinstance(data.get("data"), list):
            return data["data"]
    raise RuntimeError("Unexpected response format: expected a JSON list.")


def cancel_job(base_url: str, headers: dict, job_id: str) -> Tuple[bool, str]:
    """Cancel a single scheduled job by id."""
    resp = requests.delete(
        f"{base_url}{SCHEDULE_ENDPOINT}/{job_id}",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 200:
        return True, ""
    detail = resp.text.strip() or resp.reason
    return False, detail


def run(api_key: str, profile: str, base_url: str) -> None:
    headers = {"Authorization": f"Apikey {api_key}"}

    print(f"Fetching scheduled jobs from {base_url} ...")
    jobs = fetch_scheduled_jobs(base_url, headers)
    target_jobs = [job for job in jobs if job.get("profile_username") == profile]

    if not target_jobs:
        print(f"No scheduled posts found for profile '{profile}'. Nothing to cancel.")
        return

    print(f"Found {len(target_jobs)} scheduled post(s) for '{profile}'.")
    failures: List[Tuple[str, str]] = []

    for idx, job in enumerate(target_jobs, start=1):
        job_id = job.get("job_id")
        scheduled_date = job.get("scheduled_date")
        print(f"[{idx}/{len(target_jobs)}] Cancelling {job_id} scheduled at {scheduled_date} ...", end=" ")
        ok, detail = cancel_job(base_url, headers, job_id)
        if ok:
            print("OK")
        else:
            print("FAILED")
            failures.append((job_id, detail))

    if failures:
        print("\nSome jobs could not be cancelled:")
        for job_id, detail in failures:
            print(f"  - {job_id}: {detail}")
        sys.exit(1)

    print("\nVerifying that the profile has no remaining scheduled posts ...")
    refreshed = fetch_scheduled_jobs(base_url, headers)
    remaining = [job for job in refreshed if job.get("profile_username") == profile]
    if remaining:
        print("Cancellation verification failed. Jobs still present:")
        for job in remaining:
            print(f"  - {job.get('job_id')} scheduled at {job.get('scheduled_date')}")
        sys.exit(1)

    print(f"All scheduled posts for '{profile}' have been cancelled successfully.")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cancel all scheduled Upload-Post jobs for a specific profile.",
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="Upload-Post API key (Apikey header value).",
    )
    parser.add_argument(
        "--profile",
        required=True,
        help="Profile username whose scheduled posts should be cancelled.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Upload-Post API base URL (default: {DEFAULT_BASE_URL}).",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    try:
        run(api_key=args.api_key, profile=args.profile, base_url=args.base_url.rstrip("/"))
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc.response.status_code} {exc.response.text}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
