"""
llm.py - LLM factory.

Returns a configured ChatBedrockConverse singleton built from env vars.
Import `get_llm()` wherever an LLM instance is needed.
"""

import os
from functools import lru_cache

from langchain_aws import ChatBedrockConverse


@lru_cache(maxsize=1)
def get_llm() -> ChatBedrockConverse:
    """Build and cache a ChatBedrockConverse instance from environment variables."""
    model_id = os.getenv("BEDROCK_MODEL_ID", "")
    region = os.getenv("AWS_REGION", "us-east-1")

    kwargs: dict = {
        "model_id": model_id,
        "region_name": region,
        "temperature": 0.7,
        "max_tokens": 2048,
    }

    # Only pass explicit credentials when they are set in the environment.
    # If absent, boto3 falls back to the default credential chain
    # (IAM role, ~/.aws/credentials, instance profile, etc.).
    if os.getenv("AWS_ACCESS_KEY_ID"):
        kwargs["aws_access_key_id"] = os.environ["AWS_ACCESS_KEY_ID"]
    if os.getenv("AWS_SECRET_ACCESS_KEY"):
        kwargs["aws_secret_access_key"] = os.environ["AWS_SECRET_ACCESS_KEY"]

    return ChatBedrockConverse(**kwargs)
