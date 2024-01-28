#!/usr/bin/env python3

import yt_dlp
import validators
import sys
import unicodedata
import re
import subprocess
from vosk import Model, KaldiRecognizer, SetLogLevel
import srt
import json
import datetime
import argostranslate.package
import argostranslate.translate
import os
from pathlib import Path


def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


filename = None


def progress_download(d):
    global filename
    filename = d.get('info_dict').get('_filename')


ydl_opts = {
    'quiet': True,
    'progress_hooks': [progress_download]
}

ytl = yt_dlp.YoutubeDL(ydl_opts)

url = input("url: ")
# url = "https://www.youtube.com/watch?v=Z_b4Gf5mxV8"
if not validators.url(url):
    sys.exit(1)

try:
    dictMeta = ytl.download(url)
except:
    sys.exit(1)

SAMPLE_RATE = 16000
SetLogLevel(-1)

# # url = "https://video-weaver.arn03.hls.ttvnw.net/v1/playlist/CrsE_GjoMvQs9vI6FJpUBG2FOO402cbz5TfuSk2CcRf0t-R61tsEj4OxILMCam1oeLDZePQFUSIGz48NMmSNUvTScQFsBOkzVxTfPK3wdEyI-3RXKzfA7Sr9CvdAXlRQRUi9JKXT4hLvY6SByLxSHZmiWR8Ps_Nj3wwqzpiJzZchoey1A85FZjSB3esoHSYKVDpSevjqPtFzSj2pXYWpwbvtPf09JJWIsOpOitHtZPBV1gSCM-IRvONmyZSjJpa6YiY8ADzPLidizs5X22CYUn90jD_14arEX5EaiOPlyFG6_YJ2B7ElD-HF5a2lELNnWvbGKSMuBA1ihrtV8piFmK6m2yjwJrF-3gz4j4aqB6dcbPdjHfnyoOEbhBMoWQwC4_zSPfpZ3Zn7gyAXdussOrh8lAZonzd2ZgBytTn1aAbt0GIx2BBcy-B6ZUBk27wG_JkQpcgYiT9_da_zecu5XcNI0iZdChzpc0tnNCk743JdlMq2MEExeJMBiqim1S6Os8k7W9UJLjRJqjWv0gcRVGyXeq8MS59dvY-OG_tt5LVqxp8gyp1roODyb7SXpi1w42abFPqY903yTtlb5u-kbkFcpz9BscWAqeHZOkp0RhoFwxaxHdS8wJ_c8YFqGAv24FD8gz2yO0HsrE01PcBdCg1na_rmGmlbeLzt5HNx_JNTi2WtSyj9kZi_4oswVUEmN-WEkYrGChmWtmwDgdoF_HZ5k5UNWLnkEgZ4AMlYioErLCkVoa75t1T-9lsDPRoM5L6gP80voARslHS1IAEqCXVzLXdlc3QtMjDKCA.m3u8"
# url = "2.mp4"

model = Model(lang="en-us", model_path="vosk-model-small-en-us-0.15")
rec = KaldiRecognizer(model, SAMPLE_RATE)
rec.SetWords(True)
words_per_line = 7

from_code = "en"
to_code = "ru"

argostranslate.package.install_from_path("translate-en_ru-1_9.argosmodel")

with subprocess.Popen(["ffmpeg", "-loglevel", "quiet", "-i",
                       filename,
                       "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "s16le", "-"],
                      stdout=subprocess.PIPE).stdout as stream:
    results = []

    while True:
        data = stream.read(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            text = json.loads(rec.Result())
            if text["text"] == "":
                continue
            print(text["text"])
            results.append(json.dumps({
                "result": [
                    {
                        "conf": 1,
                        "start": text["result"][0]["start"],
                        "end": text["result"][-1]["end"],
                        "word": argostranslate.translate.translate(text["text"], from_code, to_code)
                    }
                ]
            }))
    text = json.loads(rec.FinalResult())
    # text["text"] = argostranslate.translate.translate(text["text"], from_code, to_code)
    print(text["text"])
    # results.append(json.dumps(text))
    if text["text"] != "":
        results.append(json.dumps({
            "result": [
                {
                    "conf": 1,
                    "start": text["result"][0]["start"],
                    "end": text["result"][-1]["end"],
                    "word": argostranslate.translate.translate(text["text"], from_code, to_code)
                }
            ]
        }))
    print(results)
    subs = []
    for res in results:
        jres = json.loads(res)
        if not "result" in jres:
            continue
        words = jres["result"]
        for j in range(0, len(words), words_per_line):
            line = words[j: j + words_per_line]
            s = srt.Subtitle(index=len(subs),
                             content=" ".join([l["word"] for l in line]),
                             start=datetime.timedelta(seconds=line[0]["start"]),
                             end=datetime.timedelta(seconds=line[-1]["end"]))
            subs.append(s)

    result = srt.compose(subs)


with open(Path(filename).stem + ".srt", "w") as f:
    f.write(result)
