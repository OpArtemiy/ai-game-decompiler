"""Sanity checks on the AI's reply. If a check fails, the original code is kept."""
import re

from textutil import brace_balance, public_names


def validate_clean(original, cleaned):
    if not cleaned.strip():
        return False, 'empty reply'
    if '```' in cleaned:
        return False, 'markdown fence left in the reply'
    lo, lc = len(original.strip()), len(cleaned.strip())
    if lo > 0 and lc < lo * 0.6:
        return False, 'reply much shorter than the original (maybe cut off)'
    if lc > lo * 2.5 + 200:
        return False, 'reply much longer than the original'
    if brace_balance(original) != brace_balance(cleaned):
        return False, 'braces do not balance like the original'
    missing = sorted(
        n for n in public_names(original)
        if not re.search(r'(?<![A-Za-z0-9_])' + re.escape(n) + r'(?![A-Za-z0-9_])', cleaned)
    )
    if missing:
        return False, 'public names missing: ' + ', '.join(missing[:4])
    return True, ''
