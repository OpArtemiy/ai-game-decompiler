"""Small text helpers for C# and Java source code."""
import re


def strip_noise(text):
    """Remove comments and string/char literals but keep every newline, so line numbers stay the same."""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        two = text[i:i + 2]
        if two == '//':
            while i < n and text[i] != '\n':
                i += 1
        elif two == '/*':
            j = text.find('*/', i + 2)
            j = n if j == -1 else j + 2
            out.append('\n' * text.count('\n', i, j))
            i = j
        elif two == '@"':
            i += 2
            while i < n:
                if text[i] == '"':
                    if text[i + 1:i + 2] == '"':
                        i += 2
                        continue
                    break
                if text[i] == '\n':
                    out.append('\n')
                i += 1
            i += 1
        elif c == '"':
            i += 1
            while i < n and text[i] != '"' and text[i] != '\n':
                if text[i] == '\\':
                    i += 1
                i += 1
            if i < n and text[i] == '"':
                i += 1
        elif c == "'":
            j = i + 1
            if j < n and text[j] == '\\':
                j += 2
            else:
                j += 1
            while j < n and text[j] != "'" and text[j] != '\n':
                j += 1
            i = j + 1 if j < n and text[j] == "'" else i + 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def brace_balance(text):
    s = strip_noise(text)
    return s.count('{') - s.count('}')


def depth_before_lines(text):
    """Brace depth at the start of every line (len == number of lines in text.split('\\n'))."""
    depth, result = 0, []
    for line in strip_noise(text).split('\n'):
        result.append(depth)
        depth += line.count('{') - line.count('}')
        if depth < 0:
            depth = 0
    return result


_KEYWORDS = {
    'get', 'set', 'add', 'remove', 'new', 'public', 'protected', 'internal', 'static', 'void', 'class',
    'struct', 'interface', 'enum', 'override', 'virtual', 'abstract', 'sealed', 'readonly', 'const',
    'partial', 'async', 'event', 'delegate', 'operator', 'implicit', 'explicit', 'this', 'where',
    'return', 'if', 'else', 'for', 'foreach', 'while', 'switch', 'case', 'default', 'using', 'namespace',
}
_MOD = re.compile(r'^\s*(?:\[[^\]]*\]\s*)*(?:public|protected|internal)\b(.*)$')
_LAST = re.compile(r'([A-Za-z_]\w*)\s*(?:<[^<>]*>)?\s*$')


def public_names(text):
    """Names of public/protected/internal members and types declared in the code."""
    names = set()
    for line in strip_noise(text).split('\n'):
        m = _MOD.match(line)
        if not m:
            continue
        prefix = re.split(r'[({=;:]', m.group(1), 1)[0]
        m2 = _LAST.search(prefix)
        if m2 and m2.group(1) not in _KEYWORDS:
            names.add(m2.group(1))
    return names


def estimate_tokens(chars, parts=1):
    """Rough (input, output) token estimate for cleaning `chars` characters of code in `parts` calls."""
    base = chars / 3.2
    return int(base + 450 * parts), int(base * 1.15)


def strip_fences(text):
    t = text.strip('\r\n')
    t = re.sub(r'^\s*```[A-Za-z#+]*[ \t]*\n', '', t)
    t = re.sub(r'\n[ \t]*```\s*$', '', t)
    return t


def fit_ends(cleaned, original):
    """Give the cleaned text the same leading and trailing line breaks as the original part."""
    lead = re.match(r'[\r\n]*', original).group(0)
    trail = re.search(r'\s*$', original).group(0)
    return lead + cleaned.strip('\r\n').rstrip() + trail
