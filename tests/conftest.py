import pytest
from fastapi.testclient import TestClient

import app as backend


# Cada teste começa com os dicionários vazios (sem os dados de demonstração)
# e só com o usuário de teste.
@pytest.fixture(autouse=True)
def limpar_dados():
    for store in (backend.veiculos, backend.clientes, backend.ordens, backend.usuarios,
                  backend.sessoes, backend.tokens_recuperacao):
        store.clear()
    backend.proximo_id = backend.proximo_cliente_id = backend.proximo_ordem_id = backend.proximo_usuario_id = 1
    backend.criar_usuario("Usuário", "teste@oficina.com.br", "senha-de-teste")


@pytest.fixture
def client():
    return TestClient(backend.app)


@pytest.fixture
def cliente(client):
    return client.post("/api/clientes", json={"nome": "Marina Souza", "telefone": "85900000001",
                                              "email": "marina@exemplo.com"}).json()


@pytest.fixture
def veiculo(client, cliente):
    return client.post("/api/veiculos", json={"placa": "QRS4F21", "marca": "Volkswagen", "modelo": "Gol 1.6",
                                              "ano": 2022, "quilometragem": 82300,
                                              "cliente_id": cliente["id"]}).json()


@pytest.fixture
def os_corpo(veiculo):
    return {"veiculo_id": veiculo["id"], "quilometragem": 82300, "problema_relatado": "Barulho ao frear",
            "mecanico": "Rafael", "data_abertura": "2026-11-11T08:10:00",
            "data_previsao": "2026-11-11T17:00:00", "status": "EM_SERVICO", "valor_total": 340.0}
