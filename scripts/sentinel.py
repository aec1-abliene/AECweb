import os
import json
import time
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
model = genai.GenerativeModel('gemini-2.5-flash')

# AECweb V2 Intelligence Sources
SOURCES = [
    {"name": "Utility Dive", "rss": "https://www.utilitydive.com/feeds/news/"},
    {"name": "Power Magazine", "rss": "https://www.powermag.com/feed/"},
    {"name": "Consulting-Specifying Engineer", "rss": "https://www.csemag.com/feed/"},
    {"name": "EC&M", "rss": "https://www.ecmweb.com/rss/articles"},
    {"name": "Electrical Contractor", "rss": "https://www.ecmag.com/rss.xml"}
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
    for post in blog_data[:20]:
        if title[:20].lower() in post.get("original_title", "").lower() or title[:20].lower() in post.get("title", "").lower():
            return True
    return False

def get_latest_stories():
    blog_data = load_blog()
    found_stories = []
    
    for source in SOURCES:
        print(f"Scanning {source['name']}...")
        try:
            feed = feedparser.parse(source['rss'])
            if not feed.entries:
                continue
                
            # Grab the top 3 stories from the feed to find one that isn't a duplicate
            for latest in feed.entries[:3]:
                title = latest.title
                link = latest.link
                
                if is_duplicate(title, blog_data) or is_duplicate(title, found_stories):
                    continue
                    
                content = latest.get('description', '')
                soup = BeautifulSoup(content, 'html.parser')
                clean_content = soup.get_text(separator=' ', strip=True)
                
                # Even a short 50 char teaser is enough for Gemini to extrapolate
                if len(clean_content) > 50:
                    found_stories.append({
                        "source": source['name'],
                        "original_title": title,
                        "link": link,
                        "content": clean_content[:1500]
                    })
                    break # Only grab 1 valid story per source
        except Exception as e:
            print(f"Error scanning {source['name']}: {e}")
            
    return found_stories

def rewrite_story(raw_story):
    prompt = f"""
    You are the Chief Electrical Engineer and Content Strategist for 'Abilene Electrical Contractors' (AECweb).
    You are writing a blog post based on the following industry news.
    Tone: Highly professional, industrial, authoritative, and focused on operational resilience.
    Focus on how this impacts commercial and industrial electrical infrastructure in Texas.
    
    Source Article Title: {raw_story['original_title']}
    Source Snippet: {raw_story['content']}
    
    Use your vast knowledge base to extrapolate the context of the snippet and write a full briefing.
    
    Output your response strictly in the following JSON format, do not include any markdown blocks or other text:
    {{
        "title": "Your new highly engaging, authoritative title",
        "category": "Industrial Tech",
        "summary": "A 1-2 sentence punchy summary",
        "content": "The full rewritten article, at least 2 paragraphs. Use HTML <br><br> tags for paragraph breaks instead of newlines."
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        result_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(result_text)
    except Exception as e:
        print(f"Error generating content with Gemini: {e}")
        return None

def run_sentinel():
    print("AECweb Sentinel V2 Initiated.")
    
    stories = get_latest_stories()
    if not stories:
        print("No fresh stories found today. Sentinel standing down.")
        return
        
    blog_data = load_blog()
    new_entries = []
    
    # Process only the best fresh story of the day to avoid flooding
    story = stories[0]
    print(f"Processing story: {story['original_title']}")
    
    new_post = rewrite_story(story)
    if new_post:
        new_id = 1
        if blog_data:
            new_id = max([p.get('id', 0) for p in blog_data]) + 1
            
        today_str = datetime.now().strftime("%b %d, %Y")
        
        # Convert <br> tags to standard newlines if Gemini used them
        content = new_post.get("content", "").replace('<br><br>', '\n\n')
        
        post_entry = {
            "id": new_id,
            "date": today_str,
            "category": new_post.get("category", "Industry News"),
            "title": new_post.get("title", story['original_title']),
            "summary": new_post.get("summary", ""),
            "content": content,
            "original_title": story['original_title'],
            "image": "logo.png"
        }
        
        blog_data.insert(0, post_entry)
        save_blog(blog_data)
        print(f"SUCCESS: Added new article '{post_entry['title']}' to blog.json")
    else:
        print("Failed to rewrite story. Sentinel standing down.")

if __name__ == "__main__":
    run_sentinel()
