import pytest


def test_criar_cliente_formata_telefone_e_email(client):
    r = client.post("/api/clientes", json={"nome": "  Ana Lima ", "telefone": "85 9 0000-0003", "email": " ANA@Exemplo.com "})
    assert r.status_code == 201
    c = r.json()
    assert c["nome"] == "Ana Lima"
    assert c["telefone"] == "(85) 90000-0003"
    assert c["email"] == "ana@exemplo.com"
    assert c["quantidade_veiculos"] == 0
    assert c["cliente_desde"]


def test_telefone_fixo_com_10_digitos(client):
    r = client.post("/api/clientes", json={"nome": "Ana", "telefone": "8532221111"})
    assert r.json()["telefone"] == "(85) 3222-1111"


@pytest.mark.parametrize("corpo, trecho", [
    ({"nome": " ", "telefone": "85900000001"}, "nome"),
    ({"nome": "Ana", "telefone": "123"}, "Telefone"),
    ({"nome": "Ana", "telefone": "85900000001", "email": "sem-arroba"}, "E-mail"),
])
def test_cliente_invalido_422(client, corpo, trecho):
    r = client.post("/api/clientes", json=corpo)
    assert r.status_code == 422
    assert trecho in r.json()["detail"]


def test_email_repetido_409_mas_o_proprio_cliente_pode_manter(client, cliente):
    outro = {"nome": "Outra", "telefone": "85900000002", "email": "MARINA@exemplo.com"}
    assert client.post("/api/clientes", json=outro).status_code == 409
    r = client.put(f"/api/clientes/{cliente['id']}", json={"nome": "Marina S.", "telefone": "85900000001",
                                                           "email": "marina@exemplo.com"})
    assert r.status_code == 200
    assert r.json()["nome"] == "Marina S."


def test_listar_e_filtrar_por_nome(client, cliente):
    client.post("/api/clientes", json={"nome": "Luís Araújo", "telefone": "85900000006"})
    assert [c["nome"] for c in client.get("/api/clientes").json()] == ["Luís Araújo", "Marina Souza"]
    assert [c["nome"] for c in client.get("/api/clientes?nome=araujo").json()] == ["Luís Araújo"]


def test_consultar_atualizar_e_404(client, cliente, veiculo):
    assert client.get(f"/api/clientes/{cliente['id']}").json()["quantidade_veiculos"] == 1
    assert client.get("/api/clientes/99").status_code == 404
    assert client.put("/api/clientes/99", json={"nome": "X", "telefone": "85900000001"}).status_code == 404


def test_excluir_cliente_com_veiculo_409(client, cliente, veiculo):
    assert client.delete(f"/api/clientes/{cliente['id']}").status_code == 409
    client.delete(f"/api/veiculos/{veiculo['id']}")
    assert client.delete(f"/api/clientes/{cliente['id']}").status_code == 204
    assert client.delete(f"/api/clientes/{cliente['id']}").status_code == 404


def test_veiculo_com_cliente_inexistente_422(client):
    r = client.post("/api/veiculos", json={"placa": "QRS4F21", "marca": "VW", "modelo": "Gol", "ano": 2022, "cliente_id": 99})
    assert r.status_code == 422


def test_veiculos_do_cliente(client, cliente, veiculo):
    r = client.get(f"/api/clientes/{cliente['id']}/veiculos")
    assert [v["placa"] for v in r.json()] == ["QRS4F21"]
    assert client.get("/api/clientes/99/veiculos").status_code == 404


def test_historico_do_cliente(client, cliente, os_corpo):
    client.post("/api/ordens-servico", json={**os_corpo, "data_abertura": "2026-05-12T09:00:00",
                                            "data_previsao": None, "status": "ENTREGUE"})
    client.post("/api/ordens-servico", json=os_corpo)
    r = client.get(f"/api/clientes/{cliente['id']}/historico")
    assert [o["id"] for o in r.json()] == [2, 1]
    assert client.get("/api/clientes/99/historico").status_code == 404
