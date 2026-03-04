# -*- coding: utf-8 -*-
import re

with open('Garage/scripts/test_payment_flow_e2e.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'# PASSO 7.*?else:\n    print\(f"  \{SKIP\} Sem player token ou user_id"\)'
replacement = '''# PASSO 7 — PIX checkout (DESATIVADO PARA NÃO GERAR SPAM NO ASAAS)
# ============================================================
step(7, "PIX CHECKOUT — ignorado para não gerar falsos clientes recorrentes")
print(f"  {INFO} Checkout ignorado sob solicitação. Utilizamos links diretos do Asaas.")'''

text = re.sub(pattern, replacement, text, flags=re.DOTALL)

with open('Garage/scripts/test_payment_flow_e2e.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('E2E script updated.')
