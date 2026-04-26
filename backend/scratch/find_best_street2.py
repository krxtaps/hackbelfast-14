import asyncio
from sqlmodel import Session, select
from db.database import engine
from db.models import Street
from services.safety_engine import get_street_combined_score

async def run():
    with Session(engine) as session:
        streets = session.exec(select(Street)).all()
        
    for s in streets:
        s_14 = await get_street_combined_score(s.id, "14:00")
        s_21 = await get_street_combined_score(s.id, "21:30")
        s_23 = await get_street_combined_score(s.id, "23:00")
        
        diff_21 = s_14['score'] - s_21['score']
        diff_23 = s_21['score'] - s_23['score']
        
        if diff_23 > 5:
            print(f"{s.name} (ID: {s.id})")
            print(f"  14:00 -> {s_14['score']}")
            print(f"  21:30 -> {s_21['score']}")
            print(f"  23:00 -> {s_23['score']}")
            break

if __name__ == "__main__":
    asyncio.run(run())
