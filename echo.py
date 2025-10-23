"""
FastMCP Echo Server
"""

from fastmcp import FastMCP

# Create server
mcp = FastMCP("Echo Server")


@mcp.tool
def echo_tool(text: str) -> str:
    """Echo the input text"""
    return text

@mcp.tool
def reverse_tool(text: str) -> str:
    """Reverse the input text"""
    return text[::-1]

@mcp.resource("echo://static")
def echo_resource() -> str:
    return "Echo!"

@mcp.resource("echo://{text}")
def echo_template(text: str) -> str:
    """Echo the input text"""
    return f"Echo: {text}"


@mcp.prompt("echo")
def echo_prompt(text: str) -> str:
    return text
