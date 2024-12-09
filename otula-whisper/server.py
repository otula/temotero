# python3 -m venv venv
# source venv/bin/activate
# pip install faster-whisper
# pip install PyPDF2
# pip install openai
# pip install flask
# pip install moviepy
# python3 server.py
#
# install instructions for other dependencies at: https://github.com/SYSTRAN/faster-whisper
# - cuBLAS for CUDA 12 and cuDNN 8 for CUDA 12
# if you get issues with unsupported types: https://github.com/SYSTRAN/faster-whisper/issues/42

import base64
import threading
import sqlite3
import uuid
import time
from faster_whisper import WhisperModel
import io
from pathlib import Path
from openai import AzureOpenAI
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
import re
from flask import Flask, request, redirect, send_file, jsonify, Response
import concurrent.futures
import svnrevisionchecker
from moviepy.editor import VideoFileClip, AudioFileClip
from datetime import datetime

app = Flask(__name__)

PORT = 10000
USERNAME = 'YOUR_USERNAME'
PASSWORD = 'YOUR_PASSWORD'
UPLOAD_FILE_DIRECTORY = "./files/"
STATUS_QUEUED = 'not_started'
STATUS_GENERATING = 'generating'
STATUS_GENERATED = 'generated'
STATUS_OPTIMIZING = 'optimizing'
STATUS_GENERATION_FAILED = 'generation_failed'
STATUS_OPTIMIZATION_FAILED = 'optimization_failed'
STATUS_COMPLETED = 'completed'
MODEL_SIZE = "medium"
STATUS_STORAGE_FILE_PATH = "status_storage.db"
SUBTITLE_OPTIMIZER_POLL_INTERVAL = 30 # how often the optimizer check for new jobs, in seconds
STATUS_PAGE_REFRESH_INTERVAL = 30000 # how often the html status page is refreshed, in milliseconds
MAX_SUBTITLE_LINES_PER_ITERATION = 80
SVN_REVISION = svnrevisionchecker.get_svn_revision()
OPTIMIZER_RATE_LIMIT = 65 # how long to wait while between subtitle optimization spawns, in seconds
OPTIMIZER_MAX_CONCURRENT_TASKS = 10 # maximum bumber of concurrent tasks
OPTIMIZER_MAX_RETRY = 3 # how many times to retry individual failed call
TIMESTAMP_NOT_SET = -1
SRT_SEQUENCE_NUMBER_PATTERN = re.compile(r'^\d+$')
SRT_TIMESTAMP_PATTERN = re.compile(r'^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$') # for validating that individual timestamp string is OK
SRT_LAST_TIMESTAMP_FIND_PATTERN = re.compile(r'^\s*\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}\s*$', re.MULTILINE) # for searching mathinc timestamp strings
SRT_TIMESTAMP_FORMAT = "%H:%M:%S,%f"
SRT_LAST_TIMESTAMP_MAX_INTERVAL = 5 # how much can the final timestamps differ in seconds

#
#
#
class SubtitleGenerator:
    def __init__(self, model):
        # Run on GPU with FP16
        #self.model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")

        # or run on GPU with INT8
        # self.model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="int8")
        # or run on CPU with INT8
        self.model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    def generate_subtitles(self, input_file_path, lang):
        start_time = time.time()
        print("Starting to process...")

        subtitles = ''

        try:
            decoding_options = {
                "no_speech_threshold": 0.6,
                "beam_size": 5,
                "vad_filter": True 
                #"temperature": [0.0]
            }

            if len(lang) > 0:
                decoding_options["language"] = lang
                segments, info = self.model.transcribe(input_file_path, **decoding_options)
                print(f"Language given by the user: {lang}")
            else:
                segments, info = self.model.transcribe(input_file_path, **decoding_options)
            print("Detected language '%s' with probability %f" % (info.language, info.language_probability))

            # Assuming 'segments' is a list of objects with 'start', 'end', and 'text' attributes
            index = 1
            with io.StringIO() as output:
                index = 1
                for segment in segments:
                    # Convert the start and end times from seconds to SRT time format
                    start_hours, start_minutes = divmod(int(segment.start), 3600)
                    start_minutes, start_seconds = divmod(start_minutes, 60)
                    start_milliseconds = int((segment.start - int(segment.start)) * 1000)

                    end_hours, end_minutes = divmod(int(segment.end), 3600)
                    end_minutes, end_seconds = divmod(end_minutes, 60)
                    end_milliseconds = int((segment.end - int(segment.end)) * 1000)

                    # Write the subtitle index
                    output.write(f"{index}\n")
                    # Write the formatted time range
                    output.write(f"{start_hours:02}:{start_minutes:02}:{start_seconds:02},{start_milliseconds:03} --> {end_hours:02}:{end_minutes:02}:{end_seconds:02},{end_milliseconds:03}\n")
                    # Write the subtitle text
                    output.write(f"{segment.text}\n\n")
                    index += 1
                subtitles = output.getvalue()

            end_time = time.time()
            print(f"Subtitle generation finished in {end_time - start_time} seconds.")
        except Exception as e:
            print(f"Exception during generation: {e}")

        return subtitles


#
#
#
class FileStatus:
    def __init__(self, uuid, filename, video_filepath, meta_filepath, status, srt, srt_optimized, language, timestamp_uploaded, timestamp_generation_started, timestamp_generation_completed, timestamp_optimization_started, timestamp_optimization_completed, video_duration):
        self.uuid = uuid
        self.filename = filename
        self.video_filepath = video_filepath
        self.meta_filepath = meta_filepath
        self.status = status
        self.srt = srt  # the generated subtitles
        self.srt_optimized = srt_optimized  # the optimized subtitles
        self.language = language
        self.timestamp_uploaded = timestamp_uploaded  # Unix timestamp of when the file was uploaded
        self.timestamp_generation_started = timestamp_generation_started  # Unix timestamp when generation started
        self.timestamp_generation_completed = timestamp_generation_completed  # Unix timestamp when generation completed
        self.timestamp_optimization_started = timestamp_optimization_started  # Unix timestamp when optimization started
        self.timestamp_optimization_completed = timestamp_optimization_completed  # Unix timestamp when optimization completed
        self.video_duration = video_duration  # Duration of the video in seconds


#
# ChatGPT generated SQLite handler for the status storage, if it gives issues, use the in-memory version above
#
class StatusStorage:
    def __init__(self, db_name=STATUS_STORAGE_FILE_PATH):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.lock = threading.Lock()
        self._create_table()

    def _create_table(self):
        with self.conn:
            self.conn.execute("DROP TABLE IF EXISTS file_statuses")
            self.conn.execute("CREATE TABLE IF NOT EXISTS file_statuses (uuid TEXT PRIMARY KEY, filename TEXT, video_filepath TEXT, meta_filepath TEXT, status TEXT, srt TEXT, srt_optimized TEXT, language TEXT, timestamp_uploaded INTEGER, timestamp_generation_started INTEGER, timestamp_generation_completed INTEGER, timestamp_optimization_started INTEGER, timestamp_optimization_completed INTEGER, video_duration INTEGER)")

    #
    # Retrieve the next file (oldest timestamp_uploaded first) which has the given status.
    #
    def next_file(self, status):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM file_statuses WHERE status = ? ORDER BY timestamp_uploaded ASC LIMIT 1", (status,))
            row = cur.fetchone()
            if row:
                return FileStatus(*row)
        return None

    def get_status(self, uuid):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM file_statuses WHERE uuid = ?", (uuid,))
            row = cur.fetchone()
            if row:
                return FileStatus(*row)
        return None

    def set_status(self, status):
        print("settings: " + status.language)
        with self.lock:
            with self.conn:
                self.conn.execute("INSERT OR REPLACE INTO file_statuses (uuid, filename, video_filepath, meta_filepath, status, srt, srt_optimized, language, timestamp_uploaded, timestamp_generation_started, timestamp_generation_completed, timestamp_optimization_started, timestamp_optimization_completed, video_duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (status.uuid, status.filename, status.video_filepath, status.meta_filepath, status.status, status.srt, status.srt_optimized, status.language, status.timestamp_uploaded, status.timestamp_generation_started, status.timestamp_generation_completed, status.timestamp_optimization_started, status.timestamp_optimization_completed, status.video_duration))

    #
    # Convenience method for updating status information for on file status object
    #
    # This will also update timestamp if applicaple new_status is given, as:
    #   STATUS_GENERATING                            => timestamp_generation_started
    #   STATUS_GENERATED, STATUS_GENERATION_FAILED   => timestamp_generation_completed
    #   STATUS_OPTIMIZING                            => timestamp_optimization_started
    #   STATUS_COMPLETED, STATUS_OPTIMIZATION_FAILED => timestamp_optimization_completed
    #
    def update_status(self, uuid, new_status):
        with self.lock:
            with self.conn:
                if new_status == STATUS_GENERATING:
                    self.conn.execute("UPDATE file_statuses SET status = ?, timestamp_generation_started = ? WHERE uuid = ?", (new_status, int(time.time()), uuid))
                elif new_status == STATUS_GENERATED or new_status == STATUS_GENERATION_FAILED:
                    self.conn.execute("UPDATE file_statuses SET status = ?, timestamp_generation_completed = ? WHERE uuid = ?", (new_status, int(time.time()), uuid))
                elif new_status == STATUS_OPTIMIZING:
                    self.conn.execute("UPDATE file_statuses SET status = ?, timestamp_optimization_started = ? WHERE uuid = ?", (new_status, int(time.time()), uuid))
                elif new_status == STATUS_COMPLETED or new_status == STATUS_OPTIMIZATION_FAILED:
                    self.conn.execute("UPDATE file_statuses SET status = ?, timestamp_optimization_completed = ? WHERE uuid = ?", (new_status, int(time.time()), uuid))
                else:
                    self.conn.execute("UPDATE file_statuses SET status = ? WHERE uuid = ?", (new_status, uuid))

    def set_subtitles(self, uuid, srt):
        with self.lock:
            with self.conn:
                self.conn.execute("UPDATE file_statuses SET srt = ? WHERE uuid = ?", (srt, uuid))

    def set_optimized_subtitles(self, uuid, srt_optimized):
        with self.lock:
            with self.conn:
                self.conn.execute("UPDATE file_statuses SET srt_optimized = ? WHERE uuid = ?", (srt_optimized, uuid))

    def set_meta(self, uuid, meta_filepath):
        with self.lock:
            with self.conn:
                self.conn.execute("UPDATE file_statuses SET meta_filepath = ? WHERE uuid = ?", (meta_filepath, uuid))

#
#
#
class VideoConverter:
    def __init__(self) -> None:
        pass

    def calculate_duration(self, file_path):
        duration = -1
        if file_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.flv')):
            duration = self.calculate_video_duration(file_path)
        elif file_path.lower().endswith(('.mp3', '.wav', '.aac', '.flac', '.ogg')):
            duration = self.calculate_audio_duration(file_path)
        else:
            print(f"Unsupported file format: {file_path}")
        
        return duration
    
    def calculate_video_duration(self, file_path):
        duration = -1
        try:
            clip = VideoFileClip(file_path)
            duration = clip.duration  # duration in seconds
            clip.close()
        except Exception as e:
            print(f"Exception during video duration calculation: {e}")
            duration = self.calculate_audio_duration(file_path) # sometimes we get video files which only contain audio, let's try to calculate the audio only
        return duration
    
    def calculate_audio_duration(self, file_path):
        duration = -1
        try:
            clip = AudioFileClip(file_path)
            duration = clip.duration  # duration in seconds
            clip.close()
        except Exception as e:
            print(f"Exception during audio duration calculation: {e}")
        return duration

#
#
#
class VideoProcessor:
    def __init__(self, status_storage):
        self.thread = None
        self.lock = threading.Lock()
        self.status_storage = status_storage

    def start_thread(self):
        with self.lock:
            if self.thread is not None:
                print("Already processing, not starting a new thread...")
                return
            self.thread = threading.Thread(target=self.process_video)
            print("Starting a new thread...")
            self.thread.start()

    def process_video(self):
        print("Creating subtitle generator...")
        generator = SubtitleGenerator(MODEL_SIZE)
        fs = self.status_storage.next_file(STATUS_QUEUED)
        while fs is not None:
            print(f"Processing file: {fs.uuid} / {fs.video_filepath}")
            self.status_storage.update_status(fs.uuid, STATUS_GENERATING)
            srt = generator.generate_subtitles(fs.video_filepath, fs.language)
            if srt:
                self.status_storage.set_subtitles(fs.uuid, srt)
                self.status_storage.update_status(fs.uuid, STATUS_GENERATED)
            else:
                self.status_storage.update_status(fs.uuid, STATUS_GENERATION_FAILED)
            Path(fs.video_filepath).unlink()
            fs = self.status_storage.next_file(STATUS_QUEUED)
        with self.lock:
            self.thread = None
        print("Processing finished for all active video files.")

#
#
#
#
class SubtitleOptimizer:
    def __init__(self, status_storage):
        self.thread = None
        self.lock = threading.Lock()
        self.model_engine = "gpt-4o-mini"
        self.azure_api_key = "YOUR_AZURE_API_KEY"
        self.azure_api_version = "2024-02-15-preview"
        self.azure_endpoint = "YOUR_AZURE_ENDPOINT_URI"
        self.ai_temperature = 0.0
        self.status_storage = status_storage

    def start_thread(self):
        with self.lock:
            if self.thread is not None:
                print("Already optimizing, not starting a new thread...")
                return
            self.thread = threading.Thread(target=self.optimize_subtitles)
            print("Starting a new thread...")
            self.thread.start()

    def optimize_subtitles(self):
        client = AzureOpenAI(
            api_key=self.azure_api_key,
            api_version=self.azure_api_version,
            azure_endpoint=self.azure_endpoint
        )

        while True:
            fs = self.status_storage.next_file(STATUS_GENERATED)
            if fs is None:
                print(f"No subtitles to optimize. Sleeping for {SUBTITLE_OPTIMIZER_POLL_INTERVAL} seconds...")
                time.sleep(SUBTITLE_OPTIMIZER_POLL_INTERVAL)
                continue

            if fs.meta_filepath is None or len(fs.meta_filepath) < 1:
                print(f"Skipped file without metadata: {fs.uuid}")
                self.status_storage.update_status(fs.uuid, STATUS_COMPLETED)
                continue

            print(f"Processing file: {fs.uuid} / {fs.meta_filepath}")
            self.status_storage.update_status(fs.uuid, STATUS_OPTIMIZING)
            meta = self.extract_text_from_pdf(fs.meta_filepath)
            if not meta:
                o_status = STATUS_OPTIMIZATION_FAILED
                print("Subtitle optimization failed.")
            else:
                try:
                    sprompt = self.create_system_prompt(meta)

                    o_status = STATUS_COMPLETED
                    splitted_srt = self.split_subtitles(fs.srt)

                    print(f"Spawning {len(splitted_srt)} optimizers for generated subtitles.")
                    start_time = time.time()

                    processed_blocks = [None] * len(splitted_srt)

                    # Loop through the splitted_srt in chunks of OPTIMIZER_MAX_CONCURRENT_TASKS
                    for i in range(0, len(splitted_srt), OPTIMIZER_MAX_CONCURRENT_TASKS):
                        # Create a batch of tasks
                        batch = splitted_srt[i:i + OPTIMIZER_MAX_CONCURRENT_TASKS]
                        futures = {}

                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            # Submit tasks for the current batch
                            futures = {
                                executor.submit(self.run_optimization, client, sprompt, block): idx 
                                for idx, block in enumerate(batch, start=i)
                            }

                            try:
                                for future in concurrent.futures.as_completed(futures):
                                    idx = futures[future]
                                    try:
                                        r = future.result()
                                        r = self.cleanup_srt(r)
                                        if r is None or not self.validate_last_timestamp(splitted_srt[idx], r): # check that we get results and that the last timestamp is approximately correct
                                            print("Optimization failed: last timestamp(s) does not match.")
                                            o_status = STATUS_OPTIMIZATION_FAILED
                                        processed_blocks[idx] = r # let's assign so that we can see the end result, even if it is incorrect
                                    except Exception as e:
                                        print(f"Exception during optimization: {e}")
                                        o_status = STATUS_OPTIMIZATION_FAILED
                                        for f in futures.keys():  # something has gone seriously wrong, we should cancel at this point
                                            if not f.done():
                                                f.cancel()
                                        break  # Optionally break out of the loop to stop processing further
                            except Exception as e:
                                print(f"Critical error during optimization: {e}")
                                o_status = STATUS_OPTIMIZATION_FAILED

                        # If there are more tasks to process, wait before starting the next batch
                        if o_status == STATUS_COMPLETED and i + OPTIMIZER_MAX_CONCURRENT_TASKS < len(splitted_srt):
                            print(f"Waiting for {OPTIMIZER_RATE_LIMIT} seconds before processing the next batch...")
                            time.sleep(OPTIMIZER_RATE_LIMIT)

                    optimized_srt = '\n\n'.join(processed_blocks) # let's join so that we can see the end reseult, even if it is incorrect

                    if o_status == STATUS_COMPLETED:
                        if not self.validate_srt(optimized_srt):
                            print("Subtitle validation failed.")
                            o_status = STATUS_OPTIMIZATION_FAILED

                    self.status_storage.set_optimized_subtitles(fs.uuid, optimized_srt) # set the subtitles even if incorrect so that we can see the result

                except Exception as e:
                    print(f"Failed to optimize subtitles: {str(e)}")
                    o_status = STATUS_OPTIMIZATION_FAILED

                print(f"Subtitle optimization finished in {time.time() - start_time} seconds.")

            self.status_storage.update_status(fs.uuid, o_status)

            Path(fs.meta_filepath).unlink()

    def cleanup_srt(self, srt):
        valid_lines = []
        lines = srt.splitlines(keepends=True)
        for l in lines:
            if '```' not in l: # GPT4o sometimes produce quoted lines, ignore these
                valid_lines.append(l.strip()) # remove extra whitespaces if any
        return '\n'.join(valid_lines)


    def validate_last_timestamp(self, srt, srt_optimized):
        srt_start = self.get_last_timestamp(srt)
        srt_o_start = self.get_last_timestamp(srt_optimized)
        if srt_start == None or srt_o_start == None:
            return False
        else:
            return (abs((srt_start - srt_o_start).total_seconds()) <= SRT_LAST_TIMESTAMP_MAX_INTERVAL)

    def get_last_timestamp(self, srt_content):
        timestamps = SRT_LAST_TIMESTAMP_FIND_PATTERN.findall(srt_content)
        
        if not timestamps or len(timestamps) < 1:
            return None  # No valid timestamp found
        
        # The last entry is the last timestamp line
        last_timestamp_line = timestamps[-1]
        # Split the last timestamp line to get the start timestamp
        return datetime.strptime(last_timestamp_line.split(' --> ')[0], SRT_TIMESTAMP_FORMAT)

    def validate_srt(self, srt_content):
        # Split content by double newlines to separate each subtitle block
        entries = srt_content.strip().split('\n\n')

        for entry in entries:
            lines = entry.split('\n')
            
            # Check there are at least 3 lines (sequence number, timestamp, and text)
            if len(lines) < 3:
                return False
            
            # Validate sequence number
            if not SRT_SEQUENCE_NUMBER_PATTERN.match(lines[0]):
                return False
            
            # Validate timestamp
            if not SRT_TIMESTAMP_PATTERN.match(lines[1]):
                return False
            
            # Validate that there is text in the remaining lines
            if not any(lines[2:]):
                return False

        # If all checks passed
        return True

    def split_subtitles(self, subtitles):
        # Split the content by subtitle blocks
        subtitle_blocks = subtitles.strip().split('\n\n')
        
        # Initialize variables for the output and temporary storage
        splitted_sub = []
        temp_block = []
        
        for block in subtitle_blocks:
            temp_block.append(block)
            
            if len(temp_block) == MAX_SUBTITLE_LINES_PER_ITERATION:
                splitted_sub.append('\n\n'.join(temp_block))
                temp_block = []
        
        # Add any remaining blocks
        if temp_block:
            splitted_sub.append('\n\n'.join(temp_block))
        
        return splitted_sub


    def run_optimization(self, client, system_prompt, subtitles):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": subtitles}
        ]

        for attempt in range(OPTIMIZER_MAX_RETRY):
            try:
                response = client.chat.completions.create(
                    model=self.model_engine,
                    messages=messages,
                    temperature=self.ai_temperature
                )
                choice = response.choices[0]
                if choice.finish_reason == "stop":
                    return choice.message.content
                else:
                    print(f"Call finished with invalid reason: {choice.finish_reason}")
                    return None
            except Exception as e:
                error_code = getattr(e, 'status_code', None)
                if error_code == 429:
                    print(f"Rate limit exceeded. Retrying in {OPTIMIZER_RATE_LIMIT} seconds...")
                    time.sleep(OPTIMIZER_RATE_LIMIT)
                    continue  # Retry the request
                else:
                    print(f"An unexpected error occurred: {str(e)}")
                    return None
        
    
    def create_system_prompt(self, meta):
        return f"Your task is to correct grammar and terminology errors in a subtitle files given by the user. You must process each subtitle cue individually and process every subtitle cue. Do NOT modify subtitle cue numbering, timestamps, cue timecodes or timing. Answer ONLY by printing the corrected subtitles in plain text, do not add quotes in the response. Do not add extra whitespaces after sentences. The result must have the same number of cues as the original subtitles. Use the following textual material when correcting terms and names in subtitle cues: {meta}"

    def extract_text_from_pdf(self, pdf_path):
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + " "  # Space added to avoid merging words
            return " ".join(text.split())  # Remove excessive whitespace
        except PdfReadError as e:
            print(f"Error reading PDF file: {e}")
            return ""
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return ""


status_storage = StatusStorage()
optimizer = SubtitleOptimizer(status_storage)
processor = VideoProcessor(status_storage)
converter = VideoConverter()


def calculate_duration(from_timestamp, to_timestamp):
    if from_timestamp == None or from_timestamp <= 0 or to_timestamp == None or to_timestamp <= 0:
        return "N/A"
    else:
        return to_timestamp - from_timestamp


def check_auth(auth_header):
    if not auth_header:
        return False
    encoded_creds = 'Basic ' + base64.b64encode(bytes(f"{USERNAME}:{PASSWORD}", 'utf-8')).decode('utf-8')
    return auth_header == encoded_creds


@app.route('/status')
def status():
    auth_header = request.headers.get('Authorization')
    if not check_auth(auth_header):
        return Response('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Test"'})
    uuid_query = request.args.get('uuid')
    if not uuid_query:
        return Response('Bad Request', 400)
    status = status_storage.get_status(uuid_query)
    if not status:
        return Response(f'Not found: {uuid_query}', 404)
    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>File status</title>
    </head>
    <body>
        <h1>Subtitles</h1>
        <p>Status of file: <b>{status.status}</b> of {STATUS_QUEUED}/{STATUS_GENERATING}/{STATUS_GENERATED}/{STATUS_OPTIMIZING}/{STATUS_COMPLETED}</p>
        <textarea id="textSubtitlesRaw" rows="10" cols="50">{status.srt}</textarea><br>
        <textarea id="textSubtitles" rows="10" cols="50">{status.srt_optimized}</textarea><br>
        <button onclick="downloadTextAreaContent()">Download as File</button>
        <br>Created with generator revision: {SVN_REVISION}<br>
        <br>Video duration: {status.video_duration} seconds. Subtitles generated in {calculate_duration(status.timestamp_generation_started, status.timestamp_generation_completed)} seconds, optimized in {calculate_duration(status.timestamp_optimization_started, status.timestamp_optimization_completed)} seconds, total: {calculate_duration(status.timestamp_generation_started, status.timestamp_optimization_completed)} seconds (since upload: {calculate_duration(status.timestamp_uploaded, status.timestamp_optimization_completed)} seconds).<br>

        <script>
            function downloadTextAreaContent() {{
                var text = document.getElementById("textSubtitles").value;
                if(!text){{
                    text = document.getElementById("textSubtitlesRaw").value;
                    if(!text){{
                        return;
                    }}
                }}
                var filename = '{status.filename}.srt';
                var blob = new Blob([text], {{ type: "text/plain" }});
                var link = document.createElement("a");
                link.download = filename;
                link.href = window.URL.createObjectURL(blob);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }}

            function refreshPage() {{
                location.reload()
            }}

            window.onload = function() {{
                status = "{status.status}";
                console.log(status);
                if(status === "{STATUS_QUEUED}"  || status === "{STATUS_GENERATING}" || status === "{STATUS_OPTIMIZING}" || status === "{STATUS_GENERATED}" ){{
                    setTimeout(refreshPage, {STATUS_PAGE_REFRESH_INTERVAL});
                }}
            }};
        </script>
         <a href="./">Next file</a>
    </body>
    </html>
    """


@app.route('/uploadMeta', methods=['GET', 'POST'])
def meta():
    auth_header = request.headers.get('Authorization')
    if not check_auth(auth_header):
        return Response('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Test"'})
    if request.method == 'GET':
        uuid_query = request.args.get('uuid')
        if not uuid_query:
            return Response('Bad Request', 400)
        return '''
            <html>
            <head>
                <title>Upload a PDF File</title>
            </head>
            <body>
                <h1>Upload a PDF File</h1>
                <form method="POST" enctype="multipart/form-data">
                    <input type="file" name="file" accept=".pdf">
                    <input type="hidden" name="uuid" value="{}">
                    <input type="submit" value="Upload">
                </form>
                <h2>Check File Status</h2>
                <form action="/status">
                    <input type="text" name="uuid" placeholder="Enter file UUID" value="{}">
                    <input type="submit" value="Skip and Check Status">
                </form>
            </body>
            </html>
        '''.format(uuid_query, uuid_query)
    elif request.method == 'POST':
        uuid_item = request.form.get('uuid')
        if 'file' not in request.files or not uuid_item:
            return Response('Bad Request', 400)
        
        fs = status_storage.get_status(uuid_item)
        if fs == None:
            return Response('Bad Request: Invalid UUID.', 400)
        if fs.meta_filepath: # for now, let's not allow uploading a new file
            return Response('Bad Request: Meta file already in given.', 400)

        file = request.files['file']
        if file.filename == '':
            return Response('Bad Request: Filename is missing.', 400)
        file_path = UPLOAD_FILE_DIRECTORY + uuid_item + "_" + re.sub(r'[^a-zA-Z0-9_.-]', '', file.filename) + ".meta.pdf"
        file.save(file_path)
        status_storage.set_meta(uuid_item, file_path)
        optimizer.start_thread()
        return redirect(f'./status?uuid={uuid_item}')


@app.route('/uploadVideo', methods=['POST'])
def upload_video():
    auth_header = request.headers.get('Authorization')
    if not check_auth(auth_header):
        return Response('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Test"'})
    if 'file' not in request.files:
        return Response('Bad Request', 400)
    file = request.files['file']
    if file.filename == '':
        return Response('Bad Request', 400)
    
    # Get the selected language from the form
    language = request.form.get('language', 'auto')  # Default to auto if not selected
    if language == "auto":
        language = ""
    
    file_uuid = str(uuid.uuid4())
    file_path = UPLOAD_FILE_DIRECTORY + file_uuid + "_" + re.sub(r'[^a-zA-Z0-9_.-]', '', file.filename)
    file.save(file_path)
    status_storage.set_status(FileStatus(file_uuid, file.filename, file_path, '', STATUS_QUEUED, '', '', language, int(time.time()), TIMESTAMP_NOT_SET, TIMESTAMP_NOT_SET, TIMESTAMP_NOT_SET, TIMESTAMP_NOT_SET, converter.calculate_duration(file_path)))
    processor.start_thread()
    return redirect(f'./uploadMeta?uuid={file_uuid}')


@app.route('/')
def index():
    auth_header = request.headers.get('Authorization')
    if not check_auth(auth_header):
        return Response('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Test"'})
    return '''
        <html>
        <head>
            <title>Upload a Video File</title>
        </head>
        <body>
            <h1>Upload a Video File</h1>
            <br>Supported file formats: m4a, mp3, webm, mp4, mpga, wav, mpeg<br>
            <form method="POST" enctype="multipart/form-data" action="./uploadVideo">
                <input type="file" name="file" accept=".m4a,.mp3,.webm,.mp4,.mpga,.wav,.mpeg,.aac"><br><br>
                <label for="language">Select Language:</label>
                <select name="language" id="language">
                    <option value="auto" selected>Auto-detect</option>
                    <option value="af">Afrikaans</option>
                    <option value="sq">Albanian</option>
                    <option value="am">Amharic</option>
                    <option value="ar">Arabic</option>
                    <option value="hy">Armenian</option>
                    <option value="as">Assamese</option>
                    <option value="az">Azerbaijani</option>
                    <option value="eu">Basque</option>
                    <option value="ba">Bashkir</option>
                    <option value="be">Belarusian</option>
                    <option value="bn">Bengali</option>
                    <option value="bs">Bosnian</option>
                    <option value="br">Breton</option>
                    <option value="bg">Bulgarian</option>
                    <option value="my">Burmese</option>
                    <option value="yue">Cantonese</option>
                    <option value="ca">Catalan</option>
                    <option value="zh">Chinese</option>
                    <option value="hr">Croatian</option>
                    <option value="cs">Czech</option>
                    <option value="da">Danish</option>
                    <option value="nl">Dutch</option>
                    <option value="en">English</option>
                    <option value="et">Estonian</option>
                    <option value="fa">Persian</option>
                    <option value="fo">Faroese</option>
                    <option value="fi">Finnish</option>
                    <option value="fr">French</option>
                    <option value="gl">Galician</option>
                    <option value="ka">Georgian</option>
                    <option value="de">German</option>
                    <option value="gu">Gujarati</option>
                    <option value="ht">Haitian Creole</option>
                    <option value="ha">Hausa</option>
                    <option value="haw">Hawaiian</option>
                    <option value="he">Hebrew</option>
                    <option value="hi">Hindi</option>
                    <option value="hu">Hungarian</option>
                    <option value="is">Icelandic</option>
                    <option value="id">Indonesian</option>
                    <option value="it">Italian</option>
                    <option value="ja">Japanese</option>
                    <option value="jw">Javanese</option>
                    <option value="kn">Kannada</option>
                    <option value="kk">Kazakh</option>
                    <option value="km">Khmer</option>
                    <option value="ko">Korean</option>
                    <option value="ku">Kurdish</option>
                    <option value="lo">Lao</option>
                    <option value="la">Latin</option>
                    <option value="lv">Latvian</option>
                    <option value="lt">Lithuanian</option>
                    <option value="lb">Luxembourgish</option>
                    <option value="mg">Malagasy</option>
                    <option value="ms">Malay</option>
                    <option value="ml">Malayalam</option>
                    <option value="mt">Maltese</option>
                    <option value="mi">Maori</option>
                    <option value="mr">Marathi</option>
                    <option value="mn">Mongolian</option>
                    <option value="ne">Nepali</option>
                    <option value="no">Norwegian</option>
                    <option value="nn">Norwegian Nynorsk</option>
                    <option value="oc">Occitan</option>
                    <option value="pa">Punjabi</option>
                    <option value="pl">Polish</option>
                    <option value="pt">Portuguese</option>
                    <option value="ro">Romanian</option>
                    <option value="ru">Russian</option>
                    <option value="sm">Samoan</option>
                    <option value="gd">Scottish Gaelic</option>
                    <option value="sr">Serbian</option>
                    <option value="st">Sesotho</option>
                    <option value="sn">Shona</option>
                    <option value="sd">Sindhi</option>
                    <option value="si">Sinhala</option>
                    <option value="sk">Slovak</option>
                    <option value="sl">Slovenian</option>
                    <option value="so">Somali</option>
                    <option value="es">Spanish</option>
                    <option value="su">Sundanese</option>
                    <option value="sw">Swahili</option>
                    <option value="sv">Swedish</option>
                    <option value="tl">Tagalog</option>
                    <option value="tg">Tajik</option>
                    <option value="ta">Tamil</option>
                    <option value="tt">Tatar</option>
                    <option value="te">Telugu</option>
                    <option value="th">Thai</option>
                    <option value="bo">Tibetan</option>
                    <option value="tr">Turkish</option>
                    <option value="tk">Turkmen</option>
                    <option value="uk">Ukrainian</option>
                    <option value="ur">Urdu</option>
                    <option value="uz">Uzbek</option>
                    <option value="vi">Vietnamese</option>
                    <option value="cy">Welsh</option>
                    <option value="xh">Xhosa</option>
                    <option value="yi">Yiddish</option>
                    <option value="yo">Yoruba</option>
                    <option value="zu">Zulu</option>
                </select>

                <input type="submit" value="Upload">
            </form>
            <h2>Check File Status</h2>
            <form action="./status">
                <input type="text" name="uuid" placeholder="Enter file UUID">
                <input type="submit" value="Check Status">
            </form>
        </body>
        </html>
    '''



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
