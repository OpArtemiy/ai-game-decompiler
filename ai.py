import os
import re
import boto3
from botocore.config import Config
MODEL = os.environ.get("MODEL", "eu.anthropic.claude-opus-4-6-v1")
REGION = os.environ.get("AWS_REGION_NAME", "eu-north-1")
_client = None
def client():
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime", region_name=REGION,
            config=Config(read_timeout=300, retries={"max_attempts": 10, "mode": "adaptive"}),
        )
    return _client

def ask(prompt: str, max_tokens: int = 8000) -> str:
    r = client().converse(
        modelId=MODEL,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": max_tokens},
    )
    if r.get("stopReason") == "max_tokens":
        raise ValueError("AI reply was cut off, keeping the original file")
    return r["output"]["message"]["content"][0]["text"]

CLEANUP_PROMPT = (
    "You are helping with a decompiled C# file from a Unity game.\n"
    "Rename meaningless identifiers (like num, num2, text, array) to descriptive names, "
    "add short comments explaining what the code does, and keep the behavior IDENTICAL. "
    "Do not remove or add functionality. Return ONLY the complete C# code, "
    "with no explanation and no markdown fences.\n\n"
)


def strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z#]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text

def clean_code(code: str) -> str:
    return strip_fences(ask(CLEANUP_PROMPT + code))

def make_overview(summary: str) -> str:
    prompt = (
        "Below are the class and method declarations from a decompiled Unity game, "
        "grouped by file. Write an OVERVIEW.md in Markdown that explains: what kind of "
        "game this probably is, the main systems (player, enemies, inventory, UI, "
        "saving, etc.), which files belong to each system, and anything notable. "
        "Be concise and only state what the code supports.\n\n" + summary
    )
    return ask(prompt, max_tokens=3000)

_overview_raw = make_overview
def make_overview(summary):
    try:
        return _overview_raw(summary)
    except Exception as e:
        return "# Overview unavailable: " + str(e)
