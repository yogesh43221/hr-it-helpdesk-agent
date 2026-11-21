import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def seed_database() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in .env")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    employees = [
        ("E101", "Aarav Sharma", "Engineering", "Senior Backend Engineer", "Priya Nair",
         "aarav.sharma@company.com", "Bengaluru", "2023-03-15",
         "aarav.personal@gmail.com", "+91-9876543210", "ABCDE1234F",
         "42 Indiranagar 2nd Stage, Bengaluru 560038", 2400000),
        ("E102", "Sneha Kulkarni", "Product", "Product Manager", "Rohan Mehta",
         "sneha.kulkarni@company.com", "Pune (Remote)", "2024-01-10",
         "sneha.k.home@gmail.com", "+91-9822011223", "FGHIJ5678K",
         "18 Baner Road, Pune 411045", 2100000),
        ("E103", "Kabir Verma", "HR", "People Operations Specialist", "Meera Iyer",
         "kabir.verma@company.com", "Delhi", "2023-08-01",
         "kabir.verma99@yahoo.com", "+91-9811099887", "KLMNO9012P",
         "77 Hauz Khas Enclave, New Delhi 110016", 1200000),
        ("E104", "Divya Menon", "Engineering", "AI Engineer", "Priya Nair",
         "divya.menon@company.com", "Remote", "2025-02-03",
         "divya.menon.dev@gmail.com", "+91-9745066778", "PQRST3456U",
         "14 Marine Drive, Kochi 682011", 1800000),
        ("E105", "Vikram Joshi", "Finance", "Financial Analyst", "Anil Kapoor",
         "vikram.joshi@company.com", "Mumbai", "2022-11-20",
         "vikram.joshi.fin@gmail.com", "+91-9820044556", "UVWXY7890Z",
         "902 Powai Lake View, Mumbai 400076", 1500000),
    ]

    leave_balances = [
        ("E101", 18, 6, 12, 8, 3, "2026-11-01"),
        ("E102", 18, 11, 7, 6, 2, "2026-11-01"),
        ("E103", 18, 4, 14, 10, 4, "2026-11-01"),
        ("E104", 18, 2, 16, 9, 0, "2026-11-01"),
        ("E105", 18, 15, 3, 5, 1, "2026-11-01"),
    ]

    it_tickets = [
        ("IT-2001", "E102", "Access", "VPN certificate renewal for remote access", "Resolved", "Medium", "2026-10-18"),
        ("IT-2002", "E104", "Hardware", "MacBook Pro USB-C port not charging", "Open", "High", "2026-11-18"),
        ("IT-2003", "E104", "Software", "Request Jira admin read-only access", "In Progress", "Low", "2026-11-19"),
        ("IT-2004", "E101", "Security", "Reset MFA authenticator after phone upgrade", "Resolved", "High", "2026-11-05"),
    ]

    hardware_assets = [
        ("AST-501", "E101", "Laptop", "MacBook Pro 14 M3", "SN-MBP-99101", "2023-03-15"),
        ("AST-502", "E102", "Laptop", "ThinkPad X1 Carbon Gen 11", "SN-TPX-88202", "2024-01-10"),
        ("AST-503", "E104", "Laptop", "MacBook Pro 16 M4", "SN-MBP-77404", "2025-02-03"),
    ]

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
            cur.executemany(
                """
                INSERT INTO employees VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                employees,
            )
            cur.executemany(
                """
                INSERT INTO leave_balances VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                leave_balances,
            )
            cur.executemany(
                """
                INSERT INTO it_tickets VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                it_tickets,
            )
            cur.executemany(
                """
                INSERT INTO hardware_assets VALUES (%s,%s,%s,%s,%s,%s)
                """,
                hardware_assets,
            )
        conn.commit()

    print("Database schema created and seeded successfully (employees E101-E105).")


if __name__ == "__main__":
    seed_database()