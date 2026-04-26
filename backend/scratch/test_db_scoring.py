import asyncio
from services.safety_engine import get_combined_safety_score

async def test_db_scoring():
    # Near Michael Dwyers
    lat, lng = 54.5949, -5.9509
    print(f"Testing score for {lat}, {lng}...")
    
    result = await get_combined_safety_score(lat, lng)
    
    print("\nResults:")
    print(f"Total Score: {result.get('score')}")
    print(f"Sanctuary Bonus: {result.get('breakdown', {}).get('sanctuaries', {}).get('bonus_applied')}")
    print(f"Amenity Bonus: {result.get('breakdown', {}).get('amenities', {}).get('bonus_applied')}")
    
    sanctuaries = result.get('raw_data', {}).get('sanctuaries', {}).get('items', [])
    print(f"\nSanctuaries Found ({len(sanctuaries)}):")
    for s in sanctuaries[:5]:
        print(f"- {s.get('name')} ({s.get('type')}): Bonus {s.get('bonus')}, Trust {s.get('trust')}")

if __name__ == "__main__":
    asyncio.run(test_db_scoring())
