import os
import json
import time
import requests
import feedparser
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime

# Configuration
API_KEY = os.getenv("GEMINI_API_KEY")
BLOG_FILE = "blog.json"

if not API_KEY:
    print("CRITICAL: GEMINI_API_KEY environment variable not found. Sentinel halting.")
    exit(1)

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# List of intelligence targets (RSS feeds are most reliable for automated unattended scraping)
SOURCES = [
    {"name": "Utility Dive", "rss": "https://www.utilitydive.com/feeds/news/"},
    {"name": "Power Magazine", "rss": "https://www.powermag.com/feed/"},
    {"name": "Consulting-Specifying Engineer", "rss": "https://www.csemag.com/feed/"},
    {"name": "EC&M", "rss": "https://www.ecmweb.com/rss/articles"},
    {"name": "Electrical Contractor", "rss": "https://www.ecmag.com/rss.xml"},
    {"name": "IEEE Spectrum", "rss": "https://spectrum.ieee.org/feeds/feed.rss"},
    {"name": "Plant Services", "rss": "https://www.plantservices.com/rss/articles"}
]

def load_blog():
    if os.path.exists(BLOG_FILE):
        with open(BLOG_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_blog(data):
    with open(BLOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def is_duplicate(title, blog_data):
    # Simple deduplication by checking if title keywords exist in previous posts
    for post in blog_data[:20]: # Check last 20 posts
        if title[:20].lower() in post.get("original_title", "").lower() or title[:20].lower() in post.get("title", "").lower():
            return True
    return False

def get_latest_story():
    # Loop through sources to find the freshest story that isn't a duplicate
    blog_data = load_blog()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AECweb-Sentinel/1.0'
    }
    
    for source in SOURCES:
        print(f"Scanning {source['name']}...")
        try:
            feed = feedparser.parse(source['rss'])
            if not feed.entries:
                continue
                
            latest = feed.entries[0]
            title = latest.title
            link = latest.link
            
            if is_duplicate(title, blog_data):
                print(f"Duplicate found: {title}. Skipping...")
                continue
                
            # Grab some content if available, else fetch the link
            content = latest.get('description', '')
            if len(content) < 200:
                # Try to fetch the actual page for more context
                try:
                    res = requests.get(link, headers=headers, timeout=10)
                    soup = BeautifulSoup(res.content, 'html.parser')
                    paragraphs = soup.find_all('p')
                    content = ' '.join([p.text for p in paragraphs[:5]]) # First 5 paragraphs
                except Exception as e:
                    print(f"Failed to fetch full article {link}: {e}")
                    
            if len(content) > 100:
                return {
                    "source": source['name'],
                    "original_title": title,
                    "link": link,
                    "content": content
                }
        except Exception as e:
            print(f"Error scraping {source['name']}: {e}")
            
    return None

def rewrite_story(raw_story):
    prompt = f"""
    You are the Chief Electrical Engineer and Content Strategist for 'Abilene Electrical Contractors' (AECweb).
    You are writing a blog post based on the following industry news.
    Tone: Highly professional, industrial, authoritative, and focused on operational resilience.
    Focus on how this impacts commercial and industrial electrical infrastructure in Texas.
    
    Source Article Title: {raw_story['original_title']}
    Source Content: {raw_story['content']}
    
    Output your response strictly in the following JSON format, do not include any markdown blocks or other text:
    {{
        "title": "Your new highly engaging, authoritative title",
        "category": "Industrial Tech",
        "summary": "A 1-2 sentence punchy summary",
        "content": "The full rewritten article, at least 3 paragraphs. Use \\n\\n for paragraph breaks."
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        # Strip markdown if Gemini included it
        result_text = response.text.replace('```json', '').replace('```', '').strip()
        rewritten = json.loads(result_text)
        return rewritten
    except Exception as e:
        print(f"Error generating content with Gemini: {e}")
        return None

def run_sentinel():
    print("AECweb Sentinel Initiated.")
    
    story = get_latest_story()
    if not story:
        print("No fresh stories found today. Sentinel standing down.")
        return
        
    print(f"Processing story: {story['original_title']}")
    
    new_post = rewrite_story(story)
    if not new_post:
        print("Failed to rewrite story. Sentinel standing down.")
        return
        
    blog_data = load_blog()
    
    # Assign new ID
    new_id = 1
    if blog_data:
        new_id = max([p.get('id', 0) for p in blog_data]) + 1
        
    # Format Date
    today_str = datetime.now().strftime("%b %d, %Y")
    
    post_entry = {
        "id": new_id,
        "date": today_str,
        "category": new_post.get("category", "Industry News"),
        "title": new_post.get("title", story['original_title']),
        "summary": new_post.get("summary", ""),
        "content": new_post.get("content", ""),
        "original_title": story['original_title'],
        "image": "logo.png" # Placeholder image, you can integrate DALL-E later if desired
    }
    
    blog_data.insert(0, post_entry) # Put new post at the top
    save_blog(blog_data)
    
    print(f"SUCCESS: Added new article '{post_entry['title']}' to blog.json")

if __name__ == "__main__":
    run_sentinel()
