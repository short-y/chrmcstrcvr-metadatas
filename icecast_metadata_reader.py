import requests
import argparse
import sys
import json
from urllib.parse import urlparse
import struct

def get_icecast_info(stream_url, parse_interleaved=True):
    """
    Reads a stream URL and attempts to extract Icecast-specific information:
    1. HTTP headers (Icy-*)
    2. Dynamic metadata from /status-json.xsl endpoint (if available)
    3. Interleaved metadata from the stream body (if Icy-MetaInt is present)
    """
    parsed_url = urlparse(stream_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    results = {}

    print(f"--- Inspecting: {stream_url} ---")
    
    # --- 1. Check HTTP Headers & Read Stream for Interleaved Metadata ---
    print("\nAttempting to retrieve Icecast headers and interleaved metadata...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; IcecastMetadataReader/1.0)',
        'Icy-MetaData': '1' # Request interleaved metadata
    }
    
    try:
        with requests.get(stream_url, headers=headers, stream=True, timeout=10) as r:
            r.raise_for_status()
            
            # Look for Icy- headers
            icy_headers = {k: v for k, v in r.headers.items() if k.lower().startswith('icy-')}
            if icy_headers:
                print("Found Icy- (HTTP) headers:")
                for k, v in icy_headers.items():
                    print(f"  {k}: {v}")
                    results[k] = v
            else:
                print("No Icy- headers found in HTTP response.")
                
            metaint = -1
            if 'icy-metaint' in r.headers:
                metaint = int(r.headers['icy-metaint'])
                results['Icy-MetaInt'] = metaint
                print(f"  Icy-MetaInt (Interleaved metadata interval): {metaint} bytes")
            
            # --- 3. Parse Interleaved Metadata (if enabled and present) ---
            if parse_interleaved and metaint > 0:
                print("\nAttempting to read interleaved metadata from stream body...")
                print("Reading audio chunks (this takes a moment)...")
                
                # We need to read exactly 'metaint' bytes of audio data
                # Then 1 byte for metadata length
                # Then (length * 16) bytes of metadata string
                
                # Read first chunk of audio (discarding it for this tool)
                # We use r.raw to read raw bytes
                audio_chunk = r.raw.read(metaint)
                if len(audio_chunk) < metaint:
                    print("Stream ended before first metadata interval.")
                    return results

                # Read metadata length byte
                length_byte = r.raw.read(1)
                if not length_byte:
                     print("Stream ended unexpectedly at metadata length byte.")
                     return results
                
                # The length byte represents how many 16-byte blocks follow
                length = struct.unpack('B', length_byte)[0] * 16
                
                if length > 0:
                    metadata_bytes = r.raw.read(length)
                    try:
                        # Metadata is usually "StreamTitle='...';StreamUrl='...';"
                        # decoding as utf-8, falling back to latin-1
                        metadata_str = metadata_bytes.decode('utf-8', errors='ignore') 
                        print(f"Found Interleaved Metadata (Raw): {metadata_str}")
                        
                        # Parse out StreamTitle
                        parts = metadata_str.split(';')
                        for part in parts:
                            if "StreamTitle=" in part:
                                title = part.split("StreamTitle=")[1].strip("'")
                                print(f"  --> Current Song: {title}")
                                results['StreamTitle'] = title
                    except Exception as e:
                        print(f"Error decoding metadata: {e}")
                else:
                    print("Metadata block found, but it was empty (no update).")

            elif metaint == -1:
                 print("No Icy-MetaInt header found. This stream does not support interleaved metadata.")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching stream headers/body: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


    # --- 2. Check for /status-json.xsl endpoint ---
    print(f"\nAttempting to retrieve /status-json.xsl from: {base_url}/status-json.xsl")
    status_json_url = f"{base_url}/status-json.xsl"
    try:
        response = requests.get(status_json_url, headers=headers, timeout=5)
        if response.status_code == 200:
            # Some servers return XML, not JSON, even for .xsl, so try parsing as JSON first
            try:
                status_data = response.json()
                print("Found /status-json.xsl (parsed as JSON):")
                if 'icestats' in status_data and 'source' in status_data['icestats']:
                    sources = status_data['icestats']['source']
                    if not isinstance(sources, list): sources = [sources]
                    
                    for source in sources:
                        print(f"  Mountpoint: {source.get('listenurl', 'N/A')}")
                        print(f"    Stream Title: {source.get('title', 'N/A')}")
                        print(f"    Stream Description: {source.get('description', 'N/A')}")
                else:
                    print(json.dumps(status_data, indent=2))
                results['status_json'] = status_data
            except json.JSONDecodeError:
                print("  /status-json.xsl returned non-JSON content.")
        else:
             print(f"  /status-json.xsl returned status code: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching /status-json.xsl: {e}")
    except Exception as e:
        print(f"An unexpected error occurred with /status-json.xsl: {e}")

    print("\n--- Inspection Complete ---")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect an internet radio stream for Icecast metadata.")
    parser.add_argument("stream_url", help="The URL of the internet radio stream.")
    
    args = parser.parse_args()
    
    get_icecast_info(args.stream_url)
