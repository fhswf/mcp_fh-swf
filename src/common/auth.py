# src/common/auth.py
import os
import json
from contextvars import ContextVar
from typing import Any
from jose import jwe

from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from fastmcp.server.dependencies import get_http_request

_auth_context: ContextVar[dict] = ContextVar('auth_context', default={})


class AuthUser(dict):
    """User claims accessible as dict keys or attributes."""
    
    def __getattr__(self, name: str) -> Any:
        return self.get(name)
    
def get_user() -> AuthUser:
    """Get current authenticated user."""
    user = AuthUser(_auth_context.get())
    return user


class JWETokenVerifier:
    """JWE token verifier."""
    
    def __init__(self, private_key: dict | None = None):
        self._key = private_key or self._load_key()
    
    def _load_key(self) -> dict | None:
        try:
            return json.loads(os.environ.get("MCP_PRIVATE_KEY", ""))
        except (json.JSONDecodeError, TypeError):
            return None
    
    async def verify_token(self, token: str) -> dict | None:
            if not self._key:
                return None
            try:
              payload = json.loads(jwe.decrypt(token, self._key).decode())
              return payload.get('data', payload)
            except Exception:
                 return None


class AuthMiddleware(Middleware):
    """FastMCP middleware that extracts JWT claims."""
    
    def __init__(self, verifier: JWETokenVerifier | None = None):
        self.verifier = verifier or JWETokenVerifier()
    
    async def on_message(
        self,
        context: MiddlewareContext,
        call_next: CallNext,
    ):
        claims = {}
        
        try:
            request = get_http_request()
            if request:
                auth_header = request.headers.get("authorization", "")
                if auth_header.lower().startswith("bearer "):
                    token = auth_header[7:]
                    claims = await self.verifier.verify_token(token) or {}
        except LookupError:
            pass
        
        ctx_token = _auth_context.set(claims)
        try:
            return await call_next(context)
        finally:
            _auth_context.reset(ctx_token)