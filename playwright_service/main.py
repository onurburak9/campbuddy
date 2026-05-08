import logging
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from playwright_service.browser import add_to_cart

logging.basicConfig(level=logging.INFO)
app = FastAPI()


class CartRequest(BaseModel):
    booking_url: str
    email: str
    password: str


class CartResponse(BaseModel):
    success: bool
    error: str | None = None


@app.post("/add-to-cart", response_model=CartResponse)
def cart_endpoint(req: CartRequest) -> CartResponse:
    return CartResponse(**add_to_cart(req.booking_url, req.email, req.password))


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("playwright_service.main:app", host="0.0.0.0", port=8001)
