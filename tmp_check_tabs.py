import asyncio
from sqlalchemy import text
from app.core.database import SessionFactory
async def main():
    async with SessionFactory() as s:
        r=await s.execute(text("select source_id,count(*) as n from platform.source_sheet where source_id='5563523b-9edd-4ae1-b593-2faa5789a417' group by source_id"))
        print([dict(x._mapping) for x in r])
asyncio.run(main())
