from pathlib import Path

import sqlite3

from manufacturing_agents.data.database import init_database, seed_default_factory


def test_database_initializes_expected_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "factory.db"
    init_database(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name;"
            )
        }

    assert {"factories", "production_lines", "products", "raw_materials", "bom_material_requirements", "equipment", "sales_orders", "employees", "inventory", "material_inventory", "production_runs", "quality_inspections", "weight_measurements", "scenarios", "simulation_state", "agent_events", "human_inputs"}.issubset(tables)


def test_database_seed_loads_current_factory_baseline(tmp_path: Path) -> None:
    db_path = tmp_path / "factory_seed.db"
    seed_default_factory(db_path)

    with sqlite3.connect(db_path) as conn:
        product_codes = [
            row[0]
            for row in conn.execute("SELECT product_code FROM products ORDER BY product_code;")
        ]
        line_codes = [
            row[0]
            for row in conn.execute("SELECT code FROM production_lines ORDER BY code;")
        ]
        factory_name = conn.execute("SELECT name FROM factories LIMIT 1;").fetchone()[0]
        material_count = conn.execute("SELECT COUNT(*) FROM raw_materials;").fetchone()[0]

    assert product_codes == ["A", "B", "C"]
    assert line_codes == ["line-1", "line-2", "line-3"]
    assert factory_name == "Example Manufacturing Factory"
    assert material_count >= 4
