"""Test to confirm garage-0lw9 is the correct service and garage.onrender.com is broken."""

import requests

def test_url(url: str, name: str):
    print(f"\n{'='*60}")
    print(f"TESTANDO: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    try:
        r = requests.get(url + "/health", timeout=10, allow_redirects=True)
        print(f"Status: {r.status_code}")

        if r.status_code == 200:
            data = r.json()
            print(f"✅ FUNCIONANDO")
            print(f"   Persistence: {data.get('persistence')}")
            print(f"   Database: {data.get('database')}")
            print(f"   Challenges: {data.get('challenges_loaded')}")
            print(f"   Framework: FastAPI (confirmado)")
            return True
        else:
            print(f"❌ ERRO HTTP {r.status_code}")
            print(f"   Response: {r.text[:200]}")
            return False

    except requests.exceptions.SSLError as exc:
        print(f"❌ ERRO SSL: {exc}")
        return False
    except requests.exceptions.ConnectionError as exc:
        print(f"❌ ERRO CONEXÃO: {exc}")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ TIMEOUT (servidor não respondeu em 10s)")
        return False
    except Exception as exc:
        print(f"❌ ERRO: {type(exc).__name__}: {exc}")
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("DIAGNÓSTICO - Serviços Render do Garage")
    print("="*60)

    correct = test_url("https://garage-0lw9.onrender.com", "SERVIÇO CORRETO (garage-0lw9)")
    broken = test_url("https://garage.onrender.com", "DOMÍNIO PÚBLICO (garage)")

    print(f"\n{'='*60}")
    print("RESUMO")
    print(f"{'='*60}")

    if correct and not broken:
        print("✅ garage-0lw9.onrender.com → FUNCIONANDO (FastAPI + Neon)")
        print("❌ garage.onrender.com → QUEBRADO (Django antigo)")
        print("\n⚠️  AÇÃO NECESSÁRIA:")
        print("   1. Acesse render.com/dashboard")
        print("   2. Encontre o serviço 'garage-0lw9'")
        print("   3. Settings → Custom Domains → Adicione 'garage.onrender.com'")
        print("   4. Delete ou pause o serviço Django antigo")

    elif correct and broken:
        print("✅ Ambos funcionando (redundância)")
        print("   Pode ser que garage.onrender.com já tenha sido corrigido")

    elif not correct and broken:
        print("⚠️  problema invertido — garage.onrender.com funciona mas garage-0lw9 não")
        print("   Investigue o serviço garage-0lw9 no Render")

    else:
        print("❌ AMBOS QUEBRADOS — problema crítico de infraestrutura")
        print("   Contate suporte do Render imediatamente")
