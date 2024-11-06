from typing import Union
from fastapi import FastAPI
#quita problema cors
from fastapi.middleware.cors import CORSMiddleware


#IMPORTA ROUTER
from src.routers.claim_gen_router import claim_gen_router
from src.routers.claim_test_router import claim_test_router
from src.routers.chatbot_router import chatbot_router
from src.routers.websocket_router import websocket_router  # Nuevo import

# Creación de una aplicación FastAPI:
app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router=claim_gen_router)
app.include_router(router=claim_test_router)
app.include_router(router=chatbot_router)
# Incluye el router WebSocket
app.include_router(websocket_router)

@app.get('/')
def read_root():
    return {'Hello': 'World!!!'}






