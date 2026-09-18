# -*- coding: utf-8 -*-
"""Report Chinese literals in tank_gui.py that are NOT wrapped in tr(...)."""
import io
import os
import re
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "tank_gui.py")
CJK = re.compile(r"[\u4e00-\u9fff]")
src = io.open(SRC, encoding="utf-8").read()
lines = src.splitlines(keepends=True)
toks = [t for t in tokenize.generate_tokens(io.StringIO(src).readline)
        if t.type not in {tokenize.COMMENT, tokenize.NL, tokenize.ENCODING}]

inside = set()          # 被 tr() 包住的 STRING token 下标
i = 0
while i < len(toks) - 1:
    t = toks[i]
    if t.type == tokenize.NAME and t.string == "tr" and toks[i + 1].string == "(":
        depth = 0
        j = i + 1
        while j < len(toks):
            if toks[j].string == "(":
                depth += 1
            elif toks[j].string == ")":
                depth -= 1
                if depth == 0:
                    break
            if toks[j].type == tokenize.STRING:
                inside.add(j)
            j += 1
        i = j
    i += 1

bad = []
for k, t in enumerate(toks):
    if t.type != tokenize.STRING or k in inside or not CJK.search(t.string):
        continue
    prev = toks[k - 1] if k else None
    nxt = toks[k + 1] if k + 1 < len(toks) else None
    doc = (prev is None or prev.type in (tokenize.NEWLINE, tokenize.INDENT,
                                         tokenize.DEDENT)) and \
          nxt is not None and nxt.type == tokenize.NEWLINE
    if doc:
        continue
    bad.append((t.start[0], t.string[:90]))

print("未包 tr() 的中文字符串: %d" % len(bad))
for ln, s in bad:
    print("  line %4d  %s" % (ln, s.replace("\n", "\\n")))
