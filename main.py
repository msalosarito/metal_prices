from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests
from pymongo import MongoClient, errors
from pydantic import BaseModel
import logging

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# MongoDB setup
try:
    client = MongoClient("mongodb://localhost:27017/")
    db = client.metal_prices
    collection = db.prices
except errors.ConnectionFailure as e:
    print(f"Could not connect to MongoDB: {e}")

# Models
class Price(BaseModel):
    metal: str
    price: float
    currency: str

# External APIs
GOLD_API_KEY = "goldapi-10urcwslw97x4l4-io"  # Your GoldAPI.io API key
EXCHANGERATE_API_KEY = "84e853d586d46aa5b51d7fbb"  # Your ExchangeRate-API key

CURRENCY_API_URL = f"https://v6.exchangerate-api.com/v6/{EXCHANGERATE_API_KEY}/latest/USD"

HEADERS = {
    'x-access-token': GOLD_API_KEY,
    'Content-Type': 'application/json'
}

def make_gapi_request(symbol: str, curr: str, date: str = "") -> dict:
    url = f"https://www.goldapi.io/api/{symbol}/{curr}{date}"
    
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/prices/{metal}/{currency}/{date}")
async def get_metal_price(metal: str, currency: str, date: str):
    metal_symbol = metal.upper()
    currency_symbol = currency.upper()
    
    try:
        data = make_gapi_request(metal_symbol, currency_symbol, date)
        return {"metal": metal, "price": data["price"], "currency": data["currency"], "date": data["date"]}
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@app.get("/convert/{amount}/{from_currency}/{to_currency}")
async def convert_currency(amount: float, from_currency: str, to_currency: str):
    response = requests.get(CURRENCY_API_URL)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    
    data = response.json()
    rates = data.get("conversion_rates", {})
    if from_currency in rates and to_currency in rates:
        converted_amount = amount * rates[to_currency] / rates[from_currency]
        return {"amount": converted_amount, "currency": to_currency}
    else:
        raise HTTPException(status_code=404, detail="Invalid currency code")

@app.post("/prices/")
async def add_price(price: Price):
    collection.insert_one(price.dict())
    return price
 