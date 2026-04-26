import asyncio
from sqlmodel import Session, select
from db.database import engine
from db.models import Street
from services.safety_engine import get_street_combined_score

async def run():
    with Session(engine) as session:
        streets = session.exec(select(Street)).all()
        
    for s in streets:
        res = await get_street_combined_score(s.id, "21:30")
        
        explanations = res.get('explanations', [])
        has_night = any("Sanctuary" in r for r in explanations)
        
        if has_night:
            print(f"WINNER: {s.name} (ID: {s.id})")
            
            score_day = await get_street_combined_score(s.id, "14:00")
            score_late = await get_street_combined_score(s.id, "23:00")
            print(f"Day (14:00): {score_day['score']} | Night (21:30): {res['score']} | Late (23:00): {score_late['score']}")
            print("21:30 reasons:")
            for r in res['explanations']:
                if "Sanctuary" in r: print("  ", r)
            break

if __name__ == "__main__":
    asyncio.run(run())
