#from fastmcp.server import create_proxy
from fastmcp import FastMCP 
from . import mcp

async def init():
    """
    Asynchronously initialize and mount the external AppointMe service.
    """
    try:
        # Create the proxy for the external server
        #external_service = create_proxy("https://appointme.fh-swf.cloud")
        external_service = FastMCP.as_proxy("https://appointme.fh-swf.cloud/mcp")

        # Mount the tools to the central mcp instance
        mcp.mount(external_service)
        
        print("✅ AppointMe MCP service initialized (async).")
    except Exception as e:
        print(f"⚠️ Error initializing AppointMe service: {e}")

if __name__ == "__main__":
    init()