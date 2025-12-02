import random
import argparse
import sys
import time
import logging
import requests
import pychromecast
from pychromecast.discovery import CastBrowser, SimpleCastListener
import zeroconf
import threading
import struct
import signal
from urllib.parse import quote

# Default Stream (KOZT) 
DEFAULT_STREAM_URL = "http://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u"
DEFAULT_STREAM_TYPE = "audio/mp3" # Standard audio for Default Receiver
DEFAULT_IMAGE_URL = "https://kozt.com/wp-content/uploads/KOZT-Logo-No-Tag.png" # KOZT Logo
DEFAULT_TITLE = "KOZT - The Coast"

# Silent Audio for "No-Stream" Mode
SILENT_STREAM_URL = "https://github.com/anars/blank-audio/blob/master/10-minutes-of-silence.mp3?raw=true"

# Global state for signal handling
current_cast = None
current_browser = None
current_mc = None

def graceful_exit(signum, frame):
    """Handle kill signals (SIGINT/SIGTERM) robustly."""
    print("\nSignal received. Stopping playback...")
    try:
        if current_mc:
            current_mc.stop()
        if current_cast:
            current_cast.quit_app()
            time.sleep(1) # Ensure command leaves the network buffer
    except Exception as e:
        print(f"Error during cleanup: {e}")
    
    if current_browser:
        current_browser.stop_discovery()
        
    print("Exiting.")
    sys.exit(0)

def discover_all_chromecasts(timeout=5):
    """
    Discover all chromecasts on the network using CastBrowser directly.
    """
    found_chromecasts = []
    zconf = zeroconf.Zeroconf()
    listener = SimpleCastListener(lambda uuid, service: None)
    browser = CastBrowser(listener, zconf)
    browser.start_discovery()
    
    print(f"Scanning for devices ({timeout}s)...")
    time.sleep(timeout)
    
    for uuid, service in browser.devices.items():
        try:
             cc = pychromecast.get_chromecast_from_cast_info(service, zconf)
             found_chromecasts.append(cc)
        except Exception as e:
             logging.debug(f"Error creating Chromecast object for {uuid}: {e}")
             
    return found_chromecasts, browser

def resolve_playlist(url):
    """
    If the URL looks like a playlist (.m3u, .pls), try to fetch it 
    and extract the actual stream URL.
    """
    lower_url = url.lower()
    if not (lower_url.endswith('.m3u') or lower_url.endswith('.pls')):
        return url
        
    logging.debug(f"Resolving playlist URL: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.text
        
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if lower_url.endswith('.pls') and line.lower().startswith('file'):
                if '=' in line:
                    parts = line.split('=', 1)
                    if parts[1].lower().startswith('http'):
                        return parts[1].strip()

            if line.lower().startswith('http'):
                 return line
                 
    except Exception as e:
        print(f"Warning: Failed to resolve playlist: {e}")
        print("Using original URL.")
    
    return url

def fetch_album_art(artist, title):
    """
    Fetches album art URL using the iTunes Search API.
    """
    if not artist or not title:
        return None
        
    search_term = f"{artist} {title}"
    url = f"https://itunes.apple.com/search?term={quote(search_term)}&media=music&limit=1"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['resultCount'] > 0:
                artwork_url = data['results'][0].get('artworkUrl100')
                if artwork_url:
                    return artwork_url.replace('100x100bb', '600x600bb')
    except Exception as e:
        print(f"Error fetching album art: {e}")
    
    return None

def scrape_kozt_now_playing():
    """
    Fetches KOZT now playing data from the Amperwave JSON API.
    """
    try:
        url = "https://api-nowplaying.amperwave.net/api/v1/prtplus/nowplaying/10/4756/nowplaying.json"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        if "performances" in data and isinstance(data["performances"], list) and len(data["performances"]) > 0:
            current_track = data["performances"][0]
            
            song_title = current_track.get("title", "Unknown Song").strip()
            artist_name = current_track.get("artist", "Unknown Artist").strip()
            album_name = current_track.get("album", "").strip()
            
            image_url = current_track.get("largeimage") or \
                        current_track.get("mediumimage") or \
                        current_track.get("smallimage")
            
            return song_title, artist_name, image_url, album_name
            
        return None, None, None, None

    except Exception as e:
        logging.debug(f"Error fetching KOZT now playing JSON: {e}")
        return None, None, None, None

def update_media_metadata(mc, stream_url, stream_type, title, artist, album, image_url):
    """
    Updates the metadata on the Default Media Receiver.
    """
    print(f"Updating Metadata: {title} - {artist} (Album: {album})")
    
    metadata = {
        "metadataType": 3, # MUSIC_TRACK
        "title": title,
        "artist": artist,
        "albumName": album, # Displayed as Album
        "images": [{"url": image_url}] if image_url else []
    }
    
    try:
        mc.play_media(stream_url, stream_type, title=title, thumb=image_url, metadata=metadata)
    except Exception as e:
        print(f"Failed to update metadata: {e}")

def play_radio(device_name, stream_url, stream_type, default_title, default_image, is_kozt_station=False):
    global current_cast, current_browser, current_mc
    
    print(f"Searching for Chromecast: {device_name}...")
    chromecasts, browser = pychromecast.get_listed_chromecasts(friendly_names=[device_name])
    current_browser = browser
    
    if not chromecasts:
        print(f"Device '{device_name}' not found immediately. Scanning all devices...")
        chromecasts, browser = discover_all_chromecasts()
        current_browser = browser
        chromecasts = [cc for cc in chromecasts if cc.name == device_name]

    if not chromecasts:
        print(f"Error: Could not find Chromecast named '{device_name}'.")
        sys.exit(1)

    current_cast = chromecasts[0]
    current_cast.wait()
    print(f"Connected to {current_cast.name}!")

    current_mc = current_cast.media_controller
    
    # Initial Metadata
    current_title = "Live Radio"
    current_artist = ""
    current_album = ""
    current_image = default_image

    if is_kozt_station:
        kozt_title, kozt_artist, kozt_image, kozt_album = scrape_kozt_now_playing()
        if kozt_title and kozt_artist:
            current_title = kozt_title
            current_artist = kozt_artist
            current_album = kozt_album
            if kozt_image:
                current_image = kozt_image
            else:
                current_image = fetch_album_art(kozt_artist, kozt_title)
            print(f"Initial KOZT metadata: {current_title} - {current_artist} (Album: {current_album})")
    
    # Start Playback
    update_media_metadata(current_mc, stream_url, stream_type, current_title, current_artist, current_album, current_image)
    current_mc.block_until_active()
    print("Playback started!")
    
    # Monitor Loop
    last_title = current_title
    last_artist = current_artist
    
    while True:
        time.sleep(15) # Poll every 15 seconds
        
        if is_kozt_station or "kozt" in stream_url.lower():
            song_title, artist_name, fetched_image, album_name = scrape_kozt_now_playing()
            
            if song_title and artist_name: 
                    # Check if track changed
                    if song_title != last_title or artist_name != last_artist:
                        print(f"New Track Detected: {song_title} - {artist_name} (Album: {album_name})")
                        
                        last_title = song_title
                        last_artist = artist_name
                        
                        final_image = fetched_image if fetched_image else fetch_album_art(artist_name, song_title)
                        if not final_image:
                            final_image = default_image
                            
                        update_media_metadata(current_mc, stream_url, stream_type, song_title, artist_name, album_name, final_image)
        
        # Ensure connection
        if not current_cast.socket_client.is_connected:
            print("Connection lost. Exiting loop.")
            break

if __name__ == "__main__":
    # Register signal handlers for robust exit (especially for PyInstaller)
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    parser = argparse.ArgumentParser(description="Play KOZT Radio on Default Chromecast Receiver.")
    parser.add_argument("device_name", help="The friendly name of the Chromecast")
    parser.add_argument("-ns", "--no-stream", action="store_true", help="Display metadata only (play silent audio)")
    
    args = parser.parse_args()
    
    # Determine stream URL
    if args.no_stream:
        print("Mode: No-Stream (Metadata Only). Playing silent audio.")
        stream_url_to_play = SILENT_STREAM_URL
    else:
        stream_url_to_play = resolve_playlist(DEFAULT_STREAM_URL)
    
    try:
        while True:
            try:
                play_radio(args.device_name, stream_url_to_play, DEFAULT_STREAM_TYPE, DEFAULT_TITLE, DEFAULT_IMAGE_URL, True)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)
    except KeyboardInterrupt:
        graceful_exit(signal.SIGINT, None)
