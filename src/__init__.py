import logging
from fastapi import FastAPI
from fastmcp import FastMCP

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


__version__ = "0.1.0"


server_instructions = """
This MCP server provides search and document retrieval capabilities 
for deep research. It provides the following tools:
1. `get_party_programs`: Retrieve party programs based on a user query.
2. `roll_dice`: Roll a specified number of 6-sided dice and return the results.
"""

mcp = FastMCP(name="FH-SWF MCP server", instructions=server_instructions)
mcp_app = mcp.http_app(path='/')

app = FastAPI(title="MCP API", lifespan=mcp_app.lifespan)

app.mount("/mcp", mcp_app)