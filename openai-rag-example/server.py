# simple web frontend for filesearch.py
# Setup:
#
# 1. Start python in correct folder and check python version
#   python --version
# 
# 2. Create a virtual environment: 
#    (this is not needed for every time, steps 3 and 4 are enough)
#     python -m venv venv
#
# 3. Activate the virtual environment:
#     - On Windows:
#         venv\Scripts\activate
#     - On macOS/Linux:
#         source venv/bin/activate
#
# 4. Install the required packages:
#     pip install flask openai
#     pip install pymupdf
#
# 5. Run application
#     python server.py

from flask import Flask, request, render_template_string, jsonify, send_file
import filesearch
import filecrawler
import os

ASSISTANT_ID = None # id for pre-existing assistant or None if creating a new one
VECTOR_STORE_ID = None # id for pre-existing vector store or None if creating a new one
FILE_DIRECTORY = "files"
FILE_SUFFIX = (".pdf")
PORT = 10000

app = Flask(__name__)
client = filesearch.create_azure_client()
assistant = filesearch.create_assistant(client, ASSISTANT_ID)
file_list = filecrawler.collect_files_with_suffixes(FILE_DIRECTORY, FILE_SUFFIX)
if VECTOR_STORE_ID is None:
    file_list = filecrawler.filter_pdfs_without_text(file_list) # azure vector store has issues with image-only-pdfs, so filter those out first
    vector_store = filesearch.create_vector_store(client, VECTOR_STORE_ID, file_list) # uncomment to create a new vector store
    filesearch.update_assistant(client, assistant, vector_store) # uncomment to update the vectore store to an existing assistant

# HTML template
template = '''
<!DOCTYPE html>
<html>
<head>
    <title>OpenAI RAG</title>
    <style>
        #query {
            width: 100%;
        }
        #response {
            width: 100%;
            height: 50%;
        }
        #header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            height: 75px;
            background-color: #f8f9fa;
        }
        #header-bar img {
            height: 100%;
            object-fit: cover;
        }
    </style>
</head>
<body>
    <header id="header-bar">
        <img src="{{ url_for('static', filename='images/FI_Co-fundedbytheEU_RGB_Monochrome.png') }}" alt="EU logo">
        <img src="{{ url_for('static', filename='images/logo_TAU_fi_violetti_RGB.png') }}" alt="TAU logo">
        <img src="{{ url_for('static', filename='images/GPTlab_logo_v2-2.png') }}" alt="GPT-Lab logo">
        <img src="{{ url_for('static', filename='images/logo-rautalanka_musta-160x33.png') }}" alt="RoboAI logo">
        <img src="{{ url_for('static', filename='images/SatliVaaka_PNG.png') }}" alt="Satakuntaliitto logo">
    </header>

    <h1>OpenAI RAG</h1>
    <p>Sample informative text about the contents of your files.</p>
    <form id="query-form">
        <label for="query">Enter your query and wait for response:</label><br><br>
        <input type="text" id="query" name="query"><br><br>
        <input type="submit" value="Run Query">
    </form>
    <br>
    <p id="timer">Time: 0 s</p>
    <textarea id="response" rows="10" cols="50"></textarea>
    <div id="download-links"></div> <!-- New div to display download links -->

    <script>
        var startTime;
        var timerInterval;

        function updateTimer() {
            var currentTime = new Date().getTime();
            var timeTaken = currentTime - startTime;
            document.getElementById('timer').innerText = 'Time: ' + (timeTaken/1000) + ' s';
        }

        document.getElementById('query-form').onsubmit = function(event) {
            event.preventDefault();
            var query = document.getElementById('query').value;

            startTime = new Date().getTime();
            timerInterval = setInterval(updateTimer, 1000);
            document.getElementById('response').innerText = ''

            fetch('/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query: query }),
            })
            .then(response => response.json())
            .then(data => {
                clearInterval(timerInterval);
                document.getElementById('response').value = data.response;

                // Display download links
                var downloadLinksDiv = document.getElementById('download-links');
                downloadLinksDiv.innerHTML = ''; // Clear previous links
                var addedCitations = []
                for(let i=0;i<data.citations.length;++i) {
                    let citation = data.citations[i]
                    if (addedCitations.indexOf(citation) >= 0) continue;
                    addedCitations.push(citation)
                    let link = document.createElement('a');
                    let uriCitation = encodeURIComponent(citation)
                    link.href = '/download?file=' + uriCitation;
                    link.innerText = 'Download ' + citation;
                    link.style.display = 'block';

                    fetch('/citation?citation=' + uriCitation)
                    .then(response => response.json())  // Parse the JSON response
                    .then(data => {
                        for(let j=0;j<data.length;++j)
                            details = data[j]
                            link.innerText += ' ('+details.directory + ' ' + details.subdirectory+')'
                    })
                    .catch(error => console.error('Error:', error));

                    downloadLinksDiv.appendChild(link);
                }
            });
        };
    </script>
</body>
</html>
'''

@app.route('/citation')
def get_citation_details():
    absolute_paths = find_abosulate_paths(request.args.get('citation'), False)
    if len(absolute_paths) < 1:
        return jsonify({'error': 'File/citation not found'}), 404
    data = []
    for absolute_path in absolute_paths:
        parts = absolute_path.split(os.sep)
        if len(parts) > 4:
            data.append({'directory': parts[len(parts)-3], 'subdirectory': parts[len(parts)-2]})
    return jsonify(data)

def find_abosulate_paths(file_path, only_first):
    absolute_paths = []
    for f in file_list:
        if file_path in f:
            absolute_paths.append(f)
            if only_first:
                break
    return absolute_paths

@app.route('/download')
def download_file():
    absolute_paths = find_abosulate_paths(request.args.get('file'), True)
    absolute_path = None
    if len(absolute_paths) > 0:
        absolute_path = absolute_paths[0]
    if absolute_path and os.path.exists(absolute_path):
        return send_file(absolute_path, as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404


@app.route('/')
def index():
    return render_template_string(template)


@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    user_query = data.get('query', '')
    message, citations = filesearch.run_assistant(client, assistant, user_query)
    print(f"Message:\n{message}\n\nCitations:\n{citations}")
    return jsonify({'response': message, 'citations': citations})
    

if __name__ == '__main__':
    app.run(debug=False,host='0.0.0.0',port=PORT)
