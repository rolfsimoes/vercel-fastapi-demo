import pytest


def test_criar_os_devolve_dados_do_veiculo_e_do_cliente(client, os_corpo):
    r = client.post("/api/ordens-servico", json=os_corpo)
    assert r.status_code == 201
    os_ = r.json()
    assert os_["id"] == 1
    assert os_["placa"] == "QRS4F21"
    assert os_["veiculo"] == "Volkswagen Gol 1.6"
    assert os_["cliente_nome"] == "Marina Souza"
    assert os_["cliente_telefone"] == "(85) 90000-0001"
    assert os_["valor_total"] == 340.0


def test_criar_os_usa_valores_padrao(client, veiculo):
    r = client.post("/api/ordens-servico", json={"veiculo_id": veiculo["id"], "problema_relatado": "Ruído"})
    assert r.status_code == 201
    os_ = r.json()
    assert os_["status"] == "ORCAMENTO"
    assert os_["quilometragem"] == 82300  # vem do veículo
    assert os_["data_abertura"] is not None
    assert os_["valor_total"] == 0


@pytest.mark.parametrize("mudanca, trecho", [
    ({"veiculo_id": 999}, "Veículo não encontrado"),
    ({"problema_relatado": "   "}, "problema relatado"),
    ({"quilometragem": -1}, "quilometragem"),
    ({"valor_total": -5}, "valor total"),
    ({"data_conclusao": "2026-11-10T08:00:00"}, "conclusão"),
    ({"data_previsao": "2026-11-10T08:00:00"}, "previsão"),
    ({"data_abertura": "2026-11-11T08:10:00Z"}, "fuso horário"),
])
def test_criar_os_invalida_422(client, os_corpo, mudanca, trecho):
    r = client.post("/api/ordens-servico", json={**os_corpo, **mudanca})
    assert r.status_code == 422
    assert trecho in r.json()["detail"]


def test_status_desconhecido_422(client, os_corpo):
    assert client.post("/api/ordens-servico", json={**os_corpo, "status": "QUEBRADA"}).status_code == 422


def test_conclusao_igual_a_abertura_e_aceita(client, os_corpo):
    corpo = {**os_corpo, "data_conclusao": os_corpo["data_abertura"]}
    assert client.post("/api/ordens-servico", json=corpo).status_code == 201


def test_consultar_os(client, os_corpo):
    client.post("/api/ordens-servico", json=os_corpo)
    assert client.get("/api/ordens-servico/1").json()["problema_relatado"] == "Barulho ao frear"
    r = client.get("/api/ordens-servico/99")
    assert r.status_code == 404
    assert r.json()["detail"] == "Ordem de serviço não encontrada."


def test_atualizar_os_mantem_abertura_quando_omitida(client, os_corpo):
    client.post("/api/ordens-servico", json=os_corpo)
    novo = {k: v for k, v in os_corpo.items() if k != "data_abertura"}
    r = client.put("/api/ordens-servico/1", json={**novo, "status": "PRONTA", "data_conclusao": "2026-11-11T16:00:00"})
    assert r.status_code == 200
    assert r.json()["status"] == "PRONTA"
    assert r.json()["data_abertura"] == "2026-11-11T08:10:00"
    assert client.put("/api/ordens-servico/99", json=novo).status_code == 404


def test_excluir_os(client, os_corpo):
    client.post("/api/ordens-servico", json=os_corpo)
    assert client.delete("/api/ordens-servico/1").status_code == 204
    assert client.get("/api/ordens-servico/1").status_code == 404
    assert client.delete("/api/ordens-servico/1").status_code == 404


def test_veiculo_com_os_nao_pode_ser_excluido(client, os_corpo, veiculo):
    client.post("/api/ordens-servico", json=os_corpo)
    assert client.delete(f"/api/veiculos/{veiculo['id']}").status_code == 409
    client.delete("/api/ordens-servico/1")
    assert client.delete(f"/api/veiculos/{veiculo['id']}").status_code == 204


def test_filtros_da_listagem(client, os_corpo):
    client.post("/api/ordens-servico", json=os_corpo)
    outro = client.post("/api/clientes", json={"nome": "Luís Araújo", "telefone": "85900000006"}).json()
    carro = client.post("/api/veiculos", json={"placa": "BCD8N45", "marca": "Toyota", "modelo": "Corolla",
                                               "ano": 2022, "cliente_id": outro["id"]}).json()
    client.post("/api/ordens-servico", json={**os_corpo, "veiculo_id": carro["id"], "status": "ENTREGUE"})

    def ids(query):
        return [o["id"] for o in client.get(f"/api/ordens-servico{query}").json()]

    assert ids("") == [2, 1]
    assert ids("?status=EM_SERVICO") == [1]
    assert ids("?placa=qrs-4f21") == [1]
    assert ids("?cliente=marina") == [1]
    assert ids("?cliente=araujo") == [2]  # sem acento e sem maiúsculas
    assert ids("?status=ENTREGUE&cliente=marina") == []
    assert client.get("/api/ordens-servico?status=QUEBRADA").status_code == 422


def test_exportar_csv(client, os_corpo):
    client.post("/api/ordens-servico", json={**os_corpo, "problema_relatado": "=HYPERLINK(\"http://x\")"})
    client.post("/api/ordens-servico", json={**os_corpo, "status": "ENTREGUE"})
    r = client.get("/api/ordens-servico/exportar")  # não pode ser lido como {id}
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "ordens-servico.csv" in r.headers["content-disposition"]
    linhas = r.content.decode("utf-8-sig").strip().split("\r\n")
    assert linhas[0].startswith("OS;Placa;Veículo;Cliente")
    assert len(linhas) == 3
    assert "Entregue" in linhas[1]  # a mais recente primeiro
    assert "340,00" in linhas[1]
    assert "'=HYPERLINK" in linhas[2]  # fórmula neutralizada


def test_exportar_respeita_filtros(client, os_corpo):
    client.post("/api/ordens-servico", json=os_corpo)
    client.post("/api/ordens-servico", json={**os_corpo, "status": "ENTREGUE"})
    r = client.get("/api/ordens-servico/exportar?status=ENTREGUE")
    assert len(r.content.decode("utf-8-sig").strip().split("\r\n")) == 2
