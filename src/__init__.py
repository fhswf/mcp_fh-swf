import logging
from fastmcp import FastMCP
import os
from src.common.Neo4jHandler import Neo4jHandler
from mcp_auth_middleware import JWKSAuthMiddleware
from mcp_auth_middleware.middleware import _user_context
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from urllib.parse import urlparse


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

__version__ = "0.1.0"

neo4j_uri = os.getenv('NEO4J_URI')
neo4j_user = os.getenv('NEO4J_USERNAME')
neo4j_password = os.getenv('NEO4J_PASSWORD')

neo_handler = Neo4jHandler(neo4j_uri, neo4j_user, neo4j_password)


server_instructions = """
You are a helpful assistant for answering questions about the FH SWF (Fachhochschule Südwestfalen) in Germany. You have access to various tools that allow you to retrieve information about study programs, departments, locations, mensa (cafeteria) menus, Calendly meeting slots, and course activities.

When answering questions, you should use the provided tools to fetch accurate and up-to-date information. If a user asks a question that can be answered using one of the tools, you should call the appropriate tool with the necessary parameters.
"""

required_scopes = [
    {"scope": "name"},
    {"scope": "email"},
]

class OptionalJWKSAuthMiddleware(JWKSAuthMiddleware):
    def _openid_configuration(self, request: Request) -> dict:
        issuer = self.issuer or str(request.base_url).rstrip("/")
        parsed = urlparse(issuer)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        return {
            "issuer": issuer,
            "jwks_uri": f"{base_url}{self.jwks_path}",
            "scopes_supported": [scope.scope for scope in self.scopes],
        }

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == self.jwks_path:
            logger.debug("Serving JWKS endpoint: %s %s", request.method, request.url.path)
            return JSONResponse(self.verifier.get_jwks())
        if request.method == "GET" and request.url.path == self.openid_configuration_path:
            logger.debug("Serving OpenID configuration endpoint: %s %s", request.method, request.url.path)
            return JSONResponse(self._openid_configuration(request), headers=self._cors_headers())

        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            # Allow request without token but leave context empty
            token = _user_context.set({})
            try:
                return await call_next(request)
            finally:
                _user_context.reset(token)

        claims = await self.verifier.verify_token(auth_header[7:]) or {}
        if not claims:
            return self._invalid_token_response()

        missing_scopes = [scope.as_dict() for scope in self.scopes if scope.scope not in claims]
        if missing_scopes:
            return JSONResponse(
                {"error": "missing_scopes", "missing": missing_scopes},
                status_code=403,
            )

        token = _user_context.set(claims)
        try:
            return await call_next(request)
        finally:
            _user_context.reset(token)

mcp = FastMCP(name="FH-SWF MCP server", instructions=server_instructions)
app = mcp.http_app()
app.add_middleware(
    OptionalJWKSAuthMiddleware, 
    scopes=required_scopes, 
    issuer=os.getenv("MCP_ISSUER", "https://mcp.fh-swf.cloud"),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
)
