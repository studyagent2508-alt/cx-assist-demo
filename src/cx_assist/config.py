from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    aws_region: str = os.getenv("AWS_REGION", "ap-south-1")
    s3_bucket: str = os.getenv("S3_BUCKET", "rahulcxassistdemo")
    s3_prefix: str = os.getenv("S3_PREFIX", "cx-copilot/dev").strip("/")
    model_provider: str = os.getenv("MODEL_PROVIDER", "groq").strip().lower()
    model_temperature: float = float(os.getenv("MODEL_TEMPERATURE", "0"))
    audit_prefix: str = os.getenv("AUDIT_PREFIX", "cx-copilot/dev/audit-events").strip("/")


settings = Settings()

