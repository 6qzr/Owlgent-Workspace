"""Run the Booking, Pharmacy and Medical Reports demos, then the new-medicine flow."""

import asyncio

from booking_client import run_booking_demo
from pharmacy_client import run_new_medicine_flow, run_pharmacy_demo
from reports_client import run_reports_demo


async def main() -> None:
    """Talk to the three servers together, then end with the diagram's example flow."""
    await asyncio.gather(
        run_booking_demo(),
        run_pharmacy_demo(),
        run_reports_demo(),
    )
    await run_new_medicine_flow()


if __name__ == "__main__":
    asyncio.run(main())
