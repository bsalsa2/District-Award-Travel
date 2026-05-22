from fastapi import FastAPI
from fastapi.responses import JSONResponse
from platform.src.intelligence.multimodal_ai_model import MultimodalModel
from platform.src.pipeline.data_pipeline import create_dataset

app = FastAPI()

@app.post('/api/search')
async def search(query: str):
    # Load the multimodal AI model
    model = MultimodalModel()
    # Load the dataset
    train_dataset, test_dataset = create_dataset()
    # Use the model to generate search results
    search_results = []
    for result in test_dataset:
        text = result['text']
        image = result['image']
        graph = result['graph']
        label = result['label']
        output = model(text, image, graph)
        if output > 0.5:
            search_results.append({
                'destination': text,
                'description': label
            })
    return JSONResponse(content=search_results, media_type='application/json')
