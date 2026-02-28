"""E2E test for admin DELETE user endpoint."""
import urllib.request
import json

BASE = "http://localhost:8000"


def post(url, data):
    req = urllib.request.Request(
        BASE + url,
        json.dumps(data).encode(),
        {"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())


def api(method, url, token):
    req = urllib.request.Request(
        BASE + url,
        method=method,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def main():
    # 1. Login admin
    tk = post("/api/auth/login", {"username": "cezar", "password": "cnz640064"})["access_token"]
    print("LOGIN OK")

    # 2. Listar
    users = api("GET", "/api/admin/users", tk)
    print(f"TOTAL USERS: {len(users)}")

    # 3. Encontrar tmpdeltest
    target = next((u for u in users if u["username"] == "tmpdeltest"), None)
    if not target:
        print("tmpdeltest NAO ENCONTRADO — ja foi deletado ou nunca existiu.")
        return

    uid = target["id"]
    print(f"tmpdeltest ENCONTRADO: id={uid}")

    # 4. Deletar
    resp = api("DELETE", f"/api/admin/users/{uid}", tk)
    print(f"DELETE RESP: {resp}")

    # 5. Confirmar
    after = api("GET", "/api/admin/users", tk)
    gone = not any(u["username"] == "tmpdeltest" for u in after)
    print(f"Total apos delete: {len(after)}")
    print("RESULTADO: PASSOU ✅" if gone else "RESULTADO: FALHOU ❌")


if __name__ == "__main__":
    main()
