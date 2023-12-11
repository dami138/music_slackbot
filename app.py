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
    
    musics = client.table("music").select("*").execute()
    music  = random.choice(musics.data)

    say(f"<@{music['slack_id']}>님의 추천 음악: {music['title']} \n{music['youtube_url']}")

# todo: 제목 기반 음악 추가 기능
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

# 최신 추가된 음악 리스트 n개 반환
@app.command("/new_music")
def list_music(ack, say, command):
    ack()
    count = int(command['text'])

    musics = client.table("music").select("*",count=count).order("created_at",desc=True).execute()
    msg = ""
    for i,music in enumerate(musics.data):
        msg += f"{i+1}: {music['title']} \n{music['youtube_url']} \n"
    say(msg)
    
    
# 유저이름을 입력하면 해당 유저가 최근 추가한 음악 3개 반환
@app.command("/user_music")
def user_music(ack, say, command):
    ack()    
    print(command)
    slack_id = re.search('<@(.*)\|', command['text']).group(1)    

    musics = client.table("music").select("*",count=3).eq("slack_id",slack_id).order("created_at",desc=True).execute()
    msg = ""
    for i,music in enumerate(musics.data):
        msg += f"{i+1}: {music['title']} \n{music['youtube_url']} \n"
    say(msg)
    

# todo: 음악 삭제, 추천버튼
    


if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()