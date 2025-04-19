from io import BytesIO
import os
import json
import random
import requests

from colorthief import ColorThief
from base64 import b64encode
from flask import Flask, Response, render_template, request

PLACEHOLDER_URL = "https://picsum.photos/300/300" # Changed size for consistency

FALLBACK_THEME = "spotify.html.j2"

NOW_PLAYING_URL = "https://api-spotifyx.notcoderguy.com/"

app = Flask(__name__)

def get(url):
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        # Consider more specific error handling or logging
        print(f"Failed to get data from {url}: {response.status_code}")
        # Return a default structure or raise a custom exception
        return None # Or raise specific exception

def extract_colors(albumArtURL, color_count):
    try:
        response = requests.get(albumArtURL, timeout=5) # Add timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        colortheif = ColorThief(BytesIO(response.content))
        palette = colortheif.get_palette(color_count)
        return palette
    except requests.exceptions.RequestException as e:
        print(f"Error fetching image for color extraction: {e}")
        return None # Return None or default colors
    except Exception as e:
        print(f"Error during color extraction: {e}")
        return None # Return None or default colors


def getTemplate(theme_name=None):
    try:
        with open("api/templates.json", "r") as file:
            templates_config = json.loads(file.read())

        available_templates = templates_config.get("templates", {})

        if theme_name and theme_name in available_templates:
            return available_templates[theme_name]
        else:
            # Fallback to current-theme if provided theme is invalid or None
            current_theme_name = templates_config.get("current-theme")
            if current_theme_name and current_theme_name in available_templates:
                return available_templates[current_theme_name]
            else:
                # Ultimate fallback
                print(f"Warning: Theme '{theme_name or current_theme_name}' not found or invalid. Falling back to {FALLBACK_THEME}")
                return FALLBACK_THEME

    except FileNotFoundError:
        print(f"Error: templates.json not found. Falling back to {FALLBACK_THEME}")
        return FALLBACK_THEME
    except json.JSONDecodeError:
        print(f"Error: Could not decode templates.json. Falling back to {FALLBACK_THEME}")
        return FALLBACK_THEME
    except Exception as e:
        print(f"Failed to load templates: {e}. Falling back to {FALLBACK_THEME}")
        return FALLBACK_THEME

def loadImageB64(url):
    try:
        response = requests.get(url, timeout=5) # Add timeout
        response.raise_for_status()
        return b64encode(response.content).decode("ascii")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching image for b64 encoding: {e}")
        return None # Return None or a default placeholder b64


def makeSVG(data, background_color, border_color, theme_name):
    # Determine status keyword
    if not data: # Handle case where data fetching failed
        print("No data received from Spotify API.")
        item = None
        currentStatus = "offline" # Use keyword
        image = None
        songPalette = None
        artistName = "N/A"
        songName = "N/A"
        songURI = "#"
        artistURI = "#"
    elif not data.get("is_playing", False): # Check if recently played
        currentStatus = "recent" # Use keyword
        item = data.get("item") if isinstance(data.get("item"), dict) else None
        if not item:
             print("Error: 'item' not found or invalid in recently played data.")
             # Keep status "recent" but details N/A
             item = None
             image = None
             songPalette = None
             artistName = "N/A"
             songName = "N/A"
             songURI = "#"
             artistURI = "#"
    else: # Currently playing
        item = data.get("item") if isinstance(data.get("item"), dict) else None
        if not item:
             print("Error: 'item' not found or invalid in currently playing data.")
             # Treat as offline if item is missing even if is_playing is true
             item = None
             currentStatus = "offline" # Use keyword
             image = None
             songPalette = None
             artistName = "N/A"
             songName = "N/A"
             songURI = "#"
             artistURI = "#"
        else:
            currentStatus = "playing" # Use keyword


    # Image and Color Extraction Logic (handles item being None)
    if item and item.get("album") and item["album"].get("images"):
        image_url = item["album"]["images"][1]["url"] # Use index 1 (medium size)
        image = loadImageB64(image_url)
        songPalette = extract_colors(image_url, 2) # Keep songPalette
    else:
        # Use placeholder URL directly for loading and color extraction
        image_url = PLACEHOLDER_URL
        image = loadImageB64(image_url) # Load placeholder b64
        songPalette = extract_colors(image_url, 2) # Extract colors from placeholder

    # Handle potential failure of loadImageB64 or extract_colors
    if image is None:
        print("Warning: Failed to load image (main or placeholder).")
        image = "" # Or some default
    if songPalette is None:
        print("Warning: Failed to extract colors. Using default.")
        songPalette = [(50, 50, 50), (100, 100, 100)] # Default colors


    # Extract other details safely, providing defaults if item is None
    # Use & for escaping ampersands in XML/HTML context
    artistName = item["artists"][0]["name"].replace("&", "&") if item and item.get("artists") else "Unknown Artist"
    songName = item["name"].replace("&", "&") if item and item.get("name") else "Unknown Song"
    songURI = item["external_urls"]["spotify"] if item and item.get("external_urls") else "#"
    artistURI = item["artists"][0]["external_urls"]["spotify"] if item and item.get("artists") and item["artists"][0].get("external_urls") else "#"


    dataDict = {
        "artistName": artistName,
        "songName": songName,
        "songURI": songURI,
        "artistURI": artistURI,
        "image": image,
        "status": currentStatus, # Pass the keyword
        "background_color": background_color,
        "border_color": border_color,
        "songPalette": songPalette # Keep songPalette
    }

    template_file = getTemplate(theme_name)
    return render_template(template_file, **dataDict)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
# @app.route('/with_parameters') # This route seems redundant with query params on root
def catch_all(path):
    background_color = request.args.get('background_color', '181414') # Use get with default
    border_color = request.args.get('border_color', '181414') # Use get with default
    theme_name = request.args.get('theme') # Get theme name, default handled by getTemplate

    data = get(NOW_PLAYING_URL) # Fetch data

    # Pass theme_name to makeSVG
    svg = makeSVG(data, background_color, border_color, theme_name)

    resp = Response(svg, mimetype="image/svg+xml")
    resp.headers["Cache-Control"] = "s-maxage=1, stale-while-revalidate" # Improved cache control

    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=os.getenv("PORT") or 5000)
