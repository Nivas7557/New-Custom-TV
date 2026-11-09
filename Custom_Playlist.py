import requests
import re
import os

# MULTI-SOURCE ENGINE: Combining Global Index and Telugu Language streams
GLOBAL_M3U_URL = "https://iptv-org.github.io/iptv/index.m3u"
TELUGU_M3U_URL = "https://iptv-org.github.io/iptv/languages/tel.m3u"
OUTPUT_FILE = "Custom_Playlist.m3u"
INPUT_TXT_FILE = "Channels.txt"

def load_channels_from_txt(file_path):
    """Reads the custom Channels.txt file and parses groups and channels structured in order."""
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return {}
        
    groups_dict = {}
    current_group = None
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Detect group headers like [Sports Channels]
            if line.startswith("[") and line.endswith("]"):
                current_group = line[1:-1].strip()
                groups_dict[current_group] = []
            elif current_group is not None:
                groups_dict[current_group].append(line)
                
    return groups_dict

def strict_clean(name):
    """Advanced normaliser that strips all country tags, bracket info, resolutions, and special characters."""
    if not name:
        return ""
    name = name.lower()
    # Removes all content inside parentheses entirely, e.g., (720p), (india)
    name = re.sub(r'\(.*?\)', '', name)
    # Strips country domain suffixes often found in global lists like .in, .us, .tv
    name = re.sub(r'\.in|\.us|\.tv|\.ua|\.ru|\.net|\.ke|\.et|\.do', '', name)
    # Strips all resolutions, quality descriptors, spaces, and punctuations
    name = re.sub(r'hd|sd|fhd|uhd|i|p|\s+|_|-|\+|&|,', '', name)
    return name.strip()

def process_m3u_source(url, lookup_table, final_playlist):
    """Downloads an M3U stream and filters it against the clean lookup table configuration."""
    try:
        print(f"Fetching source from: {url}")
        response = requests.get(url, timeout=60, stream=True)
        response.raise_for_status()
    except Exception as err:
        print(f"Error accessing stream source {url}: {err}")
        return final_playlist

    current_extinf = None
    vlc_options_buffer = []
    processed_urls = {item['url'] for item in final_playlist}

    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode('utf-8').strip()

        if line.startswith("#EXTM3U"):
            continue

        if line.startswith("#EXTINF:"):
            current_extinf = line
            vlc_options_buffer = []
        elif line.startswith("#EXTVLCOPT:"):
            vlc_options_buffer.append(line)
        elif not line.startswith("#"):
            if current_extinf and line not in processed_urls:
                source_channel_name = current_extinf.split(',')[-1].strip()
                clean_source_key = strict_clean(source_channel_name)
                
                matched_item = None
                for item in lookup_table:
                    if item["token"] in clean_source_key or clean_source_key in item["token"]:
                        matched_item = item
                        break
                
                if matched_item:
                    cleaned_metadata = re.sub(r'\s*group-title="[^"]+"', '', current_extinf)
                    final_metadata = re.sub(
                        r'^#EXTINF:([-0-9]*)', 
                        f'#EXTINF:\\1 group-title="{matched_item["group"]}" tvg-chno="{matched_item["number"]}"', 
                        cleaned_metadata
                    )
                    
                    final_playlist.append({
                        'metadata': final_metadata,
                        'options': list(vlc_options_buffer),
                        'url': line
                    })
                    processed_urls.add(line)
                
                current_extinf = None
                vlc_options_buffer = []
                
    return final_playlist

def fetch_and_filter_m3u():
    print(f"Loading configurations from '{INPUT_TXT_FILE}'...")
    groups_config = load_channels_from_txt(INPUT_TXT_FILE)
    
    if not groups_config:
        print("No channels found to filter. Exiting.")
        return
        
    config_lookup = []
    for g_idx, (group_name, channel_list) in enumerate(groups_config.items(), start=1):
        for ch_idx, original_name in enumerate(channel_list, start=1):
            clean_key = strict_clean(original_name)
            if clean_key:
                config_lookup.append({
                    "token": clean_key,
                    "group": group_name,
                    "number": (g_idx * 100) + ch_idx
                })
                
    playlist_payload = []
    
    # Run multi-source execution engine sequentially
    playlist_payload = process_m3u_source(TELUGU_M3U_URL, config_lookup, playlist_payload)
    playlist_payload = process_m3u_source(GLOBAL_M3U_URL, config_lookup, playlist_payload)

    # Compile the final structured M3U string array
    compiled_m3u = ["#EXTM3U"]
    for stream in playlist_payload:
        compiled_m3u.append(stream['metadata'])
        compiled_m3u.extend(stream['options'])
        compiled_m3u.append(stream['url'])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(compiled_m3u))
    print(f"Successfully processed list! Final combined playlist saved as: '{OUTPUT_FILE}'")

if __name__ == "__main__":
    fetch_and_filter_m3u()
