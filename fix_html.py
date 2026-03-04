# -*- coding: utf-8 -*-
import re

def update_account_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Substitute the modal form portion
    pattern_form = r'<p class="modal-title" style="font-size:\.82rem; margin-bottom:\.8rem;">Forma de pagamento</p>.*?<button class="btn btn--renew" style="width:100%" id="btn-gen-pix">Continuar pagamento</button>'
    replacement_form = '<button class="btn btn--renew" style="width:100%" id="btn-gen-pix">Ir para Pagamento Seguro</button>'
    content = re.sub(pattern_form, replacement_form, content, flags=re.DOTALL)

    # 2. Remove step 2 and step 3 HTML
    pattern_steps = r'<!-- Step 2: QR Code -->.*?<!-- Step 3: Card checkout -->.*?\</div>\s*</div>'
    content = re.sub(pattern_steps, '', content, flags=re.DOTALL)

    # 3. Replace the PIX logic with CHECKOUT_LINKS logic
    pattern_js = r"// Apply mask on input.*?function startPolling\(paymentId, method = 'pix'\) \{.*?\}, 5000\);\n\s*\}"
    replacement_js = '''        const CHECKOUT_LINKS = {
            monthly: "https://www.asaas.com/c/k8xqrulte259faq2",
            annual: "https://www.asaas.com/c/6l46uwz5qxlygofc",
        };

        document.getElementById('btn-gen-pix').addEventListener('click', () => {
            const link = CHECKOUT_LINKS[selectedPlan] || CHECKOUT_LINKS.monthly;
            window.open(link, '_blank', 'noopener');
            closeRenewModal();
        });'''
    content = re.sub(pattern_js, replacement_js, content, flags=re.DOTALL)

    # Reset modal init
    content = re.sub(r"document\.getElementById\('step-plan'\)\.style\.display = '';.*?document\.getElementById\('renew-modal'\)\.classList\.add\('open'\);", "document.getElementById('renew-modal').classList.add('open');", content, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

update_account_html('Garage/app/static/account.html')
update_account_html('Garage/static/account.html')
print("HTML updating finished.")

