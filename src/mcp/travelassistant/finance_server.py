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

# Standard baseline currency exchange rates against USD
RATES_TO_USD = {
    "USD": 1.0,
    "CAD": 0.74,     # 1 CAD = 0.74 USD
    "EUR": 1.08,     # 1 EUR = 1.08 USD
    "GBP": 1.29,     # 1 GBP = 1.29 USD
    "SGD": 0.77,     # 1 SGD = 0.77 USD
    "JPY": 0.0068,   # 1 JPY = 0.0068 USD
    "IDR": 0.000063, # 1 IDR = 0.000063 USD
    "AUD": 0.66      # 1 AUD = 0.66 USD
}

def convert_currency_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from_curr = arguments.get("from_currency", "USD").upper()
    to_curr = arguments.get("to_currency", "USD").upper()
    amt = float(arguments.get("amount", 1.0))

    from_to_usd = RATES_TO_USD.get(from_curr, 1.0)
    to_to_usd = RATES_TO_USD.get(to_curr, 1.0)

    # Convert to USD then to target
    usd_val = amt * from_to_usd
    target_val = round(usd_val / to_to_usd, 2)
    rate = round(from_to_usd / to_to_usd, 4)

    return {
        "source": "mcp_travelassistant_finance_server",
        "from_currency": from_curr,
        "to_currency": to_curr,
        "original_amount": amt,
        "converted_amount": target_val,
        "exchange_rate": rate,
        "formatted": f"{amt:,.2f} {from_curr} = {target_val:,.2f} {to_curr} (Rate: {rate})"
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
