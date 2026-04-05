import os
import requests
from dotenv import load_dotenv
import json
from datetime import datetime

# Laad .env (veilig!)
load_dotenv()

SECRET = os.getenv("CROSS_TRADE_SECRET")
ACCOUNT = os.getenv("ACCOUNT_ID")
INSTRUMENT = os.getenv("INSTRUMENT")

BASE_URL = "https://app.crosstrade.io/v1/api"

headers = {
    "Authorization": f"Bearer {SECRET}",
    "Content-Type": "application/json"
}

def get_quote():
    """Haal live quote op – test of connectie werkt"""
    url = f"{BASE_URL}/accounts/{ACCOUNT}/quote"
    params = {"instrument": INSTRUMENT}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ {datetime.now()} | {INSTRUMENT} Quote:")
        print(f"   Last: {data.get('last')}")
        print(f"   Bid: {data.get('bid')} | Ask: {data.get('ask')}")
        print(f"   Volume: {data.get('volume')}")
        return data
    else:
        print(f"❌ Error {response.status_code}: {response.text}")
        return None

def place_test_market_order(qty=1, action="buy"):
    """Plaats een TEST market order in SIM (1 contract) – NIET live!"""
    url = f"{BASE_URL}/accounts/{ACCOUNT}/orders"
    payload = {
        "instrument": INSTRUMENT,
        "action": action,      # "buy" of "sell"
        "qty": qty,
        "order_type": "market",
        "tif": "day"
    }
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code in (200, 201):
        print(f"✅ TEST ORDER GEPLAATST ({action} {qty} {INSTRUMENT})")
        print(json.dumps(response.json(), indent=2))
        return response.json()
    else:
        print(f"❌ Order error {response.status_code}: {response.text}")
        return None

# === RUN DE TESTS ===
if __name__ == "__main__":
    print("🚀 CrossTrade Connector Test (lokaal op PC)")
    print(f"Account: {ACCOUNT} | Instrument: {INSTRUMENT}\n")
    
    get_quote()
    # Uncomment de volgende regel ALLEEN als je een echte test-order wilt plaatsen in SIM
    # place_test_market_order(qty=1, action="buy")