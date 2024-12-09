# from https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/file-search?tabs=python with some modifications
#
# Setup:
# 1. Create a virtual environment:
#     python -m venv venv
#
# 2. Activate the virtual environment:
#     - On Windows:
#         venv\Scripts\activate
#     - On macOS/Linux:
#         source venv/bin/activate
#
# 3. Install the required packages:
#     pip install openai
#
from openai import AzureOpenAI, OpenAI
import sys
import time
import json
import contextlib


AZURE_API_KEY="YOUR AZURE API KEY"
AZURE_API_VERSION = "2024-07-01-preview"
AZURE_ENDPOINT = "YOUR AZURE END POINT"
MODEL_ENGINE = "gpt-4o-mini"
OPENAI_API_KEY = "YOUR OPENAI KEY"
VECTOR_STORE_MAX_BATCH_SIZE = 500
VECTOR_STORE_NAME = "Name of your vector storage."
ASSISTANT_NAME = "Name of you assistant."
ASSISTANT_INSTRUCTIONS = "You are a secretary. Use your knowledge base to answer questions about events, topics, discussions and decissions made during meetings. Answer only based on the given files. If the requested information does not exist in the files, report that information is not available. Answer in the language of the user query. ALWAYS include file citations."

# create or retrieve an assistant
#
# @param client the client to use
# @param assistant_id if given, this assistant is retrieved, if None, a new one is created
# @return the assistant or None on error
#
def create_assistant(client, assistant_id):
    start_time = time.time()

    assistant = None
    if assistant_id is None:
        assistant = client.beta.assistants.create(
            name=ASSISTANT_NAME,
            instructions=ASSISTANT_INSTRUCTIONS,
            model=MODEL_ENGINE,
            tools=[{"type": "file_search"}],
            )
        print(f"Created a new assistant, id: {assistant.id}")
    else:
        print(f"Retrieving an existing assistant, id: {assistant_id}")
        try:
            assistant = client.beta.assistants.retrieve(assistant_id)
        except Exception as e:
            print(f"An error occurred while retrieving the assistant: {e}", file=sys.stderr)
            assistant = None

    print(f"Assistant created in {time.time() - start_time} seconds. Id: {assistant.id}")
    return assistant

# create or retrieve a vector store
#  
# @param client the client to use
# @param vector_store_id if given, this store is retrieved, if None, a new one is created
# @param file_paths an array of files to add to the vector store or None if no files to add
# @return vector store or None on error
#
def create_vector_store(client, vector_store_id, file_paths):
    import time
    import sys
    
    start_time = time.time()

    vector_store = None
    if vector_store_id is not None:
        print(f"Retrieving an existing vector store, id: {vector_store_id}")
        try:
            vector_store = client.beta.vector_stores.retrieve(vector_store_id)
        except Exception as e:
            print(f"An error occurred while retrieving the vector store: {e}", file=sys.stderr)
            vector_store = None
    else:
        vector_store = client.beta.vector_stores.create(name=VECTOR_STORE_NAME)
        print(f"Created a new vector store, id: {vector_store.id}")

    add_files_to_vector_store(client, vector_store, file_paths)

    print(f"Vector store created in {time.time() - start_time} seconds. Id: {vector_store.id}")

    return vector_store

# add files into a vector store
#  
# @param client the client to use
# @param vector_store_id if given, this store is retrieved, if None, a new one is created
# @param file_paths an array of files to add to the vector store or None if no files to add
#
import contextlib
import time

def add_files_to_vector_store(client, vector_store, file_paths):
    if vector_store is not None and file_paths is not None:
        start_time = time.time()

        print(f"Adding {len(file_paths)} files to vector store, id: {vector_store.id}")

        file_paths_lists = split_list(file_paths, VECTOR_STORE_MAX_BATCH_SIZE) # the client will not handle file lists larger than 500 files in one go

        for fp in file_paths_lists:
            batch_start_time = time.time()
            try:
                # Ready the files for upload to OpenAI
                with contextlib.ExitStack() as stack:
                    # This allows multiple files to be opened and closed automatically after the block
                    file_streams = [stack.enter_context(open(path, "rb")) for path in fp]

                    # Use the upload and poll SDK helper to upload the files, add them to the vector store,
                    # and poll the status of the file batch for completion.
                    file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
                        vector_store_id=vector_store.id, files=file_streams
                    )

                print(f"Batch processed in {time.time() - batch_start_time} seconds.")

                # You can print the status and the file counts of the batch to see the result of this operation.
                print(file_batch.status)
                print(file_batch.file_counts)

            except Exception as e:
                # Handle any exceptions that occur during the batch upload process
                print(f"Error occurred while processing batch: {str(e)}")
            finally:
                print("Proceeding to next batch if available.")

        print(f"All batches processed in {time.time() - start_time} seconds.")

def split_list(input_list, chunk_size):
    # Use list comprehension to split the list into smaller chunks
    return [input_list[i:i + chunk_size] for i in range(0, len(input_list), chunk_size)]



# run assistant
#  
# @param client the client to use
# @param assistant the assistant to use
# @param user_message the user's prompt message
#
def run_assistant(client, assistant, user_message):
    start_time = time.time()

    thread = client.beta.threads.create()
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_message
    )

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )

    status = run.status

    while status not in ["completed", "cancelled", "expired", "failed"]:
        time.sleep(5)
        run = client.beta.threads.runs.retrieve(thread_id=thread.id,run_id=run.id)
        status = run.status
        print(f'Status: {status}')
        if status == 'failed':
            print(f"Last error: {run.last_error}")

    messages = client.beta.threads.messages.list(
        thread_id=thread.id
    ) 

    print(f'Status: {status}')

    print(f"Assistant finished in {time.time() - start_time} seconds.")
    
    message_content = messages.data[0].content[0].text
    annotations = message_content.annotations
    citations = []
    for index, annotation in enumerate(annotations):
        if file_citation := getattr(annotation, "file_citation", None):
            cited_file = client.files.retrieve(file_citation.file_id)
            citations.append(cited_file.filename)

    return message_content.value, citations

# update assistant
#  
# @param client the client to use
# @param assistant the assistant to use
# @param vector_store tthe vector store to add to the assistant
#
def update_assistant(client, assistant, vector_store):
    start_time = time.time()

    assistant = client.beta.assistants.update(
        assistant_id=assistant.id,
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )

    print(f"Assistant updated in {time.time() - start_time} seconds.")

def create_azure_client():
    client = AzureOpenAI(
        api_key=AZURE_API_KEY,
        api_version=AZURE_API_VERSION,
        azure_endpoint=AZURE_ENDPOINT
    )
    return client

def create_openai_client():
    client = OpenAI(
        api_key=OPENAI_API_KEY
    )
    return client
