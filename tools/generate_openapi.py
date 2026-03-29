"""Gera openapi.json exportável a partir da app FastAPI.
Rodar: python tools/generate_openapi.py
Saída: Garage/openapi.json
"""
import json
import os
import sys

# Ajusta path para importar a aplicação
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Garage.app.main import app

out_path = os.path.join(ROOT, 'Garage', 'openapi.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(app.openapi(), f, ensure_ascii=False, indent=2)

print(f"OpenAPI exported to: {out_path}")
