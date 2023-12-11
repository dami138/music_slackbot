import random
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import os
from dotenv import load_dotenv
from supabase import create_client

from googleapiclient.discovery import build



# 토큰 설정
load_dotenv(verbose=True)
SLACK_SIGNING_SECRET    = os.getenv('SLACK_SIGNING_SECRET')
SLACK_BOT_TOKEN         = os.getenv('SLACK_BOT_TOKEN')
SLACK_APP_TOKEN         = os.getenv('SLACK_APP_TOKEN')
SUPABASE_URL            = os.getenv('SUPABASE_URL')
SUPABASE_KEY            = os.getenv('SUPABASE_KEY')     
GOOGLE_KEY              = os.getenv('GOOGLE_KEY')

client  = create_client(SUPABASE_URL, SUPABASE_KEY)
youtube = build('youtube', 'v3', developerKey=GOOGLE_KEY)

app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET
)

# 각종 이벤트를 annotation 안에 설정하면 된다.
@app.event("message")
@app.event("app_mention")
def message_handler(message, say):   
    say(f"Hello <@{message['user']}>")

# 아무거나 냅다 하나 추천
@app.command("/recommend")
def recommend(ack, say):
    ack()
    
    musics=client.table("music").select("*").execute()
    music = random.choice(musics.data)

    say(f"<@{music['slack_id']}>님의 추천 음악: {music['title']} \n{music['youtube_url']}")


# 음악 추가
@app.command("/add_music")
def add_music(ack, say, command):
    ack()
    youtube_url = command['text']
    video_id = re.search('v=([0-9A-Za-z_-]{11})', youtube_url).group(1)

    # 비디오 정보 요청
    response = youtube.videos().list(
        part='snippet',
        id=video_id
    ).execute()

    # 제목과 설명 추출    
    title = response['items'][0]['snippet']['title']
    description = response['items'][0]['snippet']['description']
    artist = response['items'][0]['snippet']['channelTitle']    

    music_data = {  "slack_id":command['user_id'],
                    "title":title,
                    "description":description,
                    "artist":artist,
                    "youtube_url":command['text']}
    
    client.table("music").insert(music_data).execute()    
    say(f"{music_data['title']} 이(가) 추가되었습니다.")


# 이번주 추가된 전체 음악 리스트를 재생목록으로 만들어서 하나의 링크로 반환
@app.command("/list_music")
def list_music(ack, say, command):
    ack()
    

if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()