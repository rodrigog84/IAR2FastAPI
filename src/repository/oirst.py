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
from langchain.chat_models import ChatOpenAI
from langchain.chat_models import PromptLayerChatOpenAI
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

from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter


import MySQLdb

#AGREGA CARACTERES DE ESCAPE EN SQL
from sqlescapy import sqlescape


#IMPORTAR WEBSOCKET
from ..routers.websocket_router import manager


import json
import requests
import httpx

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse
from os import getcwd
from datetime import date


import os
import openai
import tiktoken
from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())

import shutil

# Diccionario global para almacenar las instancias de qa_chain
qa_chains = {}
solution = 'OIRS_T'


#FUNCION PARA INICIALIZAR RAG PARA CASOS FAQ
def initialize_qa_chain(codempresa):
    global qa_chains
    llm_name = os.environ["LLM"] 
    llm = ChatOpenAI(model_name=llm_name, temperature=0) 

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
                                    , chunk_size
                                    , chunk_overlap
                                    , prompt2                     
                        FROM iar2_empresas WHERE typechatbot = '%s' AND codempresa = '%s'""" % (solution,codempresa))
    
    idempresa = 0
    promp1 = ''
    prompt2 = ''
    var_chunk_size = 0
    var_chunk_overlap = 0
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
        var_chunk_size = row_empresa[10]     
        var_chunk_overlap = row_empresa[10]     
        prompt2 = row_empresa[11]


    promp_original = promp1
    
    if var_chunk_size == 0:
        var_chunk_size = 1500

    if var_chunk_overlap == 0:
        var_chunk_overlap = 150


    # DEFINE PREFIJO RUTA
    prefijo = os.environ["PREFIJO_RUTA"] 
    ############################################################################################################

    # Obtener la lista de archivos asociados a la empresa
    mycursor.execute("""SELECT file_path, derivacion FROM iar2_files_oirs WHERE identerprise = '%d'""" % (idempresa))
    #file_paths = [row[0] for row in mycursor.fetchall()]    

    #print(codempresa)
    #print(idempresa)
    #print(file_paths)
    all_docs = []
    for file_relative_path, derivacion in mycursor.fetchall():
        file_relative_path_full = f'{prefijo}src/routers/filesrag/{idempresa}/{file_relative_path}' 
        print(file_relative_path_full)
        loader = PyPDFLoader(file_relative_path_full)
        docs = loader.load()
        for doc in docs:
            doc.metadata["derivacion"] = derivacion  # Asociar derivacion en los metadatos
        #print(docs[0].page_content[:100])
        all_docs.extend(docs)   

    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = var_chunk_size,
        chunk_overlap = var_chunk_overlap
    )    

    #print(text_splitter)

    splits = text_splitter.split_documents(all_docs)

    persist_directory = f'{prefijo}src/routers/filesrag/{idempresa}/chroma/'
    
    # Elimina el directorio y todo su contenido

    # Verificar si el directorio existe antes de eliminarlo
    if os.path.exists(persist_directory):
        shutil.rmtree(persist_directory)


    # Crear el directorio (y cualquier directorio intermedio necesario)
    os.makedirs(persist_directory, exist_ok=True)
    
    #print(persist_directory)
    
    #AQUI FALLA CON PM2
    
    vectordb = Chroma.from_documents(
        documents=splits,
        embedding=embedding,
        persist_directory=persist_directory
    )    
    
    
    f'{prefijo}src/routers/filesrag/{idempresa}/{file_relative_path}' 
  
    template = str(prompt2) + """ Utilice las siguientes piezas de contexto para responder la pregunta al final. Si no sabe la respuesta, simplemente diga que no tiene la información, no intente inventar una respuesta. No haga referencia a que está utilizando un texto.  Responda entregando la mayor cantidad de información posible.
    {context}
    Question: {question}
    Helpful Answer:"""
    QA_CHAIN_PROMPT = PromptTemplate.from_template(template)

    
    chain_type_kwargs = {'prompt': QA_CHAIN_PROMPT}
    # Run chain
    #RetrievalQA.from_chain_type sirve para hacer solo la consulta
    
    qa_chain = ConversationalRetrievalChain.from_llm(
                    llm=llm, 
                    retriever=vectordb.as_retriever(),
                    #memory=memory,
                    get_chat_history=lambda h:h,
                    return_source_documents=True,
                    combine_docs_chain_kwargs=chain_type_kwargs)     
    
    qa_chains[codempresa] = qa_chain
    

#INICIALIZA CADA UNO DE LOS RAG EXISTENTES
def initialize_all_qa_chains():
    miConexion = MySQLdb.connect(host=hostMysql, user=userMysql, passwd=passwordMysql, db=dbMysql)
    mycursor = miConexion.cursor()
    mycursor.execute("""SELECT codempresa FROM iar2_empresas WHERE typechatbot = '%s'""" % (solution))
    for (codempresa,) in mycursor.fetchall():
        initialize_qa_chain(codempresa)


# Inicializar todas las empresas al inicio (deshabilitamos opcion.  Sólo se inicializa al ocupar servicio)
initialize_all_qa_chains() 

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




def process_message():

    global qa_chains
    apirest_url = os.environ["IP_APIREST"]
    prefix_url = os.environ["PREFIX_APIREST"]

   

    llm_name = os.environ["LLM"]   
    llm = ChatOpenAI(model_name=llm_name, temperature=0) 
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)    

    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()

    #BUSCA LA EMPRESA
    mycursor.execute("""SELECT      DISTINCT i.typemessage
                                    , i.valuetype
                                    , i.identerprise 
                                    , i.id
                                    , e.codempresa
                        FROM        iar2_interaction i
                        INNER JOIN  iar2_empresas e on i.identerprise = e.id 
                        WHERE       i.finish = 1
                        AND         internalresponse = ''
                        AND         derivationarea = ''
                        AND         e.typechatbot = '%s'
                        ORDER BY    id desc
                        LIMIT       1""" % (solution))

    reclamos = []
    registro = []
    for row_interaction in mycursor.fetchall():

        typemessage = row_interaction[0]
        valuetype = row_interaction[1]
        identerprise = row_interaction[2]
        id_interaction = row_interaction[3]
        codempresa = row_interaction[4]

        mycursor2 = miConexion.cursor()
        #EVALUA LOS MENSAJES EXISTENTES DE LA INTERACCION ACTUAL
        mycursor2.execute("""SELECT      identification
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
                            AND         typeresponse != 'Saludo'
                            ORDER BY    created_at """ % (id_interaction))
        
        messages = []
        # AGREGA CADA MENSAJE PREVIO A MEMORIA, PARA QUE EL CHAT TENGA MEMORIA DE LA CONVERSACIÓN PREVIA
        for row in mycursor2.fetchall():

            #messages.append((f'Human: {row[3]}', f'Assistant: {row[5]}'))
            if row[3] is not None and row[3] != '' and row[5] is not None and row[5] != '':
                messages.append((row[3],row[5]))

            memory.save_context({"input": row[3]}, 
                                {"output": row[5]})
                    
        #return messages
        memory.load_memory_variables({})              
       
        if codempresa not in qa_chains:
            initialize_qa_chain(codempresa)

        qa_chain = qa_chains[codempresa]
        chat_history = []
        question = ''
        result_int = qa_chain({"question": question, "chat_history": messages})              
        #print('respuesta rag')
        #print(result_int['answer'])
        #print(result_int['source_documents'])
        print(result_int)
        internal_response = result_int['answer']
        if "source_documents" in result_int:
            derivaciones_utilizadas = set(doc.metadata["derivacion"] for doc in result_int["source_documents"])

        # Determinar el departamento correspondiente (puede haber varios)
        # Aquí decides la lógica de derivación (por ejemplo, el departamento con mayor cantidad de fragmentos)
        #derivacion_destino = max(derivaciones_utilizadas, key=lambda d: derivaciones_utilizadas.count(d))


        #print(derivaciones_utilizadas)
        derivacion_final = ''
        for derivacion in derivaciones_utilizadas:
            #print(derivacion)
            derivacion_final = derivacion   


        sqlresponse =  "UPDATE iar2_interaction SET internalresponse = '%s', derivationarea = '%s' WHERE id = %d" % (sqlescape(internal_response), derivacion_final, id_interaction)
        mycursor.execute(sqlresponse)       
        miConexion.commit()

    miConexion.close()
    return {'data' : 'Conversaciones Finalizadas'}

def chatbot_message(messagedata: MessageApi, id_interaction, idrow, promp1):

    #llm_name = "gpt-3.5-turbo"   
    global qa_chains

    llm_name = os.environ["LLM"]   
    llm = ChatOpenAI(model_name=llm_name, temperature=0) 
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
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
                        AND         typeresponse != 'Saludo'
                        ORDER BY    created_at """ % (id_interaction))

    mensajes_previos = 0
    reclamo_ingresado = 0
    derivacion = 0
    messages = []

    # AGREGA CADA MENSAJE PREVIO A MEMORIA, PARA QUE EL CHAT TENGA MEMORIA DE LA CONVERSACIÓN PREVIA
    for row in mycursor.fetchall():

        mensajes_previos = mensajes_previos + 1

        #messages.append((f'Human: {row[3]}', f'Assistant: {row[5]}'))
        if row[3] is not None and row[3] != '' and row[5] is not None and row[5] != '':
            messages.append((row[3],row[5]))

        memory.save_context({"input": row[3]}, 
                            {"output": row[5]})
                
    #return messages
    memory.load_memory_variables({})        

    #ESCRIBIR LAS DISTINTAS PREGUNTAS
     
    question = messagedata.message 
    codempresa = messagedata.enterprise

    # Prompt simplificado para obtener solo la respuesta al usuario
    prompt_respuesta = promp1

    # Prompt para determinar si la conversación ha terminado
    prompt_fin_conversacion = """Dado el siguiente mensaje de un asistente virtual, indica si la conversación ha terminado o no. Una forma de saber es si en el mensaje se indicó el plazo de respuesta.  Responde con "1" si la conversación terminó y con "0" si continúa:
    "{mensaje_respuesta}" """


    # Crear la plantilla principal solo para la respuesta
    principal_prompt_respuesta = PromptTemplate(
        input_variables=["chat_history", "human_input"],
        template=prompt_respuesta + """

        {chat_history}
        Human: {human_input}
        Chatbot:"""
    )    


    # Cadena para la respuesta principal del usuario
    chain_respuesta = LLMChain(
        llm=llm,
        prompt=principal_prompt_respuesta,
        memory=memory
    )

    question = messagedata.message



    try:
        # Generar respuesta principal
        response = chain_respuesta.predict(human_input=question)
        #print("Respuesta del chatbot:", response)

        # Ahora generamos la segunda pregunta para determinar si la conversación terminó
        # Creamos un nuevo prompt con la respuesta que ya se generó
        prompt_terminacion = PromptTemplate(
            input_variables=["mensaje_respuesta"],
            template=prompt_fin_conversacion
        )

        # Llamamos a ChatGPT solo para verificar si la conversación terminó
        chain_terminacion = LLMChain(
            llm=llm,
            prompt=prompt_terminacion
        )

        # Obtener si la conversación ha terminado
        terminado = chain_terminacion.predict(mensaje_respuesta=response)
        #print("Terminación de la conversación:", terminado)

        # Convertir la respuesta de terminación a True o False según el valor recibido
        conversation_finished = True if terminado.strip() == "1" else False

        # Definir código de seguimiento
        tracking_code = "ABC123" if conversation_finished else ""

        # Crear el diccionario final de respuesta en formato JSON
        response_json = {
            "response": response,
            "conversation_finished": conversation_finished,
            "tracking_code": tracking_code
        }

        #print("Respuesta JSON:", response_json)

    except ValueError as e:
        print(f"Error de valor: {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")



    # Guardado en la base de datos
    if response:
        response_type_response = 'Interaccion'
        typeresponse = response_type_response
        responsecustomer = response

        if conversation_finished:
                typeresponse =  'Cierre Conversación'
                finish = 1
                derivacion_final = ''
                internal_response = ''

                '''
                if codempresa not in qa_chains:
                    initialize_qa_chain(codempresa)

                qa_chain = qa_chains[codempresa]
                chat_history = []
                result_int = qa_chain({"question": question, "chat_history": messages})              
                print('respuesta rag')
                print(result_int['answer'])
                print(result_int['source_documents'])
                internal_response = result_int['answer']
                if "source_documents" in result_int:
                    derivaciones_utilizadas = set(doc.metadata["derivacion"] for doc in result_int["source_documents"])

                # Determinar el departamento correspondiente (puede haber varios)
                # Aquí decides la lógica de derivación (por ejemplo, el departamento con mayor cantidad de fragmentos)
                #derivacion_destino = max(derivaciones_utilizadas, key=lambda d: derivaciones_utilizadas.count(d))


                print(derivaciones_utilizadas)
                derivacion_final = ''
                for derivacion in derivaciones_utilizadas:
                    print(derivacion)
                    derivacion_final = derivacion
                '''
        else:
                typeresponse =  'Interaccion'
                finish = 0
                derivacion_final = ''
                internal_response = ''



        sqlresponse =  "UPDATE iar2_captura SET identification = '', messageresponseia = '%s', messageresponsecustomer = '%s', typeresponse = '%s', derivacion = '%s', idinteraction = '%d'  WHERE id = %d" % (sqlescape(response), sqlescape(responsecustomer), typeresponse, 'NO', id_interaction, idrow)
        mycursor.execute(sqlresponse)   
        miConexion.commit()

        sqlresponse =  "UPDATE iar2_interaction SET lastmessage = '%s', lastmessageresponsecustomer = '%s', lastyperesponse = '%s', finish = %d, internalresponse = '%s', derivationarea = '%s' WHERE id = %d" % (sqlescape(messagedata.message), sqlescape(responsecustomer), typeresponse, finish, internal_response, derivacion_final, id_interaction)
        mycursor.execute(sqlresponse)       
        miConexion.commit()
    else:
        print("No se pudo obtener una respuesta del chatbot.")




    ### RESPUESTA INTERNA 
    '''

    
    response = result["answer"]
    typeresponse = 'Interaccion'
    responsecustomer = response
    '''

    #return result
    #return ''
    return {'respuesta': responsecustomer,
            'finish' : finish}

## ENVIA RECLAMOS USANDO LANGCHAIN
def send_message(messagedata: MessageApi):

    ##MODELO DE LENGUAJE
    #llm_name = "gpt-3.5-turbo"   
    llm_name = os.environ["LLM"]   
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
                                    , whatsappapi                          
                        FROM iar2_empresas WHERE typechatbot = '%s' AND codempresa = '%s'""" % (solution, messagedata.enterprise))

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
        whatsappapi = row_empresa[12]


    #VALIDACION DE EMPRESA
    if idempresa == 0:
        return {'respuesta': 'Empresa no existe',
                'derivacion' : 0}
    
    #VALIDACION DE CANAL
    if messagedata.typemessage == 'Whatsapp' and whatsapp == 0:
        return {'respuesta': 'Canal no permitido',
                'derivacion' : 0}
    if messagedata.typemessage == 'WebChat' and webchat == 0:
        return {'respuesta': 'Canal no permitido' ,
                'derivacion' : 0}   
    if messagedata.typemessage == 'WhatsappAPI' and whatsappapi == 0:
        return {'respuesta': 'Canal no permitido' ,
                'derivacion' : 0}   
    ###########################################################################################################

    ## LIMPIAR REGISTRO EN CASO DE PROBAR NUEVAMENTE

    ## CASO 1: LIMPIEZA REGISTRO    
    if messagedata.message == 'Limpiar registro':
         
         resp = limpiar_registro(messagedata, idempresa)

         return {'respuesta': resp,
                'finish' : 0} 
 

  
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
    derivation = 0
    tiene_mensaje = 0



    derivation = 0
    tiene_mensaje = 0
    for row_interaction in mycursor.fetchall():
        tiene_mensaje = 1
        id_interaction = row_interaction[0]
        derivation = row_interaction[1]

    ## CASO 2: INTERACCION NUEVA - SALUDO
    if tiene_mensaje == 0:
        #SI NO TIENE NINGUN MENSAJE PREVIO Y ESTÁ DENTRO DEL HORARIO, ENVIA MENSAJE DE BIENVENIDA
        sql = "INSERT INTO iar2_interaction (identerprise, typemessage, valuetype, lastmessage, lastmessageresponsecustomer, lastyperesponse, derivation) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        val = (idempresa, messagedata.typemessage, messagedata.valuetype, sqlescape(messagedata.message), '', 'Saludo',0)
        mycursor.execute(sql, val)   
        miConexion.commit()

        id_interaction = mycursor.lastrowid
 
    # GUARDADO MENSAJE ENTRANTE
    sql = "INSERT INTO iar2_captura (typemessage, valuetype, message, identerprise, idinteraction) VALUES (%s, %s, %s, %s, %s)"
    val = (messagedata.typemessage, messagedata.valuetype, sqlescape(messagedata.message), idempresa, id_interaction)
    mycursor.execute(sql, val)   
    miConexion.commit()

    idrow = mycursor.lastrowid

    idrowstr = str(idrow)

    
    ########################################################################################################
    
    ## CASO 5: COMUNICACION CON CHATBOT/ ESTO ES CUANDO EL MENSAJE NO ES DE BIENVENIDA, NI TAMPOCO LO CONTESTA UN HUMANO
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


    apirest_url = os.environ["IP_APIREST"]
    prefix_url = os.environ["PREFIX_APIREST"]

    #CONEXION
    miConexion = MySQLdb.connect( host=hostMysql, user= userMysql, passwd=passwordMysql, db=dbMysql )
    mycursor = miConexion.cursor()

    #BUSCA LA EMPRESA
    mycursor.execute("""SELECT      DISTINCT i.typemessage
                                    , i.valuetype
                                    , i.identerprise 
                        FROM        iar2_interaction i
                        INNER JOIN  iar2_empresas e on i.identerprise = e.id 
                        WHERE       i.finish = 0
                        AND         e.typechatbot = '%s'""" % (solution))
    #mycursor.execute("SELECT DISTINCT typemessage, valuetype, identerprise FROM iar2_captura WHERE created_at BETWEEN DATE_ADD(NOW(), INTERVAL -3 DAY) AND NOW()")

    typemessage = ''
    valuetype = ''
    identerprise = ''
    url = ''
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
        mycursor2.execute("""SELECT 	c.lastmessageresponsecustomer as messageresponsecustomer 
                                        ,c.lastyperesponse as typeresponse
                                        ,TIMESTAMPDIFF(MINUTE,c.updated_at,NOW()) AS minutos 
                                        ,e.port
                                        ,e.closealertminutes
                                        ,e.closeminutes
                                        ,c.id as idinteracion
                                        ,e.numberidwsapi
                                        ,e.jwtokenwsapi    
                                        ,e.whatsapp
                                        ,e.whatsappapi    
                                        ,e.webchat                     
                            FROM        iar2_interaction c  
                            INNER JOIN  iar2_empresas e  on c.identerprise = e.id
                            WHERE 	    finish = 0
                            AND         typemessage = '%s' 
                            AND 	    valuetype = '%s' 
                            AND         identerprise = %d""" % (typemessage,valuetype,identerprise))

        for row_register in mycursor2.fetchall():
                messageresponsecustomer = row_register[0]
                typeresponse = row_register[1]
                minutos = row_register[2]
                apiwsport = row_register[3]
                apiwsclosealertminutes = row_register[4]
                apiwscloseminutes = row_register[5]
                id_interaction = row_register[6]
                numberidwsapi = row_register[7]
                jwtokenwsapi = row_register[8]     
                whatsapp = row_register[9]
                whatsappapi = row_register[10]  
                webchat = row_register[11]                  
                
                mycursor3 = miConexion.cursor()

                # SI ULTIMO MENSAJE FUE DEL CHATBOT, ES DE WHATSAPP, ES DE INTERACCION O SALUDO Y FUE HACE MÁS DE 30 MINUTOS, ENVIAR MENSAJE DE ALERTA DE CIERRE
                if  (typemessage == 'Whatsapp' or typemessage == 'WhatsappAPI' or typemessage == 'WebChat') and messageresponsecustomer != '' and typeresponse != 'Alerta Cierre' and minutos > apiwsclosealertminutes:
                    
                    #response = requests.get(url)
                    
                    if typemessage == 'Whatsapp' and whatsapp == 1:
                        
                        url = f'http://' + apiwshost + ':' + str(apiwsport) + '/api/CallBack'
                        payload = json.dumps({
                            "message": message_alerta_cierre,
                            "phone": valuetype
                        })
                        headers = {
                        'Content-Type': 'application/json'
                        }
                        response = requests.request("POST", url, headers=headers, data=payload)                    
                    elif typemessage == 'WhatsappAPI' and whatsappapi == 1:

                        url = f'https://graph.facebook.com/' + apiwsapiversion + '/' + str(numberidwsapi) + '/messages'
                        payload = json.dumps({
                        "messaging_product": "whatsapp",    
                        "recipient_type": "individual",
                        "to": valuetype,
                        "type": "text",
                        "text": {
                            "body": message_alerta_cierre
                        }
                        })

                        headers = {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + jwtokenwsapi
                        }

                        response = requests.request("POST", url, headers=headers, data=payload)                 

                    elif typemessage == 'WebChat' and webchat == 1:

                        # Construir la URL del endpoint con el user_id correspondiente
                        url = f'{prefix_url}://{apirest_url}/send_inactivity_message/{valuetype}'
                        
                        # Definir el payload con el mensaje de inactividad personalizado
                        payload = {
                            "message": message_alerta_cierre
                        }
                        headers = {
                            'Content-Type': 'application/json'
                        }
                        
                        # Realizar la solicitud POST de forma sincrónica
                        try:
                            response = httpx.post(url, headers=headers, json=payload)
                            # Manejar la respuesta del servidor
                            if response.status_code == 200:
                                print("Mensaje de inactividad enviado exitosamente:", response.json())
                            else:
                                print("Error al enviar el mensaje de inactividad:", response.status_code, response.text)
                        except httpx.RequestError as exc:
                            print(f"Error de conexión: {exc}")
                    
                    sql = "INSERT INTO iar2_captura (typemessage, valuetype, messageresponsecustomer, typeresponse, identerprise) VALUES (%s, %s, %s, %s, %s)"
                    val = (typemessage, valuetype, 'Alerta de cierre de sesion', 'Alerta Cierre', identerprise)
                    mycursor3.execute(sql, val)   
                    miConexion.commit()

                    sqlresponse =  "UPDATE iar2_interaction SET  lastmessage =  '', lastmessageresponsecustomer =  'Alerta de cierre de sesion', lastyperesponse =  'Alerta Cierre', alert_finish = 1 WHERE id = %d" % (id_interaction)
                    mycursor3.execute(sqlresponse)   
                    miConexion.commit()    

                # SI ULTIMO MENSAJE FUE DE ALERTA DE CIERRE Y DE WHATSAPP, ENVIAR MENSAJE DE CIERRE
                if  (typemessage == 'Whatsapp' or typemessage == 'WhatsappAPI' or typemessage == 'WebChat') and typeresponse == 'Alerta Cierre' and minutos > apiwscloseminutes:
                    #url = f'http://' + apiwshost + ':' + apiwsport + '/api/CallBack?p=' + valuetype + '&q=2'
                    #response = requests.get(url)

                    
                    if typemessage == 'Whatsapp' and whatsapp == 1:
                        
                        url = f'http://' + apiwshost + ':' + str(apiwsport) + '/api/CallBack'
                        payload = json.dumps({
                            "message": message_cierre,
                            "phone": valuetype
                        })
                        headers = {
                        'Content-Type': 'application/json'
                        }
                        response = requests.request("POST", url, headers=headers, data=payload)                    
                    elif typemessage == 'WhatsappAPI' and whatsappapi == 1:

                        url = f'https://graph.facebook.com/' + apiwsapiversion + '/' + str(numberidwsapi) + '/messages'
                        payload = json.dumps({
                        "messaging_product": "whatsapp",    
                        "recipient_type": "individual",
                        "to": valuetype,
                        "type": "text",
                        "text": {
                            "body": message_cierre
                        }
                        })

                        headers = {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + jwtokenwsapi
                        }

                        response = requests.request("POST", url, headers=headers, data=payload)   

                    elif typemessage == 'WebChat' and webchat == 1:

                        # Construir la URL del endpoint con el user_id correspondiente
                        url = f'{prefix_url}://{apirest_url}/send_inactivity_message/{valuetype}'
                        
                        # Definir el payload con el mensaje de inactividad personalizado
                        payload = {
                            "message": message_cierre
                        }
                        headers = {
                            'Content-Type': 'application/json'
                        }
                        
                        # Realizar la solicitud POST de forma sincrónica
                        try:
                            response = httpx.post(url, headers=headers, json=payload)
                            # Manejar la respuesta del servidor
                            if response.status_code == 200:
                                print("Mensaje de inactividad enviado exitosamente:", response.json())
                            else:
                                print("Error al enviar el mensaje de inactividad:", response.status_code, response.text)
                        except httpx.RequestError as exc:
                            print(f"Error de conexión: {exc}")

                    sql = "INSERT INTO iar2_captura (typemessage, valuetype, messageresponsecustomer, typeresponse, identerprise) VALUES (%s, %s, %s, %s, %s)"
                    val = (typemessage, valuetype, 'Cierre de sesion definitivo', 'Cierre Conversación', identerprise)
                    mycursor3.execute(sql, val)   
                    miConexion.commit()

                    sqlresponse =  "UPDATE iar2_interaction SET  lastmessage =  '', lastmessageresponsecustomer =  'Cierre de sesion definitivo', lastyperesponse =  'Cierre Conversación', finish = 1 WHERE id = %d" % (id_interaction)
                    mycursor3.execute(sqlresponse)   
                    miConexion.commit()    

                content2 = {"messageresponsecustomer":messageresponsecustomer,"typeresponse":typeresponse,"minutos":minutos,"url": url}    
                registro.append(content2)
        



    miConexion.close()
    return {'data' : 'Conversaciones Finalizadas'}