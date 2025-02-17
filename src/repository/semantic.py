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
from langchain.document_loaders import PyMuPDFLoader

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
import re

import os
import openai
import tiktoken
from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())

import shutil

# Diccionario global para almacenar las instancias de qa_chain
qa_chains = {}



def filter_fragments(splits):
    filtered = []
    for split in splits:
        content = split.page_content.strip()
        # Filtrar fragmentos vacíos o pequeños
        if len(content) < 50:
            continue
        # Filtrar fragmentos con ruido excesivo
        if content.count(" ") / len(content) < 0.2:  # Demasiados caracteres sin espacios
            continue
        filtered.append(split)
    return filtered


def remove_redundant_text(splits):
    seen_texts = set()
    unique_splits = []
    for split in splits:
        snippet = split.page_content[:200]  # Usa solo los primeros 200 caracteres como "firma"
        if snippet in seen_texts:
            continue
        seen_texts.add(snippet)
        unique_splits.append(split)
    return unique_splits





def clean_snippet(snippet):
    # Remueve múltiples espacios
    #snippet = re.sub(r'\s+', ' ', snippet)
    # Corrige caracteres separados por espacios (e.g., "E s t o" -> "Esto")
    snippet = re.sub(r'(?<=[a-zA-Z])\s(?=[a-zA-Z])', '', snippet)
    return snippet.strip()


def format_snippet(snippet, max_length=200):
    snippet = clean_snippet(snippet)
    if len(snippet) > max_length:
        snippet = snippet[:max_length] + "..."
    return snippet


def enhance_snippet(snippet, context_length=100):
    # Limpia el texto primero
    snippet = clean_snippet(snippet)
    # Agrega contexto previo y posterior
    words = snippet.split()
    if len(words) > context_length:
        snippet = " ".join(words[:context_length]) + "..."
    return snippet

#FUNCION PARA INICIALIZAR RAG PARA CASOS FAQ
def initialize_qa_chain(codempresa):
    global qa_chains
    llm_name = os.environ["LLM"]  #gpt-4o-mini
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
                        FROM iar2_empresas WHERE typechatbot = 'SEMANTICO' AND codempresa = '%s'""" % (codempresa))
    
    idempresa = 0
    promp1 = ''
    var_chunk_size = 0
    var_chunk_overlap = 0
    for row_empresa in mycursor.fetchall():
        idempresa = row_empresa[0]
        print(idempresa)
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
        var_chunk_size = 800 # Tamaño moderado para evitar fragmentos muy grandes.

    if var_chunk_overlap == 0:
        var_chunk_overlap = 200 # Solapamiento suficiente para asegurar contexto.


    # DEFINE PREFIJO RUTA
    prefijo = os.environ["PREFIJO_RUTA"] 
    ############################################################################################################

    # Obtener la lista de archivos asociados a la empresa
    mycursor.execute("""SELECT file_path FROM iar2_files WHERE identerprise = '%d'""" % (idempresa))
    file_paths = [row[0] for row in mycursor.fetchall()]    

    print(codempresa)
    print(idempresa)
    print(file_paths)
    all_docs = []
    for file_relative_path in file_paths:
        file_relative_path_full = f'{prefijo}src/routers/filesrag/{idempresa}/{file_relative_path}' 
        print(file_relative_path_full)
        #loader = PyPDFLoader(file_relative_path_full)
        loader = PyMuPDFLoader(file_relative_path_full)
        docs = loader.load()

        if not docs:
            print(f"No se pudo extraer texto del documento: {file_relative_path_full}")
        else:
            print(f"Se extrajeron {len(docs)} documentos.")
            for doc in docs[:5]:  # Muestra los primeros 5 fragmentos
                print(f"Contenido del documento: {doc.page_content[:200]}")
                        
        #print(docs[0].page_content[:100])
        all_docs.extend(docs)   

    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = var_chunk_size,
        chunk_overlap = var_chunk_overlap,
        separators=["\n\n", "\n", ".", " "]  # Priorizando párrafos, luego oraciones.
    )    

    #print(text_splitter)
    
    splits = text_splitter.split_documents(all_docs)

    print(f"Fragmentos iniciales: {len(splits)}")

    #splits = filter_fragments(splits) #Es probable que algunos fragmentos generados no sean útiles, especialmente si hay ruido o texto irrelevante

    print(f"Fragmentos después del filtro: {len(splits)}")

    #splits = remove_redundant_text(splits) #Algunos documentos incluyen contenido duplicado (como encabezados o pies de página repetitivos). Usa un filtro para eliminarlos

    persist_directory = f'{prefijo}src/routers/filesrag/{idempresa}/chroma/'

    if not splits:
        print(f"No hay fragmentos válidos para indexar en: {persist_directory}")
        return



    print(f"Fragmentos después de eliminar redundancias: {len(splits)}")

  
    
    # Elimina el directorio y todo su contenido

    # Verificar si el directorio existe antes de eliminarlo
    if os.path.exists(persist_directory):
        shutil.rmtree(persist_directory)


    # Crear el directorio (y cualquier directorio intermedio necesario)
    os.makedirs(persist_directory, exist_ok=True)
    
    print(persist_directory)
    
    #AQUI FALLA CON PM2
    
    vectordb = Chroma.from_documents(
        documents=splits,
        embedding=embedding,
        persist_directory=persist_directory
    )    
    
    
    
    '''
    template = """ A continuación se presentan fragmentos de documentos relevantes para la pregunta proporcionada. No genere una respuesta interpretativa ni explique, solo entregue los textos más cercanos al contenido solicitado:
    {context}
    Question: {question}
    Helpful Answer:"""
    '''
    
    template = """ A continuación se presentan fragmentos relevantes a la pregunta proporcionada. Incluye el número de página y el documento de origen:
    {context}
    Question: {question}
    Helpful Answer:"""


    QA_CHAIN_PROMPT = PromptTemplate.from_template(template)

    
    chain_type_kwargs = {'prompt': QA_CHAIN_PROMPT}
    # Run chain
    #RetrievalQA.from_chain_type sirve para hacer solo la consulta
 
    '''   
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectordb.as_retriever(),
        chain_type_kwargs=chain_type_kwargs,
        return_source_documents=True
    )    
    '''
    qa_chain = ConversationalRetrievalChain.from_llm(
                    llm=llm, 
                    retriever=vectordb.as_retriever(search_kwargs={"k": 5}),
                    #memory=memory,
                    get_chat_history=lambda h:h,
                    return_source_documents=True,
                    combine_docs_chain_kwargs=chain_type_kwargs)     
        
    qa_chains[codempresa] = qa_chain
    

#INICIALIZA CADA UNO DE LOS RAG EXISTENTES
def initialize_all_qa_chains():
    miConexion = MySQLdb.connect(host=hostMysql, user=userMysql, passwd=passwordMysql, db=dbMysql)
    mycursor = miConexion.cursor()
    mycursor.execute("SELECT codempresa FROM iar2_empresas WHERE typechatbot = 'SEMANTICO'")
    print("SELECT codempresa FROM iar2_empresas WHERE typechatbot = 'SEMANTICO'")
    for (codempresa,) in mycursor.fetchall():
        print(codempresa)
        initialize_qa_chain(codempresa)


# Inicializar todas las empresas al inicio (deshabilitamos opcion.  Sólo se inicializa al ocupar servicio)
initialize_all_qa_chains() 


def websearch_message(messagedata: MessageApi, id_interaction, idrow, promp1):

    #llm_name = "gpt-3.5-turbo"   
    global qa_chains

    llm_name = os.environ["LLM"]   
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
    
    #ESCRIBIR LAS DISTINTAS PREGUNTAS
     
    question = messagedata.message 
    codempresa = messagedata.enterprise
    messages = []

    #return messages
    memory.load_memory_variables({})     
    
    if codempresa not in qa_chains:
        initialize_qa_chain(codempresa)

    print(qa_chains[codempresa])
    qa_chain = qa_chains[codempresa]
    chat_history = []
    result = qa_chain({"question": question, "chat_history": messages})


    processed_response = {
        "question": result["question"],
        "answer": result["answer"],
        "sources": [
            {
                "page": doc.metadata.get("page"),
                "source": doc.metadata.get("source"),
                "snippet": enhance_snippet(doc.page_content, context_length=100)  # Fragmento de texto
            } for doc in result["source_documents"]
        ]
    }


    print(result)
    print('----------------------------------------------------------------------------------------------')
    print(processed_response)
    
    #print(result["answer"])
    #print(result["source_documents"])
    for source in processed_response['sources']:
        print(f"Página: {source['page']}, Documento: {source['source']}")
        print(f"Fragmento: {source['snippet']}\n")
        

    response = result["answer"]
    typeresponse = 'Cierre Conversación'
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
    #llm_name = "gpt-3.5-turbo"   
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
                                    , CASE WHEN time (NOW()) < time_min THEN 1
                                    		 ELSE 0
                                      END AS fuera_time_min
                                    , CASE WHEN time (NOW()) > time_max THEN 1
                                    		 ELSE 0
                                      END fuera_time_max   
                                    , whatsappapi 
                                    , websearch                         
                        FROM iar2_empresas WHERE typechatbot = 'SEMANTICO' AND codempresa = '%s'""" % (messagedata.enterprise))

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
        websearch = row_empresa[13]


    #VALIDACION DE EMPRESA
    if idempresa == 0:
        return {'respuesta': 'Empresa no existe',
                'derivacion' : 0}
    
    #VALIDACION DE CANAL
    if messagedata.typemessage == 'Whatsapp' and whatsapp == 0:
        return {'respuesta': 'Canal no permitido',
                'derivacion' : 0}
    if messagedata.typemessage == 'Webchat' and webchat == 0:
        return {'respuesta': 'Canal no permitido' ,
                'derivacion' : 0}   
    if messagedata.typemessage == 'WhatsappAPI' and whatsappapi == 0:
        return {'respuesta': 'Canal no permitido' ,
                'derivacion' : 0}   
    
    if messagedata.typemessage == 'WebSeach' and websearch == 0:
        return {'respuesta': 'Canal no permitido' ,
                'derivacion' : 0}       
    ###########################################################################################################

    sql = "INSERT INTO iar2_interaction (identerprise, typemessage, valuetype, lastmessage, lastmessageresponsecustomer, lastyperesponse, derivation, alert_finish, finish) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    val = (idempresa, messagedata.typemessage, messagedata.valuetype, sqlescape(messagedata.message), '', 'Cierre Conversación',0,1,1)
    mycursor.execute(sql, val)   
    miConexion.commit()
    id_interaction = mycursor.lastrowid

    # GUARDADO MENSAJE ENTRANTE
    sql = "INSERT INTO iar2_captura (typemessage, valuetype, message, identerprise, idinteraction) VALUES (%s, %s, %s, %s, %s)"
    val = (messagedata.typemessage, messagedata.valuetype, sqlescape(messagedata.message), idempresa, id_interaction)
    mycursor.execute(sql, val)   
    miConexion.commit()

    idrow = mycursor.lastrowid

    question = messagedata.message

    ## CASO 5: COMUNICACION CON CHATBOT/ ESTO ES CUANDO EL MENSAJE NO ES DE BIENVENIDA, NI TAMPOCO LO CONTESTA UN HUMANO
    responsecustomer = websearch_message(messagedata, id_interaction, idrow,  promp1)

    return {'respuesta': responsecustomer,
            'derivacion' : 0}

