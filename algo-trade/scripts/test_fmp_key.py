import urllib.request
import json

key = "fn5dmjaApJhqNYGrZbwNkYpsLB6rHvpP"

tests = {
    "quote (free tier)":   f"https://financialmodelingprep.com/api/v3/quote/AAPL?apikey={key}",
    "gainers (paid tier)": f"https://financialmodelingprep.com/api/v3/stock_market/gainers?apikey={key}",
}

for label, url in tests.items():
    try:
        r = urllib.request.urlopen(url, timeout=10)
        data = json.loads(r.read())
        print(f"[OK]  {label}: got {len(data)} item(s)")
    except Exception as e:
        print(f"[ERR] {label}: {e}")
