def initialize_qa_chain(codempresa):
    global qa_chains

    llm_provider = os.environ["LLM_PROVIDER"] 
    
    if llm_provider == "openai":
        llm_name = os.environ["LLM"] 
        llm = ChatOpenAI(model_name=llm_name, temperature=0) 
        embedding = OpenAIEmbeddings()
    elif llm_provider == "anthropic":
        llm_name = os.environ["LLM_ANTHROPIC"] 
        llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            temperature=0,
            anthropic_api_key=os.environ["ANTHROPIC_API_KEY"]
        )
        embedding = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    else:
        llm_name = os.environ["LLM"] 
        llm = ChatOpenAI(model_name=llm_name, temperature=0) 
        embedding = OpenAIEmbeddings()

    # Conexión a la BD
    miConexion = MySQLdb.connect(host=hostMysql, user=userMysql, passwd=passwordMysql, db=dbMysql)
    mycursor = miConexion.cursor()

    # Buscar empresa y su configuración
    mycursor.execute("""
        SELECT id, promp1, chunk_size, chunk_overlap, source_pdf, source_html, source_db
        FROM iar2_empresas WHERE codempresa = %s
    """, (codempresa,))
    
    row_empresa = mycursor.fetchone()
    if not row_empresa:
        return None  # No existe la empresa
    
    idempresa, promp1, chunk_size, chunk_overlap, source_pdf, source_html, source_db = row_empresa
    chunk_size = chunk_size or 1500
    chunk_overlap = chunk_overlap or 150
    
    all_docs = []
    prefijo = os.environ["PREFIJO_RUTA"]
    
    # Cargar documentos desde PDFs
    if source_pdf:
        mycursor.execute("SELECT file_path FROM iar2_files WHERE identerprise = %s", (idempresa,))
        for file_relative_path, in mycursor.fetchall():
            file_full_path = f'{prefijo}src/routers/filesrag/{idempresa}/{file_relative_path}'
            loader = PyPDFLoader(file_full_path)
            all_docs.extend(loader.load())
    
    # Cargar documentos desde HTMLs
    if source_html:
        mycursor.execute("SELECT url FROM iar2_html_sources WHERE identerprise = %s", (idempresa,))
        for url, in mycursor.fetchall():
            loader = WebBaseLoader(url)
            all_docs.extend(loader.load())
    
    # Cargar documentos desde BD
    if source_db:
        mycursor.execute("SELECT texto FROM iar2_db_texts WHERE identerprise = %s", (idempresa,))
        for text, in mycursor.fetchall():
            all_docs.append(Document(page_content=text))
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )  
    splits = text_splitter.split_documents(all_docs)
    
    persist_directory = f'{prefijo}src/routers/filesrag/{idempresa}/{llm_provider}/chroma/'
    if os.path.exists(persist_directory):
        shutil.rmtree(persist_directory)
    os.makedirs(persist_directory, exist_ok=True)
    
    vectordb = Chroma.from_documents(
        documents=splits,
        embedding=embedding,
        persist_directory=persist_directory
    )
    
    template = promp1 + """\nUse las siguientes piezas de contexto para responder la pregunta.\n{context}\nPregunta: {question}\nRespuesta:"""
    QA_CHAIN_PROMPT = PromptTemplate.from_template(template)
    
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectordb.as_retriever(),
        get_chat_history=lambda h: h,
        return_source_documents=False,
        combine_docs_chain_kwargs={'prompt': QA_CHAIN_PROMPT},
        verbose=False
    )
    
    qa_chains[codempresa] = qa_chain
