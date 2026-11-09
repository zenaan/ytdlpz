#!/usr/bin/env python3

import json
import os
import sys
import subprocess
import shutil

def run_cmd(cmd, capture_output=False):
    """Helper to run a shell command."""
    try:
        res = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True if capture_output else False
        )
        return res.stdout if capture_output else True
    except subprocess.CalledProcessError as e:
        return None if capture_output else False

def get_configured_filename(video_id):
    """Queries yt-dlp to find the filename format specified in the user's config."""
    # Using --print filename forces yt-dlp to print the evaluated template name accurately
    cmd = [
        "yt-dlp",
        "--print", "filename",
        f"https://www.youtube.com/watch?v={video_id}"
    ]

    out = run_cmd(cmd, capture_output=True)
    if out:
        # Split lines and filter out any status logs/warnings that start with [
        lines = [line.strip() for line in out.split('\n') if line.strip() and not line.strip().startswith('[')]

        if lines:
            # Grab the actual filename template line
            final_line = lines[0]
            base, _ = os.path.splitext(final_line)
            return f"{base}.mkv"

    return None

def file_has_chapters(file_path):
    """Uses ffprobe to check if an existing file already contains chapter tracks."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_chapters",
        "-print_format", "json",
        file_path
    ]
    out = run_cmd(cmd, capture_output=True)
    if out:
        try:
            data = json.loads(out)
            return len(data.get('chapters', [])) > 0
        except json.JSONDecodeError:
            return False
    return False

def process_video(video_id, existing_file=None):
    print(f"\n=== Processing Video ID: {video_id} ===")

    # 1. Resolve your preferred output naming layout from ~/.config/yt-dlp.conf
    preferred_mkv = get_configured_filename(video_id)
    if not preferred_mkv:
        print("Warning: Could not read yt-dlp configuration format layout smoothly. Falling back to default.")
        preferred_mkv = f"{video_id}.mkv"

    # 2. Find the local file if not explicitly provided
    supported_exts = ['.webm', '.mp4', '.mkv']
    if not existing_file:
        for ext in supported_exts:
            potential_file = f"{video_id}{ext}"
            if os.path.exists(potential_file):
                existing_file = potential_file
                break

        if not existing_file:
            for f in os.listdir('.'):
                if video_id in f and any(f.endswith(ext) for ext in supported_exts):
                    existing_file = f
                    break

    if not existing_file or not os.path.exists(existing_file):
        print(f"Error: Could not find an existing local video file for ID '{video_id}'")
        return

    print(f"Found source video: {existing_file}")
    print(f"Target path template: {preferred_mkv}")
    if existing_file.endswith('.mkv') and file_has_chapters(existing_file):
        print(f"Skipping {existing_file}: Chapters are already embedded.")
        return

    # 3. Download metadata using yt-dlp
    print("Fetching live chapters, metadata, and thumbnail via yt-dlp...")
    json_name = f"{video_id}_temp"

    yt_dlp_cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-info-json",
        "--write-thumbnail",
        "-o", f"{json_name}.%(ext)s",
        f"https://www.youtube.com/watch?v={video_id}"
    ]

    if not run_cmd(yt_dlp_cmd):
        print("Failed to download metadata from YouTube.")
        return

    json_file = f"{json_name}.info.json"

    thumbnail_file = None
    for f in os.listdir('.'):
        if f.startswith(json_name) and f.endswith(('.jpg', '.jpeg', '.webp', '.png')):
            thumbnail_file = f
            break

    if not os.path.exists(json_file):
        print("Error: Expected metadata file was not generated.")
        return

    # 4. Load chapters and build standard FFMETADATA file
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    chapters = data.get('chapters', [])
    print(f"Extracted {len(chapters)} chapters from metadata.")

    ffmeta = ";FFMETADATA1\n"
    for ch in chapters:
        start_ms = int(ch['start_time'] * 1000)
        end_ms = int(ch['end_time'] * 1000)
        title = ch['title'].replace('=', '\\=').replace(';', '\\;').replace('#', '\\#').replace('\\', '\\\\')
        ffmeta += f"\n[CHAPTER]\nTIMEBASE=1/1000\nSTART={start_ms}\nEND={end_ms}\ntitle={title}\n"

    chapters_txt = f"{video_id}_chapters.txt"
    with open(chapters_txt, "w", encoding='utf-8') as f:
        f.write(ffmeta)

    # 5. Remux to MKV and inject chapters using FFmpeg
    print("Remuxing container to MKV and injecting chapters...")
    temp_mkv = f"{video_id}_temp.mkv"

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", existing_file,
        "-i", chapters_txt,
        "-map_metadata", "1",
        "-c", "copy",
        temp_mkv
    ]

    if not run_cmd(ffmpeg_cmd):
        print("FFmpeg remuxing and chapter insertion failed.")
        return

    # 6. Inject Cover Art using mkvpropedit
    if thumbnail_file and os.path.exists(thumbnail_file):
        print("Embedding thumbnail cover art...")
        mime_type = "image/jpeg" if thumbnail_file.endswith(('.jpg', '.jpeg')) else "image/webp"
        if thumbnail_file.endswith('.png'): mime_type = "image/png"

        mkvprop_cmd = [
            "mkvpropedit", temp_mkv,
            "--add-attachment", thumbnail_file,
            "--set-mime-type", mime_type,
            "--set-name", f"cover{os.path.splitext(thumbnail_file)}"
        ]
        run_cmd(mkvprop_cmd)

    # Ensure targeted output directory path layers exist seamlessly
    dest_dir = os.path.dirname(preferred_mkv)
    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    # Move temporary file to your exact configured naming scheme
    shutil.move(temp_mkv, preferred_mkv)

    # 7. Cleanup working file remnants and original videos
    print("Cleaning up temporary and source files...")
    garbage_files = [json_file, chapters_txt, thumbnail_file]
    for g_file in garbage_files:
        if g_file and os.path.exists(g_file):
            os.remove(g_file)

    # Remove original source file if it was converted/replaced
    if os.path.abspath(existing_file) != os.path.abspath(preferred_mkv):
        os.remove(existing_file)

    print(f"Success! Created: {preferred_mkv}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  ./embed_metadata.py <VIDEO_ID>")
        print("  ./embed_metadata.py <VIDEO_ID> <PATH_TO_EXISTING_FILE>")
        sys.exit(1)

    vid_id = sys.argv[1]
    file_path = sys.argv[2] if len(sys.argv) > 2 else None
    process_video(vid_id, file_path)

