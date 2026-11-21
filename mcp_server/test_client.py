"""Quick check that the MCP server works: lists tools and calls them, including bad inputs."""
import asyncio

from fastmcp import Client

URL = "http://127.0.0.1:8001/mcp"


async def main():
    async with Client(URL) as client:
        tools = await client.list_tools()
        print("Tools:", [t.name for t in tools])

        tests = [
            ("get_employee_leave_balance", {"employee_id": "E102"}),
            ("get_employee_it_tickets", {"employee_id": "E104"}),
            ("get_assigned_hardware", {"employee_id": "E102"}),
            ("get_employee_leave_balance", {"employee_id": "E999"}),  # does not exist
            ("get_employee_leave_balance", {"employee_id": "E102'; DROP TABLE employees;--"}),  # attack
        ]
        for name, args in tests:
            print(f"\n{name} {args}")
            try:
                result = await client.call_tool(name, args)
                print("  ->", result.data)
            except Exception as e:  # invalid input should land here
                print("  -> BLOCKED:", str(e)[:150])


asyncio.run(main())