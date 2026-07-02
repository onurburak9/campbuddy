import logging
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

from playwright_service.browser import add_to_cart, add_to_cart_batch

logging.basicConfig(level=logging.INFO)
app = FastAPI()


class CartRequest(BaseModel):
    booking_url: str
    email: str
    password: str
    check_in: str  # MM-DD-YYYY
    check_out: str  # MM-DD-YYYY


class CartResponse(BaseModel):
    success: bool
    error: str | None = None


class BatchSite(BaseModel):
    booking_url: str
    check_in: str
    check_out: str


class BatchRequest(BaseModel):
    email: str
    password: str
    sites: List[BatchSite]


class BatchResult(BaseModel):
    success: bool
    error: str | None = None


class BatchResponse(BaseModel):
    results: List[BatchResult]


@app.post("/add-to-cart", response_model=CartResponse)
def cart_endpoint(req: CartRequest) -> CartResponse:
    return CartResponse(**add_to_cart(req.booking_url, req.email, req.password, req.check_in, req.check_out))


@app.post("/add-to-cart-batch", response_model=BatchResponse)
def cart_batch_endpoint(req: BatchRequest) -> BatchResponse:
    results = add_to_cart_batch(
        req.email,
        req.password,
        [{"booking_url": s.booking_url, "check_in": s.check_in, "check_out": s.check_out} for s in req.sites],
    )
    return BatchResponse(results=[BatchResult(**r) for r in results])


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("playwright_service.main:app", host="0.0.0.0", port=8001)
