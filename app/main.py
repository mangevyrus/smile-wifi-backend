from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.checkout import router as checkout_router
from app.routes.payment import router as payment_router
from app.routes.ticket import router as ticket_router
from app.routes.webhooks import router as webhook_router


app = FastAPI(
    title="SMILE WiFi Backend",
    version="1.0.0",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------
#
# The MikroTik HotSpot login page is served from the
# MikroTik router while the API is running on the backend
# server.
#
# This allows login.html to request:
#
#   http://192.168.1.100:9000/ticket/...
#
# from the browser.
#
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Basic endpoints
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "service": "SMILE WiFi Backend",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


# ---------------------------------------------------------
# Routers
# ---------------------------------------------------------

app.include_router(checkout_router)
app.include_router(payment_router)
app.include_router(ticket_router)
app.include_router(webhook_router)