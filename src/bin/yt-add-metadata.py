#!/usr/bin/env python3
import json
import os
import sys
import subprocess
import shutil
import re

def run_cmd(cmd, capture_output=False):
    """Helper to run a shell command and print detailed errors if it fails."""
    try:
        res = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE,
            text=True
        )
        return res.stdout if capture_output else True
    except subprocess.CalledProcessError as e:
        print(f"\n[COMMAND FAILED]: {' '.join(cmd)}")
        if e.stderr:
            print(f"[ERROR DETAILS]:\n{e.stderr.strip()}")
        return None if capture_output else False

def get_configured_filename(video_id):
    """Queries yt-dlp to find the filename format specified in the user's config."""
    cmd = [
        "yt-dlp",
        "--print", "filename",
        f"https://youtube.com/watch?v={video_id}"
    ]
    out = run_cmd(cmd, capture_output=True)
    if out:
        lines = [line.strip() for line in out.split('\n') if line.strip() and not line.strip().startswith('[')]
        if lines:
            final_line = lines[0]
            base, _ = os.path.splitext(final_line)
            return f"{base}.mkv"
    return None

def file_has_chapters(file_path):
    """Uses ffprobe to check if an existing file already contains chapter tracks."""
    safe_path = file_path if file_path.startswith(("./", "/")) else f"./{file_path}"
    cmd = [
        "ffprobe", "-v", "error",
        "-show_chapters",
        "-print_format", "json",
        safe_path
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

    # 3. Skip check if the existing file already contains chapters
    if file_has_chapters(existing_file):
        print(f"Skipping {existing_file}: Chapters are already embedded.")
        return

    print(f"Target path template: {preferred_mkv}")

    # Define all temporary paths cleanly with an underscore prefix to guard against leading dashes
    json_name = f"_{video_id}_temp"
    json_file = f"{json_name}.info.json"
    chapters_txt = f"_{video_id}_chapters.txt"
    temp_mkv = f"_{video_id}_temp.mkv"

    # 4. Download metadata using yt-dlp safely bypassing output conflicts
    print("Fetching live chapters, metadata, and thumbnail via yt-dlp...")
    yt_dlp_cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-info-json",
        "--write-thumbnail",
        "-o", f"./{json_name}.%(ext)s",
    ]

    if "QUIET_MODE" in globals() and QUIET_MODE:
        yt_dlp_cmd.append("--quiet")

    # Append the URL at the absolute end
    yt_dlp_cmd.extend(["--", f"https://youtube.com/watch?v={video_id}"])

    if not run_cmd(yt_dlp_cmd):
        print("Failed to download metadata from YouTube.")
        return

    # Find the downloaded thumbnail using our prefix variable structure
    thumbnail_file = None
    for f in os.listdir('.'):
        if f.startswith(json_name) and f.endswith(('.jpg', '.jpeg', '.webp', '.png')):
            thumbnail_file = f
            break

    if not os.path.exists(json_file):
        print("Error: Expected metadata configuration file was not generated.")
        return

    # 5. Load chapters and build standard FFMETADATA file
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

    with open(chapters_txt, "w", encoding='utf-8') as f:
        f.write(ffmeta)

    # 6. Remux to MKV and inject chapters using FFmpeg
    print("Remuxing container to MKV and injecting chapters...")
    safe_input_file = existing_file if existing_file.startswith(("./", "/")) else f"./{existing_file}"

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", safe_input_file,
        "-i", f"./{chapters_txt}",
        "-map_metadata", "1",
        "-c:v", "copy",
        "-c:a", "copy",
        f"./{temp_mkv}"
    ]

    if not run_cmd(ffmpeg_cmd):
        print("FFmpeg remuxing and chapter insertion failed.")
        return

    # 7. Inject Cover Art using mkvpropedit
    if thumbnail_file and os.path.exists(thumbnail_file):
        print("Embedding thumbnail cover art...")
        mime_type = "image/jpeg" if thumbnail_file.endswith(('.jpg', '.jpeg')) else "image/webp"
        if thumbnail_file.endswith('.png'): mime_type = "image/png"

        # FIX: The target file must be stated first.
        # Then, use explicit attachment parameter binding to cleanly bundle options.
        mkvprop_cmd = [
            "mkvpropedit", f"./{temp_mkv}",
            "--attachment-name", f"cover{os.path.splitext(thumbnail_file)[1]}",
            "--attachment-mime-type", mime_type,
            "--add-attachment", f"./{thumbnail_file}"
        ]
        run_cmd(mkvprop_cmd)

    # Ensure targeted output directory path layers exist seamlessly
    dest_dir = os.path.dirname(preferred_mkv)
    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    # Move temporary file to your exact configured naming scheme
    shutil.move(f"./{temp_mkv}", preferred_mkv)

    # 8. Cleanup working file remnants and original videos
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
    # Check if the user passed a quiet flag anywhere on the command line
    QUIET_MODE = "--quiet" in sys.argv
    if QUIET_MODE:
        sys.argv.remove("--quiet")

    if len(sys.argv) < 2:
        print("Usage: ./embed_metadata.py [--quiet] <file1.webm> <file2.mp4> ...")
        sys.exit(1)

    # Loop through every filename passed on the command line
    for file_path in sys.argv[1:]:
        if not os.path.exists(file_path):
            # Check if arg itself is an 11-char ID and resolve a match containing it
            if len(file_path) == 11 and not '.' in file_path:
                found = False
                for f in os.listdir('.'):
                    if file_path in f and any(f.endswith(ext) for ext in ['.webm', '.mp4', '.mkv']):
                        file_path = f
                        found = True
                        break
                if not found:
                    print(f"\nError: File or matching ID tracking reference not found: {file_path}")
                    continue
            else:
                print(f"\nError: File not found: {file_path}")
                continue

        # Extract 11-character YouTube video ID strictly surrounded by dots: .[ID].
        match = re.search(r'(?<=\.)([a-zA-Z0-9_-]{11})(?=\.)', os.path.basename(file_path))
        if not match:
            # Fallback check if the raw filename is exactly the 11 character ID or ID.ext
            base_name, _ = os.path.splitext(os.path.basename(file_path))
            if len(base_name) == 11:
                detected_id = base_name
            else:
                print(f"\nSkipping {file_path}: Could not find an 11-character YouTube ID surrounded by periods.")
                continue
        else:
            detected_id = match.group(1)

        process_video(detected_id, existing_file=file_path)

