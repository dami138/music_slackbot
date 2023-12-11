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

supabase_client  = create_client(SUPABASE_URL, SUPABASE_KEY)
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
def recommend(ack, body, client):
    ack()
    
    musics = supabase_client.table("music").select("*").execute()
    music  = random.choice(musics.data)


    client.chat_postMessage(
        channel=body["channel_id"],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{music['slack_id']}>님의 추천 음악: {music['title']} \n{music['youtube_url']}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": ":thumbsup: 좋아요",
                        },
                        "action_id": "button_click"  # 버튼 액션 ID
                    }
                ]
            }
        ]
    )

@app.action("button_click")
def handle_thumb_click(ack, body, client):
    # 요청 확인
    ack()
    
    # 버튼 클릭에 대한 정보
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    message_ts = body["container"]["message_ts"]

    text = body["message"]["blocks"][0]["text"]["text"]
    match= re.search('v=([0-9A-Za-z_-]{11})', text)
    video_id = match.group(1)

    btnName = body["message"]["blocks"][1]["elements"][0]["text"]["text"]

    #supabase에서 해당 음악의 좋아요 수 +1/-1
    current_value_result = supabase_client.table("music").select("thumb").eq("youtube_url", f"https://www.youtube.com/watch?v={video_id}").execute()

    if btnName == ":thumbsup: 좋아요":
        new_thumb_value = current_value_result.data[0]['thumb'] + 1
    else:
        new_thumb_value = current_value_result.data[0]['thumb'] -1

    supabase_client.table("music").update({"thumb": new_thumb_value}).eq("youtube_url", f"https://www.youtube.com/watch?v={video_id}").execute()

    # 기존 메시지 업데이트
    new_button_text = ":thumbsup: 좋아요" if btnName == ":thumbsup: 좋아요 취소" else ":thumbsup: 좋아요 취소"
    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": new_button_text,
                        },
                        "action_id": "button_click"  # 버튼 액션 ID
                    }
                ]
            }
        ]
    )

# 음악 추가
@app.command("/add_music")
def add_music(ack, say, command):
    ack()
    text = command['text']
    match= re.search('v=([0-9A-Za-z_-]{11})', text)

    # 유튜브 링크 기반 음악 추가 
    if match:
        video_id = match.group(1)
        response = youtube.videos().list(
            part='snippet',
            id=video_id
        ).execute()

    # 제목 기반 음악 추가 
    else:
        response = youtube.search().list(
            part='snippet',
            q=text,
            type='video',
            maxResults=1
        ).execute()

    # 제목과 설명 추출    
    youtube_url = "https://www.youtube.com/watch?v=" + response['items'][0]['id']['videoId']
    title       = response['items'][0]['snippet']['title']
    description = response['items'][0]['snippet']['description']
    artist      = response['items'][0]['snippet']['channelTitle']    

    music_data = {  "slack_id"      :command['user_id'],
                    "title"         :title,
                    "description"   :description,
                    "artist"        :artist,
                    "youtube_url"   :youtube_url}
    
    supabase_client.table("music").insert(music_data).execute()    
    say(f"{music_data['title']} 이(가) 추가되었습니다.")

# 최신 추가된 음악 리스트 n개 반환
@app.command("/new_music")
def list_music(ack, say, command):
    ack()
    count = int(command['text'])

    musics = supabase_client.table("music").select("*").order("created_at",desc=True).limit(count).execute()
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

    musics = supabase_client.table("music").select("*").eq("slack_id",slack_id).order("created_at",desc=True).limit(3).execute()
    msg = ""
    for i,music in enumerate(musics.data):
        msg += f"{i+1}: {music['title']} \n{music['youtube_url']} \n"
    say(msg)
    

# todo: 음악 삭제
    


if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()