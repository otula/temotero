# Convert PDFs to JSON using a template and Azure/OpenAI APIs
# Remember to set keys/endpoints for the service you wish to use.
# Check main function for selecting which service to use
#
# Requirements:
# pip install PyPDF2
# pip install openai
#
from PyPDF2 import PdfReader
from openai import AzureOpenAI      # python3-openai
from openai import OpenAI           # python3-openai
import difflib
import time

DATA_FILE = "data/data.txt" # file in format PATH_TO_TARGET_JSON PATH_TO_SOURCE_PDF, one entry per line
JSON_TEMPLATE = "template.json" # the template for JSON output
MODEL_ENGINE = "YOUR_MODEL" # your model deployment for Azure; or , e.g., gpt-4-turbo, gpt-4, and gpt-3.5-turbo for openAI
AZURE_API_KEY="YOUR_AZURE_KEY"
AZURE_API_VERSION="2024-02-01"
AZURE_ENDPOINT = "YOUR AZURE ENDPOINT, e.g. https://EXAMPLE.openai.azure.com/"
OPENAI_API_KEY = "YOUR_OPEN_AI_API_KEY"
AI_TEMPERATURE = 0.0

def read_data_file(file_path):
    data = []
    with open(file_path, 'r') as file:
        # Read each line in the file
        for line in file:
            # Check if the line is not empty
            if line.strip():
                # Strip any leading/trailing whitespace and split the line by spaces
                line_items = line.strip().split()
                # Append the list of items to the content_list
                data.append(line_items)
    return data

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + " "  # Space added to avoid merging words
    return " ".join(text.split()) # remove excessive whitespace

def create_system_prompt(template_path):
    with open(template_path, 'r') as file:
        return "Missing values are replaced with null. Answer only by printing the JSON. "+file.read()

def call_openai(client, system_prompt, user_prompt):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response=client.chat.completions.create(model=MODEL_ENGINE, response_format={"type":"json_object"}, messages=messages, temperature=AI_TEMPERATURE) # note: azure does not support response format json object on gpt-4 and gpt-3.5-turbo
    #response=client.chat.completions.create(model=MODEL_ENGINE, messages=messages, temperature=AI_TEMPERATURE)
    return response

def diff_text(text1, text2):
    d = difflib.Differ()
    return d.compare(text1.splitlines(), text2.splitlines())

def run_tests(client, data):
    system_prompt = create_system_prompt(JSON_TEMPLATE)

    print("Starting to call endpoint...")
    start_time = time.time()

    for json, pdf in data:
        extract_start_time = time.time()
        text = extract_text_from_pdf(pdf)
        extract_end_time = time.time()
        #print(text) # print the raw text output (converted from pdf)
        openai_start_time = time.time()
        response = call_openai(client, system_prompt, text)
        result = response.choices[0].message.content
        openai_end_time = time.time()
        print('\n\n##############################################')
        print(f"PDF extract finished in {extract_end_time - extract_start_time} seconds. Call finished in {openai_end_time - openai_start_time} seconds, reason: {response.choices[0].finish_reason}, choices: {len(response.choices)}")
        print("Diff for file: "+json+" / "+pdf)
        with open(json, 'r') as file:
            diff = diff_text(file.read(), result)
            print('\n'.join(diff))

    end_time = time.time()
    print(f"Calls finished in {end_time - start_time} seconds.")

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

def main():
    data = read_data_file(DATA_FILE)
    client = create_azure_client() # comment out to use Azure's OpenAI service
    #client = create_openai_client() # comment out to use OpenAI service
    run_tests(client, data)

if __name__ == "__main__":
    main()
