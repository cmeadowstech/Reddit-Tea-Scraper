# Reddit Tea Scraper
Occasionally I like to find new online tea vendors to buy tea from, and when I do I would visit r/tea to see what was recommended. However I noticed that there were a bunch of new suggestions scattered all over the place, so I figured I would spend way too much time scraping all of those vendors to see who was most recommended.

Unfortunately, scraping an entire year's worth of data ended up being more difficult than I originally thought, in part due to Reddit's API utilization limits.

## Scraping Data

I started out making requests manually to the API endpoint, but because of the way it returns comments, I ended up switching to the [PRAW](https://praw.readthedocs.io/en/stable/) (Python Reddit API Wrapper) package to handle much of the logic. No need to reinvent the wheel when PRAW already handles tasks such as fetching all comments and metadata in a much easier-to-parse manner.

PRAW too ended up having its own limitations though. It respected Reddit's official API limitations of 1,000 submissions and there did not seem to be a good way to filter by date to batch my queries. As a result, I turned to [Pushshift](https://github.com/pushshift/api) - a third-party Reddit API that allows you to query its own database of Reddit submissions and comments.

Unfortunately, it too had some issues - due to a data migration dating back to late last year, its database was missing submissions prior to November. Fortunately, they had their data dumps stored in monthly chunks that you could download [from their site.](https://files.pushshift.io/reddit/submissions/)

In the end, I used a combination of:

1. Pushshift data dumps to get all submissions for 2022
2. PRAW to get all of their comments

```python
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
```

I had to download the dumps and process them in batches by month because the uncompressed files hit up ~130GB but allowed me to achieve what I wanted in regard to reliably getting all submissions and their comments for 2022.

I did apply some conditions to filter out low-quality submissions and comments.

## Storing Data

While I could have applied my logic to this data while scraping it, I wanted to break up the flow and simply store the data I needed for processing somewhere until I was ready to do something with it. This would also help me make changes to how I extract references to vendors.

I first considered storing it in a CSV or JSON file, but both seemed clunky ways to store data like this. Instead, I choose to write all of this to a Postgres database using the [psycopg2](https://pypi.org/project/psycopg2/) package.

```python
try:
    pg_connect = psycopg2.connect(
        host="xxx",
        database='xxx',
        user='xxx',
        password= os.environ['POSTGRES_PW'])

    print("Database connected successfully")

...

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

...

pg_connect.close
```

## Processing Data

One benefit of using a database like Postgres was that I could query from it instead of having to write a separate Python script to do it for me. 

This may not be the 'best' query but it returned to me what I needed. I used UNNEST to separate the array items in the "Comments" array and the REGEXP_MATCHES with a very loose pattern to match the domain.com syntax.

```sql
SELECT POSTID,
    PERMALINK,
    REGEXP_MATCHES(UNNEST(COMMENTS),
        '\w{4,}(?<!wordpress|blogspot|amazon|reddit|imgur|youtu.*|seriouseats|aliexpress|etsy|facebook|github|wikipedia|redd)\.(?!png|jpg|html|wordpress|pdf|htm|php|blogspot)[a-z]+',
        'g') AS WEBSITE_DOMAIN
FROM TEA
WHERE permalink !~ 'marketing_monday'
AND permalink !~ 'daily_discussion'
ORDER BY WEBSITE_DOMAIN
```

Normally I would have liked to count the results via the query as well, but the way Postgres projects the results AS WEBSITE_DOMAIN made it difficult for me to do so with my limited Postgres knowledge. Instead, I exported the results to a CSV and used pivot tables to calculate the results for me.

## Visualizing Data

Now that I had what I wanted - what do I do with it? I thought it would be neat to visualize the top 20 results.

To this end, I used the [ipyvizzu](https://github.com/vizzuhq/ipyvizzu) package in combination with a jupyter notebook to create an animated graph with my results.

I could probably write up an entire separate article on this package as I found the documentation for both it and the underlying Vizzu documentation to be lacking in some aspects. The general synopsis is that it allows you to take your data and animate it.

```python
chart.animate(
    Config(
        {
            "channels": {
                "y": {"set": ["Vendor"],"labels": False},
                "x": {"set": ["Count"],"range": { "max": '100%' },"title": "# of References on r/tea","interlacing": False},
                "label": { "attach": ['Vendor']},
                "color": { "set": ["Vendor"] }
            },
            "reverse": True,
            "title": "Most Popular Online Vendors 2022"
        }
    ),
    Style(
            {
            "plot": {
                "backgroundColor": "#1b2e24"
                }
        }
    ),
    duration=5,
    easing="ease"
)
```

Was more work than I expected to animate this to my liking, but I'm pretty happy with the end result:

![Animated graph](https://i.imgur.com/7DzJgW8.gif)