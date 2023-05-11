import os
import requests
from moviepy.editor import AudioFileClip
from tempfile import TemporaryDirectory, NamedTemporaryFile
import streamlit as st  
import shutil


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


def transcribe_audio(input_file_path, segment_duration, update_callback=None):
    predicted = ''
    temp_dir = Path("temp/splitted")
    temp_dir.mkdir(parents=True, exist_ok=True)

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
                        predicted += f'\nVoici la traduction de la partie {idx}\n{prediction}'

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



st.title("Audio Transcription App")

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
                with NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio_file:
                    tmp_audio_file.write(audio_files[selected_audio].getbuffer())
                    tmp_audio_file.flush()

                    def update_transcription(transcription):
                        st.session_state[f"transcript_{selected_audio}"] = transcription

                    st.write("en cours de chargement")
                    transcript, prediction_file_path = transcribe_audio(tmp_audio_file.name, 700, update_callback=update_transcription)
                    st.write("voici le transcript")

        except Exception as e:
            st.error(f"Error during transcription process: {e}")

if st.session_state[f"transcript_{selected_audio}"] is not None:
        st.text_area("Transcription", value=st.session_state[f"transcript_{selected_audio}"], height=400)

        # Add a download link for the prediction file
        if "prediction_file_path" in st.session_state:
            st.markdown(f"[Download prediction file](file:///{st.session_state['prediction_file_path']})")
    else:
        st.text_area("Transcription", value="Here will be printed the transcription as soon as it is finished.", height=400)
