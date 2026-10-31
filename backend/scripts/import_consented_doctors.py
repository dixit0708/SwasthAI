"""Import doctors who personally agreed to be listed, from a CSV file.

Run from backend/:

    python -m scripts.import_consented_doctors path/to/doctors.csv

Columns: see backend/scripts/consented_doctors_template.csv. A row without
consent_given=yes and a consent_date is rejected. The whole file is
validated before anything is written, and the import replaces the previous
consented list, so deleting a doctor's row and re-running removes their
details (how a withdrawn consent is honoured).

The filled-in CSV holds personal phone numbers: keep it out of git.
"""
import argparse
import asyncio
import csv
import sys

from app.db.mongodb import close_mongo_connection, connect_to_mongo, db_manager
from app.services.doctor_directory_service import SOURCE_CONSENTED
from app.services.doctor_import import consented_row_to_listing, replace_listings


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv_path")
    args = parser.parse_args()

    with open(args.csv_path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    listings, errors = [], []
    for line_number, row in enumerate(rows, start=2):
        try:
            listings.append(consented_row_to_listing(row))
        except ValueError as exc:
            errors.append(f"  line {line_number}: {exc}")
    if errors:
        print("Nothing imported. Fix these rows first:\n" + "\n".join(errors))
        return 1

    await connect_to_mongo()
    if db_manager.db is None:
        print("Could not connect to MongoDB.")
        return 1
    try:
        upserted, removed = await replace_listings(listings, {"source": SOURCE_CONSENTED})
    finally:
        await close_mongo_connection()
    print(f"Imported/updated {upserted} consented doctors, removed {removed} no longer listed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
