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


# Importaciones actualizadas para LangChain
#from langchain_community.chat_models import ChatOpenAI
from langchain_openai.chat_models import ChatOpenAI
#from langchain_community.embeddings import OpenAIEmbeddings  # Si usas embeddings
from langchain_openai import OpenAIEmbeddings  # Si usas embeddings
from langchain_anthropic import ChatAnthropic
#from langchain_community.vectorstores import Chroma
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader, PyMuPDFLoader
from langchain.prompts import PromptTemplate
from langchain.chains import ConversationalRetrievalChain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema.runnable import RunnableSequence, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
#from langchain.embeddings import HuggingFaceEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings


from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
#from langchain.llms import OpenAI
from langchain_community.llms import OpenAI
from langchain.chains import RetrievalQA
from langchain.chains import ConversationalRetrievalChain
#from langchain.embeddings.openai import OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate
#from langchain_openai import ChatOpenAI, OpenAIEmbeddings


#### NUEVOS

from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser


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

#FUNCION PARA INICIALIZAR RAG PARA CASOS FAQ
def initialize_qa_chain(codempresa):
    global qa_chains



    llm_provider = os.environ["LLM_PROVIDER"] 

    if llm_provider == "openai":
        llm_name = os.environ["LLM"] 
        #llm = ChatOpenAI(model_name=llm_name, temperature=0) 
        llm = ChatOpenAI(model_name=llm_name) 
        embedding = OpenAIEmbeddings()
    elif llm_provider == "anthropic":
        llm_name = os.environ["LLM_ANTHROPIC"] 
        llm = ChatAnthropic(
                    model="claude-3-5-sonnet-20241022",
                    temperature=0,
                    anthropic_api_key=os.environ["ANTHROPIC_API_KEY"]
                )
        #embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
        embedding = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        #embedding = OpenAIEmbeddings()        
    else:
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
                        FROM iar2_empresas WHERE typechatbot = 'STRUCT' AND codempresa = '%s'""" % (codempresa))
    
    idempresa = 0
    promp1 = ''
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


    promp_original = promp1
    
    if var_chunk_size == 0:
        var_chunk_size = 1500

    if var_chunk_overlap == 0:
        var_chunk_overlap = 150


    # DEFINE PREFIJO RUTA
    prefijo = os.environ["PREFIJO_RUTA"] 
    ############################################################################################################

    # Obtener la lista de archivos asociados a la empresa
    mycursor.execute("""SELECT file_path FROM iar2_files WHERE identerprise = '%d'""" % (idempresa))
    file_paths = [row[0] for row in mycursor.fetchall()]    

    #print(codempresa)
    #print(idempresa)
    #print(file_paths)
    all_docs = []
    for file_relative_path in file_paths:
        file_relative_path_full = f'{prefijo}src/routers/filesrag/{idempresa}/{file_relative_path}' 
        #print(file_relative_path_full)
        loader = PyPDFLoader(file_relative_path_full)
        docs = loader.load()
        #print(docs[0].page_content[:100])
        all_docs.extend(docs)   

    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = var_chunk_size,
        chunk_overlap = var_chunk_overlap
    )  

    #print(file_relative_path_full)  
    #return file_relative_path_full
    #print(text_splitter)

    splits = text_splitter.split_documents(all_docs)

    persist_directory = f'{prefijo}src/routers/filesrag/{idempresa}/{llm_provider}/chroma/'
    
    # Elimina el directorio y todo su contenido


    if os.path.exists(persist_directory) and os.path.isdir(persist_directory) and os.listdir(persist_directory):
        # ⚡ Cargar desde disco si ya existe
        vectordb = Chroma(persist_directory=persist_directory, embedding_function=embedding)
    else:
        # 🧠 Crear embeddings y persistir si no existe
        os.makedirs(persist_directory, exist_ok=True)
        vectordb = Chroma.from_documents(
            documents=splits,
            embedding=embedding,
            persist_directory=persist_directory
        )   


    #si el directorio existe, no es necesario crear nuevamente los embeddings
    # en caso de cargar más archivos, mejor borrar carpeta
    
    template = promp1 + """ Utilice las siguientes piezas de contexto para responder la pregunta al final. Si no sabe la respuesta, simplemente diga que no tiene la información, no intente inventar una respuesta. No haga referencia a que está utilizando un texto.  Responda entregando la mayor cantidad de información posible.
    {context}
    Question: {question}
    Helpful Answer:"""
    QA_CHAIN_PROMPT = PromptTemplate.from_template(template)

    
    chain_type_kwargs = {
        'prompt': QA_CHAIN_PROMPT
    }

    # Run chain
    #RetrievalQA.from_chain_type sirve para hacer solo la consulta
    
    qa_chain = ConversationalRetrievalChain.from_llm(
                    llm=llm, 
                    #retriever=vectordb.as_retriever(
                    #    search_kwargs={"k": 4}  # Ajusta el número de documentos recuperados
                    #), 
                    retriever=vectordb.as_retriever(),                   
                    #memory=memory,
                    get_chat_history=lambda h:h,
                    return_source_documents=False,
                    combine_docs_chain_kwargs=chain_type_kwargs,
                    verbose=False  # Útil para debugging
                    )     
    

    qa_chains[codempresa] = qa_chain


#INICIALIZA CADA UNO DE LOS RAG EXISTENTES
def initialize_all_qa_chains():
    miConexion = MySQLdb.connect(host=hostMysql, user=userMysql, passwd=passwordMysql, db=dbMysql)
    mycursor = miConexion.cursor()
    mycursor.execute("SELECT codempresa FROM iar2_empresas WHERE typechatbot = 'STRUCT'")
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


def chatbot_message(messagedata: MessageApi, id_interaction, idrow, promp1, llm_pregunta):


    global qa_chains



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

    ################################################################################
    key_chain = (codempresa, llm_pregunta)
    
    #if codempresa not in qa_chains:
    #    initialize_qa_chain(codempresa)
    if key_chain not in qa_chains:
        # Crear LLM según modelo
        llm_provider = os.environ["LLM_PROVIDER"]
        if llm_provider == "openai":
            llm = ChatOpenAI(model_name=llm_pregunta)
            embedding = OpenAIEmbeddings()
        elif llm_provider == "anthropic":
            llm = ChatAnthropic(
                model=llm_pregunta,
                temperature=0,
                anthropic_api_key=os.environ["ANTHROPIC_API_KEY"]
            )
            embedding = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        else:
            llm = ChatOpenAI(model_name=llm_pregunta)
            embedding = OpenAIEmbeddings()

        # Cargar Chroma ya embebido
        prefijo = os.environ["PREFIJO_RUTA"]
        persist_directory = f"{prefijo}src/routers/filesrag/{idempresa}/{llm_provider}/chroma/"
        vectordb = Chroma(persist_directory=persist_directory, embedding_function=embedding)

        # Armar prompt
        template = promp1 + """ Utilice las siguientes piezas de contexto para responder la pregunta al final. Si no sabe la respuesta, simplemente diga que no tiene la información, no intente inventar una respuesta. No haga referencia a que está utilizando un texto.  Responda entregando la mayor cantidad de información posible.
{context}
Question: {question}
Helpful Answer:"""
        QA_CHAIN_PROMPT = PromptTemplate.from_template(template)
        chain_type_kwargs = {'prompt': QA_CHAIN_PROMPT}

        # Crear chain
        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vectordb.as_retriever(),
            get_chat_history=lambda h: h,
            return_source_documents=False,
            combine_docs_chain_kwargs=chain_type_kwargs,
            verbose=False
        )

        # Cachearla
        qa_chains[key_chain] = qa_chain

    #################################################################################

    # Ejecutar con la chain correcta
    qa_chain = qa_chains[key_chain]

    result = qa_chain({"question": question, "chat_history": messages})
    #result = qa_chain | {"question": question, "chat_history": messages}

    
    response = result["answer"]
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
    #return result
    return responsecustomer

## ENVIA RECLAMOS USANDO LANGCHAIN
def send_message(messagedata: MessageApi):

    ##MODELO DE LENGUAJE
    llm_provider = os.environ["LLM_PROVIDER"] 

    


    if llm_provider == "openai":
        llm_name = os.environ["LLM"] 
        #llm = ChatOpenAI(model_name=llm_name, temperature=0) 
        llm = ChatOpenAI(model_name=llm_name) 
    elif llm_provider == "anthropic":
        llm_name = os.environ["LLM_ANTHROPIC"] 
        llm = ChatAnthropic(
                    model="claude-3-5-sonnet-20241022",
                    temperature=0,
                    anthropic_api_key=os.environ["ANTHROPIC_API_KEY"]
                )
    else:
        llm_name = os.environ["LLM"] 
        llm = ChatOpenAI(model_name=llm_name, temperature=0) 
    


   
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
                                    , prompt2                     
                        FROM iar2_empresas WHERE typechatbot = 'STRUCT' AND codempresa = '%s'""" % (messagedata.enterprise))

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
        prompt2 = row_empresa[13]




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
                'derivacion' : 0} 
 
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
    for row_interaction in mycursor.fetchall():
        tiene_mensaje = 1
        id_interaction = row_interaction[0]
        derivation = row_interaction[1]



    ## CASO 2: INTERACCION NUEVA - SALUDO
    # EN WHATSAPP Y RRSS HAY UN MENSAJE DE BIENVENIDA

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
    
    question = messagedata.message


    
    template_prompt2 = prompt2 + """
    "\n\n{human_input}"""
    derivation_prompt = ChatPromptTemplate.from_template(template_prompt2)

    
    # **Cambio importante: Uso de la nueva API de LangChain**
    chain_derivarion = derivation_prompt | llm
    
  
    #response_derivacion = chain_derivarion.predict(human_input=question)
    # Ejecutar la cadena para predecir la intención de derivación
    response_text  = chain_derivarion.invoke({"human_input": question})


    response_calculo = response_text.content
    #print("TIPO PREGUNTA CALCULO")
    #print(response_calculo)
    llm_pregunta = os.environ["LLM"] 

    ## CASO 4: CLIENTE PIDE AHORA DERIVACION
    if response_calculo == 'SI':
        llm_pregunta = os.environ["LLM2"] 


    ## CASO 5: COMUNICACION CON CHATBOT/ ESTO ES CUANDO EL MENSAJE NO ES DE BIENVENIDA, NI TAMPOCO LO CONTESTA UN HUMANO
    
    responsecustomer = chatbot_message(messagedata, id_interaction, idrow,  promp1, llm_pregunta)

    return {'respuesta': responsecustomer,
            'derivacion' : 0}

