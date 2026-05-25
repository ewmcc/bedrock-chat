"""
llm.py - LLM factory.

Returns a fresh ChatBedrockConverse instance built from env vars plus any
caller-supplied overrides.  Call `get_llm()` once per session (or whenever
model parameters change) rather than caching a single global instance.
"""

import os

from langchain_aws import ChatBedrockConverse


def get_llm(
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> ChatBedrockConverse:
    """Build a ChatBedrockConverse instance from environment variables.

    Parameters
    ----------
    temperature:
        Sampling temperature (0 = deterministic, 1 = most creative).
    max_tokens:
        Maximum number of tokens in the model response.
    """
    model_id = os.getenv("BEDROCK_MODEL_ID", "")
    region = os.getenv("AWS_REGION", "us-east-1")

    kwargs: dict = {
        "model_id": model_id,
        "region_name": region,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Only pass explicit credentials when they are set in the environment.
    # If absent, boto3 falls back to the default credential chain
    # (IAM role, ~/.aws/credentials, instance profile, etc.).
    if os.getenv("AWS_ACCESS_KEY_ID"):
        kwargs["aws_access_key_id"] = os.environ["AWS_ACCESS_KEY_ID"]
    if os.getenv("AWS_SECRET_ACCESS_KEY"):
        kwargs["aws_secret_access_key"] = os.environ["AWS_SECRET_ACCESS_KEY"]

    return ChatBedrockConverse(**kwargs)
