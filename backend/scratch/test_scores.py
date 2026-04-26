import asyncio
from services.safety_engine import get_street_combined_score
import json

async def run_tests():
    for t in ["14:00", "23:00", "02:00"]:
        res = await get_street_combined_score("botanic_4d9004d3", t)
        print(f"\n--- Botanic Avenue @ {t} ---")
        print(f"Score: {res['score']}/100")
        print(f"Sanctuaries Bonus: {res['breakdown']['sanctuaries']} (Count: {res['sanctuaries']['count']})")
        print(f"Amenities Bonus: {res['breakdown']['amenities']} (Count: {res['amenities']['count']})")
        print("Top Reasons:")
        for r in res['explanations'][:3]:
            print(f" - {r}")

if __name__ == "__main__":
    asyncio.run(run_tests())
