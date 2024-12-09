# otula-whisper
Example implementation of a subtitle generator that uses faster-whisper implementation (https://github.com/SYSTRAN/faster-whisper) of OpenAI's Whisper language model in combination of OpenAI LLMs to optimize subtitles based on a provided video file and a reference documentation (e.g., presentation slides as a .pdf format).

Uses Azure's OpenAI end-point, which is identical with the actual OpenAI API. If you want to use the OpenAI or a custom model that support the OpenAI interface specifications (e.g. ollama), check the client initialization in optimize_subtitles() function of SubtitleOptimizer class. Simply replacing the client initialization should work in most cases, but note that not all models support the same parameters (e.g. temperature is not supported in OpenAI's o1 preview models).

Check the server.py file for Python requirements.

In server.py other important variables are:
- in SubtitleOptimizer
	- self.azure_api_key = Your Azure API key
	- self.azure_endpoint = Your Azure endpoint
	- self.model_engine = Your model deployment
- UPLOAD_FILE_DIRECTORY = Location where uploaded files are temporary stored for the duration of the analysis
- STATUS_STORAGE_FILE_PATH = Sqlite database used to store information on processed files (e.g. generated subtitles)
- For authentication:
	- USERNAME = Login username
	- PASSWORD = Login password
	- Note that by-default the implementation uses HTTP Basic Authentication, which is not recommended for production environment and/or the very least, an SSL/TLS connection should be set up
- PORT = The port for listening requests. You can access this port with web browser after the server has booted up.

Note: by default the result page will contain svn revision number for tracking/debugging which version the subtitles were generated with. If you don't want this, find SVN_REVISION variable in server.py and comment out all occurrences.
