from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .config import settings
from .data import repository


def persist_audit(state: dict[str, Any], thread_id: str, duration: float) -> dict[str, Any]:
    result = state.get("investigation", {})
    decision = state.get("human_decision", {})
    recorded = datetime.now(timezone.utc)
    event = {
        "schema_version": "1.0",
        "event_id": state.get("audit_record", {}).get("event_id"),
        "recorded_at_utc": recorded.isoformat(),
        "thread_id": thread_id,
        "case_id": state.get("case_id"),
        "issue_type": result.get("issue_type"),
        "provider": settings.model_provider,
        "final_status": state.get("final_status"),
        "decision": decision.get("decision"),
        "reviewer_id": decision.get("reviewer_id"),
        "confidence": result.get("confidence"),
        "duration_seconds": round(duration, 3),
        "warning_count": len(state.get("warnings", [])),
        "data_classification": "internal-demo",
    }
    canonical = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    event["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    key = f"{settings.audit_prefix}/{recorded:%Y/%m/%d}/{event['case_id']}/{thread_id}.json"
    repository.s3.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=json.dumps(event, indent=2).encode(),
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )
    event["s3_key"] = key
    return event


def recent_events(limit: int = 20) -> list[dict[str, Any]]:
    objects = []
    paginator = repository.s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=f"{settings.audit_prefix}/"):
        objects.extend(item for item in page.get("Contents", []) if item["Key"].endswith(".json"))
    newest = sorted(objects, key=lambda item: item["LastModified"], reverse=True)[:limit]
    return [
        json.loads(repository.s3.get_object(Bucket=settings.s3_bucket, Key=item["Key"])["Body"].read())
        for item in newest
    ]

