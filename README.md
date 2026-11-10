# FastAPI na Vercel

Como colocar um backend em Python no ar, de graça, em poucos minutos.

Um site estático mostra páginas, mas não calcula nada no servidor. Para receber dados, validar e responder, é preciso um backend. A Vercel roda um app [FastAPI](https://fastapi.tiangolo.com) como uma função sob demanda: você escreve o app em Python, envia a pasta e recebe um endereço público. No plano gratuito, sem configurar servidor.

Este projeto é o mínimo que funciona: uma página e dois endpoints.

- `GET /api/hello?name=Ana` responde `{"message": "Olá, Ana!"}`.
- `POST /api/average` recebe `{"grades": [7, 8, 9]}` e responde `{"average": 8.0, "passed": true}`. Uma nota fora de 0 a 10, ou uma lista vazia, recebe o erro 422 com uma mensagem.
- `/api/docs` é a documentação automática do FastAPI, onde dá para testar cada endpoint no navegador.

## Passo a passo

Você precisa de Python 3.12 ou mais novo, do [Node.js](https://nodejs.org) (para rodar a ferramenta da Vercel com `npx`) e de uma conta gratuita na [Vercel](https://vercel.com).

### 1. Baixar o projeto e instalar

```bash
git clone https://github.com/rolfsimoes/vercel-fastapi-demo.git
cd vercel-fastapi-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 2. Rodar os testes

```bash
pytest
```

Devem passar 7 testes.

### 3. Rodar a API no seu computador

```bash
uvicorn app:app --reload
```

Abra `http://127.0.0.1:8000/api/docs`, escolha um endpoint e clique em "Try it out". Para parar, use Ctrl+C.

### 4. Publicar na Vercel

```bash
npx --yes vercel login
npx --yes vercel deploy --prod
```

Na primeira vez, a ferramenta faz algumas perguntas. Responda: configurar e publicar, sim; a sua conta; criar um projeto novo; o nome do projeto; mudar as configurações, não. A Vercel reconhece o FastAPI sozinha, instala o `requirements.txt` e mostra o endereço no fim.

### 5. Testar no ar

Troque `SEU-ENDERECO` pelo endereço que a Vercel mostrou:

```bash
curl "https://SEU-ENDERECO/api/hello?name=Ana"
curl -X POST "https://SEU-ENDERECO/api/average" -H "Content-Type: application/json" -d '{"grades": [7, 8, 9]}'
```

Abra também o endereço no navegador: a página da pasta `public/` chama os dois endpoints.

## Como funciona

| Arquivo | Papel |
|---|---|
| `app.py` | o app FastAPI. A Vercel procura uma variável `app` num arquivo com um destes nomes: `app.py`, `index.py`, `server.py`, `main.py`, `wsgi.py` ou `asgi.py`, na raiz ou em `src/` ou `app/`. |
| `requirements.txt` | o que a Vercel instala: só o FastAPI. |
| `requirements-dev.txt` | o que você instala para testar e rodar localmente: o FastAPI, o pytest, o httpx e o uvicorn. |
| `public/` | arquivos estáticos. A Vercel os serve pela CDN, sem passar pelo Python: `public/index.html` vira a página `/`. |
| `tests/test_app.py` | os testes, com os resultados esperados escritos à mão. |

Todo o app fica sob `/api`, inclusive a documentação, para que a página em `public/` fique com o resto dos endereços.

O FastAPI lê o corpo do pedido pela classe `Grades`: se não vier uma lista de números, ele mesmo responde 422. As outras duas regras, lista vazia e nota fora de 0 a 10, estão escritas na função `average`, com `HTTPException`, que devolve 422 e a mensagem.

## Detalhes

- Na Vercel, o app inteiro vira uma única função, que sobe quando chega um pedido e pode demorar um pouco no primeiro acesso depois de um tempo parado.
- A função não guarda estado entre pedidos. Para guardar dados, use um banco externo.
- O plano gratuito (Hobby) é para uso pessoal e não comercial.
- Para ligar o repositório do GitHub e publicar a cada `git push`, responda que sim quando a ferramenta perguntar sobre o repositório, ou use o painel da Vercel.
- A documentação oficial: [FastAPI na Vercel](https://vercel.com/docs/frameworks/backend/fastapi).
