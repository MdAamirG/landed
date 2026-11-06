"""Prints a fresh driver link for one trip, for opening the driver screens without an SMS.

Run with: cd api && python make_driver_link.py TRP-66134

The link can't be shown again, because only its hash is stored. Run this again for a new one.
"""

import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.driver_links import create_link, driver_url
from app.models import Trip

if __name__ == "__main__":
    trip_code = sys.argv[1]
    with SessionLocal() as session:
        trip = session.scalar(select(Trip).where(Trip.trip_code == trip_code))
        if trip is None:
            sys.exit(f"No trip with code {trip_code}")
        token = create_link(session, trip)
        session.commit()
    print(driver_url(token))
