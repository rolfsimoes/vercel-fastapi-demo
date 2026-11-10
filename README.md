# FastAPI na Vercel

Um backend em Python no ar, de graça, em 5 passos.

## 1. Baixe e instale

```bash
git clone https://github.com/rolfsimoes/vercel-fastapi-demo.git
cd vercel-fastapi-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## 2. Teste

```bash
pytest
```

Tem que dar 7 passed.

## 3. Rode no seu computador

```bash
uvicorn app:app --reload
```

Abra http://127.0.0.1:8000/api/docs e teste os endpoints.

## 4. Publique

```bash
npx --yes vercel login
npx --yes vercel deploy --prod
```

Responda as perguntas e crie um projeto novo. No fim aparece o endereço.

## 5. Use

Abra o endereço no navegador, ou:

```bash
curl "https://SEU-ENDERECO/api/hello?name=Ana"
```

## O que tem aqui

- `app.py`: o backend, com dois endpoints.
- `public/index.html`: a página que chama o backend.
- `tests/`: os testes.
- `requirements.txt`: o que a Vercel instala.

A Vercel acha sozinha o `app` dentro do `app.py`. Mais em https://vercel.com/docs/frameworks/backend/fastapi.
