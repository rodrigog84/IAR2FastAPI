#models
from src.models.message_model import MessageApi


#data conection Mysql
from config.mysql_conection import hostMysql
from config.mysql_conection import userMysql
from config.mysql_conection import passwordMysql
from config.mysql_conection import dbMysql

#data conection Wsapi
from config.apiws import apiwshost
from config.apiws import apiwsapiversion


#from config.apiws import apiwsport
#from config.apiws import apiwsclosealertminutes
#from config.apiws import apiwscloseminutes

#quita problema cors
from fastapi.middleware.cors import CORSMiddleware

#LANGCHAIN
#from langchain.chat_models import ChatOpenAI
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.chains import SequentialChain
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI


import MySQLdb

#AGREGA CARACTERES DE ESCAPE EN SQL
from sqlescapy import sqlescape


import json
import requests

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse
from os import getcwd
from datetime import date
from datetime import datetime


import os
import openai
import tiktoken
from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())



## DEVUELVE RESPUESTA
def send_message_back_Ws(messagedata: MessageApi):

    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()

    #BUSCA LA EMPRESA
    mycursor.execute("SELECT id, empresa, promp1, port, numberidwsapi, jwtokenwsapi FROM iar2_empresas WHERE codempresa = '%s'" % (messagedata.enterprise))

    idempresa = 0
    for row_empresa in mycursor.fetchall():
        idempresa = row_empresa[0]
        apiwsport = row_empresa[3]
        numberidwsapi = row_empresa[4]
        jwtokenwsapi = row_empresa[5]

    #VALIDACION DE EMPRESA
    if idempresa == 0:
        return 'Empresa no existe'
    
     #OBTIENE DATOS PRINCIPALES INTERACCION
    mycursor.execute("""SELECT      c.id
                                    ,c.idinteraction
                        FROM        iar2_captura c
                        INNER JOIN  iar2_interaction i on c.idinteraction = i.id
                        WHERE       c.typemessage = '%s' 
                        AND         c.valuetype = '%s' 
                        AND         c.identerprise = '%d' 
                        AND         i.finish = 0
                        ORDER BY    c.created_at DESC
                        LIMIT 1""" % (messagedata.typemessage,messagedata.valuetype,idempresa))   
    
    idcaptura = 0
    for row_interaction in mycursor.fetchall():
        idcaptura = row_interaction[0]
        idinteraction = row_interaction[1]

    #VALIDACION DE CONVERSACION
    if idcaptura == 0:
        return 'Conversacion no existe'




    if messagedata.typemessage == 'Whatsapp':
            url = f'http://' + apiwshost + ':' + str(apiwsport) + '/api/CallBack'

            payload = json.dumps({
                "message": messagedata.message,
                "phone": messagedata.valuetype
            })
            headers = {
            'Content-Type': 'application/json'
            }

            response = requests.request("POST", url, headers=headers, data=payload)    
    elif messagedata.typemessage == 'WhatsappAPI':
         

            url = f'https://graph.facebook.com/' + apiwsapiversion + '/' + str(numberidwsapi) + '/messages'

            payload = json.dumps({
            "messaging_product": "whatsapp",    
            "recipient_type": "individual",
            "to": messagedata.valuetype,
            "type": "text",
            "text": {
                "body": messagedata.message
            }
            })



            headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + jwtokenwsapi
            }

            response = requests.request("POST", url, headers=headers, data=payload)      


    message = messagedata.message + '\n';
    # GUARDADO RESPUESTA
    sqlresponse =  "UPDATE iar2_captura SET messageresponsecustomer = case when messageresponsecustomer IS NULL THEN '%s' ELSE concat(messageresponsecustomer,'%s') end , typeresponse = 'Derivacion', derivacion = 'SI' WHERE id = %d" % (sqlescape(message), sqlescape(message), idcaptura)
    #valresponse = (messagedata.typemessage, messagedata.valuetype, messagedata.message, messagedata.enterprise)
    mycursor.execute(sqlresponse)   
    miConexion.commit()


    sqlresponse =  "UPDATE iar2_interaction SET  lastmessageresponsecustomer =  '%s', lastyperesponse =  'Derivacion' WHERE id = %d" % (sqlescape(message), idinteraction)
    #valresponse = (messagedata.typemessage, messagedata.valuetype, messagedata.message, messagedata.enterprise)
    mycursor.execute(sqlresponse)   
    miConexion.commit()    

    return 'Respuesta Enviada'


## EVALUA CLIENTE FUNCIONANDO
def send_message_cli_healthy():

    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()


    #BUSCA LA EMPRESA
    mycursor.execute("""SELECT      DISTINCT i.id
                                    ,i.port
                                    ,i.empresa
                        FROM        iar2_empresas i
                        WHERE       i.whatsapp = 1""")
    

    ambiente = os.environ["AMBIENTE"]
    today = datetime.now()
    
    valuetype = '56995089648'
    for row_enterprise in mycursor.fetchall():
        apiwsport = row_enterprise[1]
        empresa = row_enterprise[2]
        message = 'Whatsapp ' + ambiente + ' Funcionando. Empresa: ' + empresa + '. Fecha: ' + today.strftime("%d/%m/%Y, %H:%M:%S")

        url = f'http://' + apiwshost + ':' + str(apiwsport) + '/api/CallBack'
        payload = json.dumps({
            "message": message,
            "phone": valuetype
        })
        headers = {
        'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload)     

    return 'Evaluacion Ws'
