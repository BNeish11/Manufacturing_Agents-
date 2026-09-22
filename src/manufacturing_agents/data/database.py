"""SQLite-backed persistent store for the simulated factory."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from manufacturing_agents.data.factory_data import create_initial_state

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "factory.db"


def _schema_sql() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS factories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            timezone TEXT DEFAULT 'UTC',
            simulation_seed INTEGER DEFAULT 42,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            version INTEGER DEFAULT 1
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS production_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            utilization_pct REAL NOT NULL,
            hourly_capacity INTEGER NOT NULL,
            quality_hold INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            product_code TEXT NOT NULL,
            name TEXT NOT NULL,
            dimensions TEXT NOT NULL,
            business_role TEXT NOT NULL,
            margin_per_unit REAL NOT NULL,
            expected_weight_kg REAL,
            acceptable_min_kg REAL,
            acceptable_max_kg REAL,
            is_active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(factory_id, product_code),
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS raw_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            material_code TEXT NOT NULL,
            name TEXT NOT NULL,
            unit TEXT NOT NULL,
            quantity_on_hand REAL NOT NULL,
            quantity_reserved REAL NOT NULL DEFAULT 0,
            quantity_defective REAL NOT NULL DEFAULT 0,
            reorder_point REAL NOT NULL,
            warning_threshold REAL NOT NULL,
            critical_threshold REAL NOT NULL,
            minimum_operating_quantity REAL NOT NULL,
            data_quality TEXT NOT NULL DEFAULT 'SIMULATED',
            source TEXT NOT NULL DEFAULT 'SIMULATED',
            UNIQUE(factory_id, material_code),
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS bom_material_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            quantity_per_unit REAL NOT NULL,
            notes TEXT,
            UNIQUE(product_id, material_id),
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(material_id) REFERENCES raw_materials(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            supplier_name TEXT NOT NULL,
            lead_time_days INTEGER,
            expedited_lead_time_days INTEGER,
            standard_cost REAL,
            expedited_cost_multiplier REAL DEFAULT 1.0,
            reliability_score REAL DEFAULT 1.0,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS supplier_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            material_id INTEGER,
            expected_delivery_at TEXT,
            actual_delivery_at TEXT,
            quantity_ordered REAL,
            quantity_received REAL,
            status TEXT DEFAULT 'PLANNED',
            is_expedited INTEGER NOT NULL DEFAULT 0,
            update_source TEXT DEFAULT 'SIMULATION',
            FOREIGN KEY(factory_id) REFERENCES factories(id),
            FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY(material_id) REFERENCES raw_materials(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            line_id INTEGER NOT NULL,
            equipment_code TEXT NOT NULL,
            name TEXT NOT NULL,
            equipment_type TEXT NOT NULL,
            status TEXT NOT NULL,
            health_score REAL,
            operating_hours REAL,
            temperature REAL,
            vibration REAL,
            speed REAL,
            error_code TEXT,
            fault_code TEXT,
            current_fault TEXT,
            estimated_repair_minutes INTEGER,
            repair_status TEXT,
            maintenance_due_at TEXT,
            data_quality TEXT DEFAULT 'SIMULATED',
            last_seen_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(factory_id, equipment_code),
            FOREIGN KEY(factory_id) REFERENCES factories(id),
            FOREIGN KEY(line_id) REFERENCES production_lines(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS equipment_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            measured_at TEXT NOT NULL,
            temperature REAL,
            vibration REAL,
            speed REAL,
            status_observed TEXT,
            health_score REAL,
            source TEXT DEFAULT 'SIMULATION',
            data_quality TEXT DEFAULT 'SIMULATED',
            FOREIGN KEY(equipment_id) REFERENCES equipment(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS maintenance_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            maintenance_type TEXT,
            started_at TEXT,
            completed_at TEXT,
            status TEXT,
            summary TEXT,
            required_part_id TEXT,
            technician_id INTEGER,
            downtime_minutes INTEGER,
            FOREIGN KEY(equipment_id) REFERENCES equipment(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            priority_class TEXT,
            credit_status TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sales_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            order_number TEXT NOT NULL,
            order_date TEXT NOT NULL,
            requested_ship_date TEXT,
            promised_ship_date TEXT,
            priority TEXT,
            contractual_delivery INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'OPEN',
            source TEXT DEFAULT 'SIMULATION',
            UNIQUE(factory_id, order_number),
            FOREIGN KEY(factory_id) REFERENCES factories(id),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS order_line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sales_order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price_per_unit REAL,
            reserve_quantity INTEGER NOT NULL DEFAULT 0,
            fulfilled_quantity INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(sales_order_id) REFERENCES sales_orders(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            employee_number TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'AVAILABLE',
            available INTEGER NOT NULL DEFAULT 1,
            overtime_hours REAL NOT NULL DEFAULT 0,
            max_overtime_hours REAL NOT NULL DEFAULT 8,
            active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(factory_id, employee_number),
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS employee_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            skill_type TEXT NOT NULL,
            skill_value TEXT NOT NULL,
            qualification_level REAL NOT NULL DEFAULT 1.0,
            UNIQUE(employee_id, skill_type, skill_value),
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS employee_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            line_id INTEGER,
            assigned_at TEXT NOT NULL,
            unassigned_at TEXT,
            assignment_type TEXT NOT NULL DEFAULT 'LINE',
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            FOREIGN KEY(employee_id) REFERENCES employees(id),
            FOREIGN KEY(line_id) REFERENCES production_lines(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS employee_shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            shift_name TEXT NOT NULL,
            shift_start TEXT NOT NULL,
            shift_end TEXT NOT NULL,
            coverage_status TEXT NOT NULL DEFAULT 'COVERED',
            FOREIGN KEY(factory_id) REFERENCES factories(id),
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity_on_hand INTEGER NOT NULL,
            quantity_reserved INTEGER NOT NULL DEFAULT 0,
            quantity_available INTEGER NOT NULL,
            quantity_in_production INTEGER NOT NULL DEFAULT 0,
            quantity_incoming INTEGER NOT NULL DEFAULT 0,
            quantity_defective INTEGER NOT NULL DEFAULT 0,
            quantity_accepted INTEGER NOT NULL DEFAULT 0,
            quantity_rejected INTEGER NOT NULL DEFAULT 0,
            quality_hold_quantity INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(factory_id, product_id),
            FOREIGN KEY(factory_id) REFERENCES factories(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS material_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            quantity_on_hand REAL NOT NULL,
            quantity_reserved REAL NOT NULL DEFAULT 0,
            quantity_available REAL NOT NULL,
            quantity_in_transit REAL NOT NULL DEFAULT 0,
            quantity_defective REAL NOT NULL DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(factory_id, material_id),
            FOREIGN KEY(factory_id) REFERENCES factories(id),
            FOREIGN KEY(material_id) REFERENCES raw_materials(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS production_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            line_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            started_at TEXT,
            ended_at TEXT,
            planned_quantity INTEGER,
            actual_quantity INTEGER,
            accepted_quantity INTEGER,
            defective_quantity INTEGER,
            production_rate_units_per_hour REAL,
            downtime_minutes INTEGER,
            reason_for_downtime TEXT,
            status TEXT NOT NULL DEFAULT 'PLANNED',
            FOREIGN KEY(factory_id) REFERENCES factories(id),
            FOREIGN KEY(line_id) REFERENCES production_lines(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS quality_inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            product_id INTEGER,
            line_id INTEGER,
            inspected_at TEXT NOT NULL,
            inspector_type TEXT NOT NULL,
            result_code TEXT,
            verdict TEXT,
            notes TEXT,
            severity TEXT,
            FOREIGN KEY(factory_id) REFERENCES factories(id),
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(line_id) REFERENCES production_lines(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS weight_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            observed_weight_kg REAL NOT NULL,
            expected_weight_kg REAL NOT NULL,
            acceptable_min_kg REAL NOT NULL,
            acceptable_max_kg REAL NOT NULL,
            variance_pct REAL,
            measured_at TEXT NOT NULL,
            source TEXT DEFAULT 'SIMULATION',
            status TEXT DEFAULT 'NORMAL',
            FOREIGN KEY(factory_id) REFERENCES factories(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS defects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            product_id INTEGER,
            line_id INTEGER,
            defect_code TEXT,
            description TEXT,
            severity TEXT,
            quantity INTEGER,
            detected_at TEXT,
            root_cause TEXT,
            FOREIGN KEY(factory_id) REFERENCES factories(id),
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(line_id) REFERENCES production_lines(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            seed INTEGER NOT NULL,
            description TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(factory_id, name),
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS simulation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            simulation_time TEXT,
            event_type TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            source TEXT,
            payload_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS simulation_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            simulation_time TEXT NOT NULL,
            tick INTEGER NOT NULL,
            random_seed INTEGER NOT NULL,
            state_version INTEGER NOT NULL,
            state_hash TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(factory_id),
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS agent_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            agent_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            state_version INTEGER,
            trigger TEXT,
            summary TEXT,
            evidence_json TEXT,
            recommendation_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS human_inputs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER NOT NULL,
            input_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            subject_type TEXT,
            subject_id TEXT,
            summary TEXT,
            decision TEXT,
            approved INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS simulation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_id INTEGER,
            scenario_name TEXT,
            seed INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            tick_count INTEGER NOT NULL DEFAULT 0,
            final_state_version INTEGER,
            metrics_json TEXT,
            FOREIGN KEY(factory_id) REFERENCES factories(id)
        );
        """,
    ]


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    target = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: str | Path | None = None) -> Path:
    conn = get_connection(db_path)
    try:
        for statement in _schema_sql():
            conn.execute(statement)
        conn.commit()
        return Path(conn.execute("PRAGMA database_list").fetchone()[2])
    finally:
        conn.close()


def seed_default_factory(db_path: str | Path | None = None) -> Path:
    target_path = init_database(db_path)
    state = create_initial_state()

    conn = get_connection(target_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO factories(name, timezone, simulation_seed, version) VALUES (?, ?, ?, ?)",
            (state.factory_name, "UTC", 42, 1),
        )
        factory_id = conn.execute("SELECT id FROM factories WHERE name = ? LIMIT 1", (state.factory_name,)).fetchone()["id"]

        line_rows = [
            (factory_id, "line-1", "Production Line 1", "RUNNING", 63.0, 240, 0, 1),
            (factory_id, "line-2", "Production Line 2", "DOWN", 0.0, 220, 0, 1),
            (factory_id, "line-3", "Production Line 3", "RUNNING", 81.0, 180, 0, 1),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO production_lines(factory_id, code, name, status, utilization_pct, hourly_capacity, quality_hold, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            line_rows,
        )

        conn.executemany(
            "INSERT OR IGNORE INTO products(factory_id, product_code, name, dimensions, business_role, margin_per_unit, expected_weight_kg, acceptable_min_kg, acceptable_max_kg) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (factory_id, "A", "Product A", "12x12", "HIGH_VOLUME", 18.0, 0.40, 0.37, 0.43),
                (factory_id, "B", "Product B", "24x24", "HIGHEST_MARGIN", 42.0, 0.95, 0.89, 1.01),
                (factory_id, "C", "Product C", "36x36", "CONTRACTUAL_DELIVERY", 24.0, 1.80, 1.69, 1.91),
            ],
        )

        materials = [
            (factory_id, "liner-board", "Corrugated liner board", "m2", 5000.0, 0.0, 0.0, 1250.0, 1250.0, 500.0, 500.0, "SIMULATED", "SIMULATED"),
            (factory_id, "corrugated-medium", "Corrugated medium", "m2", 2500.0, 0.0, 0.0, 625.0, 625.0, 250.0, 250.0, "SIMULATED", "SIMULATED"),
            (factory_id, "adhesive", "Box adhesive", "kg", 120.0, 0.0, 0.0, 30.0, 30.0, 12.0, 12.0, "SIMULATED", "SIMULATED"),
            (factory_id, "printing-ink", "Printing ink", "L", 30.0, 0.0, 0.0, 7.5, 7.5, 3.0, 3.0, "SIMULATED", "SIMULATED"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO raw_materials(factory_id, material_code, name, unit, quantity_on_hand, quantity_reserved, quantity_defective, reorder_point, warning_threshold, critical_threshold, minimum_operating_quantity, data_quality, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            materials,
        )

        product_map = {code: conn.execute("SELECT id FROM products WHERE factory_id = ? AND product_code = ?", (factory_id, code)).fetchone()["id"] for code in ["A", "B", "C"]}
        material_map = {code: conn.execute("SELECT id FROM raw_materials WHERE factory_id = ? AND material_code = ?", (factory_id, code)).fetchone()["id"] for code in ["liner-board", "corrugated-medium", "adhesive", "printing-ink"]}

        bom_rows = [
            (product_map["A"], material_map["liner-board"], 0.60, "Product A liner board requirement"),
            (product_map["A"], material_map["corrugated-medium"], 0.30, "Product A medium requirement"),
            (product_map["A"], material_map["adhesive"], 0.020, "Product A adhesive requirement"),
            (product_map["A"], material_map["printing-ink"], 0.004, "Product A ink requirement"),
            (product_map["B"], material_map["liner-board"], 1.80, "Product B liner board requirement"),
            (product_map["B"], material_map["corrugated-medium"], 0.90, "Product B medium requirement"),
            (product_map["B"], material_map["adhesive"], 0.035, "Product B adhesive requirement"),
            (product_map["B"], material_map["printing-ink"], 0.007, "Product B ink requirement"),
            (product_map["C"], material_map["liner-board"], 3.60, "Product C liner board requirement"),
            (product_map["C"], material_map["corrugated-medium"], 1.80, "Product C medium requirement"),
            (product_map["C"], material_map["adhesive"], 0.060, "Product C adhesive requirement"),
            (product_map["C"], material_map["printing-ink"], 0.012, "Product C ink requirement"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO bom_material_requirements(product_id, material_id, quantity_per_unit, notes) VALUES (?, ?, ?, ?)",
            bom_rows,
        )

        customer_id = conn.execute(
            "INSERT OR IGNORE INTO customers(factory_id, customer_name, priority_class, credit_status, active) VALUES (?, ?, ?, ?, ?)",
            (factory_id, "Northwind Retail", "HIGH", "GOOD", 1),
        ).lastrowid
        conn.execute(
            "INSERT OR IGNORE INTO sales_orders(factory_id, customer_id, order_number, order_date, requested_ship_date, promised_ship_date, priority, contractual_delivery, status, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (factory_id, customer_id, "order-a", "2026-09-18", "2026-09-18", "2026-09-18", "HIGH", 0, "OPEN", "SIMULATION"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO order_line_items(sales_order_id, product_id, quantity, price_per_unit, reserve_quantity, fulfilled_quantity) VALUES (?, ?, ?, ?, ?, ?)",
            (1, product_map["A"], 5000, 18.0, 0, 0),
        )

        conn.execute(
            "INSERT OR IGNORE INTO inventory(factory_id, product_id, quantity_on_hand, quantity_reserved, quantity_available, quantity_in_production, quantity_incoming, quantity_defective, quantity_accepted, quantity_rejected, quality_hold_quantity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (factory_id, product_map["A"], 1000, 700, 300, 300, 0, 20, 1180, 0, 0),
        )
        conn.execute(
            "INSERT OR IGNORE INTO inventory(factory_id, product_id, quantity_on_hand, quantity_reserved, quantity_available, quantity_in_production, quantity_incoming, quantity_defective, quantity_accepted, quantity_rejected, quality_hold_quantity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (factory_id, product_map["B"], 500, 200, 300, 150, 0, 10, 590, 0, 0),
        )
        conn.execute(
            "INSERT OR IGNORE INTO inventory(factory_id, product_id, quantity_on_hand, quantity_reserved, quantity_available, quantity_in_production, quantity_incoming, quantity_defective, quantity_accepted, quantity_rejected, quality_hold_quantity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (factory_id, product_map["C"], 300, 60, 240, 150, 0, 8, 342, 0, 0),
        )

        conn.executemany(
            "INSERT OR IGNORE INTO material_inventory(factory_id, material_id, quantity_on_hand, quantity_reserved, quantity_available, quantity_in_transit, quantity_defective) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (factory_id, material_map["liner-board"], 5000.0, 0.0, 5000.0, 0.0, 0.0),
                (factory_id, material_map["corrugated-medium"], 2500.0, 0.0, 2500.0, 0.0, 0.0),
                (factory_id, material_map["adhesive"], 120.0, 0.0, 120.0, 0.0, 0.0),
                (factory_id, material_map["printing-ink"], 30.0, 0.0, 30.0, 0.0, 0.0),
            ],
        )

        conn.executemany(
            "INSERT OR IGNORE INTO employees(factory_id, employee_number, role, status, available, overtime_hours, max_overtime_hours) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(factory_id, f"employee-{index}", "Production Technician", "AVAILABLE" if index > 12 else "ASSIGNED", 1 if index > 12 else 0, 0.0, 8.0) for index in range(1, 126)],
        )

        conn.execute(
            "INSERT OR IGNORE INTO equipment(factory_id, line_id, equipment_code, name, equipment_type, status, health_score, operating_hours, temperature, vibration, speed, error_code, fault_code, current_fault, estimated_repair_minutes, repair_status, maintenance_due_at, data_quality, last_seen_at) VALUES (?, (SELECT id FROM production_lines WHERE factory_id = ? AND code = 'line-2' LIMIT 1), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                factory_id,
                factory_id,
                "equipment-2",
                "Line 2 Main Cell",
                "MAIN_CELL",
                "DOWN",
                0.42,
                220.0,
                None,
                None,
                None,
                None,
                None,
                None,
                95,
                "PENDING",
                None,
                "UNKNOWN",
                None,
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO equipment(factory_id, line_id, equipment_code, name, equipment_type, status, health_score, operating_hours, temperature, vibration, speed, error_code, fault_code, current_fault, estimated_repair_minutes, repair_status, maintenance_due_at, data_quality, last_seen_at) VALUES (?, (SELECT id FROM production_lines WHERE factory_id = ? AND code = 'line-1' LIMIT 1), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (factory_id, factory_id, "equipment-1", "Line 1 Main Cell", "MAIN_CELL", "RUNNING", 1.0, 180.0, None, None, None, None, None, None, None, None, None, "SIMULATED", None),
        )
        conn.execute(
            "INSERT OR IGNORE INTO equipment(factory_id, line_id, equipment_code, name, equipment_type, status, health_score, operating_hours, temperature, vibration, speed, error_code, fault_code, current_fault, estimated_repair_minutes, repair_status, maintenance_due_at, data_quality, last_seen_at) VALUES (?, (SELECT id FROM production_lines WHERE factory_id = ? AND code = 'line-3' LIMIT 1), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (factory_id, factory_id, "equipment-3", "Line 3 Main Cell", "MAIN_CELL", "RUNNING", 1.0, 200.0, None, None, None, None, None, None, None, None, None, "SIMULATED", None),
        )

        conn.execute(
            "INSERT OR IGNORE INTO scenarios(factory_id, name, seed, description, enabled) VALUES (?, ?, ?, ?, ?)",
            (factory_id, "line-2-failure", 42, "Baseline line-2 failure scenario.", 1),
        )
        conn.execute(
            "INSERT OR IGNORE INTO simulation_state(factory_id, simulation_time, tick, random_seed, state_version, state_hash) VALUES (?, ?, ?, ?, ?, ?)",
            (factory_id, "08:00", 0, 42, 1, "baseline"),
        )
        conn.commit()
    finally:
        conn.close()

    return target_path


def ensure_default_database() -> Path:
    return seed_default_factory(DEFAULT_DB_PATH)


if __name__ == "__main__":
    ensure_default_database()
