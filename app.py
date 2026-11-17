# Um app FastAPI pequeno. A Vercel roda ele e serve a página da pasta public/.
# Esta versão acrescenta: 3.2 Ordens de Serviço, 3.6 Clientes, 3.7 Pesquisa e filtros,
# 3.8 Autenticação e 3.10 Exportação. Veículos seguem o código que já existia,
# com os ajustes de relacionamento descritos na seção de veículos.
import csv
import hashlib
import hmac
import io
import math
import os
import re
import secrets
import unicodedata
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# A documentação fica em /api, assim todo o app mora em /api.
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

# ---------------------------------------------------------------------------
# Dados em memória: um dicionário que liga o id ao registro, para cada entidade.
# Eles somem quando o servidor reinicia. O banco de dados vem depois.
# ---------------------------------------------------------------------------
veiculos = {}
clientes = {}
ordens = {}
usuarios = {}
sessoes = {}               # token de acesso -> {"usuario_id", "expira_em"}
tokens_recuperacao = {}    # token de recuperação de senha -> {"usuario_id", "expira_em"}

proximo_id = 1             # veículos
proximo_cliente_id = 1
proximo_ordem_id = 1
proximo_usuario_id = 1


# Tira acentos e maiúsculas, para a busca achar "Araújo" ao digitar "araujo".
def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()


# Texto opcional: vazio vira None.
def limpar(texto):
    texto = (texto or "").strip()
    return texto or None


# ---------------------------------------------------------------------------
# Veículos: cadastrar, listar, consultar, atualizar e excluir.
# Ajustes sobre o original: filtro ?placa= (3.7), o cliente_id precisa existir
# e veículo com ordens de serviço não pode ser excluído (409).
# ---------------------------------------------------------------------------

# Placa no formato antigo ABC1234 ou no Mercosul ABC1D23.
PLACA = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")


# O corpo de POST e PUT /api/veiculos, por exemplo
# {"placa": "QRS4F21", "marca": "Volkswagen", "modelo": "Gol 1.6",
#  "ano": 2022, "quilometragem": 82300, "cliente_id": 1}
class Veiculo(BaseModel):
    placa: str
    marca: str
    modelo: str
    ano: int
    quilometragem: int = 0
    cliente_id: int | None = None


# Confere os campos e devolve a placa em maiúsculas, sem "-".
def validar_veiculo(entrada: Veiculo):
    placa = entrada.placa.upper().replace("-", "").strip()
    if not PLACA.match(placa):
        raise HTTPException(status_code=422, detail="Placa inválida. Use ABC1234 ou ABC1D23.")
    if entrada.marca.strip() == "" or entrada.modelo.strip() == "":
        raise HTTPException(status_code=422, detail="Marca e modelo são obrigatórios.")
    if entrada.ano < 1900 or entrada.ano > 2100:
        raise HTTPException(status_code=422, detail="Ano inválido.")
    if entrada.quilometragem < 0:
        raise HTTPException(status_code=422, detail="A quilometragem não pode ser negativa.")
    if entrada.cliente_id is not None and entrada.cliente_id not in clientes:
        raise HTTPException(status_code=422, detail="Cliente não encontrado.")
    return placa


# Devolve o veículo, ou responde 404 se não existe nenhum com esse id.
def buscar_veiculo(id: int):
    if id not in veiculos:
        raise HTTPException(status_code=404, detail="Veículo não encontrado.")
    return veiculos[id]


# True se a placa contém o texto buscado ("qrs-4f" acha QRS4F21).
def placa_confere(placa, busca):
    busca = re.sub(r"[^A-Z0-9]", "", busca.upper())
    return busca != "" and busca in (placa or "")


# GET /api/veiculos  ou  GET /api/veiculos?placa=QRS4F21
@app.get("/api/veiculos")
def listar_veiculos(placa: str | None = None):
    encontrados = list(veiculos.values())
    if placa:
        encontrados = [v for v in encontrados if placa_confere(v["placa"], placa)]
    return encontrados


# GET /api/veiculos/1
@app.get("/api/veiculos/{id}")
def consultar_veiculo(id: int):
    return buscar_veiculo(id)


# POST /api/veiculos
@app.post("/api/veiculos", status_code=201)
def cadastrar_veiculo(entrada: Veiculo):
    global proximo_id
    placa = validar_veiculo(entrada)
    for veiculo in veiculos.values():
        if veiculo["placa"] == placa:
            raise HTTPException(status_code=409, detail="Já existe um veículo com essa placa.")

    veiculo = {"id": proximo_id, **entrada.model_dump(), "placa": placa}
    veiculos[proximo_id] = veiculo
    proximo_id += 1
    return veiculo


# PUT /api/veiculos/1
@app.put("/api/veiculos/{id}")
def atualizar_veiculo(id: int, entrada: Veiculo):
    buscar_veiculo(id)
    placa = validar_veiculo(entrada)
    for veiculo in veiculos.values():
        if veiculo["placa"] == placa and veiculo["id"] != id:
            raise HTTPException(status_code=409, detail="Já existe um veículo com essa placa.")

    veiculo = {"id": id, **entrada.model_dump(), "placa": placa}
    veiculos[id] = veiculo
    return veiculo


# DELETE /api/veiculos/1
# Um veículo com ordens de serviço não pode ser excluído (409).
@app.delete("/api/veiculos/{id}", status_code=204)
def excluir_veiculo(id: int):
    buscar_veiculo(id)
    for ordem in ordens.values():
        if ordem["veiculo_id"] == id:
            raise HTTPException(
                status_code=409,
                detail="Não é possível excluir: o veículo possui ordens de serviço.",
            )
    del veiculos[id]


# ---------------------------------------------------------------------------
# 3.6 Clientes: cadastrar, listar, consultar, atualizar e excluir, mais os
# veículos e o histórico de ordens de cada cliente.
# ---------------------------------------------------------------------------

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# O corpo de POST e PUT /api/clientes, por exemplo
# {"nome": "Marina Souza", "telefone": "(85) 90000-0001",
#  "email": "marina@exemplo.com", "cliente_desde": "2024-03-10"}
class Cliente(BaseModel):
    nome: str
    telefone: str
    email: str | None = None
    cliente_desde: date | None = None


# Confere os campos e devolve os dados prontos para gravar: telefone no formato
# (85) 90000-0001 e e-mail em minúsculas. Na atualização, o id do próprio cliente
# é ignorado na checagem de e-mail repetido.
def validar_cliente(entrada: Cliente, id: int | None = None):
    nome = entrada.nome.strip()
    if nome == "":
        raise HTTPException(status_code=422, detail="O nome é obrigatório.")

    digitos = re.sub(r"\D", "", entrada.telefone)
    if len(digitos) not in (10, 11):
        raise HTTPException(status_code=422, detail="Telefone inválido. Use DDD + número, ex.: (85) 90000-0001.")
    corte = 7 if len(digitos) == 11 else 6
    telefone = f"({digitos[:2]}) {digitos[2:corte]}-{digitos[corte:]}"

    email = limpar(entrada.email)
    if email is not None:
        email = email.lower()
        if not EMAIL.match(email):
            raise HTTPException(status_code=422, detail="E-mail inválido.")
        for cliente in clientes.values():
            if cliente["email"] == email and cliente["id"] != id:
                raise HTTPException(status_code=409, detail="Já existe um cliente com esse e-mail.")

    return {"nome": nome, "telefone": telefone, "email": email,
            "cliente_desde": entrada.cliente_desde or date.today()}


# Devolve o cliente, ou responde 404 se não existe nenhum com esse id.
def buscar_cliente(id: int):
    if id not in clientes:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return clientes[id]


# Veículos de um cliente.
def veiculos_do_cliente(cliente_id: int):
    return [v for v in veiculos.values() if v.get("cliente_id") == cliente_id]


# O cliente com a quantidade de veículos (a tela mostra "2 veículos").
# A quantidade é calculada na leitura, não é gravada.
def cliente_completo(cliente):
    return {**cliente, "quantidade_veiculos": len(veiculos_do_cliente(cliente["id"]))}


# GET /api/clientes  ou  GET /api/clientes?nome=Marina
@app.get("/api/clientes")
def listar_clientes(nome: str | None = None):
    encontrados = list(clientes.values())
    if nome:
        encontrados = [c for c in encontrados if normalizar(nome) in normalizar(c["nome"])]
    encontrados.sort(key=lambda c: normalizar(c["nome"]))
    return [cliente_completo(c) for c in encontrados]


# GET /api/clientes/1
@app.get("/api/clientes/{id}")
def consultar_cliente(id: int):
    return cliente_completo(buscar_cliente(id))


# POST /api/clientes
@app.post("/api/clientes", status_code=201)
def cadastrar_cliente(entrada: Cliente):
    global proximo_cliente_id
    cliente = {"id": proximo_cliente_id, **validar_cliente(entrada)}
    clientes[proximo_cliente_id] = cliente
    proximo_cliente_id += 1
    return cliente_completo(cliente)


# PUT /api/clientes/1
@app.put("/api/clientes/{id}")
def atualizar_cliente(id: int, entrada: Cliente):
    buscar_cliente(id)
    cliente = {"id": id, **validar_cliente(entrada, id)}
    clientes[id] = cliente
    return cliente_completo(cliente)


# DELETE /api/clientes/1
# Um cliente com veículos vinculados não pode ser excluído (409).
@app.delete("/api/clientes/{id}", status_code=204)
def excluir_cliente(id: int):
    buscar_cliente(id)
    if veiculos_do_cliente(id):
        raise HTTPException(
            status_code=409,
            detail="Não é possível excluir: o cliente possui veículos vinculados.",
        )
    del clientes[id]


# GET /api/clientes/1/veiculos
@app.get("/api/clientes/{id}/veiculos")
def listar_veiculos_do_cliente(id: int):
    buscar_cliente(id)
    return veiculos_do_cliente(id)


# GET /api/clientes/1/historico
# As ordens de serviço dos veículos do cliente, da mais recente para a mais antiga.
@app.get("/api/clientes/{id}/historico")
def consultar_historico_do_cliente(id: int):
    buscar_cliente(id)
    ids_dos_veiculos = {v["id"] for v in veiculos_do_cliente(id)}
    historico = [ordem_completa(o) for o in ordens.values() if o["veiculo_id"] in ids_dos_veiculos]
    historico.sort(key=lambda o: (o["data_abertura"], o["id"]), reverse=True)
    return historico


# ---------------------------------------------------------------------------
# 3.2 Ordens de Serviço: cadastrar, listar, consultar, atualizar e excluir.
# ---------------------------------------------------------------------------

Status = Literal["ORCAMENTO", "EM_SERVICO", "AGUARDANDO_PECA", "PRONTA", "ENTREGUE"]

# Nomes para mostrar no arquivo exportado.
STATUS_ROTULO = {
    "ORCAMENTO": "Orçamento",
    "EM_SERVICO": "Em serviço",
    "AGUARDANDO_PECA": "Aguardando peça",
    "PRONTA": "Pronta",
    "ENTREGUE": "Entregue",
}


# O corpo de POST e PUT /api/ordens-servico, por exemplo
# {"veiculo_id": 1, "quilometragem": 82300, "problema_relatado": "Barulho ao frear",
#  "servico": "Troca de óleo e filtros", "mecanico": "Rafael",
#  "data_abertura": "2026-11-11T08:10:00", "data_previsao": "2026-11-11T17:00:00",
#  "data_conclusao": null, "status": "EM_SERVICO",
#  "observacoes": "Verificar pastilhas", "valor_total": 340.00}
# O cliente não vai no corpo: ele é o dono do veículo.
# As datas vão sem fuso horário. Se data_abertura faltar, vale o momento atual.
class OrdemServico(BaseModel):
    veiculo_id: int
    quilometragem: int | None = None
    problema_relatado: str
    servico: str | None = None
    mecanico: str | None = None
    data_abertura: datetime | None = None
    data_previsao: datetime | None = None
    data_conclusao: datetime | None = None
    status: Status = "ORCAMENTO"
    observacoes: str | None = None
    valor_total: float = 0


# Confere os campos e devolve os dados prontos para gravar. `atual` é a OS já gravada
# (na atualização): se data_abertura vier vazia, fica a original.
def validar_ordem(entrada: OrdemServico, atual=None):
    veiculo = veiculos.get(entrada.veiculo_id)
    if veiculo is None:
        raise HTTPException(status_code=422, detail="Veículo não encontrado.")

    problema = entrada.problema_relatado.strip()
    if problema == "":
        raise HTTPException(status_code=422, detail="O problema relatado é obrigatório.")

    # Sem quilometragem na OS, vale a do cadastro do veículo.
    km = entrada.quilometragem if entrada.quilometragem is not None else veiculo["quilometragem"]
    if km < 0:
        raise HTTPException(status_code=422, detail="A quilometragem não pode ser negativa.")

    if not math.isfinite(entrada.valor_total) or entrada.valor_total < 0:
        raise HTTPException(status_code=422, detail="O valor total não pode ser negativo.")

    for data in (entrada.data_abertura, entrada.data_previsao, entrada.data_conclusao):
        if data is not None and data.tzinfo is not None:
            raise HTTPException(
                status_code=422,
                detail="Informe as datas sem fuso horário, ex.: 2026-11-11T08:10:00.",
            )

    if entrada.data_abertura is not None:
        abertura = entrada.data_abertura
    elif atual is not None:
        abertura = atual["data_abertura"]
    else:
        abertura = datetime.now().replace(microsecond=0)

    if entrada.data_conclusao is not None and entrada.data_conclusao < abertura:
        raise HTTPException(status_code=422, detail="A data de conclusão não pode ser anterior à data de abertura.")
    if entrada.data_previsao is not None and entrada.data_previsao < abertura:
        raise HTTPException(status_code=422, detail="A data de previsão não pode ser anterior à data de abertura.")

    return {
        "veiculo_id": entrada.veiculo_id,
        "quilometragem": km,
        "problema_relatado": problema,
        "servico": limpar(entrada.servico),
        "mecanico": limpar(entrada.mecanico),
        "data_abertura": abertura,
        "data_previsao": entrada.data_previsao,
        "data_conclusao": entrada.data_conclusao,
        "status": entrada.status,
        "observacoes": limpar(entrada.observacoes),
        "valor_total": round(entrada.valor_total, 2),
    }


# Devolve a OS, ou responde 404 se não existe nenhuma com esse id.
def buscar_ordem(id: int):
    if id not in ordens:
        raise HTTPException(status_code=404, detail="Ordem de serviço não encontrada.")
    return ordens[id]


# A OS com os dados que as telas mostram: placa, veículo e cliente.
# Eles vêm do veículo e do cliente na hora da leitura, não ficam gravados na OS.
def ordem_completa(ordem):
    veiculo = veiculos.get(ordem["veiculo_id"], {})
    cliente = clientes.get(veiculo.get("cliente_id"), {})
    return {
        **ordem,
        "placa": veiculo.get("placa"),
        "veiculo": f"{veiculo.get('marca', '')} {veiculo.get('modelo', '')}".strip(),
        "cliente_id": cliente.get("id"),
        "cliente_nome": cliente.get("nome"),
        "cliente_telefone": cliente.get("telefone"),
    }


# As OS que passam nos filtros da 3.7, da mais recente para a mais antiga.
# Usada pela listagem e pela exportação.
def filtrar_ordens(status, placa, cliente):
    encontradas = []
    for ordem in ordens.values():
        completa = ordem_completa(ordem)
        if status and completa["status"] != status:
            continue
        if placa and not placa_confere(completa["placa"], placa):
            continue
        if cliente and normalizar(cliente) not in normalizar(completa["cliente_nome"]):
            continue
        encontradas.append(completa)
    encontradas.sort(key=lambda o: (o["data_abertura"], o["id"]), reverse=True)
    return encontradas


# GET /api/ordens-servico
# Filtros: ?status=EM_SERVICO  ?placa=QRS4F21  ?cliente=Marina (podem ser combinados)
@app.get("/api/ordens-servico")
def listar_ordens(status: Status | None = None, placa: str | None = None, cliente: str | None = None):
    return filtrar_ordens(status, placa, cliente)


# Uma célula do CSV que começa com = + - @ vira fórmula ao abrir no Excel.
# O apóstrofo faz o Excel tratar como texto.
def celula_csv(valor):
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + valor
    return valor


def formatar_data(data):
    return data.strftime("%d/%m/%Y %H:%M") if data else ""


# GET /api/ordens-servico/exportar  (aceita os mesmos filtros da listagem)
# Precisa vir antes de /api/ordens-servico/{id}, senão "exportar" seria lido como id.
# Separador ";", valores com vírgula e BOM, para abrir certo no Excel em português.
@app.get("/api/ordens-servico/exportar")
def exportar_ordens(status: Status | None = None, placa: str | None = None, cliente: str | None = None):
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(["OS", "Placa", "Veículo", "Cliente", "Serviço", "Problema relatado", "Mecânico",
                       "Status", "Abertura", "Previsão", "Conclusão", "Valor total (R$)"])
    for o in filtrar_ordens(status, placa, cliente):
        escritor.writerow([celula_csv(valor) for valor in [
            o["id"], o["placa"] or "", o["veiculo"], o["cliente_nome"] or "", o["servico"] or "",
            o["problema_relatado"], o["mecanico"] or "", STATUS_ROTULO[o["status"]],
            formatar_data(o["data_abertura"]), formatar_data(o["data_previsao"]),
            formatar_data(o["data_conclusao"]), f"{o['valor_total']:.2f}".replace(".", ","),
        ]])
    return Response(
        content="﻿" + saida.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ordens-servico.csv"'},
    )


# GET /api/ordens-servico/1042
@app.get("/api/ordens-servico/{id}")
def consultar_ordem(id: int):
    return ordem_completa(buscar_ordem(id))


# POST /api/ordens-servico
@app.post("/api/ordens-servico", status_code=201)
def cadastrar_ordem(entrada: OrdemServico):
    global proximo_ordem_id
    ordem = {"id": proximo_ordem_id, **validar_ordem(entrada)}
    ordens[proximo_ordem_id] = ordem
    proximo_ordem_id += 1
    return ordem_completa(ordem)


# PUT /api/ordens-servico/1042
@app.put("/api/ordens-servico/{id}")
def atualizar_ordem(id: int, entrada: OrdemServico):
    atual = buscar_ordem(id)
    ordem = {"id": id, **validar_ordem(entrada, atual)}
    ordens[id] = ordem
    return ordem_completa(ordem)


# DELETE /api/ordens-servico/1042
@app.delete("/api/ordens-servico/{id}", status_code=204)
def excluir_ordem(id: int):
    buscar_ordem(id)
    del ordens[id]


# ---------------------------------------------------------------------------
# 3.7 Pesquisa geral. Os outros filtros da 3.7 são parâmetros das rotas acima:
# /api/ordens-servico?status|placa|cliente, /api/veiculos?placa, /api/clientes?nome.
# ---------------------------------------------------------------------------

# GET /api/busca?q=QRS4F21  (placa, nome do cliente ou número da OS, ex.: "1042" ou "OS 1042")
@app.get("/api/busca")
def pesquisar(q: str):
    termo = q.strip()
    if termo == "":
        raise HTTPException(status_code=422, detail="Informe o termo da pesquisa.")

    # Só número ("1042" ou "OS 1042") é número de OS: placa sempre tem letras.
    numero = re.sub(r"^(os)?\s*#?\s*", "", normalizar(termo))
    if numero.isdigit():
        encontradas = [o for o in filtrar_ordens(None, None, None) if o["id"] == int(numero)]
        return {"ordens": encontradas, "veiculos": [], "clientes": []}

    veiculos_achados = [v for v in veiculos.values() if placa_confere(v["placa"], termo)]
    ids_dos_donos = {v.get("cliente_id") for v in veiculos_achados}
    clientes_achados = [c for c in clientes.values()
                        if normalizar(termo) in normalizar(c["nome"]) or c["id"] in ids_dos_donos]
    ordens_achadas = [o for o in filtrar_ordens(None, None, None)
                      if placa_confere(o["placa"], termo)
                      or normalizar(termo) in normalizar(o["cliente_nome"])]

    return {
        "ordens": ordens_achadas,
        "veiculos": veiculos_achados,
        "clientes": [cliente_completo(c) for c in clientes_achados],
    }


# ---------------------------------------------------------------------------
# 3.8 Autenticação (opcional). A senha é guardada com hash (PBKDF2) e o acesso
# é por token "Bearer". Nenhuma outra rota exige login por enquanto.
# ---------------------------------------------------------------------------

HORAS_DA_SESSAO = 8
MINUTOS_DA_RECUPERACAO = 30
bearer = HTTPBearer(auto_error=False)


def hash_senha(senha: str, sal: bytes):
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, 200_000).hex()


# Usado quando o e-mail não existe, para o login levar o mesmo tempo nos dois casos.
SAL_FALSO = secrets.token_bytes(16)


def criar_usuario(nome: str, email: str, senha: str, perfil: str = "Recepção"):
    global proximo_usuario_id
    sal = secrets.token_bytes(16)
    usuarios[proximo_usuario_id] = {"id": proximo_usuario_id, "nome": nome, "email": email.lower(),
                                    "perfil": perfil, "sal": sal, "senha_hash": hash_senha(senha, sal)}
    proximo_usuario_id += 1


# Os dados do usuário que podem sair na resposta (nunca o hash).
def usuario_publico(usuario):
    return {"id": usuario["id"], "nome": usuario["nome"], "email": usuario["email"], "perfil": usuario["perfil"]}


# O corpo de POST /api/auth/login, por exemplo {"email": "voce@oficina.com.br", "senha": "..."}
class Login(BaseModel):
    email: str
    senha: str


# O corpo de POST /api/auth/esqueci-senha
class EsqueciSenha(BaseModel):
    email: str


# O usuário do token enviado em "Authorization: Bearer <token>", ou 401.
def usuario_atual(credenciais: HTTPAuthorizationCredentials | None = Depends(bearer)):
    negado = HTTPException(status_code=401, detail="Sessão inválida ou expirada. Entre novamente.",
                           headers={"WWW-Authenticate": "Bearer"})
    if credenciais is None:
        raise negado
    sessao = sessoes.get(credenciais.credentials)
    if sessao is None or sessao["expira_em"] < datetime.now() or sessao["usuario_id"] not in usuarios:
        sessoes.pop(credenciais.credentials, None)
        raise negado
    return usuarios[sessao["usuario_id"]]


# POST /api/auth/login
@app.post("/api/auth/login")
def entrar(entrada: Login):
    usuario = next((u for u in usuarios.values() if u["email"] == entrada.email.strip().lower()), None)
    hash_calculado = hash_senha(entrada.senha, usuario["sal"] if usuario else SAL_FALSO)
    # A mesma mensagem para e-mail desconhecido e senha errada, para não revelar quem tem conta.
    if usuario is None or not hmac.compare_digest(hash_calculado, usuario["senha_hash"]):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")

    token = secrets.token_urlsafe(32)
    sessoes[token] = {"usuario_id": usuario["id"], "expira_em": datetime.now() + timedelta(hours=HORAS_DA_SESSAO)}
    return {"access_token": token, "token_type": "bearer", "usuario": usuario_publico(usuario)}


# POST /api/auth/esqueci-senha
# Responde igual exista o e-mail ou não. O envio do e-mail com o link ainda não existe:
# o token de recuperação fica só na memória e nunca vai na resposta.
@app.post("/api/auth/esqueci-senha")
def esqueci_senha(entrada: EsqueciSenha):
    email = entrada.email.strip().lower()
    if not EMAIL.match(email):
        raise HTTPException(status_code=422, detail="E-mail inválido.")
    usuario = next((u for u in usuarios.values() if u["email"] == email), None)
    if usuario is not None:
        tokens_recuperacao[secrets.token_urlsafe(32)] = {
            "usuario_id": usuario["id"],
            "expira_em": datetime.now() + timedelta(minutes=MINUTOS_DA_RECUPERACAO)}
    return {"mensagem": "Se o e-mail estiver cadastrado, enviaremos as instruções para recuperar a senha."}


# GET /api/auth/me
@app.get("/api/auth/me")
def consultar_usuario_logado(usuario=Depends(usuario_atual)):
    return usuario_publico(usuario)


# ---------------------------------------------------------------------------
# Dados de demonstração, tirados do protótipo (Marina Souza, OS 1042, etc.),
# e o usuário de teste. Valem só para desenvolvimento: o e-mail e a senha vêm
# de ADMIN_EMAIL e ADMIN_SENHA. Sem elas, usa-se o par abaixo; troque antes de publicar.
# ---------------------------------------------------------------------------

def carregar_dados_demo():
    global proximo_id, proximo_cliente_id, proximo_ordem_id
    criar_usuario("Usuário", os.environ.get("ADMIN_EMAIL", "recepcao@oficina.com.br"),
                  os.environ.get("ADMIN_SENHA", "oficina123"))

    pessoas = [("Marina Souza", "(85) 90000-0001", "marina@exemplo.com", date(2024, 3, 10)),
               ("João Pereira", "(85) 90000-0002", None, date(2024, 6, 2)),
               ("Ana Lima", "(85) 90000-0003", None, date(2025, 1, 15)),
               ("Carlos Mendes", "(85) 90000-0004", None, date(2025, 4, 8)),
               ("Patrícia Rocha", "(85) 90000-0005", None, date(2025, 9, 1)),
               ("Luís Araújo", "(85) 90000-0006", None, date(2026, 2, 20))]
    for nome, telefone, email, desde in pessoas:
        clientes[proximo_cliente_id] = {"id": proximo_cliente_id, "nome": nome, "telefone": telefone,
                                        "email": email, "cliente_desde": desde}
        proximo_cliente_id += 1

    carros = [("QRS4F21", "Volkswagen", "Gol 1.6", 2022, 82300, 1),
              ("TUV7G84", "Fiat", "Strada 1.3", 2021, 61000, 2),
              ("MNP2K56", "Chevrolet", "Onix 1.0", 2023, 24500, 3),
              ("HJK9L13", "Honda", "Civic 2.0", 2019, 60120, 4),
              ("DFG3M72", "Hyundai", "HB20 1.6", 2020, 74800, 5),
              ("BCD8N45", "Toyota", "Corolla 2.0", 2022, 39900, 6)]
    for placa, marca, modelo, ano, km, cliente_id in carros:
        veiculos[proximo_id] = {"id": proximo_id, "placa": placa, "marca": marca, "modelo": modelo,
                                "ano": ano, "quilometragem": km, "cliente_id": cliente_id}
        proximo_id += 1

    agora = datetime.now().replace(minute=0, second=0, microsecond=0)
    hoje = lambda hora, minuto=0: agora.replace(hour=hora, minute=minuto)
    dia = timedelta(days=1)
    # (id, veículo, km, problema, serviço, mecânico, abertura, previsão, conclusão, status, observações, valor)
    ordens_demo = [
        (912, 1, 70100, "Carro não liga", "Bateria nova", "Rafael", datetime(2026, 5, 12, 9), datetime(2026, 5, 12, 17), datetime(2026, 5, 12, 16), "ENTREGUE", None, 520),
        (987, 1, 78900, "Carro puxando para a direita", "Alinhamento", "Rafael", datetime(2026, 8, 20, 9), datetime(2026, 8, 20, 12), datetime(2026, 8, 20, 11), "ENTREGUE", None, 160),
        (1042, 1, 82300, "Barulho ao frear", "Troca de óleo e filtros", "Rafael", hoje(8, 10), hoje(17), None, "EM_SERVICO",
         "Cliente relatou barulho ao frear em baixa velocidade. Verificar pastilhas na próxima revisão.", 340),
        (1043, 2, 61000, "Pedal do freio baixo", "Freios dianteiros", "Diego", hoje(9) - dia, hoje(17) + dia, None, "AGUARDANDO_PECA", None, 780),
        (1044, 3, 24500, "Volante tremendo", "Alinhamento e balanceamento", "Rafael", hoje(7), hoje(15, 30), None, "PRONTA", None, 160),
        (1045, 4, 60120, "Revisão programada", "Revisão de 60 mil km", "Diego", hoje(8) - dia, hoje(17) + 2 * dia, None, "EM_SERVICO", None, 1250),
        (1046, 5, 74800, "Embreagem patinando", "Troca de embreagem", None, hoje(10), None, None, "ORCAMENTO", None, 1980),
        (1047, 6, 39900, "Luz da bateria acesa", "Diagnóstico elétrico", "Rafael", hoje(9) - dia, hoje(16) - dia, hoje(15) - dia, "ENTREGUE", None, 220),
    ]
    for (oid, vid, km, problema, servico, mecanico, abertura, previsao, conclusao, status, obs, total) in ordens_demo:
        ordens[oid] = {"id": oid, "veiculo_id": vid, "quilometragem": km, "problema_relatado": problema,
                       "servico": servico, "mecanico": mecanico, "data_abertura": abertura,
                       "data_previsao": previsao, "data_conclusao": conclusao, "status": status,
                       "observacoes": obs, "valor_total": float(total)}
    proximo_ordem_id = max(ordens) + 1


carregar_dados_demo()
