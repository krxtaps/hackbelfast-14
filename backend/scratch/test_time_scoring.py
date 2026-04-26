import asyncio
from services.safety_engine import get_combined_safety_score

async def test_time_scoring():
    # Near McDowell Pharmacy (09:00-18:00)
    lat, lng = 54.5888, -5.9502
    
    print(f"Testing score for {lat}, {lng}...")
    
    # 11:00 AM (Open)
    res_day = await get_combined_safety_score(lat, lng, check_time="11:00")
    bonus_day = res_day.get('breakdown', {}).get('sanctuaries', {}).get('bonus_applied')
    
    # 11:00 PM (Closed)
    res_night = await get_combined_safety_score(lat, lng, check_time="23:00")
    bonus_night = res_night.get('breakdown', {}).get('sanctuaries', {}).get('bonus_applied')
    
    print(f"\n11:00 AM Sanctuary Bonus: {bonus_day}")
    print(f"11:00 PM Sanctuary Bonus: {bonus_night}")
    
    if bonus_day > bonus_night:
        print("\nSUCCESS: Bonus correctly reduced at night when venues are closed.")
    else:
        print("\nFAILURE: Bonus did not change between day and night.")

if __name__ == "__main__":
    asyncio.run(test_time_scoring())
