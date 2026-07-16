from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import FastAPI, HTTPException
from datetime import datetime, timedelta
import random
import psycopg2
import requests

app = FastAPI()

# Mount the static folder to serve web files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create a route that loads the frontend dashboard
@app.get("/play")
def serve_frontend():
    return FileResponse("static/index.html")

DB_CONFIG = {
    "dbname": "dsa_tracker_db",
    "user": "postgres",
    "password": "Makemake29@",  # <- Update this!
    "host": "127.0.0.1",                      # <- Change localhost to 127.0.0.1
    "port": "5433"
}

@app.get("/")
def read_root():
    return {"message": "Welcome to the DSA Rating API!"}

@app.post("/register")
def register_user(username: str, cf_handle: str):
    # 1. Verify the handle with Codeforces API
    cf_url = f"https://codeforces.com/api/user.info?handles={cf_handle}"
    
    try:
        response = requests.get(cf_url, timeout=5)
        cf_data = response.json()
        
        if cf_data.get("status") != "OK":
            raise HTTPException(status_code=400, detail="Codeforces handle not found.")
            
        # Extract details from Codeforces response
        user_info = cf_data["result"][0]
        # Default to 1200 if the user is unrated on Codeforces
        cf_rating = float(user_info.get("rating", 1200.0))
        
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail="Codeforces API is currently unreachable.")

    # 2. Insert the verified profile into PostgreSQL
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO users (username, cf_handle, current_rating, peak_rating)
            VALUES (%s, %s, %s, %s)
            RETURNING id, username, cf_handle, current_rating;
        """
        
        cursor.execute(insert_query, (username, cf_handle, cf_rating, cf_rating))
        new_user = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "status": "User registered successfully!",
            "user_id": new_user[0],
            "username": new_user[1],
            "cf_handle": new_user[2],
            "initial_rating": new_user[3]
        }
        
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=400, detail="Username or Codeforces handle already registered.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    
@app.post("/sync-problems")
def sync_codeforces_problems():
    cf_url = "https://codeforces.com/api/problemset.problems"
    
    try:
        # 1. Fetch data from Codeforces
        response = requests.get(cf_url, timeout=10)
        data = response.json()
        
        if data.get("status") != "OK":
            raise HTTPException(status_code=400, detail="Failed to fetch from Codeforces")
            
        all_problems = data["result"]["problems"]
        
        # 2. Filter and prepare the data
        batch_data = []
        for p in all_problems:
            rating = p.get("rating")
            
            # Skip problems that don't have a difficulty rating yet
            if not rating:
                continue 
                
           # Calculate the Unforgiving Timers mathematically
            # Base 10 mins + 3.5 mins for every 100 rating points above 800
            expected = int(10 + ((rating - 800) / 100) * 3.5)
            
            # Ensure no weird data gives less than 10 mins
            expected = max(10, expected) 
            
            # Hard limit is 1.5x the expected time
            hard = int(expected * 1.5)
                
            batch_data.append((
                p["contestId"], 
                str(p["index"]), 
                p["name"], 
                rating, 
                expected, 
                hard
            ))
        
        # We will grab just the 1000 most recent problems for this test 
        # so you don't have to wait 30 seconds for the database to process all 9,000+!
        batch_data = batch_data[:1000] 
        
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail="Codeforces API is currently unreachable.")

    # 3. Bulk insert into PostgreSQL
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # ON CONFLICT DO NOTHING ensures if we run this twice, it won't crash on duplicates
        insert_query = """
            INSERT INTO problems (cf_contest_id, cf_index, title, difficulty, expected_time_mins, hard_limit_mins)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (cf_contest_id, cf_index) DO NOTHING;
        """
        
        # executemany inserts the whole list in one massive chunk (very fast)
        cursor.executemany(insert_query, batch_data)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "status": "Success", 
            "message": f"Successfully synced {len(batch_data)} rated problems to the database!"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
@app.post("/start-match")
def start_match(user_id: int, mode: str = "focus"):
    # Ensure mode is valid
    if mode not in ["focus", "chill"]:
        raise HTTPException(status_code=400, detail="Mode must be 'focus' or 'chill'")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. Get the user's current rating
        cursor.execute("SELECT current_rating FROM users WHERE id = %s;", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        rating = user[0]

        # 2. Find a suitable problem (Targeting their rating up to +200 for a challenge)
        cursor.execute("""
            SELECT id, title, difficulty, expected_time_mins, hard_limit_mins, cf_contest_id, cf_index 
            FROM problems 
            WHERE difficulty >= %s AND difficulty <= %s
        """, (rating, rating + 200))
        
        suitable_problems = cursor.fetchall()
        if not suitable_problems:
            raise HTTPException(status_code=404, detail="No suitable problems found for your rating bracket.")
            
        # Pick a random problem from the valid list
        problem = random.choice(suitable_problems)
        prob_id, title, diff, exp_time, hard_time, cf_cid, cf_idx = problem

        # 3. Determine the time limit based on the mode
        time_limit = exp_time if mode == "focus" else hard_time
        
        # 4. Create a "Pending" submission in the history log
        insert_sub = """
            INSERT INTO submissions (user_id, problem_id, mode, time_taken_seconds, verdict)
            VALUES (%s, %s, %s, 0, 'Pending')
            RETURNING id;
        """
        cursor.execute(insert_sub, (user_id, prob_id, mode))
        submission_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()

        # Calculate exact server deadlines for the unforgiving timer
        now = datetime.now()
        deadline = now + timedelta(minutes=time_limit)

        return {
            "match_id": submission_id,
            "problem_name": f"{title} ({cf_cid}{cf_idx})",
            "difficulty": diff,
            "mode": mode,
            "time_limit_minutes": time_limit,
            "server_start_time": now.isoformat(),
            "server_deadline_time": deadline.isoformat(),
            "codeforces_url": f"https://codeforces.com/contest/{cf_cid}/problem/{cf_idx}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matchmaking error: {str(e)}")
    
@app.post("/submit")
def submit_match(match_id: int, completed_successfully: bool):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. Fetch the active match and related user/problem data
        cursor.execute("""
            SELECT s.user_id, s.problem_id, s.submitted_at, p.difficulty, u.current_rating, p.expected_time_mins 
            FROM submissions s
            JOIN problems p ON s.problem_id = p.id
            JOIN users u ON s.user_id = u.id
            WHERE s.id = %s AND s.verdict = 'Pending';
        """, (match_id,))
        
        match_data = cursor.fetchone()
        if not match_data:
            raise HTTPException(status_code=404, detail="Active match not found or already resolved.")
            
        user_id, problem_id, start_time, problem_rating, user_rating, expected_mins = match_data
        
        # 2. Calculate the exact time taken
        end_time = datetime.now()
        time_taken_seconds = (end_time - start_time).total_seconds()
        time_limit_seconds = expected_mins * 60
        
        # 3. Determine the Unforgiving Verdict
        if not completed_successfully:
            verdict = "Failed (Gave Up)"
            score = 0
        elif time_taken_seconds > time_limit_seconds:
            verdict = "Timeout (Solved too late)"
            score = 0
        else:
            verdict = "Accepted"
            score = 1
            
        # 4. The Elo Rating Math
        # Calculate Expected Probability (E) and apply the Rating Delta
        expected_probability = 1 / (1 + 10 ** ((problem_rating - user_rating) / 400))
        volatility_k = 40 
        
        rating_delta = volatility_k * (score - expected_probability)
        new_rating = user_rating + rating_delta
        
        # 5. Lock in the results to the database
        cursor.execute("""
            UPDATE submissions 
            SET verdict = %s, time_taken_seconds = %s, rating_delta = %s
            WHERE id = %s;
        """, (verdict, time_taken_seconds, rating_delta, match_id))
        
        # Update the user's profile with their new rating
        cursor.execute("""
            UPDATE users 
            SET current_rating = %s, peak_rating = GREATEST(peak_rating, %s)
            WHERE id = %s;
        """, (new_rating, new_rating, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "verdict": verdict,
            "time_taken_minutes": round(time_taken_seconds / 60, 2),
            "rating_change": round(rating_delta, 2),
            "new_rating": round(new_rating, 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Submission error: {str(e)}")