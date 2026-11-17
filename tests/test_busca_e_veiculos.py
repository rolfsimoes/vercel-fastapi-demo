def test_filtro_de_veiculos_por_placa(client, veiculo):
    assert len(client.get("/api/veiculos?placa=qrs4f21").json()) == 1
    assert len(client.get("/api/veiculos?placa=QRS").json()) == 1
    assert client.get("/api/veiculos?placa=ZZZ").json() == []
    assert len(client.get("/api/veiculos").json()) == 1


def test_busca_por_placa(client, os_corpo):
    client.post("/api/ordens-servico", json=os_corpo)
    r = client.get("/api/busca?q=QRS4F21").json()
    assert [o["id"] for o in r["ordens"]] == [1]
    assert [v["placa"] for v in r["veiculos"]] == ["QRS4F21"]
    assert [c["nome"] for c in r["clientes"]] == ["Marina Souza"]  # dona do veículo


def test_busca_por_cliente(client, os_corpo):
    client.post("/api/ordens-servico", json=os_corpo)
    r = client.get("/api/busca?q=marina").json()
    assert [o["id"] for o in r["ordens"]] == [1]
    assert r["veiculos"] == []
    assert len(r["clientes"]) == 1


def test_busca_por_numero_da_os(client, os_corpo):
    client.post("/api/ordens-servico", json=os_corpo)
    assert [o["id"] for o in client.get("/api/busca?q=1").json()["ordens"]] == [1]
    assert [o["id"] for o in client.get("/api/busca?q=OS 1").json()["ordens"]] == [1]
    assert client.get("/api/busca?q=2").json()["ordens"] == []


def test_busca_sem_resultado_e_sem_termo(client, os_corpo):
    assert client.get("/api/busca?q=naoexiste").json() == {"ordens": [], "veiculos": [], "clientes": []}
    assert client.get("/api/busca?q=%20").status_code == 422
    assert client.get("/api/busca").status_code == 422
