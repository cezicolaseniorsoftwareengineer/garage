#!/usr/bin/env python3
"""
Runner local que simula/orquestra envio de prompts aos modelos configurados em `.local/cezicola_policy.yaml`.
Não envia nada para GitHub; registra localmente em `.local/cezicola_usage.log`.
"""
import os
import sys
import yaml
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / '.local'
POLICY = LOCAL / 'cezicola_policy.yaml'
USAGE_LOG = LOCAL / 'cezicola_usage.log'

def load_policy():
    if not POLICY.exists():
        raise SystemExit('Missing local policy. Run tools/install_local_env.py')
    return yaml.safe_load(POLICY.read_text(encoding='utf-8'))

def select_model_for_prompt(policy, prompt: str):
    # Strategy: prefer explicit model in policy by role, else round-robin through pref list
    prefs = policy.get('model_preferences', [])
    # Simple round-robin by timestamp
    idx = int(datetime.utcnow().timestamp()) % max(1, len(prefs))
    return prefs[idx]

def simulate_call(model_name: str, prompt: str):
    # Emulate invocation: do NOT call external APIs.
    LOCAL.mkdir(exist_ok=True)
    now = datetime.utcnow().isoformat() + 'Z'
    entry = f"{now} | model={model_name} | prompt_preview={prompt[:120].replace('\n',' ')}\n"
    with open(USAGE_LOG, 'a', encoding='utf-8') as f:
        f.write(entry)
    print(f"[SIM] Routed to {model_name}. Logged to {USAGE_LOG}")

def main():
    if len(sys.argv) < 2:
        print('Usage: cezicola_local_runner.py "<prompt text>"')
        sys.exit(1)
    prompt = sys.argv[1]
    policy = load_policy()
    model = select_model_for_prompt(policy, prompt)
    simulate_call(model, prompt)

if __name__ == '__main__':
    main()
