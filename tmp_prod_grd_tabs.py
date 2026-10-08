import asyncio
from sqlalchemy import text
from app.core.database import SessionFactory

async def main():
    async with SessionFactory() as session:
        rows = await session.execute(text("select id, sheet_id, sheet_name, enabled, classification_status from platform.source_sheet where source_id='5563523b-9edd-4ae1-b593-2faa5789a417' order by sheet_id"))
        for row in rows:
            print(dict(row._mapping))

asyncio.run(main())
