# Deal Hunter API

Deal Hunter API é um backend RESTful construído com Flask e Flask-OpenAPI3. Fornece autenticação de usuários (JWT), gerenciamento de lista de desejos e agregação de ofertas de jogos via API CheapShark. A documentação Swagger está disponível em `/openapi/swagger`.

[English (EN)](./README.md)

## Requisitos

- [Python 3.14+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/) (gerenciador de pacotes)

## Instalação

1. Clone o repositório:

   ```bash
   git clone https://github.com/imLymei/deal-hunter-api.git
   cd deal-hunter-api
   ```

2. Instale as dependências com uv:

   ```bash
   uv sync
   ```

3. Inicie o servidor de desenvolvimento:

   ```bash
   uv run flask --app main:create_app run
   ```

4. A API estará disponível em `http://localhost:5000`. Documentação Swagger em `http://localhost:5000/openapi/swagger`.

## Produção

Compile e execute com Docker:

```bash
docker build -t deal-hunter-api .
docker run -p 5000:5000 -e JWT_SECRET=sua-chave-secreta deal-hunter-api
```

## Endpoints da API

### Autenticação (`/api/auth`)

| Método | Endpoint             | Descrição                          | Auth Obrigatório |
| ------ | -------------------- | ---------------------------------- | ---------------- |
| POST   | `/api/auth/register` | Criar nova conta                   | Não              |
| POST   | `/api/auth/login`    | Autenticar e receber cookie JWT    | Não              |
| POST   | `/api/auth/logout`   | Limpar cookie de autenticação JWT  | Não              |
| GET    | `/api/auth/me`       | Obter informações do usuário atual | Sim              |

### Usuários (`/api/users`)

| Método | Endpoint          | Descrição                      | Auth Obrigatório |
| ------ | ----------------- | ------------------------------ | ---------------- |
| GET    | `/api/users/<id>` | Obter usuário por ID           | Não              |
| GET    | `/api/users/me`   | Obter perfil do usuário atual  | Sim              |
| PUT    | `/api/users/me`   | Atualizar nome, email ou senha | Sim              |
| DELETE | `/api/users/me`   | Excluir conta e limpar cookie  | Sim              |

### Lista de Desejos (`/api/wishlist`)

| Método | Endpoint                             | Descrição                                     | Auth Obrigatório |
| ------ | ------------------------------------ | --------------------------------------------- | ---------------- |
| GET    | `/api/wishlist/search?q=`            | Pesquisar jogos via CheapShark (mín. 2 chars) | Não              |
| GET    | `/api/wishlist/`                     | Obter lista de desejos do usuário atual       | Sim              |
| POST   | `/api/wishlist/`                     | Adicionar jogo à lista de desejos             | Sim              |
| PUT    | `/api/wishlist/<id>`                 | Atualizar notas do item (máx. 500 chars)      | Sim              |
| DELETE | `/api/wishlist/<id>`                 | Remover da lista de desejos                   | Sim              |
| PUT    | `/api/wishlist/visibility`           | Alternar visibilidade público/privado         | Sim              |
| GET    | `/api/wishlist/user/<username>`      | Obter lista pública de outro usuário          | Não              |
| GET    | `/api/wishlist/game/<cheapshark_id>` | Obter ofertas, menor preço e histórico        | Não              |

## API Externa — CheapShark

O Deal Hunter utiliza a [API CheapShark](https://www.cheapshark.com/api/1.0), um agregador público gratuito de ofertas de jogos que não requer cadastro nem chave de API.

### Endpoints Utilizados

| Endpoint                    | Finalidade                                                     |
| --------------------------- | -------------------------------------------------------------- |
| `GET /api/1.0/games?title=` | Pesquisar jogos por título (retorna até 30 resultados)         |
| `GET /api/1.0/games?id=`    | Obter detalhes do jogo, ofertas ativas e menor preço histórico |

### Detalhes da Integração

- As requisições são feitas no lado do servidor usando `urllib` do Python com um cabeçalho `User-Agent` personalizado (`DealHunter/1.0`)
- Um timeout de 15 segundos é aplicado a todas as requisições externas
- Erros (falhas de rede, JSON inválido) são capturados e logados; os endpoints retornam `500` em caso de falha
- O agregamento de ofertas de jogos (melhor oferta ativa, todas as ofertas, mínimo histórico) é calculado no servidor antes de retornar os resultados

[English (EN)](./README.md)
