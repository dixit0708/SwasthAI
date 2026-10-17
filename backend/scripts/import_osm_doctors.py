"""Import a city's hospitals, clinics and doctors from OpenStreetMap.

Run from backend/ (uses MONGODB_URL / DATABASE_NAME from backend/.env):

    python -m scripts.import_osm_doctors --city Moradabad --admin-level 5   # whole district
    python -m scripts.import_osm_doctors --city Moradabad --dry-run

Data is © OpenStreetMap contributors, licensed ODbL; storing it is allowed
with attribution, which every listing's API response carries. Re-running
refreshes the city: listings removed from OSM are removed here too.
Uses the public Overpass API, which needs no key or account.
"""
import argparse
import asyncio
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from app.db.mongodb import close_mongo_connection, connect_to_mongo, db_manager
from app.services.doctor_directory_service import SOURCE_OSM
from app.services.doctor_import import osm_element_to_listing, replace_listings

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "SwasthAI-doctor-directory-import (student project)"

QUERY_TEMPLATE = """
[out:json][timeout:90];
area["name"="{city}"]["boundary"="administrative"]{admin_level}->.city;
(
  nwr(area.city)["amenity"~"^(hospital|clinic|doctors|dentist)$"];
  nwr(area.city)["healthcare"~"^(hospital|clinic|doctor|dentist|centre)$"];
);
out tags center;
"""


def fetch_elements(city: str, admin_level: int | None = None) -> list[dict]:
    if '"' in city or "\\" in city:
        raise ValueError("City name must not contain quotes or backslashes.")
    level = f'["admin_level"="{admin_level}"]' if admin_level else ""
    query = QUERY_TEMPLATE.format(city=city, admin_level=level)
    data = urllib.parse.urlencode({"data": query}).encode()

    # Public Overpass servers are often overloaded (504/429), so try mirrors.
    last_error = None
    for url in OVERPASS_URLS:
        request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response).get("elements", [])
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"{url} failed ({exc}); trying next server...")
            last_error = exc
    raise RuntimeError("All Overpass servers failed; try again in a few minutes.") from last_error


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", required=True)
    parser.add_argument(
        "--admin-level", type=int, choices=range(2, 11), metavar="N",
        help="OSM boundary level to match, e.g. 5 = district in India (default: any level)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print counts only")
    args = parser.parse_args()

    elements = fetch_elements(args.city, args.admin_level)
    listings = {}
    for element in elements:
        listing = osm_element_to_listing(element, args.city)
        if listing:
            listings[listing["source_id"]] = listing  # Overpass can repeat elements
    listings = list(listings.values())

    with_specialty = sum(1 for listing in listings if listing["specialties"])
    print(f"OSM features: {len(elements)}, usable named listings: {len(listings)}, "
          f"with a specialty inferred from the name: {with_specialty}")
    if not listings:
        print("Nothing to import (check the city name spelling as used on OpenStreetMap).")
        return 1
    if args.dry_run:
        return 0

    await connect_to_mongo()
    if db_manager.db is None:
        print("Could not connect to MongoDB.")
        return 1
    try:
        upserted, removed = await replace_listings(listings, {"source": SOURCE_OSM, "city": args.city})
    finally:
        await close_mongo_connection()
    print(f"Imported/updated {upserted} listings, removed {removed} stale ones.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
