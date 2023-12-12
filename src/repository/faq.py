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
        mycursor.execute("SELECT identification, typemessage, valuetype, message, messageresponseia, messageresponsecustomer, classification, sla, isclaim, typeresponse, derivacion FROM iar2_captura WHERE typemessage = '%s' AND valuetype = '%s' AND identerprise = '%d' AND typeresponse != 'Alerta Cierre' AND created_at BETWEEN DATE_ADD(NOW(), INTERVAL -1 HOUR) AND NOW() and id > (SELECT ifnull(MAX(id),0) AS id FROM iar2_captura WHERE typemessage = '%s' AND valuetype = '%s' AND identerprise = '%d' AND 	typeresponse = 'Cierre Conversación') ORDER BY created_at " % (messagedata.typemessage,messagedata.valuetype,idempresa,messagedata.typemessage,messagedata.valuetype,idempresa))

        mensajes_previos = 0
        reclamo_ingresado = 0
        derivacion = 0

        for row in mycursor.fetchall():
            # SI HUBO DERIVACION ENTONCES NO DEBE HABER RESPUESTA DEL BOT
            if row[10] == 'SI':
                derivacion = 1
            else:
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

        #mensajes_previos = 1
        # tiene mensajes previos, pero no hay derivacion
        if mensajes_previos > 0 and derivacion == 0:
            

            ############################################################################################################
            ##   OBTENER PREGUNTAS FRECUENTES

            texts = [
                """¿Qué es el Registro de Empresas y Sociedades? El Registro de Empresas y Sociedades (RES) es un registro electrónico que dispone de un portal en Internet (www.RegistroDeEmpresasySociedades.cl), al cual deben incorporarse las personas jurídicas o empresas que deseen acogerse a la Ley N° 20.659, para los efectos de ser constituidas o migradas, modificadas, transformadas, fusionadas, divididas, terminadas o disueltas. El RES es un registro único y rige en todo el territorio de Chile. Es esencialmente público y está permanentemente actualizado a disposición de quien lo consulte en el sitio web, de manera que asegure la fiel y oportuna publicidad de la información incorporada en él. La información que conste en este Registro da plena fe de su autenticidad y cuenta con valor probatorio en contra de quienes han suscrito los formularios incorporados a este registro y sus empresas.""",
                """¿Puedo constituir una empresa o sociedad si estoy en Dicom?. Sí, puedes constituir una empresa o sociedad. No es un impedimento estar en Dicom, aunque es posible que los bancos e instituciones financieras impongan restricciones a la hora de otorgar financiamiento.""",
                """¿Qué tipos de empresas puedo constituir en el Registro de Empresas y Sociedades?. Por el momento, el registro comprende los siguientes tipos de empresas: Empresas Individuales de Responsabilidad Limitada (E.I.R.L.), Sociedades de Responsabilidad Limitada (SRL o Ltda.), Sociedades por Acciones (SpA), Sociedades Anónimas (S.A.) y Sociedades Anónimas de Garantía Recíproca (S.A.G.R.).""",
            ]    

            vectordb = Chroma.from_texts(texts, embedding=embedding)
                        

            #ESCRIBIR LAS DISTINTAS PREGUNTAS 
            promp_original = promp1

            question = messagedata.message
            

            second_prompt = ChatPromptTemplate.from_template(
                "Indícame si en la siguiente pregunta el usuario indica de manera explícita que quiere derivar la conversación a un ejecutivo humano y terminar la conversación con el bot.  Tu respuesta debe ser SI o NO:"
                "\n\n{human_input}"
            )
            # chain 2: input= English_Review and output= summary
            chain_two = LLMChain(llm=llm, prompt=second_prompt,
                                output_key="intencion_derivacion"
                                )

            response_derivacion = chain_two.predict(human_input=question)
            if response_derivacion == 'SI':
                response_type_response = 'Derivacion'
                response = ''
                response_is_claim = 'SI'
            else:


                # Build prompt
                template = promp1 + """Utilice las siguientes piezas de contexto para responder la pregunta al final. Si no sabe la respuesta, simplemente diga que no tiene la información, no intente inventar una respuesta. No haga referencia a que está utilizando un texto.  Responda entregando la mayor cantidad de información posible.
                {context}
                Question: {question}
                Helpful Answer:"""
                QA_CHAIN_PROMPT = PromptTemplate.from_template(template)

                # Run chain
                qa_chain = RetrievalQA.from_chain_type(
                    llm,
                    retriever=vectordb.as_retriever(),
                    return_source_documents=True,
                    chain_type_kwargs={"prompt": QA_CHAIN_PROMPT}
                )


                question = messagedata.message
                result = qa_chain({"query": question})

                response = result["result"]

                response_is_claim = 'SI'
                response_type_response = 'Interaccion'
             
        else:
            response = 'Sin Respuesta'
            response_is_claim = ''
            response_derivacion = ''
            response_type_response = ''


        if derivacion == 0:
            classification = "Área de Ventas"
            derivacion = "Área de Ventas"
            sla = "48 Horas"
            isclaim = response_is_claim
            today = date.today()
            identification = "R-" + today.strftime("%y%m%d"+str(idrowstr.zfill(4)))

            if response == 'Sin Respuesta':
                responsecustomer = 'Hola! soy el asistente virtual del servicio de Preguntas Frecuentes Iars2!.😎. Soy un asistente creado con Inteligencia Artificial preparado para atender a tus necesidades. Puedes indicar tu situación, y gestionaremos correctamente para dar una respuesta oportuna.  Para comenzar, favor indícame tu nombre'
                typeresponse = 'Saludo'
            else:

                if response_derivacion == 'SI':
                    responsecustomer = 'Para proporcionarte una asistencia más detallada y personalizada, voy a derivar tu solicitud a uno de nuestros ejecutivos. Estarán en contacto contigo en breve para abordar tus inquietudes de manera más directa.'
                    typeresponse = 'Derivacion'
                else:
                    #responsecustomer = "Su reclamo identificado como " + identification + " ha sido generado con éxito.  Su solicitud fue derivada al " + classification + ", y será resuelta en un plazo máximo de " + sla + "."
                    responsecustomerfinal = "Su reclamo está identificado por el siguiente código: " + identification + "."
                    typeresponse = response_type_response

                    responsecustomer = response

        # response = ''
            # GUARDADO RESPUESTA
            sqlresponse =  "UPDATE iar2_captura SET identification = '%s', messageresponseia = '%s', messageresponsecustomer = '%s', typeresponse = '%s', classification ='%s', sla = '%s', isclaim = '%s', derivacion = '%s'  WHERE id = %d" % (identification, sqlescape(response), sqlescape(responsecustomer), typeresponse, classification, sla, isclaim, response_derivacion, idrow)
            #valresponse = (messagedata.typemessage, messagedata.valuetype, messagedata.message, messagedata.enterprise)
            mycursor.execute(sqlresponse)   
            miConexion.commit()
        else:
            responsecustomer = ''

    #return {'respuesta': promp1}
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