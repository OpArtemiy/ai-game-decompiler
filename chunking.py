"""Split big source files into parts at natural boundaries so every part fits in one AI call."""
import re

from textutil import depth_before_lines


def split_code(text, limit):
    """Return parts whose concatenation is exactly `text`. Prefers cutting at blank lines with a low brace depth."""
    if len(text) <= limit:
        return [text]
    lines = text.split('\n')
    n = len(lines)
    depth = depth_before_lines(text)
    offs = [0]
    for ln in lines:
        offs.append(offs[-1] + len(ln) + 1)

    chunks, s = [], 0
    while s < n:
        if offs[n] - offs[s] <= limit + 1:
            end = n
        else:
            lo, hi = offs[s] + int(limit * 0.5), offs[s] + limit
            cands = [i for i in range(s + 1, n) if lines[i].strip() == '' and lo <= offs[i] and offs[i + 1] <= hi]
            if cands:
                end = min(cands, key=lambda i: (depth[i], -i)) + 1
            else:
                fits = [i for i in range(s + 1, n) if offs[i] <= hi]
                end = fits[-1] if fits else s + 1
        chunks.append('\n'.join(lines[s:end]) + ('\n' if end < n else ''))
        s = end
    return chunks


def header_context(text, max_chars=1200):
    """The beginning of the file up to the first type declaration (usings, namespace, class line)."""
    out = []
    for ln in text.split('\n')[:80]:
        out.append(ln)
        if re.search(r'\b(class|struct|interface|enum)\b', ln) and not ln.strip().startswith(('//', '*', '/*')):
            break
    return '\n'.join(out)[:max_chars]
