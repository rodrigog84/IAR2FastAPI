from typing import Union
from fastapi import FastAPI, APIRouter



#models
from src.models.message_model import MessageApi


#data conection Mysql
from config.mysql_conection import hostMysql
from config.mysql_conection import userMysql
from config.mysql_conection import passwordMysql
from config.mysql_conection import dbMysql

#data conection Openai
#from config.openai_conf import openai_api_key

#data conection Wsapi
from config.apiws import apiwshost
from config.apiws import apiwsport
from config.apiws import apiwsclosealertminutes
from config.apiws import apiwscloseminutes

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


claim_test_router = APIRouter()

def get_completion(prompt, model="gpt-3.5-turbo"):
    messages = [{"role": "user", "content": prompt}]
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0,
    )
    return response.choices[0].message["content"]

def get_completion_from_messages(messages, model="gpt-3.5-turbo", temperature=0):
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature, # this is the degree of randomness of the model's output
    )
#     print(str(response.choices[0].message))
    return response.choices[0].message["content"]

#ENVIA RECLAMOS USANDO CHATGPT BASICO
@claim_test_router.post('/enviareclamo/')
def enviareclamo(messagedata: MessageApi):

    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()

    #BUSCA LA EMPRESA
    mycursor.execute("SELECT id, empresa, promp1 FROM iar2_empresas WHERE empresa = '%s'" % (messagedata.enterprise))

    idempresa = 0
    promp1 = ''
    for row_empresa in mycursor.fetchall():
        idempresa = row_empresa[0]
        promp1 = row_empresa[2]


    ###########################################################################################################

    ## LIMPIAR REGISTRO EN CASO DE PROBAR NUEVAMENTE


    if messagedata.message == 'Limpiar registro':
         mycursor.execute("DELETE FROM iar2_captura WHERE typemessage = '%s' AND valuetype = '%s' AND identerprise = '%d' AND created_at BETWEEN DATE_ADD(NOW(), INTERVAL -1 HOUR) AND NOW()" % (messagedata.typemessage,messagedata.valuetype,idempresa))
         miConexion.commit()
         responsecustomer = 'Limpieza Realizada'
         
    else:
        #EVALUA LOS MENSAJES EXISTENTES EN LA ÚLTIMA HORA
        #CONSIDERA TODOS LOS MENSAJES POSTERIORES A UN CIERRE (POR SI TIENE UN CIERRE ANTERIOR EN LA ULTIMA HORA, Y NO CONSIDERA LA ALERTA DE CIERRE EN LA INTERACCION)
        mycursor.execute("SELECT identification, typemessage, valuetype, message, messageresponseia, messageresponsecustomer, classification, sla, isclaim, typeresponse FROM iar2_captura WHERE typemessage = '%s' AND valuetype = '%s' AND identerprise = '%d' AND typeresponse != 'Alerta Cierre' AND created_at BETWEEN DATE_ADD(NOW(), INTERVAL -1 HOUR) AND NOW() and id > (SELECT ifnull(MAX(id),0) AS id FROM iar2_captura WHERE typemessage = '%s' AND valuetype = '%s' AND identerprise = '%d' AND 	typeresponse = 'Cierre Conversación') ORDER BY created_at " % (messagedata.typemessage,messagedata.valuetype,idempresa,messagedata.typemessage,messagedata.valuetype,idempresa))

        mensajes_previos = 0
        messages = []
        content_line = {}
        reclamo_ingresado = 0
        content_line = {'role':'system', 'content':promp1}
        messages.append(content_line)
        for row in mycursor.fetchall():
            mensajes_previos = mensajes_previos + 1

            content_line = {'role':'user', 'content':row[3]}
            messages.append(content_line)

            content_line = {'role':'assistant', 'content':row[5]}
            messages.append(content_line)

            if row[9] == 'Reclamo Ingresado':
                reclamo_ingresado = 1

        content_line = {'role':'user', 'content':messagedata.message}
        messages.append(content_line)
        #messagesjson = json.dumps(messages)
        ########################################################################################################

        # GUARDADO MENSAJE ENTRANTE
        sql = "INSERT INTO iar2_captura (typemessage, valuetype, message, identerprise) VALUES (%s, %s, %s, %s)"
        val = (messagedata.typemessage, messagedata.valuetype, sqlescape(messagedata.message), idempresa)
        mycursor.execute(sql, val)   
        miConexion.commit()

        idrow = mycursor.lastrowid
        idrowstr = str(idrow)

        
        if mensajes_previos > 0:
            response = get_completion_from_messages(messages,temperature=1)
        else:
            response = 'Sin Respuesta'
        
        classification = "Área de Ventas"
        sla = "48 Horas"
        isclaim = 'Si'
        today = date.today()
        identification = "R-" + today.strftime("%y%m%d"+str(idrowstr.zfill(4)))

        if response == 'Sin Respuesta':
            responsecustomer = 'Hola! soy el asistente virtual del servicio de Reclamos Iars2!.😎. Soy un asistente creado con Inteligencia Artificial preparado para atender a tus necesidades. Puedes indicar tu situación, y gestionaremos correctamente para dar una respuesta oportuna.  Para comenzar, favor indícame tu nombre'
            typeresponse = 'Saludo'
        else:
            #responsecustomer = "Su reclamo identificado como " + identification + " ha sido generado con éxito.  Su solicitud fue derivada al " + classification + ", y será resuelta en un plazo máximo de " + sla + "."
            responsecustomerfinal = "Su reclamo está identificado por el siguiente código: " + identification + "."
            typeresponse = 'Interaccion'

            array_response = response.split('##')
            

            if len(array_response) > 1:
                if array_response[1] != '' and reclamo_ingresado == 0:
                    array_response[0] = array_response[0] + '. ' + responsecustomerfinal 
                    typeresponse = 'Reclamo Ingresado'

            responsecustomer = array_response[0];


    # response = ''
        # GUARDADO RESPUESTA
        sqlresponse =  "UPDATE iar2_captura SET identification = '%s', messageresponseia = '%s', messageresponsecustomer = '%s', typeresponse = '%s', classification ='%s', sla = '%s', isclaim = '%s' WHERE id = %d" % (identification, sqlescape(response), sqlescape(responsecustomer), typeresponse, classification, sla, isclaim, idrow)
        #valresponse = (messagedata.typemessage, messagedata.valuetype, messagedata.message, messagedata.enterprise)
        mycursor.execute(sqlresponse)   
        miConexion.commit()

    
    #return {'respuesta': promp1}
    return {'respuesta': responsecustomer}





###### ENVIA RECLAMOS EN LANGCHAIN VERSION 2
@claim_test_router.post('/enviareclamolangchain2/')
def enviareclamolangchain2(messagedata: MessageApi):

    ##MODELO DE LENGUAJE
    #llm_name = "gpt-3.5-turbo"    
    llm_name = os.environ["LLM"]   
    memory = ConversationBufferMemory(memory_key="chat_history")
    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()

    #BUSCA LA EMPRESA
    mycursor.execute("SELECT id, empresa, promp1 FROM iar2_empresas WHERE empresa = '%s'" % (messagedata.enterprise))

    idempresa = 0
    promp1 = ''
    for row_empresa in mycursor.fetchall():
        idempresa = row_empresa[0]
        promp1 = row_empresa[2]


    ###########################################################################################################

    ## LIMPIAR REGISTRO EN CASO DE PROBAR NUEVAMENTE


    if messagedata.message == 'Limpiar registro':
         mycursor.execute("DELETE FROM iar2_captura WHERE typemessage = '%s' AND valuetype = '%s' AND identerprise = '%d' AND created_at BETWEEN DATE_ADD(NOW(), INTERVAL -1 HOUR) AND NOW()" % (messagedata.typemessage,messagedata.valuetype,idempresa))
         miConexion.commit()
         responsecustomer = 'Limpieza Realizada'
         
    else:
        #EVALUA LOS MENSAJES EXISTENTES EN LA ÚLTIMA HORA
        #CONSIDERA TODOS LOS MENSAJES POSTERIORES A UN CIERRE (POR SI TIENE UN CIERRE ANTERIOR EN LA ULTIMA HORA, Y NO CONSIDERA LA ALERTA DE CIERRE EN LA INTERACCION)
        mycursor.execute("SELECT identification, typemessage, valuetype, message, messageresponseia, messageresponsecustomer, classification, sla, isclaim, typeresponse FROM iar2_captura WHERE typemessage = '%s' AND valuetype = '%s' AND identerprise = '%d' AND typeresponse != 'Alerta Cierre' AND created_at BETWEEN DATE_ADD(NOW(), INTERVAL -1 HOUR) AND NOW() and id > (SELECT ifnull(MAX(id),0) AS id FROM iar2_captura WHERE typemessage = '%s' AND valuetype = '%s' AND identerprise = '%d' AND 	typeresponse = 'Cierre Conversación') ORDER BY created_at " % (messagedata.typemessage,messagedata.valuetype,idempresa,messagedata.typemessage,messagedata.valuetype,idempresa))

        mensajes_previos = 0
        reclamo_ingresado = 0


        for row in mycursor.fetchall():
            mensajes_previos = mensajes_previos + 1

            memory.save_context({"input": row[3]}, 
                                {"output": row[5]})

            if row[9] == 'Reclamo Ingresado':
                reclamo_ingresado = 1

        memory.load_memory_variables({})

      
        ########################################################################################################

        # GUARDADO MENSAJE ENTRANTE
        sql = "INSERT INTO iar2_captura (typemessage, valuetype, message, identerprise) VALUES (%s, %s, %s, %s)"
        val = (messagedata.typemessage, messagedata.valuetype, sqlescape(messagedata.message), idempresa)
        mycursor.execute(sql, val)   
        miConexion.commit()

        idrow = mycursor.lastrowid
        idrowstr = str(idrow)

        #return {'respuesta': memory}

        #mensajes_previos = 1
        if mensajes_previos > 0:
            
            template = promp1 + """

            {chat_history}
            Human: {human_input}
            Chatbot:"""

            prompt = PromptTemplate(
                input_variables=["chat_history", "human_input"], template=template
            )            



            llm = OpenAI()
            llm_chain = LLMChain(
                llm=llm,
                prompt=prompt,
                verbose=False,
                memory=memory,
            )    

            
            response = llm_chain.predict(human_input=messagedata.message)
            return {'response': response};
        else:
            response = 'Sin Respuesta'


        
        classification = "Área de Ventas"
        sla = "48 Horas"
        isclaim = 'Si'
        today = date.today()
        identification = "R-" + today.strftime("%y%m%d"+str(idrowstr.zfill(4)))

        if response == 'Sin Respuesta':
            responsecustomer = 'Hola! soy el asistente virtual del servicio de Reclamos Iars2!.😎. Soy un asistente creado con Inteligencia Artificial preparado para atender a tus necesidades. Puedes indicar tu situación, y gestionaremos correctamente para dar una respuesta oportuna.  Para comenzar, favor indícame tu nombre'
            typeresponse = 'Saludo'
        else:
            #responsecustomer = "Su reclamo identificado como " + identification + " ha sido generado con éxito.  Su solicitud fue derivada al " + classification + ", y será resuelta en un plazo máximo de " + sla + "."
            responsecustomerfinal = "Su reclamo está identificado por el siguiente código: " + identification + "."
            typeresponse = 'Interaccion'

            array_response = response.split('##')
            

            '''if len(array_response) > 1:
                if array_response[1] != '' and reclamo_ingresado == 0:
                    array_response[0] = array_response[0] + '. ' + responsecustomerfinal 
                    typeresponse = 'Reclamo Ingresado'
            '''
            responsecustomer = array_response[0];
            #responsecustomer = response_complete["respuesta_cliente"]


    # response = ''
        # GUARDADO RESPUESTA
        sqlresponse =  "UPDATE iar2_captura SET identification = '%s', messageresponseia = '%s', messageresponsecustomer = '%s', typeresponse = '%s', classification ='%s', sla = '%s', isclaim = '%s' WHERE id = %d" % (identification, sqlescape(response), sqlescape(responsecustomer), typeresponse, classification, sla, isclaim, idrow)
        #valresponse = (messagedata.typemessage, messagedata.valuetype, messagedata.message, messagedata.enterprise)
        mycursor.execute(sqlresponse)   
        miConexion.commit()

    #return {'respuesta': promp1}
    return {'respuesta': responsecustomer}
