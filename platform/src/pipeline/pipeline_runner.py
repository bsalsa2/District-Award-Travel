import asyncio
from fastapi import FastAPI
from platform.src.pipeline.pipeline import app

async def run_pipeline():
    # Run the pipeline every 5 seconds
    while True:
        # Fetch the latest data from the database
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM award_travel_data')
        data = cursor.fetchall()

        # Process the data
        result = process_data(data)

        # Update the dashboard with the latest insights
        await update_dashboard(result)

        await asyncio.sleep(5)

async def update_dashboard(data: Dict):
    # Update the dashboard with the latest insights
    # This can be implemented using a dashboard library such as Dash or Bokeh
    pass

# Run the pipeline
async def main():
    await run_pipeline()

# Start the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
