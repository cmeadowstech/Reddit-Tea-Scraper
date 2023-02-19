from pprint import pprint
import os
import json
from datetime import datetime

import praw
from praw.models import MoreComments
from prawcore.exceptions import Forbidden

import psycopg2

reddit = praw.Reddit(
    client_id="xxxx",
    client_secret="xxxx",
    user_agent="tea-scraper/0.0.1",
)

try:
    pg_connect = psycopg2.connect(
        host="xxx",
        database='xxx',
        user='xxx',
        password= os.environ['POSTGRES_PW'])

    print("Database connected successfully")

except (Exception, psycopg2.DatabaseError) as error:
    print(error)

with open('RS_2022-12', "r", encoding="utf8") as f:
    for line in f:
        smb = json.loads(line)
        if smb['subreddit_id'] == "t5_2qq5e" and smb['score'] > 1:
            pprint(smb['permalink'])

            comments = []

            try:
                submission = reddit.submission(smb['id'])

                submission.comments.replace_more(limit=None)
                for comment in submission.comments.list():
                    if comment.score > 0:
                        comments.append(comment.body_html)

                cur = pg_connect.cursor()
                try:
                    cur.execute("""
                        INSERT INTO tea (postid, title, url, permalink, selftext, comments, created_utc)
                        VALUES (%s, %s, %s, %s, %s, ARRAY [%s], %s)
                        ON CONFLICT DO NOTHING
                    """,
                    (submission.id, submission.title, submission.url, submission.permalink, submission.selftext_html, comments, datetime.utcfromtimestamp(submission.created_utc).strftime('%Y-%m-%d %H:%M:%S')))
                    pg_connect.commit()
                except (Exception, psycopg2.DatabaseError) as error:
                    print(error)

            except Forbidden as error:
                print(f'Failed to get {submission.id}: {error}')

pg_connect.close

