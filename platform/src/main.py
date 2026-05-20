import asyncio
from platform.src.api.server import app

async def main():
    await app.startup_event()
    print("Server started")

if __name__ == "__main__":
    asyncio.run(main())
