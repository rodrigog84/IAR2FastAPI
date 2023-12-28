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
from langchain.chains import RetrievalQA
from langchain.chains import ConversationalRetrievalChain
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma

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

def limpiar_registro(messagedata: MessageApi, idempresa):

    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()        
    mycursor.execute("""DELETE     
                        FROM       iar2_captura 
                        WHERE      typemessage = '%s' 
                        AND        valuetype = '%s' 
                        AND        identerprise = '%d' 
                        AND        idinteraction in (
                                                     SELECT     id
                                                     FROM       iar2_interaction
                                                     WHERE      finish = 0
                                                    )
                        AND        created_at BETWEEN DATE_ADD(NOW(), INTERVAL -1 HOUR) AND NOW()""" % (messagedata.typemessage,messagedata.valuetype,idempresa))
    
    miConexion.commit()

    mycursor.execute("""DELETE     
                        FROM       iar2_interaction 
                        WHERE      typemessage = '%s' 
                        AND        valuetype = '%s' 
                        AND        identerprise = '%d' 
                        AND        finish = 0
                        AND        updated_at BETWEEN DATE_ADD(NOW(), INTERVAL -1 HOUR) AND NOW()""" % (messagedata.typemessage,messagedata.valuetype,idempresa))

    miConexion.commit()
    return 'Limpieza Realizada'



def out_time_message(messagedata: MessageApi):


    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()

    #BUSCA LA EMPRESA
    mycursor.execute("""SELECT      id
                                    , empresa
                                    , promp1
                                    , greeting
                                    , whatsapp
                                    , webchat
                                    , time_min
                                    , time_max
                                    , derivation
                                    , derivation_message
                                    , chatbot
                        FROM iar2_empresas WHERE codempresa = '%s'""" % (messagedata.enterprise))
    
    idempresa = 0
    promp1 = ''
    for row_empresa in mycursor.fetchall():
        idempresa = row_empresa[0]
        promp1 = row_empresa[2]
        greeting = row_empresa[3]
        whatsapp = row_empresa[4]
        webchat = row_empresa[5]
        time_min = row_empresa[6]
        time_max = row_empresa[7]
        tiene_derivacion = row_empresa[8]
        derivation_message = row_empresa[9]
        chatbot = row_empresa[10]


    if chatbot == 0:
        derivation = 1
        derivacion = 'SI'
    else:
        derivation = 0
        derivacion = 'NO'

    responsecustomer = f'Hola! Nuestro horario de atencion es entre las {time_min} y las {time_max}.  Disculpe las molestias'
    
    sql = "INSERT INTO iar2_interaction (identerprise, typemessage, valuetype, lastmessage, lastmessageresponsecustomer, lastyperesponse, derivation,alert_finish, finish) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    val = (idempresa, messagedata.typemessage, messagedata.valuetype, sqlescape(messagedata.message), sqlescape(responsecustomer), 'Saludo',derivation, 1, 1)
    mycursor.execute(sql, val)   
    miConexion.commit()

    idinteraction = mycursor.lastrowid
    idinteractionstr = str(idinteraction)        

    # GUARDADO MENSAJE ENTRANTE
    sql = "INSERT INTO iar2_captura (typemessage, valuetype, message, messageresponseia, messageresponsecustomer, typeresponse, identerprise,idinteraction, derivacion) VALUES (%s, %s, %s, %s, %s, 'Fuera de Horario', %s, %s, %s)"
    val = (messagedata.typemessage, messagedata.valuetype, sqlescape(messagedata.message), sqlescape(responsecustomer), sqlescape(responsecustomer), idempresa, idinteractionstr, derivacion)
    mycursor.execute(sql, val)   
    miConexion.commit()   
    return responsecustomer 


def greeting_message(messagedata: MessageApi):


    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()

    #BUSCA LA EMPRESA
    mycursor.execute("""SELECT      id
                                    , empresa
                                    , promp1
                                    , greeting
                                    , whatsapp
                                    , webchat
                                    , time_min
                                    , time_max
                                    , derivation
                                    , derivation_message
                                    , chatbot
                        FROM iar2_empresas WHERE codempresa = '%s'""" % (messagedata.enterprise))
    
    idempresa = 0
    promp1 = ''
    for row_empresa in mycursor.fetchall():
        idempresa = row_empresa[0]
        promp1 = row_empresa[2]
        greeting = row_empresa[3]
        whatsapp = row_empresa[4]
        webchat = row_empresa[5]
        time_min = row_empresa[6]
        time_max = row_empresa[7]
        tiene_derivacion = row_empresa[8]
        derivation_message = row_empresa[9]
        chatbot = row_empresa[10]


    if chatbot == 0:
        derivation = 1
        derivacion = 'SI'
    else:
        derivation = 0
        derivacion = 'NO'

    if greeting is None:
        responsecustomer = 'Hola! soy el asistente virtual del servicio de Preguntas Frecuentes Iars2!.😎. Soy un asistente creado con Inteligencia Artificial preparado para atender a tus necesidades. Puedes indicar tu situación, y gestionaremos correctamente para dar una respuesta oportuna.  Para comenzar, favor indícame tu nombre'
    else:
        responsecustomer = greeting
    
    sql = "INSERT INTO iar2_interaction (identerprise, typemessage, valuetype, lastmessage, lastmessageresponsecustomer, lastyperesponse, derivation) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    val = (idempresa, messagedata.typemessage, messagedata.valuetype, sqlescape(messagedata.message), sqlescape(responsecustomer), 'Saludo',derivation)
    mycursor.execute(sql, val)   
    miConexion.commit()

    idinteraction = mycursor.lastrowid
    idinteractionstr = str(idinteraction)        

    # GUARDADO MENSAJE ENTRANTE
    sql = "INSERT INTO iar2_captura (typemessage, valuetype, message, messageresponseia, messageresponsecustomer, typeresponse, identerprise,idinteraction, derivacion) VALUES (%s, %s, %s, %s, %s, 'Saludo', %s, %s, %s)"
    val = (messagedata.typemessage, messagedata.valuetype, sqlescape(messagedata.message), sqlescape(responsecustomer), sqlescape(responsecustomer), idempresa, idinteractionstr, derivacion)
    mycursor.execute(sql, val)   
    miConexion.commit()   
    return responsecustomer


def derivation_option(messagedata: MessageApi, id_interaction, idrow):


    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()

    #BUSCA LA EMPRESA
    mycursor.execute("""SELECT      id
                                    , empresa
                                    , promp1
                                    , greeting
                                    , whatsapp
                                    , webchat
                                    , time_min
                                    , time_max
                                    , derivation
                                    , derivation_message
                        FROM iar2_empresas WHERE codempresa = '%s'""" % (messagedata.enterprise))
    
    idempresa = 0
    promp1 = ''
    for row_empresa in mycursor.fetchall():
        idempresa = row_empresa[0]
        promp1 = row_empresa[2]
        greeting = row_empresa[3]
        whatsapp = row_empresa[4]
        webchat = row_empresa[5]
        time_min = row_empresa[6]
        time_max = row_empresa[7]
        tiene_derivacion = row_empresa[8]
        derivation_message = row_empresa[9]    
    
    response_type_response = 'Derivacion'
    response = ''

    if tiene_derivacion == 1:
        if derivation_message is None:
            responsecustomer = 'Para proporcionarte una asistencia más detallada y personalizada, voy a derivar tu solicitud a uno de nuestros ejecutivos. Estarán en contacto contigo en breve para abordar tus inquietudes de manera más directa.'
        else:
            responsecustomer = derivation_message   
    else:
        responsecustomer = 'Como su asistente virtual, me encargaré de responder a sus necesidades.'
     

    sqlresponse =  "UPDATE iar2_captura SET messageresponseia = '%s', messageresponsecustomer = '%s', typeresponse = '%s',  derivacion = '%s', idinteraction = '%d'  WHERE id = %d" % (sqlescape(responsecustomer), sqlescape(responsecustomer), 'Derivacion', 'SI', id_interaction, idrow)
    #valresponse = (messagedata.typemessage, messagedata.valuetype, messagedata.message, messagedata.enterprise)
    mycursor.execute(sqlresponse)   
    miConexion.commit()
    sqlresponse =  "UPDATE iar2_interaction SET typemessage = '%s', derivation = 1, lastmessage =  '%s', lastmessageresponsecustomer =  '%s', lastyperesponse =  '%s' WHERE id = %d" % ( messagedata.typemessage, sqlescape(messagedata.message), sqlescape(responsecustomer), 'Derivacion', id_interaction)
    #valresponse = (messagedata.typemessage, messagedata.valuetype, messagedata.message, messagedata.enterprise)
    mycursor.execute(sqlresponse)   
    miConexion.commit()
    return responsecustomer


def chatbot_message(messagedata: MessageApi, id_interaction, idrow, promp1):

    llm_name = "gpt-3.5-turbo"   
    llm = ChatOpenAI(model_name=llm_name, temperature=0) 
    memory = ConversationBufferMemory(memory_key="chat_history")
    embedding = OpenAIEmbeddings()
    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()

    #BUSCA LA EMPRESA
    mycursor.execute("""SELECT      id
                                    , empresa
                                    , promp1
                                    , greeting
                                    , whatsapp
                                    , webchat
                                    , time_min
                                    , time_max
                                    , derivation
                                    , derivation_message
                        FROM iar2_empresas WHERE codempresa = '%s'""" % (messagedata.enterprise))
    
    idempresa = 0
    promp1 = ''
    for row_empresa in mycursor.fetchall():
        idempresa = row_empresa[0]
        promp1 = row_empresa[2]
        greeting = row_empresa[3]
        whatsapp = row_empresa[4]
        webchat = row_empresa[5]
        time_min = row_empresa[6]
        time_max = row_empresa[7]
        tiene_derivacion = row_empresa[8]
        derivation_message = row_empresa[9]    
    

    #EVALUA LOS MENSAJES EXISTENTES DE LA INTERACCION ACTUAL
    mycursor.execute("""SELECT      identification
                                    , typemessage
                                    , valuetype
                                    , ifnull(message,'') as message 
                                    , messageresponseia
                                    , ifnull(messageresponsecustomer,'') as messageresponsecustomer
                                    , classification
                                    , sla
                                    , isclaim
                                    , typeresponse
                                    , derivacion 
                        FROM        iar2_captura 
                        WHERE       idinteraction = '%s' 
                        ORDER BY    created_at """ % (id_interaction))

    mensajes_previos = 0
    reclamo_ingresado = 0
    derivacion = 0
    messages = []

    for row in mycursor.fetchall():

        mensajes_previos = mensajes_previos + 1
        messages.append((row[3], row[5]))

        memory.save_context({"input": row[3]}, 
                            {"output": row[5]})
                
 
    #memory.load_memory_variables({})        

    #ESCRIBIR LAS DISTINTAS PREGUNTAS
     
    question = messagedata.message 
    promp_original = promp1
    memory.save_context({"input": question}, 
                        {"output": ''})
    memory.load_memory_variables({})

    ############################################################################################################
    ##   OBTENER PREGUNTAS FRECUENTES

    mycursor.execute("""SELECT  question
                            , answer
                    FROM    iar2_faq
                    WHERE   identerprise = '%d' 
                    ORDER BY id """ % (idempresa))            


    texts = []
    question_text = ""
    for questions in mycursor.fetchall():
        question_text = f'Pregunta: {questions[0]}, Respuesta: {questions[1]}'
        texts.append(question_text)

    vectordb = Chroma.from_texts(texts, embedding=embedding)

    template = promp1 + """ Utilice las siguientes piezas de contexto para responder la pregunta al final. Si no sabe la respuesta, simplemente diga que no tiene la información, no intente inventar una respuesta. No haga referencia a que está utilizando un texto.  Responda entregando la mayor cantidad de información posible.
    {context}
    Question: {question}
    Helpful Answer:"""
    QA_CHAIN_PROMPT = PromptTemplate.from_template(template)
    

    chain_type_kwargs = {'prompt': QA_CHAIN_PROMPT}
    # Run chain
    #RetrievalQA.from_chain_type sirve para hacer solo la consulta
    
    qa_chain = RetrievalQA.from_chain_type(
        llm,
        retriever=vectordb.as_retriever(),
        return_source_documents=True,
        chain_type_kwargs=chain_type_kwargs
    )
    result = qa_chain({"query": question})    
    response = result['result']
    typeresponse = 'Interaccion'
    responsecustomer = response

    # response = ''
    # GUARDADO RESPUESTA
    sqlresponse =  "UPDATE iar2_captura SET identification = '', messageresponseia = '%s', messageresponsecustomer = '%s', typeresponse = '%s', derivacion = '%s', idinteraction = '%d'  WHERE id = %d" % (sqlescape(response), sqlescape(responsecustomer), typeresponse, 'NO', id_interaction, idrow)
    #valresponse = (messagedata.typemessage, messagedata.valuetype, messagedata.message, messagedata.enterprise)
    mycursor.execute(sqlresponse)   
    miConexion.commit()

    sqlresponse =  "UPDATE iar2_interaction SET  lastmessage =  '%s', lastmessageresponsecustomer =  '%s', lastyperesponse =  '%s' WHERE id = %d" % (sqlescape(messagedata.message), sqlescape(responsecustomer), typeresponse, id_interaction)
    #valresponse = (messagedata.typemessage, messagedata.valuetype, messagedata.message, messagedata.enterprise)
    mycursor.execute(sqlresponse)   
    miConexion.commit()    

    return responsecustomer

## ENVIA RECLAMOS USANDO LANGCHAIN
def send_message(messagedata: MessageApi):

    ##MODELO DE LENGUAJE
    llm_name = "gpt-3.5-turbo"   
    llm = ChatOpenAI(model_name=llm_name, temperature=0) 
    embedding = OpenAIEmbeddings()

    memory = ConversationBufferMemory(memory_key="chat_history")

    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()


    #BUSCA LA EMPRESA
    mycursor.execute("""SELECT      id
                                    , empresa
                                    , promp1
                                    , greeting
                                    , whatsapp
                                    , webchat
                                    , time_min
                                    , time_max
                                    , derivation
                                    , derivation_message
                                    , CASE WHEN time (NOW()) < time_min THEN 1
                                    		 ELSE 0
                                      END AS fuera_time_min
                                    , CASE WHEN time (NOW()) > time_max THEN 1
                                    		 ELSE 0
                                      END fuera_time_max                            
                        FROM iar2_empresas WHERE codempresa = '%s'""" % (messagedata.enterprise))

    idempresa = 0
    promp1 = ''
    for row_empresa in mycursor.fetchall():
        idempresa = row_empresa[0]
        promp1 = row_empresa[2]
        greeting = row_empresa[3]
        whatsapp = row_empresa[4]
        webchat = row_empresa[5]
        time_min = row_empresa[6]
        time_max = row_empresa[7]
        tiene_derivacion = row_empresa[8]
        derivation_message = row_empresa[9]
        fuera_time_min = row_empresa[10]
        fuera_time_max = row_empresa[11]


    #VALIDACION DE EMPRESA
    if idempresa == 0:
        return 'Empresa no existe'
    
    #VALIDACION DE CANAL
    if messagedata.typemessage == 'Whatsapp' and whatsapp == 0:
        return 'Canal no permitido'
    if messagedata.typemessage == 'Webchat' and webchat == 0:
        return 'Canal no permitido'    
    ###########################################################################################################

    ## LIMPIAR REGISTRO EN CASO DE PROBAR NUEVAMENTE

    ## CASO 1: LIMPIEZA REGISTRO    
    if messagedata.message == 'Limpiar registro':
         
         resp = limpiar_registro(messagedata, idempresa)

         return resp
 
    #OBTIENE DATOS PRINCIPALES INTERACCION
    mycursor.execute("""SELECT      id
                                    ,derivation
                        FROM        iar2_interaction 
                        WHERE       typemessage = '%s' 
                        AND         valuetype = '%s' 
                        AND         identerprise = '%d' 
                        AND         finish = 0
                        ORDER BY    updated_at DESC
                        LIMIT 1""" % (messagedata.typemessage,messagedata.valuetype,idempresa))

    tiene_mensaje = 0
    for row_interaction in mycursor.fetchall():
        tiene_mensaje = 1
        id_interaction = row_interaction[0]
        derivation = row_interaction[1]


    ## CASO 2: INTERACCION NUEVA - SALUDO
    if tiene_mensaje == 0:
        if fuera_time_min == 1 or fuera_time_max == 1:
            responsecustomer = out_time_message(messagedata)
        else:
            responsecustomer = greeting_message(messagedata)
            
        return responsecustomer

    # GUARDADO MENSAJE ENTRANTE
    sql = "INSERT INTO iar2_captura (typemessage, valuetype, message, identerprise, idinteraction) VALUES (%s, %s, %s, %s, %s)"
    val = (messagedata.typemessage, messagedata.valuetype, sqlescape(messagedata.message), idempresa, id_interaction)
    mycursor.execute(sql, val)   
    miConexion.commit()

    idrow = mycursor.lastrowid
    idrowstr = str(idrow)


    ## CASO 3: DERIVACION
    if derivation == 1:
        derivation = 1 # VER QUE HACER ACA

        if tiene_derivacion == 1:
            return ''
     
    ########################################################################################################
    
    question = messagedata.message

    derivation_prompt = ChatPromptTemplate.from_template(
        "Indícame si en la siguiente pregunta el usuario indica de manera explícita que quiere derivar la conversación a un ejecutivo humano y terminar la conversación con el bot.  Tu respuesta debe ser SI o NO:"
        "\n\n{human_input}"
    )
    # chain 2: input= English_Review and output= summary
    chain_derivarion = LLMChain(llm=llm, prompt=derivation_prompt,
                        output_key="intencion_derivacion"
                        )
    

    response_derivacion = chain_derivarion.predict(human_input=question)


    ## CASO 4: CLIENTE PIDE AHORA DERIVACION
    if response_derivacion == 'SI':
        responsecustomer = derivation_option(messagedata, id_interaction, idrow)
        return responsecustomer



    ## CASO 5: COMUNICACION CON CHATBOT
    responsecustomer = chatbot_message(messagedata, id_interaction, idrow,  promp1)

    return responsecustomer


def get_messages(enterprise: str):

    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()



    #BUSCA LA EMPRESA
    mycursor.execute("SELECT id, empresa, promp1 FROM iar2_empresas WHERE empresa = '%s'" % (enterprise))

    idempresa = 0
    promp1 = ''
    for row_empresa in mycursor.fetchall():
        idempresa = row_empresa[0]
        promp1 = row_empresa[2]

    mycursor.execute("SELECT identification, typemessage, valuetype, message, messageresponseia, messageresponsecustomer, classification, sla, isclaim FROM iar2_captura WHERE identerprise = '%s'" % (idempresa))
    reclamos = []
    content = {}

    #for identification, typemessage, valuetype, message, messageresponseia, messageresponsecustomer, classification, sla, isclaim in mycursor.fetchall():
    #    content = {"Identificador":identification,"Tipo Mensaje":typemessage,"Valor Tipo Mensaje":valuetype,"Mensaje":message,"Mensaje Respuesta IA":messageresponseia,"Mensaje Respuesta Cliente":messageresponsecustomer,"Clasificacion":classification,"SLA":sla,"Es Reclamo":isclaim}
    #    reclamos.append(content)
    for row in mycursor.fetchall():
        content = {"identificador":row[0],"Tipo Mensaje":row[1],"Valor Tipo Mensaje":row[2],"Mensaje":row[3],"Mensaje Respuesta IA":row[4],"Mensaje Respuesta Cliente":row[5],"Clasificacion":row[6],"SLA":row[7],"Es Reclamo":row[8]}
        reclamos.append(content)
    #resultjson = json.dumps(reclamos)
    miConexion.close()
    return reclamos


def finish_message():

    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()



    #BUSCA LA EMPRESA
    mycursor.execute("SELECT DISTINCT typemessage, valuetype, identerprise FROM iar2_captura WHERE created_at BETWEEN DATE_ADD(NOW(), INTERVAL -1 HOUR) AND NOW()")
    #mycursor.execute("SELECT DISTINCT typemessage, valuetype, identerprise FROM iar2_captura WHERE created_at BETWEEN DATE_ADD(NOW(), INTERVAL -3 DAY) AND NOW()")

    typemessage = ''
    valuetype = ''
    identerprise = ''

    message_alerta_cierre = '¡Hola de nuevo! Parece que ha pasado un tiempo desde nuestra última interacción. Nuestro sistema de seguridad cerrará en unos minutos la sesión por inactividad. Si tienes alguna información adicional, por favor, no dudes en escribir..'
    message_cierre = 'Nuestro sistema de seguridad ha cerrado la sesión por inactividad..'
    
    reclamos = []
    registro = []
    for row_interaction in mycursor.fetchall():
        typemessage = row_interaction[0]
        valuetype = row_interaction[1]
        identerprise = row_interaction[2]
        content = {"typemessage":typemessage,"valuetype":valuetype,"identerprise":identerprise}
        reclamos.append(content)
        mycursor2 = miConexion.cursor()
        
        #OBTIENE EL ÚLTIMO MENSAJE DEL NUMERO QUE SE ESTÁ COMUNICANDO
        mycursor2.execute("""SELECT 	c.messageresponsecustomer 
                                        ,c.typeresponse
                                        ,TIMESTAMPDIFF(MINUTE,c.created_at,NOW()) AS minutos 
                                        ,e.port
                                        ,e.closealertminutes
                                        ,e.closeminutes
                            FROM        iar2_captura c  
                            INNER JOIN  iar2_empresas e  on c.identerprise = e.id
                            WHERE 	c.id = (
                                                                SELECT   MAX(id) 
                                                                FROM    iar2_captura c 
                                                                WHERE 	typemessage = '%s' 
                                                                AND 	valuetype = '%s' 
                                                                AND     identerprise = %d
                                                                )""" % (typemessage,valuetype,identerprise))
        for row_register in mycursor2.fetchall():
                messageresponsecustomer = row_register[0]
                typeresponse = row_register[1]
                minutos = row_register[2]
                apiwsport = row_register[3]
                apiwsclosealertminutes = row_register[4]
                apiwscloseminutes = row_register[5]
                
                url = f'http://' + apiwshost + ':' + str(apiwsport) + '/api/CallBack'
                mycursor3 = miConexion.cursor()
                # SI ULTIMO MENSAJE FUE DEL CHATBOT, ES DE WHATSAPP, ES DE INTERACCION O SALUDO Y FUE HACE MÁS DE 30 MINUTOS, ENVIAR MENSAJE DE ALERTA DE CIERRE
                if typemessage == 'Whatsapp' and messageresponsecustomer != '' and (typeresponse == 'Interaccion' or typeresponse == 'Saludo') and minutos > apiwsclosealertminutes:
                    
                    #response = requests.get(url)
                    
                    payload = json.dumps({
                        "message": message_alerta_cierre,
                        "phone": valuetype
                    })
                    headers = {
                    'Content-Type': 'application/json'
                    }
                    
                    response = requests.request("POST", url, headers=headers, data=payload)                    


                    sql = "INSERT INTO iar2_captura (typemessage, valuetype, messageresponsecustomer, typeresponse, identerprise) VALUES (%s, %s, %s, %s, %s)"
                    val = (typemessage, valuetype, 'Alerta de cierre de sesion', 'Alerta Cierre', identerprise)
                    mycursor3.execute(sql, val)   
                    miConexion.commit()


                # SI ULTIMO MENSAJE FUE DE ALERTA DE CIERRE Y DE WHATSAPP, ENVIAR MENSAJE DE CIERRE
                if typemessage == 'Whatsapp' and typeresponse == 'Alerta Cierre' and minutos > apiwscloseminutes:
                    #url = f'http://' + apiwshost + ':' + apiwsport + '/api/CallBack?p=' + valuetype + '&q=2'
                    #response = requests.get(url)


                    payload = json.dumps({
                        "message": message_cierre,
                        "phone": valuetype
                    })
                    headers = {
                    'Content-Type': 'application/json'
                    }

                    response = requests.request("POST", url, headers=headers, data=payload) 

                    sql = "INSERT INTO iar2_captura (typemessage, valuetype, messageresponsecustomer, typeresponse, identerprise) VALUES (%s, %s, %s, %s, %s)"
                    val = (typemessage, valuetype, 'Cierre de sesion definitivo', 'Cierre Conversación', identerprise)
                    mycursor3.execute(sql, val)   
                    miConexion.commit()


                content2 = {"messageresponsecustomer":messageresponsecustomer,"typeresponse":typeresponse,"minutos":minutos,"url": url}    
                registro.append(content2)
        



    miConexion.close()
    return {'data' : 'Conversaciones Finalizadas'}