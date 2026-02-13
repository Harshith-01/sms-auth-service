
---

# Auth Service – School ERP Microservice

## Overview

This is the Authentication Microservice for the School ERP system.

It is a production-ready, Dockerized, secure FastAPI-based service responsible for:

* Admin account creation
* User login
* JWT token issuance
* Role-based authentication foundation

This service follows microservice architecture principles and is cloud-deployment ready.

---

## Architecture Highlights

* Stateless JWT-based authentication
* Environment variable configuration
* Docker containerized
* Cloud-ready (AWS ECS / EC2 / Render compatible)
* OWASP-aligned security practices
* Rate limiting enabled
* Strict schema validation
* No hardcoded secrets

---

## Features

* Create initial Admin account
* Login with email & password
* JWT access token generation
* Role embedded inside token
* Secure password hashing (bcrypt)
* Token expiration enforced
* Issued-at (iat) claim included
* Health check endpoint

**Stack:**

* **Framework:** FastAPI
* **Database:** PostgreSQL
* **ORM:** SQLAlchemy
* **Containerization:** Docker

---

## Security Features

### 1. No Hardcoded Secrets

All secrets are loaded from environment variables:

* `DATABASE_URL`
* `SECRET_KEY`
* `ACCESS_TOKEN_EXPIRE_MINUTES`
* `ALLOWED_ORIGINS`

The application will refuse to start if required environment variables are missing.

---

### 2. Password Security

* Passwords hashed using bcrypt via passlib
* Plain text passwords never stored
* Minimum length enforced
* Maximum length capped

---

### 3. JWT Security

* Signed using HS256
* Includes `exp` (expiration)
* Includes `iat` (issued at)
* Minimal claims (sub + role only)
* No sensitive data inside token

---

### 4. Rate Limiting

Implemented using SlowAPI.

**Limits:**

* Create Admin: 5 requests per minute
* Login: 10 requests per minute
* Health: 20 requests per minute

**Prevents:**

* Brute force attacks
* Infinite API loops
* Excessive AWS cost usage

Returns graceful 429 responses.

---

### 5. Strict Input Validation

Using Pydantic schemas with:

* Type validation
* Email validation
* Length constraints
* `extra="forbid"` (reject unexpected fields)

**Prevents:**

* Mass assignment attacks
* Payload injection
* Invalid schema abuse

---

### 6. CORS Security

CORS is restricted using environment-based allowed origins.
No wildcard origins in production configuration.

---

### 7. Database Security

* SQLAlchemy ORM
* Connection pooling enabled
* `pool_pre_ping` enabled
* `echo` disabled
* Transaction rollback on failure

---

## Project Structure

```text
auth-service/
│
├── api/
│   └── routes.py
├── core/
│   ├── database.py
│   ├── security.py
│   └── id_generator.py
├── models/
│   └── sql_models.py
├── schemas/
│   └── dto.py
├── main.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .env.example
└── .gitignore

```

---

## Environment Variables

Create a `.env` file locally:

```ini
DATABASE_URL=postgresql://user:password@localhost:5432/school_db
SECRET_KEY=your_super_secure_random_secret
ACCESS_TOKEN_EXPIRE_MINUTES=60
ALLOWED_ORIGINS=http://127.0.0.1:5500,http://localhost:5500

```

**Do NOT commit `.env`.**

---

## Local Development

Install dependencies:

```bash
pip install -r requirements.txt

```

Run:

```bash
uvicorn main:app --reload

```

Access Swagger UI:
http://localhost:8000/docs

---

## Docker Usage

Build image:

```bash
docker build -t auth-service .

```

Run container:

```bash
docker run -p 8000:8000 --env-file .env auth-service

```

Service will run on:
http://localhost:8000

---

## Cloud Deployment

This service is ready for:

* AWS ECS
* AWS EC2
* Render
* Railway
* Fly.io

**Requirements:**

* Set environment variables in cloud platform
* Connect to managed PostgreSQL (e.g., AWS RDS)
* Use HTTPS via load balancer

No code changes required.

---

## Health Endpoint

`GET /health`

Returns:

```json
{
  "status": "ok",
  "service": "auth_service"
}

```

---

## Important Notes

* `SECRET_KEY` must be identical across services that validate JWT.
* Rate limiting is in-memory (sufficient for moderate traffic).
* For high-scale deployments, Redis-backed limiter is recommended.

---

## Production Readiness Checklist

* [x] No hardcoded credentials
* [x] Strict schema validation
* [x] Rate limiting enabled
* [x] Secure CORS
* [x] Environment-based config
* [x] Dockerized
* [x] Stateless architecture

---

## Maintainer

School ERP Backend Team

---