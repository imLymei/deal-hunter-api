# Deal Hunter API

Deal Hunter API is a RESTful backend built with Flask and Flask-OpenAPI3. It provides user authentication (JWT), wishlist management, and game deal aggregation via the CheapShark API. Swagger documentation is available at `/openapi/swagger`.

[Português (PT-BR)](./README_pt-BR.md)

## Requirements

- [Python 3.14+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/) (package manager)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/imLymei/deal-hunter-api.git
   cd deal-hunter-api
   ```

2. Install dependencies with uv:

   ```bash
   uv sync
   ```

3. Start the development server:

   ```bash
   uv run flask --app main:create_app run
   ```

4. The API will be available at `http://localhost:5000`. Swagger docs at `http://localhost:5000/openapi/swagger`.

## Production

Build and run with Docker:

```bash
docker build -t deal-hunter-api .
docker run -p 5000:5000 -e JWT_SECRET=your-secret-key deal-hunter-api
```

## API Endpoints

### Authentication (`/api/auth`)

| Method | Endpoint             | Description                         | Auth Required |
| ------ | -------------------- | ----------------------------------- | ------------- |
| POST   | `/api/auth/register` | Create a new account                | No            |
| POST   | `/api/auth/login`    | Authenticate and receive JWT cookie | No            |
| POST   | `/api/auth/logout`   | Clear JWT auth cookie               | No            |
| GET    | `/api/auth/me`       | Get current user info               | Yes           |

### Users (`/api/users`)

| Method | Endpoint          | Description                         | Auth Required |
| ------ | ----------------- | ----------------------------------- | ------------- |
| GET    | `/api/users/<id>` | Get user by ID                      | No            |
| GET    | `/api/users/me`   | Get current user profile            | Yes           |
| PUT    | `/api/users/me`   | Update username, email, or password | Yes           |
| DELETE | `/api/users/me`   | Delete account and clear cookie     | Yes           |

### Wishlist (`/api/wishlist`)

| Method | Endpoint                             | Description                               | Auth Required |
| ------ | ------------------------------------ | ----------------------------------------- | ------------- |
| GET    | `/api/wishlist/search?q=`            | Search games via CheapShark (min 2 chars) | No            |
| GET    | `/api/wishlist/`                     | Get current user's wishlist               | Yes           |
| POST   | `/api/wishlist/`                     | Add game to wishlist                      | Yes           |
| PUT    | `/api/wishlist/<id>`                 | Update item notes (max 500 chars)         | Yes           |
| DELETE | `/api/wishlist/<id>`                 | Remove from wishlist                      | Yes           |
| PUT    | `/api/wishlist/visibility`           | Toggle public/private visibility          | Yes           |
| GET    | `/api/wishlist/user/<username>`      | Get another user's public wishlist        | No            |
| GET    | `/api/wishlist/game/<cheapshark_id>` | Get deals, cheapest price, historical low | No            |

## External API — CheapShark

Deal Hunter uses the [CheapShark API](https://www.cheapshark.com/api/1.0), a free public game deal aggregator that requires no registration or API key.

### Endpoints Used

| Endpoint                    | Purpose                                                     |
| --------------------------- | ----------------------------------------------------------- |
| `GET /api/1.0/games?title=` | Search games by title (returns up to 30 results)            |
| `GET /api/1.0/games?id=`    | Get game details, active deals, and historical lowest price |

### Integration Details

- Requests are made server-side using Python's `urllib` with a custom `User-Agent` header (`DealHunter/1.0`)
- A 15-second timeout is applied to all external requests
- Errors (network failures, invalid JSON) are caught and logged; endpoints return `500` on failure
- Game deal aggregation (cheapest active deal, all offers, historical low) is computed server-side before returning results

[Português (PT-BR)](./README_pt-BR.md)
