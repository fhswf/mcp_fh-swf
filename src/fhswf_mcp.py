from fastmcp import FastMCP
import os
from dotenv import load_dotenv
load_dotenv()

from common.Neo4jHandler import Neo4jHandler

neo4j_uri = os.getenv('NEO4J_URI')
neo4j_user = os.getenv('NEO4J_USERNAME')
neo4j_password = os.getenv('NEO4J_PASSWORD')

neo_handler = Neo4jHandler(neo4j_uri, neo4j_user, neo4j_password)

mcp = FastMCP("FH SWF MCP Server")


import mensa
import calendly_mcp
import vpis_mcp
import graphdata_mcp


   
def run_server():
    try:
        mcp.run(transport="stdio")
    finally:
        neo_handler.close() 

    
