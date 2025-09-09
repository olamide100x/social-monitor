import requests
import sqlite3
import time
import re
from collections import Counter
from datetime import datetime, timedelta
import json
import logging
import os

# Setup logging for cloud
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CloudTrendMonitor:
    def __init__(self):
        self.db_path = 'trends.db'
        self.previous_trends = {}
        self.init_database()
        
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trends (
                id INTEGER PRIMARY KEY,
                word TEXT,
                count INTEGER,
                source TEXT DEFAULT 'reddit',
                timestamp TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                word TEXT,
                count INTEGER,
                change_percent REAL,
                alert_type TEXT,
                timestamp TEXT
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def clean_text(self, text):
        if not text:
            return []
        
        text = text.lower()
        
        # Extract hashtags
        hashtags = re.findall(r'#\w+', text)
        
        # Clean and extract words
        text = re.sub(r'http\S+|@\w+|\[.*?\]|\(.*?\)', '', text)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        
        # Filter stopwords
        stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 
                    'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day',
                    'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new',
                    'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'this',
                    'that', 'with', 'have', 'from', 'they', 'know', 'want',
                    'been', 'good', 'much', 'some', 'time', 'very', 'when',
                    'come', 'here', 'just', 'like', 'long', 'make', 'many',
                    'over', 'such', 'take', 'than', 'them', 'well', 'were',
                    'what', 'will', 'your', 'about', 'after', 'again', 'back',
                    'could', 'first', 'found', 'great', 'group', 'hand', 'high',
                    'keep', 'large', 'last', 'left', 'life', 'live', 'made',
                    'might', 'move', 'must', 'name', 'need', 'never', 'next',
                    'number', 'part', 'place', 'point', 'put', 'right', 'said',
                    'same', 'seem', 'small', 'still', 'tell', 'think', 'turn',
                    'use', 'want', 'way', 'where', 'which', 'work', 'world',
                    'year', 'young', 'reddit', 'comment', 'comments', 'post'}
        
        clean_words = [w for w in words if w not in stopwords and len(w) >= 4]
        
        return hashtags + clean_words
    
    def scrape_reddit(self):
        try:
            headers = {
                'User-Agent': 'CloudTrendMonitor/1.0 (Educational Project)'
            }
            
            # Get multiple subreddits for more diverse content
            subreddits = ['all', 'popular', 'worldnews', 'technology', 'science']
            all_words = []
            
            for subreddit in subreddits[:2]:  # Limit to avoid rate limits
                url = f'https://www.reddit.com/r/{subreddit}/hot.json?limit=25'
                
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    
                    for post in data['data']['children']:
                        post_data = post['data']
                        title = post_data.get('title', '')
                        selftext = post_data.get('selftext', '')
                        
                        words = self.clean_text(title + ' ' + selftext)
                        all_words.extend(words)
                
                time.sleep(1)  # Be nice to Reddit's servers
            
            logger.info(f"Scraped {len(all_words)} words from Reddit")
            return all_words
            
        except Exception as e:
            logger.error(f"Reddit scraping error: {e}")
            return []
    
    def detect_trends(self, current_words):
        if not current_words:
            return []
        
        current_counts = Counter(current_words)
        trends = []
        
        for word, count in current_counts.most_common(30):
            if count >= 2:  # Word must appear at least twice
                previous_count = self.previous_trends.get(word, 0)
                
                if previous_count == 0 and count >= 3:
                    # New trending word
                    trends.append({
                        'word': word,
                        'count': count,
                        'type': 'new',
                        'change': 0
                    })
                elif previous_count > 0:
                    # Calculate change
                    change_percent = ((count - previous_count) / previous_count) * 100
                    if change_percent >= 50:  # 50% increase threshold
                        trends.append({
                            'word': word,
                            'count': count,
                            'type': 'spike',
                            'change': change_percent
                        })
        
        # Update previous trends
        self.previous_trends = dict(current_counts.most_common(100))
        return trends
    
    def save_data(self, words, trends):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        
        # Save word counts
        word_counts = Counter(words)
        for word, count in word_counts.items():
            cursor.execute(
                "INSERT INTO trends (word, count, source, timestamp) VALUES (?, ?, ?, ?)",
                (word, count, 'reddit', timestamp)
            )
        
        # Save alerts for trending words
        for trend in trends:
            cursor.execute(
                "INSERT INTO alerts (word, count, change_percent, alert_type, timestamp) VALUES (?, ?, ?, ?, ?)",
                (trend['word'], trend['count'], trend['change'], trend['type'], timestamp)
            )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Saved {len(word_counts)} words and {len(trends)} alerts to database")
    
    def print_trends(self, trends):
        if not trends:
            logger.info("No significant trends detected")
            return
        
        logger.info("🔥 TRENDING WORDS:")
        for trend in trends[:10]:  # Top 10
            emoji = "🆕" if trend['type'] == 'new' else "📈"
            if trend['type'] == 'new':
                logger.info(f"{emoji} {trend['word']} - {trend['count']} mentions (NEW)")
            else:
                logger.info(f"{emoji} {trend['word']} - {trend['count']} mentions (+{trend['change']:.0f}%)")
    
    def run_cycle(self):
        logger.info("Starting trend monitoring cycle")
        
        # Scrape data
        words = self.scrape_reddit()
        
        if not words:
            logger.warning("No words collected, skipping cycle")
            return
        
        # Detect trends
        trends = self.detect_trends(words)
        
        # Save everything
        self.save_data(words, trends)
        
        # Log results
        self.print_trends(trends)
        
        logger.info(f"Cycle complete. Processed {len(words)} words, found {len(trends)} trends")
    
    def run_forever(self):
        logger.info("🚀 Cloud Trend Monitor started")
        
        while True:
            try:
                self.run_cycle()
                logger.info("💤 Sleeping for 10 minutes...")
                time.sleep(600)  # 10 minutes
                
            except KeyboardInterrupt:
                logger.info("👋 Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(60)  # Wait 1 minute before retry

if __name__ == "__main__":
    monitor = CloudTrendMonitor()
    monitor.run_forever()
