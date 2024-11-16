from fastapi import BackgroundTasks, APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Dict
import json
import httpx
import asyncio


import os


#INCLUDE REPOSITORY
from . import chatbot_router

import requests

# Router para WebSocket
websocket_router = APIRouter()


# Función para hacer fetch con reintentos (corregida para ser asíncrona)
async def fetch_with_retries(url, headers, payload, max_retries=3):
    retries = 0
    while retries < max_retries:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=headers, json=payload)
                #print('respuesta websocket: ')
                #print(response)
                response.raise_for_status()  # Verifica si el estado es 2xx
                return response.json()
        except httpx.RequestError as exc:
            print(f"Request error: {exc}")
            # Muestra detalles de la URL y payload para diagnósticos
            print(f"Request error to {url} with payload {payload} (Retry {retries + 1}/{max_retries}): {exc}")
               
        except httpx.HTTPStatusError as exc:
            print(f"HTTP error: {exc}")
            print(f"HTTP error {exc.response.status_code} for URL {url} with payload {payload}: {exc}")
            #print("Traceback:", traceback.format_exc())            
        retries += 1
        await asyncio.sleep(2 ** retries)  # Exponencial backoff
    return None  # Devuelve None si los reintentos fallan

# Clase para gestionar las conexiones con user_id
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    async def send_message_to_user(self, message: str, user_id: str):
        connection = self.active_connections.get(user_id)
        if connection:
            await connection.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)



manager = ConnectionManager()


@websocket_router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    # Aceptar la conexión antes de  recibir el `user_id`
    await websocket.accept()

    # Espera el primer mensaje que debe contener  el `user_id`
    data = await websocket.receive_text()
    initial_data = json.loads(data)
    user_id = initial_data["user_id"]
    chatClientId = initial_data["chatClientId"]
    solution = initial_data["solution"]

    apirest_url = os.environ["IP_APIREST"]
    prefix_url = os.environ["PREFIX_APIREST"]


    # Conecta al usuario usando su `user_id`
    await manager.connect(websocket, user_id)

    try:
        while True:
            # Recibe el mensaje del usuario y responde
            data = await websocket.receive_text()
            message_data = json.loads(data)
            message = message_data["message"]
            print(user_id)
            #print(message)

            
            url = f'{prefix_url}://{apirest_url}/send_message/'
            #print(url)
            payload = {
                "message": message,
                "typemessage": "WebChat",
                "valuetype": user_id,
                "solution": solution,
                "enterprise": chatClientId
            }
            headers = {
                'Content-Type': 'application/json'
            }
            respuesta = ''
            respuesta_data = await fetch_with_retries(url, headers, payload)

            if respuesta_data:
                respuesta = respuesta_data.get("respuesta", "")
                finish = respuesta_data.get("finish", "")
                #print('Respuesta websocket user id : ' + user_id + ' , respuesta : ' + respuesta)
                if respuesta:
                    await manager.send_message_to_user(respuesta, user_id)            
          
                if finish == 1:
                    await manager.send_message_to_user('Fin', user_id)                       
            '''
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                #print(response.json())  # Imprime la respuesta recibida en JSON
                # Obtén el valor de "respuesta"
                # Accede al contenido JSON de la respuesta
                respuesta_data = response.json()  # Convierte la respuesta en un diccionario                
                respuesta = respuesta_data.get("respuesta")          
                print('Respuesta websocket user id : ' + user_id + ' , respuesta : ' + respuesta)      
            

            # Enviar de vuelta el mensaje o algún procesamiento
            if respuesta != '':
                await manager.send_message_to_user(f"{respuesta}", user_id)
            '''
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        #await manager.broadcast(f"Usuario {user_id} se ha desconectado")



# Define un modelo para el cuerpo de la solicitud
class InactivityMessageRequest(BaseModel):
    message: str  # El mensaje de inactividad personalizado

# Modifica la función para aceptar un mensaje personalizado
async def send_inactivity_message(user_id: str, message: str):
    await manager.send_message_to_user(message, user_id)
    #manager.disconnect(user_id)  # O desconecta al usuario si deseas cerrar el chat

# Endpoint para programar el envío de mensajes de inactividad
@websocket_router.post("/send_inactivity_message/{user_id}")
async def program_inactivity_message(
    user_id: str, 
    request: InactivityMessageRequest, 
    background_tasks: BackgroundTasks
):
    # Programa el mensaje de inactividad para enviar en segundo plano con el mensaje personalizado
    background_tasks.add_task(send_inactivity_message, user_id, request.message)
    return {"status": "Mensaje de inactividad programado"}