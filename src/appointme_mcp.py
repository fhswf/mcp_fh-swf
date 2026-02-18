from fastmcp.server import create_proxy
from src import mcp

async def init():
    """
    Asynchronously initialize and mount the external AppointMe service.
    """
    try:
        # Create the proxy for the external server
        external_service = create_proxy("https://appointme.fh-swf.cloud")
        
        # Mount the tools to the central mcp instance
        mcp.mount(external_service)
        
        print("✅ AppointMe MCP service initialized (async).")
    except Exception as e:
        print(f"⚠️ Error initializing AppointMe service: {e}")