from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass
from typing import Any

import boto3
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import settings


DATASET_NAMES = [
    "customers", "vehicles", "contracts", "invoices", "payments",
    "service_records", "cases", "case_interactions",
]


@dataclass(frozen=True)
class PolicyChunk:
    document_id: str
    document_name: str
    version: str
    section: str
    content: str
    source_key: str


class DataRepository:
    def __init__(self) -> None:
        # No profile name: locally Boto3 uses ~/.aws; App Runner uses its instance role.
        self.session = boto3.Session(region_name=settings.aws_region)
        self.s3 = self.session.client("s3")
        self.datasets: dict[str, pd.DataFrame] = {}
        self.policy_chunks: list[PolicyChunk] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.policy_matrix = None

    def _bytes(self, relative_path: str) -> bytes:
        key = f"{settings.s3_prefix}/{relative_path.lstrip('/')}"
        return self.s3.get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()

    def load(self) -> None:
        self.datasets = {
            name: pd.read_csv(
                io.BytesIO(self._bytes(f"structured/{name}.csv")),
                dtype=str,
            ).fillna("")
            for name in DATASET_NAMES
        }
        prefix = f"{settings.s3_prefix}/policies/"
        listing = self.s3.list_objects_v2(Bucket=settings.s3_bucket, Prefix=prefix)
        documents: dict[str, str] = {}
        for item in listing.get("Contents", []):
            key = item["Key"]
            if key.endswith(".md"):
                documents[key.rsplit("/", 1)[-1]] = self.s3.get_object(
                    Bucket=settings.s3_bucket, Key=key
                )["Body"].read().decode("utf-8")
        self.policy_chunks = [chunk for filename, text in documents.items() for chunk in self._split_policy(filename, text)]
        if not self.policy_chunks:
            raise RuntimeError("No policy chunks were loaded from S3")
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.policy_matrix = self.vectorizer.fit_transform(
            [f"{c.document_name} {c.section} {c.content}" for c in self.policy_chunks]
        )

    @staticmethod
    def _meta(text: str, label: str) -> str:
        match = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+)", text)
        return match.group(1).strip() if match else "Unknown"

    def _split_policy(self, filename: str, text: str) -> list[PolicyChunk]:
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else filename
        document_id = self._meta(text, "Document ID")
        version = self._meta(text, "Version")
        chunks = []
        for raw in re.split(r"^##\s+", text, flags=re.MULTILINE)[1:]:
            lines = raw.strip().splitlines()
            if len(lines) > 1:
                chunks.append(PolicyChunk(
                    document_id, title, version, lines[0].strip(),
                    "\n".join(lines[1:]).strip(),
                    f"{settings.s3_prefix}/policies/{filename}",
                ))
        return chunks

    @staticmethod
    def _records(frame: pd.DataFrame, column: str, values: list[Any]) -> list[dict[str, Any]]:
        wanted = [value for value in values if value is not None and not pd.isna(value)]
        if column not in frame.columns or not wanted:
            return []
        subset = frame.loc[frame[column].isin(wanted)]
        return subset.where(pd.notna(subset), None).to_dict("records")

    def _one(self, name: str, column: str, value: Any) -> dict[str, Any] | None:
        found = self._records(self.datasets[name], column, [value])
        return found[0] if found else None

    def case_context(self, case_id: str) -> dict[str, Any]:
        case_id = case_id.strip().upper()
        case = self._one("cases", "case_id", case_id)
        if not case:
            raise ValueError(f"Case {case_id} was not found")
        invoice_id = case.get("invoice_id")
        invoices = self._records(self.datasets["invoices"], "invoice_id", [invoice_id])
        related_ids = {invoice_id}
        for invoice in list(invoices):
            for key in ("related_invoice_id", "original_invoice_id", "parent_invoice_id"):
                if invoice.get(key):
                    related_ids.add(invoice[key])
        invoice_frame = self.datasets["invoices"]
        if "related_invoice_id" in invoice_frame.columns:
            reverse = invoice_frame.loc[invoice_frame["related_invoice_id"].astype(str).isin(related_ids)]
            invoices.extend(reverse.where(pd.notna(reverse), None).to_dict("records"))
            related_ids.update(row.get("invoice_id") for row in invoices if row.get("invoice_id"))
        unique_invoices = {row.get("invoice_id", f"row-{index}"): row for index, row in enumerate(invoices)}
        contract_id = unique_invoices.get(invoice_id, {}).get("contract_id")
        return {
            "case": case,
            "customer": self._one("customers", "customer_id", case.get("customer_id")),
            "vehicle": self._one("vehicles", "unit_number", case.get("unit_number")),
            "contract": self._one("contracts", "contract_id", contract_id),
            "invoices_under_review": list(unique_invoices.values()),
            "payments": self._records(self.datasets["payments"], "invoice_id", sorted(value for value in related_ids if value)),
            "service_records": self._records(self.datasets["service_records"], "unit_number", [case.get("unit_number")]),
            "interactions": self._records(self.datasets["case_interactions"], "case_id", [case_id]),
        }

    def retrieve_policies(self, context: dict[str, Any], top_k: int = 5) -> list[dict[str, Any]]:
        if self.vectorizer is None or self.policy_matrix is None:
            raise RuntimeError("Repository has not been loaded")
        case = context["case"]
        query = " ".join(str(case.get(k, "")) for k in ("issue_type", "priority", "subject", "description"))
        scores = cosine_similarity(self.vectorizer.transform([query]), self.policy_matrix).flatten()
        ranked = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)[:top_k]
        output = []
        for index in ranked:
            item = asdict(self.policy_chunks[index])
            item["retrieval_score"] = round(float(scores[index]), 4)
            output.append(item)
        return output


repository = DataRepository()
