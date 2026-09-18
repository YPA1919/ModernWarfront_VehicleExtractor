# -*- coding: utf-8 -*-
"""Find widgets that stick out of the right-hand notebook panel (clipped text)."""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "pylibs"))

import tkinter as tk
import tank_gui as G

app = G.App(os.path.join(HERE, "sample"))
app.update_idletasks()
app.update()

nb = app.nb
for tab in nb.tabs():
    name = nb.tab(tab, "text")
    nb.select(tab)
    app.update_idletasks()
    app.update()
    frame = app.nametowidget(tab)
    left = frame.winfo_rootx()
    right = left + frame.winfo_width()
    bad = []

    def walk(w):
        for c in w.winfo_children():
            try:
                cr = c.winfo_rootx() + c.winfo_width()
                if c.winfo_ismapped() and cr > right + 1:
                    txt = ""
                    try:
                        txt = c.cget("text")
                    except Exception:
                        pass
                    bad.append((c.winfo_class(), txt, cr - right))
            except Exception:
                pass
            walk(c)

    walk(frame)
    print("tab %-8s width=%d  overflowing widgets: %d" % (name, frame.winfo_width(), len(bad)))
    for cls, txt, over in bad:
        print("    %-14s +%dpx  %r" % (cls, over, txt))

app.destroy()
