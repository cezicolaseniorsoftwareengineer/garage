"""Gera openapi.json exportável a partir da app FastAPI.
Versão 2: corrige import path.
Rodar: python tools/generate_openapi_v2.py
Saída: Garage/openapi.json
"""
import json
import os
import sys

# Ajusta path para importar a aplicação
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ensure the `Garage` package modules (and its `app` subpackage) are importable
GARAGE_DIR = os.path.join(ROOT, 'Garage')
if GARAGE_DIR not in sys.path:
    sys.path.insert(0, GARAGE_DIR)

from app.main import app

out_path = os.path.join(ROOT, 'Garage', 'openapi.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(app.openapi(), f, ensure_ascii=False, indent=2)

print(f"OpenAPI exported to: {out_path}")
