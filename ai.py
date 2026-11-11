"""Calls to the AI model (Amazon Bedrock), prompts and the overview generator."""
import threading
import time

import config

RULES = {
    'csharp': (
        'You are cleaning up a decompiled C# source file from a Unity game. '
        'Rename ONLY local variables, parameters and private members whose names are meaningless '
        '(for example num, num2, text3, array, flag). '
        'NEVER rename types, namespaces, or public, protected or internal members, and never rename anything '
        'declared outside this code, because other files refer to those names. '
        'Add short helpful comments that explain intent. '
        'Do not change logic, order, types, string literals or numbers. '
        'Return ONLY the complete code of the part you are given, without explanations and without markdown fences.'
    ),
    'java': (
        'You are cleaning up a decompiled Java source file (from an Android app or game). '
        'Rename ONLY local variables and parameters whose names are meaningless (for example i2, str2, obj). '
        'NEVER rename classes, packages, fields or methods, because other files refer to those names. '
        'Add short helpful comments that explain intent. '
        'Do not change logic, order, types, string literals or numbers. '
        'Return ONLY the complete code of the part you are given, without explanations and without markdown fences.'
    ),
}


def build_prompt(language, name, code, part=1, parts=1, header=''):
    prompt = RULES[language]
    if parts > 1:
        prompt += (
            f'\n\nThis is part {part} of {parts} of the file {name}. For context only, this is the beginning of '
            f'the file (do not repeat it in your reply):\n{header}\n\nNow clean ONLY the following part:'
        )
    return prompt + '\n\n' + code


_client = None
_lock = threading.Lock()
_last_call = [0.0]


def _get_client():
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config
        _client = boto3.client(
            'bedrock-runtime', region_name=config.REGION,
            config=Config(read_timeout=300, retries={'max_attempts': 10, 'mode': 'adaptive'}),
        )
    return _client


def _wait_turn():
    if config.MIN_INTERVAL <= 0:
        return
    with _lock:
        gap = config.MIN_INTERVAL - (time.time() - _last_call[0])
        if gap > 0:
            time.sleep(gap)
        _last_call[0] = time.time()


def ask(prompt, model=None, max_tokens=8000):
    """Returns (text, {'input': n, 'output': n}). Raises on failure."""
    for attempt in range(1, 4):
        _wait_turn()
        try:
            r = _get_client().converse(
                modelId=model or config.MODEL,
                messages=[{'role': 'user', 'content': [{'text': prompt}]}],
                inferenceConfig={'maxTokens': max_tokens},
            )
            break
        except Exception as e:
            text = f'{type(e).__name__} {e}'
            if attempt < 3 and ('Throttling' in text or 'TooManyRequests' in text):
                time.sleep(20 * attempt)
                continue
            raise
    if r.get('stopReason') == 'max_tokens':
        raise ValueError('reply was cut off (max_tokens)')
    blocks = r['output']['message']['content']
    text = ''.join(b.get('text', '') for b in blocks)
    u = r.get('usage', {})
    return text, {'input': u.get('inputTokens', 0), 'output': u.get('outputTokens', 0)}


def make_overview(summary, ask_fn=None):
    ask_fn = ask_fn or ask
    prompt = (
        'From these class and method declarations of a decompiled game, write a concise OVERVIEW.md in Markdown: '
        'the likely type of game, the main systems, and which files belong to each. '
        'State only what the code supports.\n\n' + summary
    )
    text, usage = ask_fn(prompt, model=config.MODEL, max_tokens=3000)
    return text, usage
