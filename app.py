import os
import requests
from moviepy.editor import AudioFileClip
from tempfile import TemporaryDirectory, NamedTemporaryFile
import streamlit as st


def split_audio(file_path, part_duration):
    try:
        audio = AudioFileClip(file_path)
        duration = audio.duration
        parts = int(duration // part_duration)

        temp_dir = TemporaryDirectory()

        for i in range(parts):
            start_time = i * part_duration
            end_time = (i + 1) * part_duration
            split_audio = audio.subclip(start_time, end_time)
            split_audio.write_audiofile(os.path.join(temp_dir.name, f"part_{i + 1}.mp3"), codec='mp3')

        return parts, temp_dir
    except Exception as e:
        print(f"Error in split_audio: {e}")
        raise


def transcribe_audio_files(directory):
    responses = []
    headers = {
        'accept': 'application/json',
        'x-gladia-key': st.secrets["GLADIA_KEY"],
    }

    for filename in os.listdir(directory):
        if filename.endswith(".mp3"):
            try:
                file_path = os.path.join(directory, filename)
                files = {
                    'audio': (filename, open(file_path, 'rb'), 'audio/mpeg'),
                    'diarization_max_speakers': (None, '2'),
                    'language': (None, 'french'),
                    'language_behaviour': (None, 'manual'),
                    'output_format': (None, 'txt'),
                    'target_translation_language': (None, 'english'),
                }

                response = requests.post('https://api.gladia.io/audio/text/audio-transcription/', headers=headers, files=files)
                if response.status_code == 200:
                    responses.append(response)
                else:
                    print(f"Request for {filename} failed with status code {response.status_code}: {response.text}")
            except Exception as e:
                print(f"Error in transcribe_audio_files for {filename}: {e}")

    return responses


def transcribe_audio(input_file_path, segment_duration):
    try:
        num_parts, temp_dir = split_audio(input_file_path, segment_duration)
        resp = transcribe_audio_files(temp_dir.name)
        predictions = []
        for response in resp:
            data = response.json()
            if 'prediction' in data:
                predictions.append(data['prediction'])
            else:
                print(f"Key 'prediction' not found in response from {response.url}")

        transcript = "\n".join(predictions)

        return transcript
    except Exception as e:
        print(f"Error in transcribe_audio: {e}")
        raise


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
                    st.write("en cours de chargement")
                    transcript = transcribe_audio(tmp_audio_file.name, 700)
                    st.write("voici le transcript")
                    st.session_state[f"transcript_{selected_audio}"] = transcript
        except Exception as e:
            st.error(f"Error during transcription process: {e}")

    if st.session_state[f"transcript_{selected_audio}"] is not None:
        st.text_area("Transcription", value=st.session_state[f"transcript_{selected_audio}"], height=400)
    else:
        st.text_area("Transcription", value="Here will be printed the transcription as soon as it is finished.", height=400)
        
# Test section in the sidebar
st.sidebar.title("Test Section")

# Upload a sample audio file for testing purposes
test_audio_file = st.sidebar.file_uploader("Upload an audio file for testing", type=["mp3", "mp4", "wav"])

if test_audio_file is not None:
    st.sidebar.write("Sample Audio File:")
    st.sidebar.audio(test_audio_file)

    # Save the test audio file to a temporary file
    with NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio_file:
        tmp_audio_file.write(test_audio_file.getbuffer())
        tmp_audio_file.flush()
        test_audio_file_path = tmp_audio_file.name

    # Add buttons to test individual functions
    if st.sidebar.button("Test split_audio"):
        try:
            parts, temp_dir = split_audio(test_audio_file_path, 700)
            st.sidebar.write(f"Sample audio split into {parts} parts")
        except Exception as e:
            st.sidebar.error(f"Error in split_audio: {e}")

    if st.sidebar.button("Test transcribe_audio_files"):
        try:
            responses = transcribe_audio_files(temp_dir.name)
            st.sidebar.write(f"Received {len(responses)} responses from the transcription API")
        except Exception as e:
            st.sidebar.error(f"Error in transcribe_audio_files: {e}")

    if st.sidebar.button("Test transcribe_audio"):
        try:
            transcript = transcribe_audio(test_audio_file_path, 700)
            st.sidebar.write("Transcription result:")
            st.sidebar.write(transcript)
        except Exception as e:
            st.sidebar.error(f"Error in transcribe_audio: {e}")
else:
    st.sidebar.warning("Please upload an audio file to test the functions.")

