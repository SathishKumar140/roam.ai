#!/usr/bin/env python3
import sys
import json
from typing import Dict, Any

TOOLS_DEFINITIONS = [
    {
        "name": "convert_currency",
        "description": "Converts travel expenses and budgets across different currencies (e.g. USD, CAD, EUR, SGD, JPY) via mcp_travelassistant finance server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_currency": {"type": "string", "description": "Source currency code (e.g. 'USD', 'CAD', 'EUR', 'SGD')"},
                "to_currency": {"type": "string", "description": "Target currency code (e.g. 'USD', 'CAD', 'EUR', 'SGD')"},
                "amount": {"type": "number", "description": "Amount to convert (default: 1.0)"}
            },
            "required": ["from_currency", "to_currency", "amount"]
        }
    }
]

import requests

# Extended baseline currency exchange rates against USD (fallback)
RATES_TO_USD = {
    "USD": 1.0,
    "CAD": 0.74,     # 1 CAD = 0.74 USD
    "EUR": 1.08,     # 1 EUR = 1.08 USD
    "GBP": 1.29,     # 1 GBP = 1.29 USD
    "SGD": 0.78,     # 1 SGD = 0.78 USD
    "JPY": 0.0068,   # 1 JPY = 0.0068 USD
    "IDR": 0.000063, # 1 IDR = 0.000063 USD
    "AUD": 0.66,     # 1 AUD = 0.66 USD
    "VND": 0.000039, # 1 VND = 0.000039 USD (1 SGD ≈ 20,000 VND)
    "THB": 0.030,    # 1 THB = 0.030 USD
    "MYR": 0.23      # 1 MYR = 0.23 USD
}

def convert_currency_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from_curr = str(arguments.get("from_currency", "SGD") or "SGD").upper().strip()
    to_curr = str(arguments.get("to_currency", "VND") or "VND").upper().strip()
    try:
        amt = float(arguments.get("amount", 1.0))
    except (TypeError, ValueError):
        amt = 1.0

    rate = None
    source = "live_exchange_rate_api"

    # 1. Live real-time open exchange rate API
    try:
        resp = requests.get(f"https://open.er-api.com/v6/latest/{from_curr}", timeout=4)
        if resp.status_code == 200:
            rates = resp.json().get("rates", {})
            if to_curr in rates:
                rate = float(rates[to_curr])
    except Exception:
        pass

    # 2. Live Web Search fallback via DDGS
    if rate is None:
        try:
            from duckduckgo_search import DDGS
            import re
            q = f"{amt} {from_curr} to {to_curr} currency exchange rate"
            results = list(DDGS().text(q, max_results=3))
            for r in results:
                text = f"{r.get('title', '')} {r.get('body', '')}"
                match = re.search(rf"1\s*{from_curr}\s*=\s*([\d,.]+)\s*{to_curr}", text, re.IGNORECASE)
                if match:
                    val_str = match.group(1).replace(",", "")
                    rate = float(val_str)
                    source = "live_web_search"
                    break
        except Exception:
            pass

    # 3. Baseline Rates Table fallback
    if rate is None:
        source = "mcp_travelassistant_finance_server"
        from_to_usd = RATES_TO_USD.get(from_curr, 1.0)
        to_to_usd = RATES_TO_USD.get(to_curr, 1.0)
        rate = round(from_to_usd / to_to_usd, 6)

    target_val = round(amt * rate, 2) if rate < 100 else round(amt * rate)
    rate_display = round(rate, 4) if rate > 0.001 else f"{rate:.6f}"

    return {
        "source": "mcp_travelassistant_finance_server",
        "from_currency": from_curr,
        "to_currency": to_curr,
        "original_amount": amt,
        "converted_amount": target_val,
        "exchange_rate": rate_display,
        "rate_source": source,
        "formatted": f"{amt:,.2f} {from_curr} = {target_val:,.2f} {to_curr} (1 {from_curr} ≈ {rate_display} {to_curr})"
    }

def handle_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "convert_currency":
        res = convert_currency_handler(arguments)
        return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
    return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

def run_server():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "mcp-travelassistant-finance", "version": "1.0.0"},
                    "capabilities": {"tools": {}}
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS_DEFINITIONS}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        elif method == "tools/call":
            call_res = handle_call(params.get("name"), params.get("arguments", {}))
            resp = {"jsonrpc": "2.0", "id": req_id, "result": call_res}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    run_server()
