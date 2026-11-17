# Ordens de serviço, clientes, pesquisa, autenticação e exportação

Dados em memória (dicionários): tudo se perde ao reiniciar o servidor. O banco de dados vem depois.
Segue o padrão do `app.py` dos veículos: rotas em `/api`, nomes em português, erros com `HTTPException`.

## Como rodar

```bash
pip install -r requirements-dev.txt
uvicorn app:app --reload
```

Documentação interativa (Swagger): http://127.0.0.1:8000/api/docs
Testes dessas rotas: `pytest tests/test_ordens_servico.py tests/test_clientes.py tests/test_busca_e_veiculos.py tests/test_autenticacao.py`

Ao subir, o app carrega dados de demonstração do protótipo (Marina Souza, OS 1042 etc.) e um usuário de teste:
`recepcao@oficina.com.br` / `oficina123`. Para trocar, defina `ADMIN_EMAIL` e `ADMIN_SENHA`. **Troque antes de publicar.**

## O que está implementado aqui

| Guia | Rotas |
|---|---|
| 3.2 Ordens de Serviço | `GET/POST /api/ordens-servico`, `GET/PUT/DELETE /api/ordens-servico/{id}` |
| 3.6 Clientes | `GET/POST /api/clientes`, `GET/PUT/DELETE /api/clientes/{id}`, `GET /api/clientes/{id}/veiculos`, `GET /api/clientes/{id}/historico` |
| 3.7 Pesquisa e filtros | `?status=` `?placa=` `?cliente=` em ordens, `?placa=` em veículos, `?nome=` em clientes, `GET /api/busca?q=` |
| 3.8 Autenticação | `POST /api/auth/login`, `POST /api/auth/esqueci-senha`, `GET /api/auth/me` |
| 3.10 Exportação | `GET /api/ordens-servico/exportar` (CSV; aceita os mesmos filtros da listagem) |

Os veículos (3.1) continuam sendo o código que já existia, com três ajustes de relacionamento: filtro `?placa=`, `cliente_id` precisa existir
(422) e veículo com ordens de serviço não pode ser excluído (409). Quem fizer a 3.1 deve manter esses três pontos ao juntar.

## Harmonização: campos do front ↔ modelo relacional

Tabelas sugeridas (para quem fizer o banco). Colunas em `snake_case`, iguais aos campos do JSON.

```
cliente        id PK, nome NOT NULL, telefone NOT NULL, email UNIQUE NULL, cliente_desde DATE NOT NULL
veiculo        id PK, placa UNIQUE NOT NULL, marca, modelo, ano, quilometragem,
               cliente_id FK -> cliente (NULL, ON DELETE RESTRICT)
ordem_servico  id PK, veiculo_id FK -> veiculo (NOT NULL, ON DELETE RESTRICT),
               quilometragem, problema_relatado NOT NULL, servico NULL, mecanico NULL,
               data_abertura NOT NULL, data_previsao NULL, data_conclusao NULL,
               status CHECK (ORCAMENTO, EM_SERVICO, AGUARDANDO_PECA, PRONTA, ENTREGUE),
               observacoes NULL, valor_total NUMERIC(10,2) CHECK (>= 0),
               CHECK (data_conclusao IS NULL OR data_conclusao >= data_abertura)
```

A OS **não tem** `cliente_id`: o cliente é o dono do veículo (`ordem_servico → veiculo → cliente`). Assim não há como a OS
apontar um cliente diferente do dono do veículo.

Tela "Nova ordem" (protótipo) → API:

| Campo na tela | Vai para | Observação |
|---|---|---|
| Placa | `veiculo_id` | O front busca `GET /api/veiculos?placa=` e envia o `id` do veículo |
| Cliente, Veículo | (não são enviados) | Só exibição, preenchidos a partir do veículo. A resposta da OS traz `placa`, `veiculo`, `cliente_id`, `cliente_nome`, `cliente_telefone` |
| Quilometragem | `quilometragem` | Se omitida, vale a do cadastro do veículo |
| Problema relatado | `problema_relatado` | Obrigatório |
| Mecânico | `mecanico` | Texto livre. "A definir" na tela = `null` |
| Previsão | `data_previsao` | ISO, sem fuso: `2026-11-11T17:00:00`. "Hoje, 17:00" é formatação do front |
| (Entrada) | `data_abertura` | Se omitida, vale o momento atual |
| Coluna "Serviço" da lista | `servico` | Campo novo e opcional. Resumo exibido na lista; ver "Decisões abertas" |
| Observações (detalhe da OS) | `observacoes` | |
| Total | `valor_total` | Hoje informado no corpo; deve passar a ser a soma dos itens (3.3) |

Status: `ORCAMENTO` (Orçamento), `EM_SERVICO` (Em serviço), `AGUARDANDO_PECA` (Aguardando peça), `PRONTA` (Pronto/Prontas), `ENTREGUE` (Entregue).

Cliente: `telefone` é gravado como `(85) 90000-0001` (aceita qualquer formatação na entrada); `quantidade_veiculos` é calculado na
leitura ("2 veículos" na tela), não é coluna.

## Regras validadas (422 salvo indicação)

- OS: veículo existente, problema relatado preenchido, quilometragem e valor total não negativos, conclusão e previsão não anteriores
  à abertura, datas sem fuso horário, status dentro da lista.
- Cliente: nome, telefone com DDD (10 ou 11 dígitos), e-mail válido e único (409 se repetido).
- Exclusão: veículo com OS e cliente com veículos respondem 409.
- Login: 401 com a mesma mensagem para e-mail desconhecido e senha errada. `esqueci-senha` responde sempre igual.

## Decisões abertas (para combinar com o grupo)

1. **`servico` na OS.** O guia não tem esse campo, mas a lista do protótipo mostra "Troca de óleo e filtros" por OS. Quando os itens
   (3.3) existirem, ele pode virar um texto derivado dos itens.
2. **Dono do histórico.** Como a OS não guarda o cliente, trocar o dono de um veículo move o histórico dele para o novo dono. Se o
   histórico deve ficar com o dono da época, a OS precisa de `cliente_id` próprio.
3. **`valor_total`** é informado hoje; com os itens, passar a calcular e recusar valor manual.
4. **Status da OS** aceita qualquer troca pelo PUT. As transições permitidas ficam com a 3.5.
5. **Login** ainda não protege nenhuma rota; falta o fluxo de nova senha e o envio do e-mail de recuperação.
