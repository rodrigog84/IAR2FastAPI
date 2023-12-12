from typing import Union
from fastapi import FastAPI, APIRouter



#models
from src.models.message_model import MessageApi

#quita problema cors
from fastapi.middleware.cors import CORSMiddleware


import json
import requests

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse
from os import getcwd
from datetime import date


#INCLUDE REPOSITORY
from src.repository import claim
from src.repository import faq
from src.repository import utils


import os
import openai
import tiktoken
from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())


chatbot_router = APIRouter()


## ENVIA RECLAMOS USANDO LANGCHAIN
@chatbot_router.post('/send_message/')
def send_message(messagedata: MessageApi):

    if messagedata.solution == 'Reclamos':     
        responsecustomer = claim.send_message(messagedata)
    elif messagedata.solution == 'FAQ': 
        responsecustomer = faq.send_message(messagedata)
    else:
        responsecustomer = 'Parametros Incorrectos'

    return {'respuesta': responsecustomer}



####LECTURA DE RECLAMOS
@chatbot_router.get('/get_messages/')
def get_messages(enterprise: str,solution: str):

    if solution == 'Reclamos':     
        reclamos = claim.get_messages(enterprise)
    else:
        reclamos = []

    return {'data' : reclamos}


### ENVIA MENSAJE DE FINALIZACION DE CONVERSACION
@chatbot_router.get('/finish_message/')
def finish_message():
    message = claim.finish_message()
    return {'data' : message}




### ENVIA MENSAJE DE VUELTA
@chatbot_router.post('/send_message_back/')
def send_message_back(messagedata: MessageApi):

    if messagedata.typemessage == 'Whatsapp':     
        reclamos = utils.send_message_back_Ws(messagedata)
    else:
        reclamos = []
    

    return {'respuesta': 'Respuesta Enviada'}

