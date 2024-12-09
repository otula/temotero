# openai-rag-example
Example implementation of a RAG that uses OpenAI's assistants and vector storages.

Check the files filecrawler.py, filesearch.py and server.py for Python requirements.

Other important variables in server.py:
- ASSISTANT_ID = Identifier for your assistant, use None if you want to create a new one
- VECTOR_STORE_ID = Identifier for your vector store, use None if you want to create a new one
- FILE_DIRECTORY = Directory where to look for files to be added in the vector store
- FILE_SUFFIX = The file types to add to vector store
- PORT = The port number to use. You can access the service from this port after server startup.
- client = The client to use, the default is filesearch.create_azure_client(), you can also use filesearch.create_openai_client() if you want to use OpenAI API

Other important variables in filesearch.py:
- AZURE_API_KEY = If you are using Azure, add your Azure API key
- AZURE_ENDPOINT = If you are using Azure, add your Azure end-point url
- MODEL_ENGINE = You model deployment (or model name for OpenAI)
- OPENAI_API_KEY = If you are using OpenAI, add your OpenAI API key
- VECTOR_STORE_NAME = "Name of your vector storage."
- ASSISTANT_NAME = "Name of you assistant."
- ASSISTANT_INSTRUCTIONS = The common instructions for each task. Modify to match your use case.

Note: The implementation will ignore all .pdf files, which do not contain any text (image only pdf). This is because Azure's implementation may have issues with these files.

Note: You can also run filecrawler.py separately, but this is not required. It is also not required to modify the main method unless you plan to use the file separately. You can start the main web application by running: python server.py

The default implementation expects a two-level directory tree to exist (Directory-Subdirectory). This is used to refer the file locations in the result lists. You can add any number of directories and subdirectories. The directories can have any names (Directory-Subdirectory are created simply for an example), but you must create the required two-level directory tree. For more information, check the readme.txt in files directory.
