"""User-partitioned asynchronous recap regeneration; never scans users."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from uuid import uuid4

import boto3
from boto3.dynamodb.conditions import Key

import wrap_generator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(user_id: str, job_id: str) -> dict:
    return {"PK": f"USER#{user_id}", "SK": f"WRAP#JOB#{job_id}"}


def public_job(job: dict) -> dict:
    return {key: job[key] for key in (
        "job_id", "status", "benchmark_id", "periods", "completed_periods",
        "failed_periods", "created_at", "updated_at",
    )}


def get_job(user_id: str, job_id: str) -> dict | None:
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise ValueError("job_id must be a 32-character hexadecimal ID")
    return wrap_generator._wrap_table().get_item(
        Key=_key(user_id, job_id), ConsistentRead=True,
    ).get("Item")


def _save(job: dict) -> None:
    job["updated_at"] = _now()
    wrap_generator._wrap_table().put_item(Item=job)


def _invoke(user_id: str, job_id: str) -> None:
    function_name = os.environ.get("MONTHLY_WRAP_FUNCTION_NAME")
    if not function_name:
        raise RuntimeError("Monthly wrap worker is not configured")
    response = boto3.client("lambda").invoke(
        FunctionName=function_name, InvocationType="Event",
        Payload=json.dumps({"action": "recalculate", "user_id": user_id, "job_id": job_id}).encode(),
    )
    if response.get("StatusCode") != 202:
        raise RuntimeError("Monthly wrap worker did not accept the job")


def create_job(user_id: str, payload: dict) -> dict:
    if not isinstance(payload, dict) or set(payload) - {"consent", "periods"}:
        raise ValueError("Only consent and periods are accepted; user and benchmark come from the authenticated profile")
    if "consent" in payload and payload["consent"] is not True:
        raise ValueError("consent must be true when supplied; do not call this endpoint if consent is declined")
    requested = payload.get("periods")
    if "periods" in payload and (
        not isinstance(requested, list) or not requested or len(requested) > 600
        or any(not isinstance(p, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", p) for p in requested)
    ):
        raise ValueError("periods must be a nonempty array of at most 600 YYYY-MM strings")
    table = wrap_generator._wrap_table()
    query = {
        "KeyConditionExpression": Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("WRAP#MONTH#"),
        "ProjectionExpression": "SK", "ConsistentRead": True,
    }
    periods = set()
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    while True:
        response = table.query(**query)
        for item in response.get("Items", []):
            period = item["SK"].removeprefix("WRAP#MONTH#")
            if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period) and "0001-01" <= period < current_month:
                periods.add(period)
        if not response.get("LastEvaluatedKey"):
            break
        query["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    if requested is not None and not set(requested).issubset(periods):
        raise ValueError("periods may contain only your existing, completed historical monthly wraps")
    selected = sorted(set(requested) if requested is not None else periods)
    job_id = uuid4().hex
    job = {
        **_key(user_id, job_id), "job_id": job_id,
        "status": "accepted" if selected else "completed",
        "benchmark_id": wrap_generator.selected_benchmark(user_id),
        "periods": selected, "completed_periods": [], "failed_periods": [],
        "created_at": _now(),
    }
    _save(job)
    if selected:
        try:
            _invoke(user_id, job_id)
        except Exception:
            job["status"] = "failed"
            _save(job)
            raise
    return public_job(job)


def run_job(event: dict, context=None) -> dict:
    """Trusted Lambda invoke only. Event carries identity, never a user list.

    Persist progress after every month. Lambda retries skip finished months;
    a near-timeout execution hands remaining work to the same monthly Lambda.
    Regeneration overwrites the same user/month keys (at-least-once safe).
    """
    user_id, job_id = event.get("user_id"), event.get("job_id")
    if not isinstance(user_id, str) or not user_id.strip() or not isinstance(job_id, str):
        raise ValueError("A user_id and job_id are required")
    job = get_job(user_id, job_id)
    if not job:
        raise ValueError("Job not found for this user")
    if job["status"] in {"completed", "completed_with_errors", "failed"}:
        return public_job(job)
    job["status"] = "running"
    _save(job)
    for period in job["periods"]:
        if period in job["completed_periods"] or period in job["failed_periods"]:
            continue
        if context is not None and context.get_remaining_time_in_millis() < 120000:
            # An invoke failure is raised, letting Lambda's async retry resume.
            _invoke(user_id, job_id)
            return public_job(job)
        year, month = map(int, period.split("-"))
        try:
            wrap_generator.generate_monthly_wrap(user_id, year, month, benchmark_id=job["benchmark_id"])
            job["completed_periods"].append(period)
        except Exception as exc:
            print(f"Monthly regeneration failed for job {job_id}, period {period}: {exc}")
            job["failed_periods"].append(period)
        _save(job)
    job["status"] = "completed_with_errors" if job["failed_periods"] else "completed"
    _save(job)
    return public_job(job)