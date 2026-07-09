import sqlite3

conn = sqlite3.connect("subscriptions.db")
cur = conn.cursor()
cur.execute("DROP TABLE IF EXISTS subscriptions")
cur.execute("DROP TABLE IF EXISTS users")
cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
""")
cur.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        due_date TEXT NOT NULL,
        category TEXT,
        user_id INTEGER NOT NULL,
        billing_cycle TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')
conn.commit()
conn.close()
print("DB setup complete with email!")