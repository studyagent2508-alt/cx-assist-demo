import io
import os

import boto3
import pandas as pd
from dotenv import load_dotenv


load_dotenv()

AWS_PROFILE = os.getenv("AWS_PROFILE")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_PREFIX = os.getenv("S3_PREFIX")


def create_s3_client():
    session = boto3.Session(
        profile_name=AWS_PROFILE,
        region_name=AWS_REGION,
    )
    return session.client("s3")


def test_list_objects(s3_client):
    response = s3_client.list_objects_v2(
        Bucket=S3_BUCKET,
        Prefix=f"{S3_PREFIX}/",
    )

    objects = response.get("Contents", [])

    assert objects, "No objects were found in the CX Assist S3 prefix."

    print(f"\nFound {len(objects)} objects:")

    for item in objects:
        print(f"  - {item['Key']}")

    return objects


def test_read_csv(s3_client):
    key = f"{S3_PREFIX}/structured/cases.csv"

    response = s3_client.get_object(
        Bucket=S3_BUCKET,
        Key=key,
    )

    content = response["Body"].read()
    cases = pd.read_csv(io.BytesIO(content))

    assert not cases.empty, "cases.csv is empty."
    assert "case_id" in cases.columns
    assert "CASE-3021" in cases["case_id"].values

    print("\nSuccessfully retrieved cases.csv")
    print(f"Rows: {len(cases)}")
    print(f"Columns: {list(cases.columns)}")

    print(
        cases[
            ["case_id", "issue_type", "priority", "status"]
        ].to_string(index=False)
    )


def test_read_policy(s3_client):
    key = (
        f"{S3_PREFIX}/policies/"
        "maintenance_downtime_policy.md"
    )

    response = s3_client.get_object(
        Bucket=S3_BUCKET,
        Key=key,
    )

    policy_text = response["Body"].read().decode("utf-8")

    assert "Maintenance Downtime Credit Policy" in policy_text
    assert "24 consecutive hours" in policy_text

    print("\nSuccessfully retrieved maintenance policy")
    print(f"Policy size: {len(policy_text)} characters")
    print("\nPolicy preview:")
    print(policy_text[:400])


def main():
    print("Testing Python connection to Amazon S3...")

    print(f"Profile: {AWS_PROFILE}")
    print(f"Region: {AWS_REGION}")
    print(f"Bucket: {S3_BUCKET}")
    print(f"Prefix: {S3_PREFIX}")

    required_settings = {
        "AWS_PROFILE": AWS_PROFILE,
        "AWS_REGION": AWS_REGION,
        "S3_BUCKET": S3_BUCKET,
        "S3_PREFIX": S3_PREFIX,
    }

    missing = [
        name
        for name, value in required_settings.items()
        if not value
    ]

    if missing:
        raise ValueError(
            f"Missing environment variables: {', '.join(missing)}"
        )

    s3_client = create_s3_client()

    test_list_objects(s3_client)
    test_read_csv(s3_client)
    test_read_policy(s3_client)

    print("\nSUCCESS: Python can access the CX Assist data in S3.")


if __name__ == "__main__":
    main()