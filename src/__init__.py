import logging
from fastmcp import FastMCP
import os
from src.common.Neo4jHandler import Neo4jHandler


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

mcp = FastMCP(name="FH-SWF MCP server", instructions=server_instructions)
