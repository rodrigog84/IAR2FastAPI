#models
from src.models.message_model import MessageApi


#data conection Mysql
from config.mysql_conection import hostMysql
from config.mysql_conection import userMysql
from config.mysql_conection import passwordMysql
from config.mysql_conection import dbMysql

#data conection Wsapi
from config.apiws import apiwshost
#from config.apiws import apiwsport
#from config.apiws import apiwsclosealertminutes
#from config.apiws import apiwscloseminutes

#quita problema cors
from fastapi.middleware.cors import CORSMiddleware

#LANGCHAIN
from langchain.chat_models import ChatOpenAI
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
    mycursor.execute("SELECT id, empresa, promp1, port FROM iar2_empresas WHERE empresa = '%s'" % (messagedata.enterprise))

    idempresa = 0
    for row_empresa in mycursor.fetchall():
        idempresa = row_empresa[0]
        apiwsport = row_empresa[3]


    url = f'http://' + apiwshost + ':' + str(apiwsport) + '/api/CallBack'

    payload = json.dumps({
        "message": messagedata.message,
        "phone": messagedata.valuetype
    })
    headers = {
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)     


    sql = "INSERT INTO iar2_captura (typemessage, valuetype, messageresponsecustomer, typeresponse, identerprise) VALUES (%s, %s, %s, %s, %s)"
    val = (messagedata.typemessage, messagedata.valuetype, messagedata.message, 'Agente', messagedata.enterprise)
    mycursor.execute(sql, val)   
    miConexion.commit()    
    


    return 'Respuesta Enviada'
