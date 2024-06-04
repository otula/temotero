# pdf-to-json-converter
Python script for converting PDF files to JSON files using a pre-defined JSON template and OpenAI/Azure APIs.

Check the converter.py file for Python requirements.

Remember to modify MODEL_ENGINE, AZURE_API_KEY, AZURE_API_VERSION, AZURE_ENDPOINT or OPENAI_API_KEY to match your own credentials. You also need to comment/uncomment your desired client implementation in the main() function (for Azure or OpenAI). These properties can be found in the converter.py.

The template.json defines the output format, i.e., the format into the given .pdf files will be converted to. The example uses product details, but feel free to modify the format to fit your needs. In general, modifying the template.json should be enough, as long as the details can be found in your .pdf files in some reasonable manner. If you also want to modify the prompt, it can be found in converter.py (create_system_prompt() function).

You can add your .pdf files into the data directory, or use any other directory, but remember to modify the file paths in data.txt (in data directory) to match your needs.
