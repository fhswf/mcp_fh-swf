import json, base64
from fastapi import Request
from nacl.public import  SealedBox
from nacl.bindings import sodium_unpad

def _decrypt(value: str, limit: int) -> str:
    if not value: return ""
    try:
        decrypted = SealedBox(SERVER_PRIVATE_KEY).decrypt(base64.b64decode(value))
        return sodium_unpad(decrypted, limit).decode("utf-8")
    except Exception:
        return ""

def _process_data(data):
    """Internal helper to traverse and clean the JSON"""
    if isinstance(data, dict):
        if "value" in data and "limit" in data:
            return _decrypt(data["value"], int(data.get("limit", 256)))
        return {k: _process_data(v) for k, v in data.items()}
    return data

async def mcp_middleware(request: Request, call_next):
    """The actual middleware function"""
    try:
        payload = request.headers.get("MCP-Payload", "{}")
        request.state.mcp = _process_data(json.loads(payload))
    except:
        request.state.mcp = {}
    return await call_next(request)

def get_mcp(request: Request):
    """The dependency for your endpoints"""
    return request.state.mcp