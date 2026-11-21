CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS it_tickets CASCADE;
DROP TABLE IF EXISTS hardware_assets CASCADE;
DROP TABLE IF EXISTS leave_balances CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS policy_chunks CASCADE;

CREATE TABLE employees (
    employee_id VARCHAR(10) PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    department VARCHAR(50) NOT NULL,
    role_title VARCHAR(80) NOT NULL,
    manager_name VARCHAR(100) NOT NULL,
    work_email VARCHAR(120) NOT NULL,
    work_location VARCHAR(50) NOT NULL,
    hire_date DATE NOT NULL,
    -- Sensitive PII columns (used to verify output redaction guardrails)
    personal_email VARCHAR(120) NOT NULL,
    phone_number VARCHAR(25) NOT NULL,
    pan_id VARCHAR(20) NOT NULL,
    home_address TEXT NOT NULL,
    base_salary INTEGER NOT NULL
);

CREATE TABLE leave_balances (
    employee_id VARCHAR(10) PRIMARY KEY REFERENCES employees(employee_id),
    annual_leave_total INTEGER NOT NULL,
    annual_leave_used INTEGER NOT NULL,
    annual_leave_remaining INTEGER NOT NULL,
    sick_leave_remaining INTEGER NOT NULL,
    carryover_days INTEGER NOT NULL,
    updated_at DATE NOT NULL
);

CREATE TABLE it_tickets (
    ticket_id VARCHAR(15) PRIMARY KEY,
    employee_id VARCHAR(10) NOT NULL REFERENCES employees(employee_id),
    category VARCHAR(40) NOT NULL,
    subject VARCHAR(150) NOT NULL,
    status VARCHAR(30) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    created_at DATE NOT NULL
);

CREATE TABLE hardware_assets (
    asset_id VARCHAR(15) PRIMARY KEY,
    employee_id VARCHAR(10) NOT NULL REFERENCES employees(employee_id),
    device_type VARCHAR(40) NOT NULL,
    model_name VARCHAR(80) NOT NULL,
    serial_number VARCHAR(50) NOT NULL,
    assigned_date DATE NOT NULL
);

CREATE TABLE policy_chunks (
    id SERIAL PRIMARY KEY,
    source_file VARCHAR(120) NOT NULL,
    section_title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    embedding vector NOT NULL
);