import app as backend

LOGIN = {"email": "teste@oficina.com.br", "senha": "senha-de-teste"}


def entrar(client):
    return client.post("/api/auth/login", json=LOGIN).json()["access_token"]


def test_login_e_me(client):
    r = client.post("/api/auth/login", json={**LOGIN, "email": " TESTE@oficina.com.br "})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert "senha" not in str(corpo["usuario"]) and "hash" not in str(corpo["usuario"])
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {corpo['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "teste@oficina.com.br"


def test_login_invalido_tem_a_mesma_mensagem(client):
    errada = client.post("/api/auth/login", json={**LOGIN, "senha": "errada"})
    desconhecido = client.post("/api/auth/login", json={"email": "x@y.com", "senha": "qualquer"})
    assert errada.status_code == desconhecido.status_code == 401
    assert errada.json() == desconhecido.json()


def test_me_sem_token_ou_com_token_ruim_401(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer inventado"}).status_code == 401


def test_me_com_sessao_expirada_401(client):
    token = entrar(client)
    backend.sessoes[token]["expira_em"] = backend.datetime.now() - backend.timedelta(seconds=1)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert token not in backend.sessoes


def test_senha_nao_fica_em_texto_puro(client):
    assert "senha-de-teste" not in str(backend.usuarios)


def test_esqueci_senha_responde_igual_para_qualquer_email(client):
    existe = client.post("/api/auth/esqueci-senha", json={"email": "teste@oficina.com.br"})
    nao_existe = client.post("/api/auth/esqueci-senha", json={"email": "ninguem@oficina.com.br"})
    assert existe.status_code == nao_existe.status_code == 200
    assert existe.json() == nao_existe.json()
    assert len(backend.tokens_recuperacao) == 1
    assert next(iter(backend.tokens_recuperacao)) not in existe.text


def test_esqueci_senha_com_email_invalido_422(client):
    assert client.post("/api/auth/esqueci-senha", json={"email": "abc"}).status_code == 422
