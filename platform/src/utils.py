import asyncio

async def async_task(func):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func)
