"""Offline assistant used when no API key is configured. Rule-based, runs anywhere."""
import ast
import operator
import re
from datetime import datetime

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos}


def safe_eval(expr):
    """Evaluate arithmetic only. No names, calls or attributes, so nothing can be executed."""
    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent too large")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.operand))
        raise ValueError("unsupported expression")
    return walk(ast.parse(expr, mode="eval"))


MATH_RE = re.compile(r"^[\d\s+\-*/().%^]+$")
JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "A SQL query walks into a bar, goes up to two tables and asks: \"Can I join you?\"",
    "There are 10 kinds of people: those who understand binary and those who don't.",
]
_joke_i = 0

HELP = """I'm running in **offline mode**, so I can only handle a few things:

- **Maths**: try `12 * (3 + 4)` or `what is 2^10`
- **Date and time**: ask "what time is it?"
- **Code snippets**: ask for a `python` or `javascript` example
- **Jokes**: say "tell me a joke"

To get full AI answers, set `ANTHROPIC_API_KEY` and restart the server."""

SNIPPETS = {
    "python": ("Here's a small Python example that reads a file and counts words:",
               "python", "from collections import Counter\n\nwith open('notes.txt', encoding='utf-8') as f:\n    words = f.read().lower().split()\n\nprint(Counter(words).most_common(5))"),
    "javascript": ("Here's a small JavaScript example that debounces a function:",
                   "javascript", "function debounce(fn, ms = 300) {\n  let t;\n  return (...args) => {\n    clearTimeout(t);\n    t = setTimeout(() => fn(...args), ms);\n  };\n}"),
}


def reply(message, now=None):
    global _joke_i
    text = message.strip()
    low = text.lower()
    now = now or datetime.now()
    if not text:
        return "Type a message and I'll reply."
    if re.match(r"^(hi|hello|hey|namaste)\b", low):
        return "Hello! I can do maths, tell the time, share code snippets and jokes. Type **help** to see everything."
    if low in {"help", "/help", "what can you do", "what can you do?"}:
        return HELP
    if "time" in low and re.search(r"\b(what|current|tell)\b", low):
        return f"It's **{now.strftime('%I:%M %p')}** right now."
    if re.search(r"\b(date|today|day is it)\b", low):
        return f"Today is **{now.strftime('%A, %d %B %Y')}**."
    if "joke" in low:
        out = JOKES[_joke_i % len(JOKES)]
        _joke_i += 1
        return out
    for lang, (intro, fence, code) in SNIPPETS.items():
        if lang in low or (lang == "javascript" and re.search(r"\bjs\b", low)):
            return f"{intro}\n\n```{fence}\n{code}\n```"
    expr = re.sub(r"^(what is|what's|calculate|calc|solve)\s+", "", low).rstrip("?= ").replace("^", "**")
    if expr and MATH_RE.match(expr) and re.search(r"\d", expr):
        try:
            value = safe_eval(expr)
            shown = int(value) if isinstance(value, float) and value.is_integer() else round(value, 8)
            return f"`{text.rstrip('?= ')}` = **{shown}**"
        except ZeroDivisionError:
            return "That divides by zero, which has no answer."
        except (ValueError, SyntaxError, OverflowError):
            return "I couldn't work that expression out. Check the brackets and operators."
    return ("I can't answer that in offline mode. I can do maths, date and time, code snippets and jokes. "
            "Type **help** for examples, or add an API key to get full answers.")
