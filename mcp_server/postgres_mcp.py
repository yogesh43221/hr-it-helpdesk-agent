import argparse
import os
import re
from typing import Any

import psycopg
from dotenv import load_dotenv
from fastmcp import FastMCP
from psycopg.rows import dict_row

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
EMPLOYEE_ID_PATTERN = re.compile(r"^E\d{3,6}$")

READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

mcp = FastMCP(
    name="hr-it-postgres-mcp",
    instructions=(
        "Read-only HR & IT Helpdesk PostgreSQL server. "
        "Use these tools to look up employee leave balances, IT support tickets, "
        "assigned hardware assets, and employee profiles by employee_id (e.g. E102)."
    ),
)


def _validate_employee_id(employee_id: str) -> str:
    cleaned = employee_id.strip().upper()
    if not EMPLOYEE_ID_PATTERN.match(cleaned):
        raise ValueError(
            f"Invalid employee_id '{employee_id}'. Expected format like 'E102'."
        )
    return cleaned


def _get_readonly_connection() -> psycopg.Connection:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in .env")
    # Enforces read-only mode at the PostgreSQL session level
    return psycopg.connect(
        DATABASE_URL,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    )


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert date/datetime objects to ISO strings for clean JSON serialization."""
    return {
        key: (val.isoformat() if hasattr(val, "isoformat") else val)
        for key, val in row.items()
    }


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_employee_leave_balance(employee_id: str) -> dict[str, Any]:
    """Get annual, sick, and carryover leave balances for a specific employee ID (e.g. E102)."""
    emp_id = _validate_employee_id(employee_id)

    query = """
        SELECT
            e.employee_id,
            e.full_name,
            e.department,
            lb.annual_leave_total,
            lb.annual_leave_used,
            lb.annual_leave_remaining,
            lb.sick_leave_remaining,
            lb.carryover_days,
            lb.updated_at
        FROM leave_balances lb
        JOIN employees e ON e.employee_id = lb.employee_id
        WHERE lb.employee_id = %s
    """

    with _get_readonly_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (emp_id,))
            row = cur.fetchone()

    if not row:
        return {"found": False, "employee_id": emp_id, "message": "Employee not found."}

    return {"found": True, "leave_balance": _serialize_row(row)}


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_employee_it_tickets(
    employee_id: str,
    status: str | None = None,
) -> dict[str, Any]:
    """Get IT support tickets for an employee. Optionally filter by status (Open, In Progress, Resolved)."""
    emp_id = _validate_employee_id(employee_id)

    allowed_statuses = {"open", "in progress", "resolved"}
    status_filter = status.strip().lower() if status else None
    if status_filter and status_filter not in allowed_statuses:
        raise ValueError(
            f"Invalid status '{status}'. Allowed values: Open, In Progress, Resolved."
        )

    with _get_readonly_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT full_name FROM employees WHERE employee_id = %s",
                (emp_id,),
            )
            emp = cur.fetchone()
            if not emp:
                return {"found": False, "employee_id": emp_id, "tickets": []}

            if status_filter:
                cur.execute(
                    """
                    SELECT ticket_id, category, subject, status, priority, created_at
                    FROM it_tickets
                    WHERE employee_id = %s AND LOWER(status) = %s
                    ORDER BY created_at DESC
                    """,
                    (emp_id, status_filter),
                )
            else:
                cur.execute(
                    """
                    SELECT ticket_id, category, subject, status, priority, created_at
                    FROM it_tickets
                    WHERE employee_id = %s
                    ORDER BY created_at DESC
                    """,
                    (emp_id,),
                )
            rows = cur.fetchall()

    return {
        "found": True,
        "employee_id": emp_id,
        "full_name": emp["full_name"],
        "ticket_count": len(rows),
        "tickets": [_serialize_row(r) for r in rows],
    }


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_assigned_hardware(employee_id: str) -> dict[str, Any]:
    """Get company hardware assets (laptops/devices) assigned to a specific employee ID."""
    emp_id = _validate_employee_id(employee_id)

    with _get_readonly_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT full_name FROM employees WHERE employee_id = %s",
                (emp_id,),
            )
            emp = cur.fetchone()
            if not emp:
                return {"found": False, "employee_id": emp_id, "assets": []}

            cur.execute(
                """
                SELECT asset_id, device_type, model_name, serial_number, assigned_date
                FROM hardware_assets
                WHERE employee_id = %s
                ORDER BY assigned_date DESC
                """,
                (emp_id,),
            )
            rows = cur.fetchall()

    return {
        "found": True,
        "employee_id": emp_id,
        "full_name": emp["full_name"],
        "assets": [_serialize_row(r) for r in rows],
    }


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_employee_profile(employee_id: str) -> dict[str, Any]:
    """Get employee directory and HR profile details by employee ID (excludes payroll salary)."""
    emp_id = _validate_employee_id(employee_id)

    # Note: base_salary is intentionally excluded at the SQL layer (least privilege).
    # Contact/ID fields remain present so the agent's Output Guardrail PII scrubber is exercised.
    query = """
        SELECT
            employee_id,
            full_name,
            department,
            role_title,
            manager_name,
            work_email,
            work_location,
            hire_date,
            personal_email,
            phone_number,
            pan_id,
            home_address
        FROM employees
        WHERE employee_id = %s
    """

    with _get_readonly_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (emp_id,))
            row = cur.fetchone()

    if not row:
        return {"found": False, "employee_id": emp_id, "message": "Employee not found."}

    return {"found": True, "profile": _serialize_row(row)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run HR/IT Read-Only Postgres MCP Server")
    parser.add_argument(
        "--transport",
        choices=["http", "stdio"],
        default="http",
        help="MCP transport protocol (default: http for Streamable HTTP)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="http", host=args.host, port=args.port)