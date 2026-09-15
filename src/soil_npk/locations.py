"""India location lookup backed by the official LGD/Census directory export.

The full village directory has hundreds of thousands of rows, so it is loaded
into SQLite instead of being sent to the browser.  The UI fetches only the
next level after a user selects its parent location.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
from pathlib import Path

from openpyxl import load_workbook


APP_DATA_DIR = Path(os.getenv("NPK_APP_DATA_DIR", "data/app_data"))
DATABASE_PATH = Path(os.getenv("NPK_DATABASE_PATH", str(APP_DATA_DIR / "terranpk.db")))

# State/UT selector is always available; lower levels come from the official
# directory export so village names remain current and do not depend on a demo list.
INDIA_STATES_AND_UTS = (
    "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chandigarh",
    "Chhattisgarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry",
    "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal",
)
_CANONICAL_STATES = {name.casefold(): name for name in INDIA_STATES_AND_UTS}


def _canonical_state(name: str) -> str:
    normalized = name.strip().casefold()
    return _CANONICAL_STATES.get(normalized, _CANONICAL_STATES.get(normalized.removeprefix("the "), name.strip()))


def _connection() -> sqlite3.Connection:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialise_locations() -> None:
    with _connection() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS india_locations (
            state TEXT NOT NULL, district TEXT NOT NULL, tehsil TEXT NOT NULL, village TEXT NOT NULL,
            PRIMARY KEY (state, district, tehsil, village)
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS india_districts (
            state TEXT NOT NULL, district TEXT NOT NULL, PRIMARY KEY (state, district)
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS india_tehsils (
            state TEXT NOT NULL, district TEXT NOT NULL, tehsil TEXT NOT NULL,
            PRIMARY KEY (state, district, tehsil)
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_location_district ON india_locations(state, district)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_location_tehsil ON india_locations(state, district, tehsil)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_imported_district ON india_districts(state, district)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_imported_tehsil ON india_tehsils(state, district, tehsil)")
    _bootstrap_district_workbook()
    _bootstrap_tehsil_workbook()
    _bootstrap_village_workbook()


def _bootstrap_district_workbook() -> None:
    """Load the supplied all-India district workbook when it is present."""
    workbooks = sorted(Path.cwd().glob("All_Districtof_India_*.xlsx"))
    if not workbooks:
        return
    with _connection() as connection:
        if connection.execute("SELECT COUNT(*) FROM india_districts").fetchone()[0]:
            return
    workbook = load_workbook(workbooks[-1], read_only=True, data_only=True)
    sheet = workbook.active
    headers = [str(value or "").strip().lower() for value in next(sheet.iter_rows(min_row=2, max_row=2, values_only=True))]
    state_index = next((index for index, value in enumerate(headers) if "state name" in value), None)
    district_index = next((index for index, value in enumerate(headers) if "district name" in value), None)
    if state_index is None or district_index is None:
        raise ValueError("District workbook must contain State Name and District Name columns on row 2.")
    records = []
    for row in sheet.iter_rows(min_row=3, values_only=True):
        state, district = _canonical_state(str(row[state_index] or "")), str(row[district_index] or "").strip()
        if state and district:
            records.append((state, district))
    with _connection() as connection:
        connection.executemany("INSERT OR IGNORE INTO india_districts(state, district) VALUES (?, ?)", records)


def _workbook_column_indexes(sheet, required: tuple[str, ...]) -> dict[str, int]:
    """Resolve official LGD workbook headers without relying on exact punctuation."""
    headers = [str(value or "").strip().lower() for value in next(sheet.iter_rows(min_row=2, max_row=2, values_only=True))]
    indexes: dict[str, int] = {}
    for field in required:
        matches = [index for index, header in enumerate(headers) if field in header]
        if not matches:
            raise ValueError(f"Workbook must contain a {field.title()} column on row 2.")
        indexes[field] = matches[0]
    return indexes


def _insert_batches(connection: sqlite3.Connection, query: str, rows) -> None:
    """Write a large official directory without retaining it all in application memory."""
    batch: list[tuple[str, ...]] = []
    for row in rows:
        batch.append(row)
        if len(batch) == 5_000:
            connection.executemany(query, batch)
            batch.clear()
    if batch:
        connection.executemany(query, batch)


def _bootstrap_tehsil_workbook() -> None:
    """Load the supplied State → District → Sub-district (Tehsil) directory."""
    workbooks = sorted(Path.cwd().glob("All_Sub_Districtof_India_*.xlsx"))
    if not workbooks:
        return
    with _connection() as connection:
        if connection.execute("SELECT COUNT(*) FROM india_tehsils").fetchone()[0]:
            return
    workbook = load_workbook(workbooks[-1], read_only=True, data_only=True)
    sheet = workbook.active
    indexes = _workbook_column_indexes(sheet, ("state name", "district name", "sub-district name"))

    def rows():
        for row in sheet.iter_rows(min_row=3, values_only=True):
            state = _canonical_state(str(row[indexes["state name"]] or ""))
            district = str(row[indexes["district name"]] or "").strip()
            tehsil = str(row[indexes["sub-district name"]] or "").strip()
            if state and district and tehsil:
                yield state, district, tehsil

    with _connection() as connection:
        _insert_batches(
            connection,
            "INSERT OR IGNORE INTO india_tehsils(state, district, tehsil) VALUES (?, ?, ?)",
            rows(),
        )
    workbook.close()


def _bootstrap_village_workbook() -> None:
    """Load the supplied all-India village directory for filtered village lookups."""
    workbooks = sorted(Path.cwd().glob("All_Villagesof_India_*.xlsx"))
    if not workbooks:
        return
    with _connection() as connection:
        if connection.execute("SELECT COUNT(*) FROM india_locations").fetchone()[0]:
            return
    workbook = load_workbook(workbooks[-1], read_only=True, data_only=True)
    sheet = workbook.active
    indexes = _workbook_column_indexes(sheet, ("state name", "district name", "sub-district name", "village name"))

    def rows():
        for row in sheet.iter_rows(min_row=3, values_only=True):
            state = _canonical_state(str(row[indexes["state name"]] or ""))
            district = str(row[indexes["district name"]] or "").strip()
            tehsil = str(row[indexes["sub-district name"]] or "").strip()
            village = str(row[indexes["village name"]] or "").strip()
            if state and district and tehsil and village:
                yield state, district, tehsil, village

    with _connection() as connection:
        _insert_batches(
            connection,
            "INSERT OR IGNORE INTO india_locations(state, district, tehsil, village) VALUES (?, ?, ?, ?)",
            rows(),
        )
    workbook.close()


def import_directory(csv_path: str | Path) -> int:
    """Import an LGD CSV with state, district, sub-district and village columns."""
    path = Path(csv_path)
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError("Location CSV needs a header row.")
        normalised = {re.sub(r"[^a-z]", "", header.lower()): header for header in reader.fieldnames}
        aliases = {
            "state": ("state", "statename", "statenameinenglish"),
            "district": ("district", "districtname", "districtnameinenglish"),
            "tehsil": ("tehsil", "tehsilname", "subdistrict", "subdistrictname", "subdistrictnameinenglish"),
            "village": ("village", "villagename", "villagenameinenglish"),
        }
        columns = {key: next((normalised[name] for name in choices if name in normalised), None) for key, choices in aliases.items()}
        if not all(columns.values()):
            raise ValueError("Location CSV requires State, District, Sub-District/Tehsil and Village columns.")
        records = [
            tuple(row[str(columns[field])].strip() for field in ("state", "district", "tehsil", "village"))
            for row in reader
            if all(row.get(str(columns[field]), "").strip() for field in columns)
        ]
    initialise_locations()
    with _connection() as connection:
        connection.execute("DELETE FROM india_locations")
        connection.executemany(
            "INSERT OR IGNORE INTO india_locations(state, district, tehsil, village) VALUES (?, ?, ?, ?)", records
        )
    return len(records)


def _items(query: str, values: tuple[str, ...]) -> list[str]:
    with _connection() as connection:
        rows = connection.execute(query, values).fetchall()
    return [str(row[0]) for row in rows]


def states() -> list[str]:
    with _connection() as connection:
        imported = [str(row[0]) for row in connection.execute("SELECT DISTINCT state FROM india_districts").fetchall()]
    deduplicated = {name.casefold(): name for name in (*INDIA_STATES_AND_UTS, *(_canonical_state(name) for name in imported))}
    return sorted(deduplicated.values(), key=str.casefold)


def districts(state: str) -> list[str]:
    return _items(
        """SELECT district FROM (
        SELECT DISTINCT district FROM india_locations WHERE state=? COLLATE NOCASE
        UNION
        SELECT DISTINCT district FROM india_districts WHERE state=? COLLATE NOCASE
        ) ORDER BY district COLLATE NOCASE""",
        (state, state),
    )


def tehsils(state: str, district: str) -> list[str]:
    return _items(
        """SELECT tehsil FROM (
        SELECT DISTINCT tehsil FROM india_locations WHERE state=? AND district=? COLLATE NOCASE
        UNION
        SELECT DISTINCT tehsil FROM india_tehsils WHERE state=? AND district=? COLLATE NOCASE
        ) ORDER BY tehsil COLLATE NOCASE""",
        (state, district, state, district),
    )


def villages(state: str, district: str, tehsil: str) -> list[str]:
    return _items(
        "SELECT village FROM india_locations WHERE state=? AND district=? AND tehsil=? ORDER BY village COLLATE NOCASE",
        (state, district, tehsil),
    )


def location_status() -> dict[str, int]:
    with _connection() as connection:
        count = int(connection.execute("SELECT COUNT(*) FROM india_locations").fetchone()[0])
        districts_count = int(connection.execute("SELECT COUNT(*) FROM india_districts").fetchone()[0])
        tehsils_count = int(connection.execute("SELECT COUNT(*) FROM india_tehsils").fetchone()[0])
    return {
        "loaded_location_rows": count,
        "loaded_districts": districts_count,
        "loaded_tehsils": tehsils_count,
        "states": len(states()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the official India location directory into MittiMitra.")
    parser.add_argument("--import-csv", type=Path, required=True, help="CSV with state,district,tehsil,village headers")
    args = parser.parse_args()
    print(f"Imported {import_directory(args.import_csv):,} location rows.")


if __name__ == "__main__":
    main()
