from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
from datetime import datetime, timedelta
import psycopg2
import requests
import random

app = FastAPI()

# Replace with your actual database credentials
DB_CONFIG = {
    "dbname": "dsa_tracker_db",
    "user": "postgres",
    "password": "Makemake29@",
    "host": "localhost",
    "port": "5433"
}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/play")
def serve_frontend():
    return FileResponse("static/index.html")

@app.post("/sync-problems")
def sync_codeforces_problems():
    cf_url = "https://codeforces.com/api/problemset.problems"
    
    try:
        response = requests.get(cf_url, timeout=10)
        data = response.json()
        
        if data.get("status") != "OK":
            raise HTTPException(status_code=400, detail="Failed to fetch from Codeforces")
            
        all_problems = data["result"]["problems"]
        batch_data = []
        
        for p in all_problems:
            rating = p.get("rating")
            if not rating:
                continue 
                
            # Continuous Mathematical Scaling
            expected = int(10 + ((rating - 800) / 100) * 3.5)
            expected = max(10, expected) 
            hard = int(expected * 1.5)
                
            batch_data.append((
                p["contestId"], 
                str(p["index"]), 
                p["name"], 
                rating, 
                expected, 
                hard
            ))
        
        batch_data = batch_data[:1000] 
        
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail="Codeforces API is currently unreachable.")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO problems (cf_contest_id, cf_index, title, difficulty, expected_time_mins, hard_limit_mins)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (cf_contest_id, cf_index) DO NOTHING;
        """
        cursor.executemany(insert_query, batch_data)
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"status": "Success", "message": f"Successfully synced {len(batch_data)} rated problems!"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/unsolved-problems")
def get_unsolved_problems(user_id: int, limit: int = 100):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, difficulty, expected_time_mins, hard_limit_mins, cf_contest_id, cf_index
            FROM problems
            WHERE id NOT IN (
                SELECT problem_id FROM submissions 
                WHERE user_id = %s AND verdict = 'Accepted'
            )
            ORDER BY difficulty ASC
            LIMIT %s;
        """, (user_id, limit))
        
        problems = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [
            {
                "problem_id": p[0],
                "title": f"{p[1]} ({p[5]}{p[6]})",
                "difficulty": p[2],
                "expected_time": p[3],
                "hard_time": p[4]
            } for p in problems
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/sync-profile")
def sync_user_profile(user_id: int, cf_handle: str):
    try:
        # 1. Fetch ALL historical submissions from Codeforces
        cf_url = f"https://codeforces.com/api/user.status?handle={cf_handle}"
        response = requests.get(cf_url, timeout=15)
        data = response.json()
        
        if data.get("status") != "OK":
            raise HTTPException(status_code=400, detail="Failed to fetch from Codeforces")
        
        # 2. Filter out only the uniquely Accepted problems
        solved_problems = set()
        for sub in data.get("result", []):
            if sub.get("verdict") == "OK":
                prob = sub.get("problem", {})
                if "contestId" in prob and "index" in prob:
                    solved_problems.add((str(prob["contestId"]), str(prob["index"])))
        
        # 3. Cross-reference with our local database and mark them as solved
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        inserted_count = 0
        for cid, idx in solved_problems:
            # Check if we have this problem in our local DB
            cursor.execute("SELECT id FROM problems WHERE cf_contest_id = %s AND cf_index = %s", (cid, idx))
            prob_row = cursor.fetchone()
            
            if prob_row:
                prob_id = prob_row[0]
                # Check if it's already marked as solved for this user
                cursor.execute("SELECT id FROM submissions WHERE user_id = %s AND problem_id = %s AND verdict = 'Accepted'", (user_id, prob_id))
                if not cursor.fetchone():
                    # Insert a "ghost" submission so the matchmaker ignores it in the future
                    cursor.execute("""
                        INSERT INTO submissions (user_id, problem_id, mode, time_taken_seconds, verdict, rating_delta)
                        VALUES (%s, %s, 'sync', 0, 'Accepted', 0)
                    """, (user_id, prob_id))
                    inserted_count += 1
                    
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"status": "Success", "message": f"Successfully synced {inserted_count} past solved problems! The Matchmaker will now avoid these."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync error: {str(e)}")

@app.post("/start-match")
def start_match(user_id: int, mode: str, target_rating: Optional[int] = None, problem_id: Optional[int] = None):
    if mode not in ["focus", "chill"]:
        raise HTTPException(status_code=400, detail="Mode must be 'focus' or 'chill'")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("SELECT current_rating FROM users WHERE id = %s;", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        current_rating = user[0]

        if mode == "chill":
            if not problem_id:
                raise HTTPException(status_code=400, detail="Chill mode requires a specific problem_id.")
                
            cursor.execute("""
                SELECT id, title, difficulty, expected_time_mins, hard_limit_mins, cf_contest_id, cf_index 
                FROM problems WHERE id = %s
            """, (problem_id,))
            problem = cursor.fetchone()
            
            if not problem:
                raise HTTPException(status_code=404, detail="Problem not found.")
                
        elif mode == "focus":
            if target_rating == 0:
                cursor.execute("""
                    SELECT id, title, difficulty, expected_time_mins, hard_limit_mins, cf_contest_id, cf_index 
                    FROM problems 
                    WHERE id NOT IN (
                        SELECT problem_id FROM submissions WHERE user_id = %s AND verdict = 'Accepted'
                    )
                """, (user_id,))
            else:
                rating_to_use = target_rating if target_rating else current_rating
                cursor.execute("""
                    SELECT id, title, difficulty, expected_time_mins, hard_limit_mins, cf_contest_id, cf_index 
                    FROM problems 
                    WHERE difficulty >= %s AND difficulty <= %s
                    AND id NOT IN (
                        SELECT problem_id FROM submissions WHERE user_id = %s AND verdict = 'Accepted'
                    )
                """, (rating_to_use, rating_to_use + 200, user_id))
            
            suitable_problems = cursor.fetchall()
            if not suitable_problems:
                raise HTTPException(status_code=404, detail="No unsolved problems found for your criteria.")
                
            problem = random.choice(suitable_problems)

        prob_id, title, diff, exp_time, hard_time, cf_cid, cf_idx = problem
        
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

        now = datetime.now()

        return {
            "match_id": submission_id,
            "problem_name": f"{title} ({cf_cid}{cf_idx})",
            "difficulty": diff,
            "mode": mode,
            "expected_time_minutes": exp_time,
            "hard_time_minutes": hard_time,
            "server_start_time": now.isoformat(),
            "codeforces_url": f"https://codeforces.com/contest/{cf_cid}/problem/{cf_idx}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matchmaking error: {str(e)}")


@app.post("/submit")
def submit_match(match_id: int, gave_up: bool = False, cf_handle: Optional[str] = None):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Fetch match data
        cursor.execute("""
            SELECT s.user_id, s.problem_id, s.submitted_at, p.difficulty, u.current_rating, 
                   p.hard_limit_mins, p.cf_contest_id, p.cf_index 
            FROM submissions s 
            JOIN problems p ON s.problem_id = p.id 
            JOIN users u ON s.user_id = u.id
            WHERE s.id = %s AND s.verdict = 'Pending';
        """, (match_id,))
        match = cursor.fetchone()
        
        if not match:
            raise HTTPException(status_code=404, detail="Match not found.")

        # Verification Logic
        if not gave_up:
            if not cf_handle:
                raise HTTPException(status_code=400, detail="Codeforces handle required.")
            
            cf_url = f"https://codeforces.com/api/user.status?handle={cf_handle}&from=1&count=20"
            resp = requests.get(cf_url, timeout=10)
            data = resp.json()
            
            if data.get("status") != "OK":
                raise HTTPException(status_code=400, detail="Codeforces API error.")
            
            # Logic: Check recent 20 for an 'OK' verdict on this problem
            found = False
            for sub in data.get('result', []):
                prob = sub.get('problem', {})
                if str(prob.get('contestId')) == str(match[6]) and str(prob.get('index')) == str(match[7]):
                    if sub.get('verdict') == 'OK':
                        found = True
                        break
            
            if not found:
                # Instead of raising an exception here which causes a 500, return a clear 400
                raise HTTPException(status_code=400, detail="No 'Accepted' submission found for this problem on your recent Codeforces history.")
        # Elo Logic
        verdict = "Accepted" if not gave_up else "Failed (Gave Up)"
        delta = 40 * (1 - (1 / (1 + 10 ** ((match[3] - match[4]) / 400)))) if verdict == "Accepted" else -20
        
        # Calculate time taken
        time_taken_seconds = 0.0
        if match[2] is not None:
            time_taken_seconds = (datetime.now() - match[2]).total_seconds()
        time_taken_minutes = round(time_taken_seconds / 60, 2)
        
        # Compute new rating
        new_rating = round(max(0.0, match[4] + delta), 2)
        
        cursor.execute("""
            UPDATE submissions 
            SET verdict = %s, rating_delta = %s, time_taken_seconds = %s 
            WHERE id = %s
        """, (verdict, delta, time_taken_seconds, match_id))
        
        cursor.execute("""
            UPDATE users 
            SET current_rating = %s,
                peak_rating = GREATEST(COALESCE(peak_rating, 0), %s)
            WHERE id = %s
        """, (new_rating, new_rating, match[0]))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "verdict": verdict, 
            "rating_change": round(delta, 2),
            "time_taken_minutes": time_taken_minutes,
            "new_rating": new_rating
        }
        
    except HTTPException as he:
        # If it's an HTTPException, re-raise it so FastAPI handles it as a 400/404
        raise he
    except Exception as e:
        # If it's a real unexpected crash, log it and return 500
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
import bcrypt

@app.post("/register")
def register_user(username: str, password: str, cf_handle: str):
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (username, password_hash, cf_handle, current_rating, peak_rating) 
        VALUES (%s, %s, %s, 800.0, 800.0)
    """, (username, hashed, cf_handle))
    conn.commit()
    conn.close()
    return {"message": "User registered successfully"}

@app.post("/login")
def login(username: str, password: str):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    
    if user and user[1] and bcrypt.checkpw(password.encode('utf-8'), user[1].encode('utf-8')):
        return {"user_id": user[0], "message": "Login successful"}
    raise HTTPException(status_code=401, detail="Invalid username or password")