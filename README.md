# ytdlpz - yt-dlp wrapper(s)
============================

`yt-dlp` wrapper script, factored libsh-.. support fns, and symlinks for quick use.

Terminal output is partially colorized to highlight:

- the Youtube video IDs detected on the command line
- the (non-commented portion) content of `$HOME/.config/yt-dlp.conf`
- yt-dlp subtitle options reminder
- the actual command being run
- the resultant filename(s) downloaded

The download step shows a fixed-width 10 char progress bar.

![Simple terminal session for `ytl-dlpz` script](Screenshot-20261013.png)

The script symlink names are designed with the leading part optimized for qwerty keyboard and tab-expansion, to make it as quick as possible to download either high quality or low bitrate video.

The script supports symlinks `yth-dlpz` for default highest quality download, and `ytl-dlpz` for default lowest video bitrate + highest audio quality download.

I listen to a lot of music, and perhaps 1 in 4 vids I like to archive, but by default with the lowest bitrate video stream and highest quality audio stream - in the land of Youtube and yt-dlp, for audio streams, higher bitrate is considered higher quality, but for videos, better codec is considered better quality regardless of resolution or bitrate, which confused me for a long time until AI eventually explained that to me.

Sometimes I also like to download subtitles and just read them rather than listen to the video, and for that there is the symlink `ytp-srt+txt` which will if needed download an english `.srt` subtitles file (if there's not one in the current dir) and convert that .srt file to `.txt` . For conversion to text it uses `perl` which has full Unicode support, so should work reasonably well with all languages, not only English.

Also provided is my example `yt-dlp.conf` file, showing my current preferred output file format - I now include most characters so that foreign language filenames don't "collapse" down to a dot and a few underscores, but I still `"\s+" "_"` replace all whitespace with underscores.
And also in yt-dlp.conf is `--embed-chapters` which I only found recently, and is supported by e.g `mpv` - yee haw!

Here is the extract from my example yt-dlp.conf describing remuxing to add embedded chapters to a previously downloaded video:

```
# if e.g a music album has 'chapters' or 'tracks', the following option will embed them into the local file:
--embed-chapters
# but doing so requires mkv or mp4 container format, and mp4 will down-convert modern codecs, so just use mkv always!
# yt-dlp Disables Chapter Embedding for WebM (which is intended for html embedding)
# YouTube natively hosts its highest-quality video tracks as WebM (VP9/AV1) and its best audio tracks as WebM (Opus).
# If you tell yt-dlp to merge them into an MKV container, it pulls those identical, native WebM streams directly from YouTube and encapsulates them into an MKV wrapper without re-encoding them. MKV fully supports binary chapters, and mpv reads them perfectly.
--merge-output-format mkv

# If you've already downloaded say a music video, but did not use the --embed-chapters option,
# the currently downloaded file can be updated as follows:
# yt-dlp --remux-video mkv --embed-chapters VIDEO_ID
# --remux-video mkv changes the container to mkv (as needed), and --embed-chapters adds the chapter metadata.
# If you have an existing file, but it's not using your current filename format, you can do the remux and add metadata by specifying the existing filename as follows e.g:
# yt-dlp --remux-video mkv --embed-chapters -o "Your_Existing_Video_File.webm" "VIDEO_URL"
```

DEPENDENCIES
------------

- GNU Bash
- `yt-dlp`: these days with `yt-dlp` we sometimes have to use `secretstorage` (python) module to get browser cookies, which has to have the yt-dlp module in SAME environment as the secretstorage module; one way to do this is use pipx..., ultimately you need a working `yt-dlp` in your PATH, e.g:

```
   # This is just one way to make yt-dlp and modules it depends on, work:
   # as root:
   apt install pipx
   # as user, installing yt-dlp from pipx, then "injecting" the required dependencies:
   pipx install yt-dlp
   pipx inject yt-dlp secretstorage cryptography curl-cffi
```

FILES
-----
- [GitHub project](https://github.com/yt-dlp/yt-dlp)
- `ytdlpz` - the wrapper script
- `yth-dlpz` - symlink to quickly download max-quality video
- `ytl-dlpz` - symlink to quickly download min-bitrate video and max-quality audio
- `ytp-srt+txt` - symlink to convert `.srt` subtitle file to `.txt` file, downloading the .srt if needed

- `yt-dlp.conf` - example `~/.config/yt-dlp.conf` file

- `libsh-env.sh` - environment utils: `SCRIPT_DIR`
- `libsh-msg.sh` - output utils: `msg_error()`, `msg_info()` ...
- `libsh-yt.sh` - yt-dlp utils: `yt_isValidVideoID()` ...

DISCUSSION
----------

So I tried a number of ways to achieve "minimum bitrate" and "max quality" downloads, some of which you'll see in the "CUTS" comments in bin/ytdlpz, and here is what I settled on:

I want the `-F` "sorted" format output list, to somehow match my thinking, and make it quick and consistent to assess what's on the screen. To do this, we use yt-dlp's "-S" option to sort the output in two different ways depending on need.

Once the output is sorted according to the need, we simply download the "bv+ba" best video and best audio, in that sorted list - if the list preferences minimum bitrate, then the format with the lowest bitrate is considered "best", and we keep a "/b" best format as a fallback (still according to the sort we've chosen).

So to default to best quality, we sort in this order, first by
- `vcodec` video codec (whatever is yt-dlp's internal decision of codec ranking), next by
- `fps` frames per second, higher is "better", then by
- `vbr` video bitrate, higher is better, then by
- `lang:en` english language audio first, then by
- `abr` audio bitrate, higher is better

which looks like these command line options which are the default for the `yth-dlpz` command:
`-f bv+ba/b -S "vcodec,res,fps,vbr,lang:en,abr"`

Similarly, for lowest-bitrate video and best audio:
`-f bv+ba/b -S "+vbr,res,lang:en,abr"`

where, as the first sorting preference, you can see we use `vbr` for video bitrate (rather than codec as above), but also invert it (with a `+`) in order to reverse-sort by video bitrate, that is, to give us the LOWest bitrate video stream as the "best": `"+vbr,..."`.
