from flask import Flask, render_template, jsonify
import sqlite3
import json
from datetime import datetime, timedelta
import os

app = Flask(__name__)

class CloudDatabase:
    def __init__(self):
        self.db_path = 'trends.db'
        self.init_db()
    
    def init_db(self):
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
    
    def get_recent_trends(self, hours=1):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute('''
            SELECT word, SUM(count) as total_count, source
            FROM trends 
            WHERE timestamp > ?
            GROUP BY word, source
            ORDER BY total_count DESC
            LIMIT 20
        ''', (cutoff,))
        
        results = cursor.fetchall()
        conn.close()
        return results

db = CloudDatabase()

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/trends/<timeframe>')
def get_trends(timeframe):
    hours_map = {'10min': 0.17, '1hour': 1, '6hour': 6, '24hour': 24}
    hours = hours_map.get(timeframe, 1)
    
    trends = db.get_recent_trends(hours)
    
    result = []
    for word, count, source in trends:
        result.append({
            'word': word,
            'count': count,
            'source': source,
            'emoji': '🔥' if count > 10 else '📈'
        })
    
    return jsonify(result)

@app.route('/api/stats')
def get_stats():
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    # Get total trends in last 24h
    cursor.execute('''
        SELECT COUNT(*) FROM trends 
        WHERE timestamp > datetime('now', '-24 hours')
    ''')
    total_trends = cursor.fetchone()[0]
    
    # Get unique words
    cursor.execute('''
        SELECT COUNT(DISTINCT word) FROM trends 
        WHERE timestamp > datetime('now', '-24 hours')
    ''')
    unique_words = cursor.fetchone()[0]
    
    # Get recent alerts
    cursor.execute('''
        SELECT COUNT(*) FROM alerts 
        WHERE timestamp > datetime('now', '-24 hours')
    ''')
    alerts_count = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_trends': total_trends,
        'unique_words': unique_words,
        'alerts_today': alerts_count,
        'status': 'active'
    })

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
