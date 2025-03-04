from typing import Union
from fastapi import FastAPI, APIRouter, Request, Response

#data conection Mysql
from config.mysql_conection import hostMysql
from config.mysql_conection import userMysql
from config.mysql_conection import passwordMysql
from config.mysql_conection import dbMysql

import MySQLdb

#models
from src.models.message_model import MessageApi

from pydantic import BaseModel
from typing import List


#data conection Wsapi
from config.apiws import fastapiwshost
from config.apiws import fastapiwsport
from config.apiws import apiwshost
from config.apiws import apiwsapiversion

#quita problema cors
from fastapi.middleware.cors import CORSMiddleware


import json
import requests

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse
from os import getcwd
from datetime import date
from datetime import datetime

#INCLUDE REPOSITORY

# GESTION DE RECLAMOS
#from src.repository import claim    

# PREGUNTAS FRECUENTES
from src.repository import faq

# CHATBOT CON PDF
from src.repository import pdf

# CHATBOT CON CONTENIDO DE PAGINA WEB
from src.repository import html

# CHATBOT CON API (TRANSFORMA DATOS NO ESTRUCTURADOS EN ESTRUCTURADOS)
#from src.repository import api

# CHATBOT OIRS
#from src.repository import oirst

# BUSCADOR SEMANTICO
#from src.repository import semantic

# FUNCIONES PARA TODAS LAS CLASES
from src.repository import utils


import os
import openai
import tiktoken
from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())


chatbot_router = APIRouter()


# Request Models.
class WebhookRequestData(BaseModel):
    object: str = ""
    entry: List = []


## ENVIA RECLAMOS USANDO LANGCHAIN
@chatbot_router.post('/send_message/')
def send_message(messagedata: MessageApi):

    derivacion = 0
    responsecustomer = ''

    if messagedata.solution == 'FAQ': 
        response = faq.send_message(messagedata)
    elif messagedata.solution == 'PDF': 
        response = pdf.send_message(messagedata)
    elif messagedata.solution == 'HTML': 
        response = html.send_message(messagedata)            
    else:
        responsecustomer = 'Parametros Incorrectos'


    if responsecustomer == 'Parametros Incorrectos':
        return {'respuesta': responsecustomer,
                'derivacion' : derivacion}
    else:

        if messagedata.solution == 'OIRS_T': 
            return {'respuesta': response['respuesta'],
                    'finish' : response['finish']}
        else:
            return {'respuesta': response['respuesta'],
                    'derivacion' : response['derivacion']}

'''
def send_message(messagedata: MessageApi):
    #print(messagedata)
    derivacion = 0
    responsecustomer = ''
    if messagedata.solution == 'Reclamos':     
        response = claim.send_message(messagedata)
    elif messagedata.solution == 'FAQ': 
        response = faq.send_message(messagedata)
    elif messagedata.solution == 'PDF': 
        response = pdf.send_message(messagedata)
    elif messagedata.solution == 'API': 
        response = api.send_message(messagedata)    
    elif messagedata.solution == 'OIRS_T': 
        response = oirst.send_message(messagedata)           
    elif messagedata.solution == 'HTML': 
        response = html.send_message(messagedata)        
    elif messagedata.solution == 'SEMANTICO': 
        response = semantic.send_message(messagedata)       
    else:
        responsecustomer = 'Parametros Incorrectos'


    if responsecustomer == 'Parametros Incorrectos':
        return {'respuesta': responsecustomer,
                'derivacion' : derivacion}
    else:

        if messagedata.solution == 'OIRS_T': 
            return {'respuesta': response['respuesta'],
                    'finish' : response['finish']}
        else:
            return {'respuesta': response['respuesta'],
                    'derivacion' : response['derivacion']}
'''


####LECTURA DE RECLAMOS
@chatbot_router.get('/get_messages/')
def get_messages(enterprise: str,solution: str):

    if solution == 'Reclamos':     
        #reclamos = claim.get_messages(enterprise)
        reclamos = []
    else:
        reclamos = []

    return {'data' : reclamos}


### ENVIA MENSAJE DE FINALIZACION DE CONVERSACION
@chatbot_router.get('/finish_message/')
def finish_message():
    #message = claim.finish_message()
    #message = faq.finish_message()
    message = pdf.finish_message()
    #message = oirst.finish_message()
    return {'data' : message}


### ENVIA MENSAJE DE FINALIZACION DE CONVERSACION
'''
@chatbot_router.get('/process_message/')
def process_message():
    message = oirst.process_message()
    return {'data' : message}
'''

### ENVIA MENSAJE DE VUELTA
@chatbot_router.post('/send_message_back/')
def send_message_back(messagedata: MessageApi):

    reclamos = utils.send_message_back_Ws(messagedata)

    return {'respuesta': reclamos}




### ENVIA MENSAJE ALERTANDO QUE PROCESO SIGUE FUNCIONANDO
@chatbot_router.get('/send_message_api_healthy/')
def send_message_api_healthy():
    
    #EVALUA WS
    #reclamos = utils.send_message_cli_healthy() 
    #print(reclamos)

    #EVALUA API
    telegram_token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHATID"]
    ambiente = os.environ["AMBIENTE"]
    today = datetime.now()
    message = 'Api ' + ambiente + ' Funcionando. Fecha: ' + today.strftime("%d/%m/%Y, %H:%M:%S")
    url = f'https://api.telegram.org/bot' + telegram_token + '/sendMessage?chat_id=' + chat_id + '&parse_mode=Markdown&text='+message

    payload = {}
    headers = {}

    response = requests.request("GET", url, headers=headers, data=payload)

    print(response.text)

    return {'data' : 'API funcionando'}


### ENVIA MENSAJE ALERTANDO QUE PROCESO SIGUE FUNCIONANDO (NO FUNCIONA)
@chatbot_router.get('/send_message_cli_healthy/')
def send_message_cli_healthy():


    reclamos = utils.send_message_cli_healthy()
    print('API WS')
    return {'data' : 'Evaluacion Ws'}


### ENVIA MENSAJE ALERTANDO QUE PROCESO SIGUE FUNCIONANDO
@chatbot_router.get('/send_image_qr_whatsapp/')
def send_image_qr_whatsapp():
    telegram_token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHATID"]
    ambiente = os.environ["AMBIENTE"]
    today = datetime.now()
    caption  = 'Envío QR Whatsapp ' + ambiente + ' Funcionando. Fecha: ' + today.strftime("%d/%m/%Y, %H:%M:%S")

    image_path = 'src/routers/uploads/bot.qr.png'  # Ruta de la imagen que deseas enviar

    if os.path.exists(image_path):
        img = open(image_path, 'rb')
        url = f'https://api.telegram.org/bot' + telegram_token + '/sendPhoto?chat_id=' + chat_id

        payload = {}
        headers = {}

        response = requests.post(url, headers=headers, files = {'photo': img})

        print(response.text)


    
    return {'data' : 'Envío QR'}


################################ WEBHOOK ####################################


### ENVIA MENSAJE DE VUELTA
@chatbot_router.post('/api/webhook')
async def webhook(data: WebhookRequestData):
    """
    Messages handler.
    """

    print(data)

    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()


    if data.object == "whatsapp_business_account":
        for entry in data.entry:
            
            messages = entry.get("changes")
            dict_message = messages[0]
            data_message = dict_message["value"]
            #print(data_message["messages"]["from"])

            numberid = data_message["metadata"]["phone_number_id"]
            numberphone = data_message["metadata"]["display_phone_number"]



            #BUSCA LA EMPRESA
            mycursor.execute("""SELECT      id
                                            , codempresa
                                            , typechatbot    
                                            , jwtokenwsapi          
                                FROM iar2_empresas WHERE numberidwsapi = '%s'""" % (numberid))

            idempresa = 0
            typechatbot = ''
            jwtokenwsapi = ''
            codempresa = ''
            for row_empresa in mycursor.fetchall():
                idempresa = row_empresa[0]
                codempresa = row_empresa[1]
                typechatbot = row_empresa[2]
                jwtokenwsapi = row_empresa[3]

            if "messages" in data_message: 
                list_messages = data_message["messages"][0]


                fromphone = list_messages["from"]
                type = list_messages["type"]

                #posibles valores type: text, image, location, document, contacts

                if type == 'text':
                    txt_message = list_messages["text"]["body"]
                    
                    #send_message()
                    payload = {
                        "message": txt_message,
                        "typemessage": "WhatsappAPI",
                        "valuetype": fromphone,
                        "solution" : typechatbot,
                        "enterprise": codempresa                
                    }

                    instancia = MessageApi(**payload)
                    response_text = send_message(instancia)


                    response_respuesta = response_text["respuesta"]

                    if response_respuesta != '':

                            numberidwsapi = numberid
                            url = f'https://graph.facebook.com/' + apiwsapiversion + '/' + str(numberidwsapi) + '/messages'
                            payload = json.dumps({
                            "messaging_product": "whatsapp",    
                            "recipient_type": "individual",
                            "to": fromphone,
                            "type": "text",
                            "text": {
                                "body": response_respuesta
                            }
                            })

                            headers = {
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer ' + jwtokenwsapi
                            }
                            response = requests.request("POST", url, headers=headers, data=payload)                     

    return Response(content="ok")


@chatbot_router.get("/api/webhook")
async def verify(request: Request):
    """
    On webook verification VERIFY_TOKEN has to match the token at the
    configuration and send back "hub.challenge" as success.
    """
    if request.query_params.get("hub.mode") == "subscribe" and request.query_params.get(
        "hub.challenge"
    ):
       

        if (
            not request.query_params.get("hub.verify_token")
            == os.environ["VERIFY_TOKEN"]
        ):
            return Response(content="Verification token mismatch", status_code=403)
        return Response(content=request.query_params["hub.challenge"])

    return Response(content="Required arguments haven't passed.", status_code=400)
