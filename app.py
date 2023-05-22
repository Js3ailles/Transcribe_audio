import os
import requests
from moviepy.editor import AudioFileClip
from tempfile import TemporaryDirectory, NamedTemporaryFile
import streamlit as st  
import shutil
from summarizer import *


import os
import requests
from moviepy.editor import AudioFileClip
import time
import shutil
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_fixed
import concurrent.futures


def split_audio(file_path, output_dir, part_duration):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    audio = AudioFileClip(file_path)
    duration = audio.duration
    parts = int(duration // part_duration)

    for i in range(parts + 1):  # Add 1 to include the last part
        start_time = i * part_duration
        end_time = (i + 1) * part_duration if i < parts else duration  # Use the duration for the last part's end_time
        split_audio = audio.subclip(start_time, end_time)
        split_audio.write_audiofile(os.path.join(output_dir, f"part_{i + 1:03d}.mp3"), codec='mp3')

    print(f"Audio file successfully split into {parts + 1} parts and saved in '{output_dir}'.")  # Update the printed message
    return parts + 1  # Return the total number of parts



@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def transcribe_single_file(filename, directory, headers):
    file_path = os.path.join(directory, filename)
    with open(file_path, 'rb') as file:
        files = {
            'audio': (filename, file, 'audio/mpeg'),
            'diarization_max_speakers': (None, '2'),
            'language': (None, 'french'),
            'language_behaviour': (None, 'manual'),
            'output_format': (None, 'txt'),
            'target_translation_language': (None, 'english'),
        }

        response = requests.post('https://api.gladia.io/audio/text/audio-transcription/', headers=headers, files=files)

        if response.status_code != 200:
            raise Exception(f"Request for {filename} failed with status code {response.status_code}: {response.text}")

    return filename, response



def transcribe_audio_files(directory, max_workers=5):
    responses = {}
    headers = {
        'accept': 'application/json',
        'x-gladia-key': st.secrets["GLADIA_KEY"],
    }

    sorted_files = sorted(os.listdir(directory))

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(transcribe_single_file, filename, directory, headers): filename for filename in sorted_files if filename.endswith(".mp3")}
        for future in concurrent.futures.as_completed(futures):
            filename = futures[future]
            try:
                response = future.result()
                responses[filename] = response
            except Exception as e:
                print(f"Failed to transcribe {filename}: {e}")

    return [responses[filename] for filename in sorted_files if filename.endswith(".mp3")]


def transcribe_audio(input_file_path, segment_duration, file_type, update_callback=None):
    predicted = ''
    temp_dir = Path("temp/splitted")
    temp_dir.mkdir(parents=True, exist_ok=True)

    if file_type == "mp4":
        video = AudioFileClip(input_file_path)
        input_file_path = input_file_path.replace(".mp4", ".mp3")
        video.audio.write_audiofile(input_file_path)

    num_parts = split_audio(input_file_path, temp_dir, segment_duration)
    resp = transcribe_audio_files(temp_dir)
    predictions = []

    with NamedTemporaryFile(delete=False, suffix=".txt") as tmp_prediction_file:
        for idx, (filename, response) in enumerate(resp, start=1):
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'prediction' in data:
                        prediction = data['prediction']
                        predictions.append(prediction)
                        predicted += f'\n\n{prediction}'

                        if update_callback:
                            update_callback(predicted)

                        tmp_prediction_file.write((prediction + f'\n\n').encode('utf-8'))
                    else:
                        print(f"Key 'prediction' not found in response from {response.url}")
                except JSONDecodeError:
                    print(f"Failed to parse JSON response for {filename}: {response.text}")
            else:
                print(f"Request for {filename} failed with status code {response.status_code}: {response.text}")

    shutil.rmtree(temp_dir)

    print("Predictions have been saved.")
    return predicted, tmp_prediction_file.name






st.sidebar.title("Navigation")

# Add the features that your application provides
features = [ "PDF summarizer","Audio Transcription"]
choice = st.sidebar.radio("Go to", features)


if choice == "Audio Transcription":
    st.title("Audio Transcription App")

    # Introduction
    st.markdown(
        """
        ## Introduction

        Bienvenue sur l'application de transcription audio ! Cette application permet de convertir automatiquement des fichiers audio en texte en utilisant une technologie de reconnaissance vocale avancée.
        """
    )

    # Comment utiliser l'application
    st.markdown(
        """
        ## Comment utiliser l'application

        1. Utilisez le bouton "Upload one or multiple audio files" pour télécharger un ou plusieurs fichiers audio de votre choix.
        2. Sélectionnez un fichier audio dans le menu déroulant situé dans la barre latérale gauche pour afficher la transcription.
        3. Cliquez sur le bouton "Transcribe" pour lancer le processus de transcription.
        4. Attendez que la transcription soit terminée et visualisez-la dans la zone de texte.
        5. Téléchargez le fichier de transcription en cliquant sur le bouton "Download transcription file".
        """
    )

    # Formats de fichiers pris en charge
    st.markdown(
        """
        ## Formats de fichiers pris en charge

        Les formats de fichiers audio pris en charge sont les suivants :
    
        - MP3
        - MP4 (la piste audio sera extraite)
        - WAV
     """
    )

    # À propos du processus de transcription
    st.markdown(
        """
        ## À propos du processus de transcription

        L'application utilise une API de transcription pour effectuer la conversion audio en texte. Le fichier audio est divisé en segments plus courts pour accélérer le processus de transcription. Les transcriptions sont ensuite fusionnées pour créer un fichier texte complet. Notez que la qualité de la transcription peut varier en fonction de la clarté de l'audio et des accents des locuteurs.
        """
    )
    uploaded_files = st.file_uploader("Upload one or multiple audio files", type=["mp3", "mp4", "wav"], accept_multiple_files=True)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            if f"transcript_{uploaded_file.name}" not in st.session_state:
                st.session_state[f"transcript_{uploaded_file.name}"] = None

        audio_files = {f.name: f for f in uploaded_files}
        selected_audio = st.sidebar.selectbox("Select an audio file to view transcription", list(audio_files.keys()))

        if st.button("Transcribe"):
            try:
                with st.spinner('Creating this audio transcript'):
                    with NamedTemporaryFile(delete=False, suffix=f".{audio_files[selected_audio].type.split('/')[-1]}") as tmp_audio_file:
                        tmp_audio_file.write(audio_files[selected_audio].getbuffer())
                        tmp_audio_file.flush()

                        def update_transcription(transcription):
                            st.session_state[f"transcript_{selected_audio}"] = transcription

                        st.write("en cours de chargement")
                        transcript, prediction_file_path = transcribe_audio(tmp_audio_file.name, 700, audio_files[selected_audio].type.split('/')[-1], update_callback=update_transcription)
                        st.session_state['prediction_file_path'] = prediction_file_path  # Add this line
                        st.write("voici le transcript")

            except Exception as e:
                st.error(f"Error during transcription process: {e}")


        if st.session_state[f"transcript_{selected_audio}"] is not None:
                st.text_area("Transcription", value=st.session_state[f"transcript_{selected_audio}"], height=400)

                # Add a download link for the prediction file
                if "prediction_file_path" in st.session_state:
                    with open(st.session_state['prediction_file_path'], 'r') as prediction_file:
                        st.download_button(
            label="Download transcription file",
            data=prediction_file,
            file_name=f"transcription_{selected_audio}.txt",
            mime="text/plain"
        )

        else:
            st.text_area("Transcription", value="Here will be printed the transcription as soon as it is finished.", height=400)

elif choice == "PDF summarizer":
    Language = st.sidebar.selectbox("Choose the output language for summary", [ "English","French", "German"])
    api_key = st.sidebar.text_input("OpenAI API KEY")
    if api_key is not None:
        openai.api_key = api_key
    Modchoice= st.sidebar.selectbox("Choose the OpenAI model",["gpt-3.5-turbo","gpt-4","gpt-4-32k"])
    if Modchoice is not None:
        Model_choice=Modchoice
    CLEAR=st.sidebar.button("Clear cache")
    if CLEAR:
        st.cache_data.clear()
    
    st.title("PDF Summarizer")
    st.write("Upload a PDF file and get a brief summary of it.")
    
    st.sidebar.title("Options")

    file = st.sidebar.file_uploader("Upload a PDF", type="pdf")

    if file is not None:
        with st.spinner('Processing the PDF file...'):
            paragraphs = get_paragraphs(file)

            if not paragraphs:
                st.error("Unable to extract content from the PDF.")
            return

            paragraphs = concatenate_short_paragraphs(paragraphs)
            # Reset the cache to avoid errors when re-running the code
            caching.clear_cache()
            st.success('PDF processed successfully. Now generating summary...')

        with st.spinner('Generating the summary...'):
            text = " ".join(paragraphs)
            summary = total_summarizer(text)
            caching.clear_cache()
            st.success('Summary generated successfully.')

        st.subheader("Summary")
        st.textbox(summary)
    else:
        st.info("Please upload a PDF file to get started.")

    st.sidebar.info("This app uses OpenAI's GPT-3 model to generate a brief summary of the uploaded PDF.")
