from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class Expense(BaseModel):
    id: int
    description: str
    amount: float

_expenses: list[Expense] = [Expense(id=1, description="Coffee", amount=4.50),]

@app.get("/")
def read_root() -> dict[str, str]:
    return {"status":"ok"}

@app.get("/expenses", response_model=list[Expense])
def read_expenses() -> list[Expense]:
    return _expenses