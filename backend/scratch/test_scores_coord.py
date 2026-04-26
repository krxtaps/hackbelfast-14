import asyncio
from services.safety_engine import get_combined_safety_score

async def run_tests():
    lat, lng = 54.594961, -5.950914
    for t in ["14:00", "23:00", "02:00"]:
        res = await get_combined_safety_score(lat, lng, t)
        print(f"\n--- Near Night Club @ {t} ---")
        print(f"Score: {res['score']}/100")
        print(res.keys())
        print(res.get('explanations'))
        
if __name__ == "__main__":
    asyncio.run(run_tests())
