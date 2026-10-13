# SMILE WiFi Backend

A FastAPI backend for the SMILE WiFi hotspot system. It supports WiFi checkout workflows, payment processing integration, hotspot ticket management, and payment webhooks.

## Features

- FastAPI REST API
- HTML checkout and payment-pending pages using Jinja2
- WiFi package management
- ClickPesa payment integration
- Support for M-Pesa, Airtel Money, Mixx by Yas, and HaloPesa
- MikroTik hotspot integration
- Order and payment management using SQLAlchemy
- Database migrations with Alembic
- Mock payment mode for local development and testing

## Technology Stack

- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- Pydantic Settings
- Jinja2
- Alembic
- PostgreSQL or a supported SQLAlchemy database
- MikroTik RouterOS API
- ClickPesa API

## Project Structure

```text
smile-wifi-backend/
├── alembic/
├── app/
│   ├── routes/
│   ├── services/
│   ├── templates/
│   │   ├── checkout.html
│   │   └── payment_pending.html
│   ├── main.py
│   ├── config.py
│   └── database.py
├── tests/
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.11 or a compatible version supported by the dependencies
- pip
- Git

## Installation

Clone the repository:

```bash
git clone https://github.com/mangevyrus/smile-wifi-backend.git
cd smile-wifi-backend
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate it with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configuration

Create a local `.env` file based on your environment configuration.

Set the required database connection string using `DATABASE_URL`. Configure payment and MikroTik settings according to your deployment environment.

**Security:** Never commit `.env` files, API keys, payment credentials, database passwords, or MikroTik credentials to GitHub.

## Run Locally

For local development, use a test database and enable mock payments:

```bash
DATABASE_URL="sqlite:///./smile_wifi_test.db" \
MOCK_PAYMENTS=true \
python -m uvicorn app.main:app --host 127.0.0.1 --port 9000
```

Open the API root:

http://127.0.0.1:9000/

Open the interactive API documentation:

http://127.0.0.1:9000/docs

## Checkout UI

The checkout pages are rendered from Jinja2 templates.

Example checkout URLs, depending on available package codes:

- http://127.0.0.1:9000/checkout/1H
- http://127.0.0.1:9000/checkout/24H

The payment-pending page is rendered as part of the checkout payment workflow. It may require a valid checkout submission and associated order/payment data.

## Testing

Run the available test suite with:

```bash
python -m pytest
```

## Database Migrations

Database migrations are managed using Alembic. Review the project configuration and migration history before applying migrations to any database.

## Security Notes

- Use mock payments during local development.
- Do not expose development services publicly without appropriate security controls.
- Keep API credentials and production configuration out of source control.
- Test payment callbacks and webhook handling before production deployment.

## Status

This project is under development. Available features and deployment requirements depend on the current implementation and configuration.

## Author

**mangevyrus**

GitHub: https://github.com/mangevyrus
