import subprocess
#subprocess.run(["sed", "-i", "s/transform_plan_raw =.*/transform_plan_raw = js/g", "/home/appuser/venv/lib/python3.9/site-packages/pytube/cipher.py"],check=True)


import openai
import io #data manipulation
import PyPDF2
import re #textual regression
import openai
import tiktoken
import pandas as pd
import openai
import time
import numpy as np
from pytube import YouTube
import os
from pathlib import Path
import requests
import json
import time
import tempfile
import streamlit as st
from streamlit_chat import message
from io import StringIO
import requests
from bs4 import BeautifulSoup
from openai.embeddings_utils import distances_from_embeddings
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)  # for exponential backoff
from datetime import date
    
Model_choice='gpt-3.5-turbo'

max_tokens=3000

import time

import random as rnd
import time 

def typewrite_text(text: str):
    tokens = text.split()
    container = st.empty()

    for index in range(len(tokens)):
        container.markdown(" ".join(tokens[:index]))
        time.sleep(rnd.uniform(0.05,0.3))


#---------------- Summarizing function ------------------#
def updatestate(docs,add):
    l=st.session_state[docs]
    l.append(add)
    st.session_state[docs]=l
    

@st.cache_data
def get_content_from_webpage(url):
  response=requests.get(url)
  content=response.content
  soup=BeautifulSoup(content,"html.parser")
  text=""
  if 'antler' in url:
    firstelem='div'
    classes='max-width-large align-center'
  elif 'lemonde.fr' in url:
    firstelem='article'
    classes="article__content old__article-content-single"
  elif 'cnn.com' in url:
    firstelem='main'
    classes="article__main"
  for element in soup.find_all(firstelem, class_=classes):
    text += element.get_text()
  text=clean_text(text)
  return text

def remove_newlines(serie):
    serie = serie.str.replace('\n', ' ')
    serie = serie.str.replace('\\n', ' ')
    serie = serie.str.replace('  ', ' ')
    return serie

#In order to process the data we want to make sure that the text is well formated

def clean_text(text):
    # Remove digits directly preceding words
    text = re.sub(r'\b\d+([^\d\s]+)\b', r'\1', text)

    # Remove newlines and extra whitespace
    text = text.replace('\n', ' ').strip()
    text = re.sub(' +', ' ', text)
    text = text.replace('\\n', ' ')
    text = text.replace('  ', ' ')
    text = text.replace('  ', ' ')

    return text

#function to extract paragraphs from the pdf

@st.cache_data
def get_paragraphs(pdf_file):
    outfp = io.StringIO() #extracts document in binary

    
    reader = PyPDF2.PdfReader(pdf_file)
    for i in range(len(reader.pages)):
        page = reader.pages[i]
        outfp.write(page.extract_text())

    text = outfp.getvalue()
    paragraphs = [clean_text(p) for p in text.split('.\n') if p.strip()]
    

    return paragraphs


@st.cache_data
def content(pdf_file):
    outfp = io.StringIO()

    reader = PyPDF2.PdfReader(pdf_file)
    for i in range(len(reader.pages)):
      page = reader.pages[i]
      outfp.write(page.extract_text())

    text = outfp.getvalue()
    

    return text




def concatenate_short_paragraphs(paragraphs):
    # Concatenate paragraphs if they follow each other and have less than 20 words inside each other
    new_paragraphs = []
    i = 0
    while i < len(paragraphs):
        current_paragraph = paragraphs[i]
        if i < len(paragraphs) - 1:
            next_paragraph = paragraphs[i+1]
            words_in_current = len(re.findall(r'\b\w+\b', current_paragraph))
            words_in_next = len(re.findall(r'\b\w+\b', next_paragraph))
            if words_in_current < 60 and words_in_next < 60:
                combined = current_paragraph + ' ' + next_paragraph
                new_paragraphs.append(combined)
                i += 2
                continue
        new_paragraphs.append(current_paragraph)
        i += 1
    return new_paragraphs

def paragraphgenerator(text):
    prompt = "act as a summarizer, reformulate this content cleaned and organized : " + text
    response = openai.ChatCompletion.create(
        model=Model_choice,
        messages=[{"role": "system", "content": "You are an ai assistant that act as a summarizer, reformulate the content provided by the user in a cleaned and organized way."},
        {"role": "user", "content": prompt}],max_tokens=900,n=1,stop=None,temperature=0.3,)
    summary_3 = response.choices['content'].text.strip()

    return summary_3

import re

def split_text_into_chunks(text):
    # Split the text into a list of sentences using regular expressions
    sentences = re.findall('[A-Z][^\.!?]*[\.!?]', text)

    # Initialize a list to hold the chunks of text
    chunks = []

    # Initialize a counter to keep track of the number of words in each chunk
    word_count = 0

    # Initialize a string to hold the current chunk of text
    current_chunk = ""

    # Loop through each sentence in the text
    for sentence in sentences:
        # Add the sentence to the current chunk of text
        current_chunk += sentence

        # Count the number of words in the current sentence
        sentence_word_count = len(sentence.split())

        # Add the number of words in the current sentence to the total word count
        word_count += sentence_word_count

        # If the word count is greater than or equal to 1500, add the current chunk to the list of chunks
        # and reset the current chunk and word count
        if word_count >= 700:
            chunks.append(clean_text(current_chunk))
            current_chunk = ""
            word_count = 0

    # If there is any remaining text in the current chunk, add it to the list of chunks
    if current_chunk != "":
        chunks.append(clean_text(current_chunk))

    return chunks


def split_text_into_chunks_for_summary(text):
    # Split the text into a list of sentences using regular expressions
    sentences = re.findall('[A-Z][^\.!?]*[\.!?]', text)

    # Initialize a list to hold the chunks of text
    chunks = []

    # Initialize a counter to keep track of the number of words in each chunk
    word_count = 0

    # Initialize a string to hold the current chunk of text
    current_chunk = ""

    # Loop through each sentence in the text
    for sentence in sentences:
        # Add the sentence to the current chunk of text
        current_chunk += sentence

        # Count the number of words in the current sentence
        sentence_word_count = len(sentence.split())

        # Add the number of words in the current sentence to the total word count
        word_count += sentence_word_count

        # If the word count is greater than or equal to 1500, add the current chunk to the list of chunks
        # and reset the current chunk and word count
        if word_count >= 700:
            chunks.append(clean_text(current_chunk))
            current_chunk = ""
            word_count = 0

    # If there is any remaining text in the current chunk, add it to the list of chunks
    if current_chunk != "":
        chunks.append(clean_text(current_chunk))

    return chunks

def concat_paragraphs(paragraphs):
    """
    Concatenates adjacent paragraphs if the total number of words is less than 1200.
    
    Args:
        paragraphs (list of str): A list of paragraphs.
    
    Returns:
        list of str: The concatenated paragraphs.
    """
    total_words = sum(len(paragraph.split()) for paragraph in paragraphs)
    if total_words > 1200:
        concatenated_paragraphs = []
        for i in range(0, len(paragraphs), 2):
            if i+1 < len(paragraphs):
                concatenated_paragraphs.append(paragraphs[i] + ' ' + paragraphs[i+1])
            else:
                concatenated_paragraphs.append(paragraphs[i])
        return concatenated_paragraphs
    else:
        return paragraphs

import concurrent.futures

@st.cache_data
def total_summarizer(text, lang, model=Model_choice):
  L1 = split_text_into_chunks_for_summary(text)
  with concurrent.futures.ThreadPoolExecutor() as executor:
    L2 = list(executor.map(summarize_this, L1))
  total_words = sum(len(paragraph.split()) for paragraph in L2)
  while total_words > 3000:
    L2 = concat_paragraphs(L2)
    with concurrent.futures.ThreadPoolExecutor() as executor:
      L2 = list(executor.map(summarize_this, L2))
    total_words = sum(len(paragraph.split()) for paragraph in L2)
  fs = finalsummary(L2)

  # Break fs into chunks of 1000 words
  fs_chunks = []
  words = fs.split()
  for i in range(0, len(words), 1000):
    fs_chunks.append(' '.join(words[i:i+1000]))

  # Call summarize_in_english function in parallel on each chunk
  with concurrent.futures.ThreadPoolExecutor() as executor:
    summaries = list(executor.map(lambda chunk: summarize_in_english(chunk, model, lang), fs_chunks))

  # Concatenate these summaries to create the final summary
  final_summary = ' '.join(summaries)

  return final_summary


  
def finalsummary(lst):
    concatenated = ""
    for i in range(len(lst)):
        concatenated += lst[i]
        if i != len(lst) - 1:
            concatenated += "\n"
    return concatenated

def summarize_this(text,model=Model_choice,stop_sequence=None,Lang="English"):
  pr="act as an academic researcher, summarize and translate this text in "+str(Lang)+":  '" +str(text)+"' "
  try:
    # Create a completions using the question and context
    response = openai.ChatCompletion.create(model=Model_choice,messages=[{"role": "system", "content": "You are an ai assistant that act as a summarizer, summarize the text provided by the user in 500 words."},
        {"role": "user", "content": pr}],max_tokens=500,temperature=0.9,top_p=1,n=1)
    return response['choices'][0]['message']['content'].strip()
  except Exception as e:
    print(e)
    return ""


def summarize_in_english(text,model=Model_choice,stop_sequence=None,Lang="English"):
  pr="act as an academic researcher, summarize and translate this text in "+str(Lang)+":  '" +str(text)+"' "
  try:
    # Create a completions using the question and context
    response = openai.ChatCompletion.create(model=Model_choice,messages=[{"role": "system", "content": "You are an ai assistant that act as a summarizer, summarize the text provided by the user in 500 words."},
        {"role": "user", "content": pr}],max_tokens=500,temperature=0.9,top_p=1,n=1)
    return response['choices'][0]['message']['content'].strip()
  except Exception as e:
    print(e)
    return ""
