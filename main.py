from fastmcp import FastMCP
import os
from dotenv import load_dotenv
load_dotenv()

from src.common.Neo4jHandler import Neo4jHandler

from src import mcp, neo_handler

import src.mensa
_ = src.mensa
import src.calendly_mcp
_ = src.calendly_mcp
import src.vpis_mcp
_ = src.vpis_mcp
import src.graphdata_mcp
_ = src.graphdata_mcp


if __name__ == "__main__":
    try:
        mcp.run(transport="http", host="0.0.0.0", port=8000, stateless_http=True )
    finally:
        neo_handler.close() 