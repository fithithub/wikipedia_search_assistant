from flask import Flask, request, render_template
import os
from PIL import Image
import base64
from io import BytesIO
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if request.method == 'POST':
        audio_file = request.files['audio_data']
        if audio_file:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = os.path.join('recordings', f'audio_{timestamp}.webm')
            audio_file.save(filename)
            return 'File uploaded successfully'
    return 'Failed to upload'

###############################################################
# process audio file:

import os
from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

def transcribe_audio(audio_file_path):
    with open(audio_file_path, 'rb') as audio_file:
        transcription = client.audio.transcriptions.create(model = "whisper-1",
                                                           language="en", # surprisingly, I, a native spanish speaker, had my audios translated from english to spa 
                                                           file = audio_file)
    return transcription.text

def find_latest_modified_element(folder_path):
    # List all the entries in the given folder
    entries = os.listdir(folder_path)
    # Initialize variables to store the name and modification time of the latest file
    latest_file = None
    latest_mod_time = 0
    # Iterate over all entries
    for entry in entries:
        # Get the full path of the entry
        entry_path = os.path.join(folder_path, entry)
        # Get the modification time and compare it to the latest known
        mod_time = os.path.getmtime(entry_path)
        if mod_time > latest_mod_time:
            latest_mod_time = mod_time
            latest_file = entry
    return latest_file

def get_completion(prompt, model="gpt-3.5-turbo", tmptr = 0):
    messages = [{"role": "user", "content": prompt}]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=tmptr,
    )
    return response.choices[0].message.content

import requests

def get_wikipedia_url(search_term):
    endpoint = "https://en.wikipedia.org/w/api.php"
    
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": search_term
    }
    headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    response = requests.get(endpoint, params=params, headers = headers , verify=True)
    
    # if good
    if response.status_code == 200:
        data = response.json()
        
        # check if there are results
        search_results = data.get("query", {}).get("search", [])
        if search_results:
            title = search_results[0]["title"]
            wikipedia_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            return wikipedia_url
        else:
            return None # "No Wikipedia page found."
    else:
        return None # "Error in API request."


import requests
from pathlib import Path
import time
def download_image(image_url, output_dir):
    image_name = image_url.split('/')[-1].split('?')[0]  
    image_name = image_name.split('*')[-1]
    output_path = output_dir / image_name
    headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    response = requests.get(image_url, headers=headers , verify=True)
    response.raise_for_status()  
    with open(output_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
    return output_path

import requests
from bs4 import BeautifulSoup
 
def obtain_text_from_url(url,chars=4000):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
 
        response = requests.get(url, headers=headers, verify=True)
        response.raise_for_status()  # Lanza una excepción para errores HTTP
 
        soup = BeautifulSoup(response.text, 'html.parser')
        texto = soup.get_text()
        texto=texto[:chars]
 
        return texto
    except Exception as e:
        return f"Error: {e}"
    
def q_url(question, url):
    text_page = obtain_text_from_url(url,10000)
    prompt= f"""
        Given the following text extracted from a webpage:
        ///
        {text_page}
        ///
        Perform the following task:
        {question}
        Answer:
        """
    answer = get_completion(prompt, "gpt-4-turbo-preview", 0.1)
    return answer 

import os
import requests
import base64
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
 
 # Function to encode the image
def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

def get_response_v(PROMPT, IMAGE_PATH):
    encoded_image = encode_image(IMAGE_PATH)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
    }
 
    # Payload for the request
    payload = {
    "model": "gpt-4-vision-preview",
    "messages": [
        {
        "role": "user",
        "content": [
            {
            "type": "text",
            "text": PROMPT
            },
            {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{encoded_image}"
            }
            }
        ]
        }
    ],
    "temperature": 0,
    "max_tokens": 2000
    }
 
    # Send request
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.RequestException as e:
        raise SystemExit(f"Failed to make the request. Error: {e}")
 
    return response.json()['choices'][0]['message']['content']

# uses all previous functions to get the audio file, the image, the text from the wikipedia page
# and finally the description of the image and the text from the wikipedia page
# and also transcribes the result
def main(recording_path = "recordings"):

    recording = find_latest_modified_element(recording_path)
    transcription = transcribe_audio(recording_path + '\\' +recording)
    print("Transcription: ", transcription)

    prompt_entity = """Given a text, you must return the person/place/entity/... that the text is about.\
    Your answer will be just that entity, nothing else. If many are mentioned, return the most important/known one.
    If none is mentioned or you it is unknown to you, return 'No entity'.
    Text:
    """
    prompt_n_context = prompt_entity + transcription + "\nEntity:\n"
    search_term=get_completion(prompt_n_context, "gpt-4-turbo-preview", 0.1)
    print('Search term:', search_term)
    if search_term == "No entity":
        return None, None, None
    
    url = get_wikipedia_url(search_term)
    if url is None:
        return None, None, None
    else:
        # get the main image from the wikipedia page
        import requests
        from bs4 import BeautifulSoup
        headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        
        response = requests.get(url, headers=headers, verify=True)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            infobox_image = soup.find('table', class_='infobox').find('img')
            if infobox_image and infobox_image.has_attr('src'):
                image_url = infobox_image['src']
                print(f'URL img is: {image_url}')
            else:
                print('No main image found.')
        else:
            print(f'Error: {response.status_code}')
        if image_url[:2] == "//":
            image_url = "https:" + image_url.strip()

        from pathlib import Path
        # dir for saving imgs
        output_dir = Path('data_imgs')
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            image_path = str(download_image(image_url, output_dir))
            print(f'Image downloaded and stored in: {image_path}')
        except requests.HTTPError as e:
            print(f'Error {url}: {e}')
        except requests.exceptions.MissingSchema as e:
            print(f'URL invalid {url}: {e}')
        time.sleep(1)  

        # use wiki text to answer if required
        task_wiki_text = f"""If there is a question or order between the asterisks \
            and you can use the text provided (from public Wikipedia) to answer,
            you must answer using it.
            Otherwise, you must summarize the text.
            Answer in the same language as the possible order. 
            Begin with a phrase like: "With respect to the text in Wikipedia, ..." in whichever language you are answering.
            Whatever happens, you answer must be based on the text, do not use information you know if it is not in the text provided.
            You answer shall be about 2 or 3 sentences long.
            Possible order:
            ***
            {transcription}
            ***
            """
        # get the answer from the wikipedia page
        description_wikipedia=q_url(task_wiki_text, url)

        # finally we try the same from the pic
        task_wiki_img = f"""If there is a question or order between the asterisks \
            and you can use the image provided (from public Wikipedia) to answer,
            you must answer using it.
            Otherwise, you must describe the image.
            Answer in the same language as the possible order. 
            Begin with a phrase like: "With respect to the image in Wikipedia, ..." in whichever language you are answering.
            Whatever happens, you answer must be based on the image, do not use information you know if it is not in the image.
            You answer shall be about 2 or 3 sentences long.
            Possible order:
            ***
            {transcription}
            ***
            """
        imagen = mpimg.imread(image_path)
        response_wiki_img = get_response_v(task_wiki_img, image_path)

        # from pathlib import Path
        from openai import OpenAI
        client = OpenAI()

        # input_tts = "With respect to the text in Wikipedia: " + description_wikipedia + "\nWith respect to the main image: " + response_wiki_img
        input_tts =  description_wikipedia + "\n" + response_wiki_img
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        speech_file_path = Path("tts_audios") / f"speech_{timestamp}.mp3"

        with client.audio.speech.with_streaming_response.create(
        model= "tts-1", # "tts-1-hd",
        voice="onyx", # "alloy",
        input=input_tts,
        ) as response_tts:
            response_tts.stream_to_file(speech_file_path)

        return speech_file_path, image_path, input_tts

@app.route('/process_audio', methods=['POST'])
def handle_audio():
    
    speech_file_path, image_path, text= main()
    if speech_file_path is None and image_path is None and text is None:
        return {'status': 'error', 
                'message': 'No Wikipedia page found.',
                'image': None, 'audio': None}
    
    # IMAGE
    img = Image.open(image_path)
    img_io = BytesIO()
    img.convert('RGB').save(img_io, 'JPEG', quality=70)
    img_io.seek(0)
    img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')

    # AUDIO
    # load 'recordings/audio.webm'
    audio = open(speech_file_path, 'rb')
    audio_base64 = base64.b64encode(audio.read()).decode('utf-8')
    audio.close()

    # Send back the result or confirmation as needed
    return {'status': 'success', 'message': text,
            'image': 'data:image/jpeg;base64,' + img_base64,
            'audio': 'data:audio/webm;base64,' + audio_base64}


if __name__ == '__main__':
    app.run(debug=True)

# to run the app from the terminal:
# $ python flask_wiki_app.py