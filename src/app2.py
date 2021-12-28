from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.extractor_expander import extractor_expander

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/health')
async def index():
    return {"health": "hello this is the concept extraction and expansion API"}

app.include_router(extractor_expander)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
