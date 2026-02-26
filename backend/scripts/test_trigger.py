import asyncio
import httpx

async def test():
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post("http://localhost:8000/api/v1/leads/f03fb5c5-aaf4-4779-b2db-17065b7a4f18/research?force_refresh=true")
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
