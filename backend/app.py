import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
import requests

app = Flask(__name__)
# Enable CORS for all routes so the browser/frontend can fetch data
CORS(app, resources={r"/*": {"origins": "*"}})

MONGO_URI = os.getenv("MONGO_URI", "mongodb://movie-db:27017/movies_db")

client = MongoClient(MONGO_URI)
db = client.get_database("movies_db")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://movie-ai:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")

@app.route("/api/movies", methods=["GET"])
def get_movies():
    try:
        category = request.args.get("category", "").lower().strip()
        query = {"category": category} if category else {}
        
        # EXPLICITLY exclude _id from projection: {"_id": 0}
        movies = list(db.movies.find(query, {"_id": 0}))
        
        return jsonify({
            "category": category or "all",
            "count": len(movies),
            "movies": movies
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/category-details", methods=["GET"])
def get_category_details():
    """Use the local Ollama model to summarize movies in a category."""
    category = request.args.get("category", "").lower().strip()
    if not category:
        return jsonify({"error": "category is required"}), 400

    try:
        movies = list(db.movies.find({"category": category}, {"_id": 0}))
        if not movies:
            return jsonify({"category": category, "count": 0, "details": "No movies found in this category."}), 200

        movie_list = "\n".join(
            f"- {movie.get('title', 'Unknown title')} ({movie.get('year', 'year unknown')})"
            for movie in movies
        )
        prompt = (
            "You are a concise movie guide. Use only the movie titles and years provided; "
            "do not invent plot details. Describe what this category's selection has in common "
            "and mention each listed movie. Keep the answer under 100 words.\n"
            f"Category: {category}\nMovies:\n{movie_list}"
        )
        response = requests.post(
            f"{OLLAMA_URL.rstrip('/')}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        details = response.json().get("response", "").strip()
        return jsonify({"category": category, "count": len(movies), "details": details}), 200
    except requests.RequestException as e:
        app.logger.exception("Local AI service request failed")
        return jsonify({"error": "AI model is unavailable. Check that the model has been downloaded."}), 503
    except Exception as e:
        app.logger.exception("Could not generate category details")
        return jsonify({"error": "Could not generate category details."}), 500

if __name__ == "__main__":
    
    app.run(host="0.0.0.0", port=5000)
