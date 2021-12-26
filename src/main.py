from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyngrok import ngrok

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
ngrok.set_auth_token("22mp3afgBR9n2u1y5OVK04jMAzH_6qoX6Fr4ANwEibALrmMwC")
ngrok_tunnel = ngrok.connect(8000)
print('Public URL:', ngrok_tunnel.public_url)

@app.get('/health')
async def index():
    return {"health": "hello this is the concept extraction and expansion API"}

app.include_router(extractor_expander)