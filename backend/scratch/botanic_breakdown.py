import asyncio
from sqlmodel import Session, select
from db.database import engine
from db.models import Street
from services.safety_engine import get_street_combined_score

async def run():
    with Session(engine) as session:
        streets = session.exec(select(Street).where(Street.name == "Botanic Avenue")).all()
        
    for s in streets[:1]: # Just look at the first segment
        res = await get_street_combined_score(s.id, "14:00")
        print(f"Segment: {s.id}")
        print("Score:", res["score"])
        print("Breakdown:", res["breakdown"])
        for exp in res["explanations"]:
            if "crime" in exp.lower() or "anti-social" in exp.lower():
                print("CRIME:", exp)

if __name__ == "__main__":
    asyncio.run(run())
