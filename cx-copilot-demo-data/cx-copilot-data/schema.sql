CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY, customer_name TEXT NOT NULL, segment TEXT,
  primary_contact TEXT, email TEXT, phone TEXT, city TEXT, state TEXT, account_status TEXT
);
CREATE TABLE vehicles (
  unit_number TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  vin TEXT UNIQUE, vehicle_type TEXT, make TEXT, model TEXT, model_year INTEGER,
  operational_status TEXT, current_location TEXT, odometer_miles INTEGER
);
CREATE TABLE contracts (
  contract_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  unit_number TEXT NOT NULL REFERENCES vehicles(unit_number), contract_type TEXT,
  start_date TEXT, end_date TEXT, monthly_rate REAL, status TEXT, billing_frequency TEXT
);
CREATE TABLE invoices (
  invoice_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  contract_id TEXT NOT NULL REFERENCES contracts(contract_id), unit_number TEXT NOT NULL REFERENCES vehicles(unit_number),
  billing_period_start TEXT, billing_period_end TEXT, invoice_date TEXT, due_date TEXT,
  amount REAL, charge_type TEXT, status TEXT, related_invoice_id TEXT REFERENCES invoices(invoice_id)
);
CREATE TABLE payments (
  payment_id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id),
  customer_id TEXT NOT NULL REFERENCES customers(customer_id), payment_date TEXT,
  amount REAL, payment_method TEXT, transaction_reference TEXT UNIQUE, status TEXT
);
CREATE TABLE service_records (
  service_id TEXT PRIMARY KEY, unit_number TEXT NOT NULL REFERENCES vehicles(unit_number),
  customer_id TEXT NOT NULL REFERENCES customers(customer_id), service_type TEXT,
  opened_at TEXT, completed_at TEXT, downtime_hours REAL, service_location TEXT, work_summary TEXT, status TEXT
);
CREATE TABLE cases (
  case_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  unit_number TEXT REFERENCES vehicles(unit_number), invoice_id TEXT REFERENCES invoices(invoice_id),
  opened_at TEXT, channel TEXT, issue_type TEXT, priority TEXT, status TEXT, subject TEXT, description TEXT
);
CREATE TABLE case_interactions (
  interaction_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  interaction_at TEXT, channel TEXT, direction TEXT, agent_id TEXT, summary TEXT
);
