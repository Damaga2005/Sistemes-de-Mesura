"""Arrel del projecte al davant del sys.path perquе `import web.server` /
`import app.*` funcionin a pytest (evita que `tests/web/` amagui el paquet `web`).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
