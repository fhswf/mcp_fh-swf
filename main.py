from fastmcp import FastMCP
import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.common.Neo4jHandler import Neo4jHandler

from src import mcp, neo_handler

import src.mensa
_ = src.mensa
import src.vpis_mcp
_ = src.vpis_mcp
import src.graphdata_mcp
_ = src.graphdata_mcp
import src.bib_mcp
_ = src.bib_mcp
import src.faq_mcp
asyncio.run(src.faq_mcp.init())
import src.news_events_mcp
_ = src.news_events_mcp
import src.portale_mcp
asyncio.run(src.portale_mcp.init())
import src.appointme_mcp
asyncio.run(src.appointme_mcp.init())

if __name__ == "__main__":
    try:
        mcp.run(transport="http", host="0.0.0.0", port=8000, stateless_http=True )
    finally:
        neo_handler.close() 