"""Redact secrets before anything leaves a gate.

Gate output travels to four places: the console, the JSON log, the next
attempt's $SGL_FEEDBACK (an agent reads it), and in CI the public job summary.
A gate that echoes a token would leak it to all four. Every one of those paths
goes through `redact()` first.

Two layers:
1. Values of environment variables whose NAME looks secret
   (TOKEN, KEY, SECRET, PASSWORD, ...). Exact-value match, so any format.
2. Well-known token shapes (GitHub, OpenAI, Anthropic, AWS, Stripe, Slack,
   JWTs, private key blocks, bearer headers) even when they never came from env.

This is defence in depth, not a guarantee. The real rule: gates should not
print secrets.
"""

from __future__ import annotations

import os
import re
from typing import Dict, Iterable, List, Optional

MASK = "[REDACTED]"
MIN_SECRET_LEN = 8  # shorter values are too likely to collide with normal text

SECRET_NAME = re.compile(
    r"(TOKEN|SECRET|PASSW(OR)?D|PASSPHRASE|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY|"
    r"CREDENTIAL|AUTH|COOKIE|SESSION|SIGNING|WEBHOOK|DSN|CONN(ECTION)?_?STR)",
    re.IGNORECASE,
)

PATTERNS: List[re.Pattern] = [re.compile(p) for p in (
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
    r"\bgh[pousr]_[A-Za-z0-9]{30,}\b",                 # GitHub tokens
    r"\bgithub_pat_[A-Za-z0-9_]{40,}\b",
    r"\bsk-ant-[A-Za-z0-9_-]{20,}",                    # Anthropic
    r"\bsk-(proj-|or-v1-)?[A-Za-z0-9_-]{20,}",         # OpenAI / OpenRouter
    r"\b(sk|rk)_(live|test)_[A-Za-z0-9]{16,}\b",       # Stripe
    r"\bwhsec_[A-Za-z0-9]{20,}\b",
    r"\bxox[abprs]-[A-Za-z0-9-]{10,}",                 # Slack
    r"\b(AKIA|ASIA)[A-Z0-9]{16}\b",                    # AWS access key id
    r"\bAIza[0-9A-Za-z_-]{35}\b",                      # Google API key
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",  # JWT
    r"(?i)(authorization:\s*(bearer|basic|token)\s+)[^\s'\"]+",
    r"(?i)\b([a-z][a-z0-9+.-]*://[^:/\s@]+:)[^@\s/]+(@)",  # user:pass@ in URLs
)]


def secret_values(env: Optional[Dict[str, str]] = None) -> List[str]:
    env = os.environ if env is None else env
    vals = {v for k, v in env.items() if SECRET_NAME.search(k) and v and len(v) >= MIN_SECRET_LEN}
    return sorted(vals, key=len, reverse=True)  # longest first, so substrings don't half-mask


def redact(text: str, extra: Iterable[str] = ()) -> str:
    if not text:
        return text
    for v in list(extra) + secret_values():
        if v and len(v) >= MIN_SECRET_LEN:
            text = text.replace(v, MASK)
    for p in PATTERNS:
        if p.groups >= 2 and "authorization" in p.pattern:
            text = p.sub(lambda m: m.group(1) + MASK, text)
        elif p.groups >= 2 and "://" in p.pattern:
            text = p.sub(lambda m: m.group(1) + MASK + m.group(2), text)
        else:
            text = p.sub(MASK, text)
    return text
