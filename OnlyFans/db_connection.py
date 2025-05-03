# Magic cell to establish database connection
# %%capture
import sqlite3
import pandas as pd


conn = sqlite3.connect(
    r"F:\OF.DL\__user_data__\sites\OnlyFans\jameswithlola\Metadata\user_data.db"
)
cursor = conn.cursor()

# Test the connection
# %%capture
print("Database connected successfully!")

# Magic cell to list all tables in the database
# %%capture
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("\nAvailable tables in the database:")
for table in tables:
    print(table[0])
