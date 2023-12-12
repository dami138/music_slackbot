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
GOOGLE_CLIENT_SECRET    = os.getenv('GOOGLE_CLIENT_SECRET')

supabase_client  = create_client(SUPABASE_URL, SUPABASE_KEY)
youtube = build('youtube', 'v3', developerKey=GOOGLE_KEY)

app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET
)


# 'like' 테이블에서 해당 유저가 '좋아요'한 곡을 가져옵니다.
def get_liked_musics(user_id):
    liked_musics = supabase_client.table("like").select("music_id").eq("liked_by", user_id).execute().data
    return liked_musics

# 해당 유저가 '좋아요' 하지 않은 곡을 가져옵니다.
def get_unliked_musics(user_id):
    # 'music' 테이블에서 모든 곡을 가져옵니다.
    all_musics = supabase_client.table("music").select("*").execute().data

    # 'like' 테이블에서 해당 유저가 좋아요한 곡을 가져옵니다.
    liked_musics = get_liked_musics(user_id)
    liked_music_ids = set(music["music_id"] for music in liked_musics)

    # 유저가 좋아요하지 않은 곡을 필터링합니다.
    unliked_musics = [music for music in all_musics if music["id"] not in liked_music_ids]
    return unliked_musics

# 작동 확인
@app.event("message")
@app.event("app_mention")
def message_handler(message, say):   
    say(f"Hello <@{message['user']}>")

# '좋아요' 하지 않은 음악 중 랜덤으로 추천
@app.command("/recommend")
def recommend(ack, body, client):
    ack()

    user_id = body["user_id"]    
    unliked_musics = get_unliked_musics(user_id)

    if unliked_musics==[]:
        client.chat_postMessage(
            channel=body["channel_id"],
            text="더이상 추천할 음악이 없습니다."
        )
        return

    music   = random.choice(unliked_musics)      

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

    music = supabase_client.table("music").select("id").eq("youtube_url", f"https://www.youtube.com/watch?v={video_id}").execute()
    music_id = music.data[0]['id']

    # 좋아요 정보 있는지 확인
    liked = supabase_client.table("like").select("id").eq("music_id",music_id).eq("liked_by",user_id).execute()

    if btnName == ":thumbsup: 좋아요":
        if liked.data == []:
            supabase_client.table("like").insert({"music_id":music_id, "liked_by":user_id}).execute()   
        
    else:
        supabase_client.table("like").delete().eq("id", liked.data[0]["id"]).execute()

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
    video_id    = response['items'][0]['id']['videoId']
    youtube_url = "https://www.youtube.com/watch?v=" + video_id
    title       = response['items'][0]['snippet']['title']
    description = response['items'][0]['snippet']['description']
    artist      = response['items'][0]['snippet']['channelTitle']    

    exist_data = supabase_client.table("music").select("slack_id").eq("video_id",video_id).execute().data
    if exist_data :
        say(f"{title}은(는) <@{exist_data[0]['slack_id']}>님이 이미 추가한 곡입니다.")
        return


    music_data = {  "slack_id"      :command['user_id'],
                    "title"         :title,
                    "description"   :description,
                    "artist"        :artist,
                    "youtube_url"   :youtube_url,
                    "video_id"      :video_id}
    
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
    slack_id = re.search('<@(.*)\|', command['text']).group(1)    

    musics = supabase_client.table("music").select("*").eq("slack_id",slack_id).order("created_at",desc=True).limit(3).execute()

    if musics.data == []:
        msg = f"<@{slack_id}> 유저가 곡을 추가하지 않았습니다."

    else:
        msg = ""
        for i,music in enumerate(musics.data):
            msg += f"{i+1}: {music['title']} \n{music['youtube_url']} \n"

    say(msg)
    

@app.command("/topn_music")
def top10_music(ack, say, command):
    ack()
    count = int(command['text'])
    musics = supabase_client.table("music").select("*").order("likes",desc=True).limit(count).execute()
    msg = ""
    for i,music in enumerate(musics.data):
        msg += f"{i+1}: {music['title']} \n{music['youtube_url']} \n"
    say(msg)


# todo: 음악 삭제


if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()