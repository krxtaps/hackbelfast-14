import asyncio
from services.safety_engine import get_street_combined_score

async def run():
    for t in ["14:00", "21:30", "23:00"]:
        res = await get_street_combined_score("botanic_e2929def", t)
        print(f"\n--- {t} ---")
        for r in res['explanations']:
            if "Sanctuary" in r: print(r)

if __name__ == "__main__":
    asyncio.run(run())
