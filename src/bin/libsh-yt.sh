# Youtube utility functions and vars for yt-dlp bash scripts.
# Source this file to use it in your script e.g:  . ~/bin/libsh-yt.sh

. libsh-msg.sh

SUBS_FORMAT=srt  # default subtitle format
SUBS_LANG=en     # default subtitle language

# A var to add subtitles download to yt-dlp (remember --skip-download if needed):
SUBS_ARGS="--sub-langs $SUBS_LANG --write-auto-sub --sub-format $SUBS_FORMAT"

# Dump yt-dlp.conf for reference:
yt_dumpConf () {
	# dump my yt-dlp.conf config with default format etc:
	msg_usage "____________________"

	YTDLPCONF="$HOME/.config/yt-dlp.conf"

	# simply dump yt-dlp.conf:
	#msg_usage "Contents of yt-dlp config file $YTDLPCONF :"
	#cat "$YTDLPCONF"

	# dump yt-dlp.conf, stripping all comments and blank lines:
	msg_info "Args from $YTDLPCONF :"
	sed -e 's/#.*//' -e '/^$/d' "$YTDLPCONF"

	# remind user of options to use to download subtitles if wanted:
	msg_usage "Remember \$subs:  " "$SUBS_ARGS --skip-download"
}

# Validates if the exact 11-character string is a valid YouTube Video ID format
yt_isValidVideoID () { [[ "$1" =~ ^[a-zA-Z0-9_-]{11}$ ]] ; }

# Processes arguments, extracts potential IDs, and validates them
yt_fromArgs_VIDIDs () {
	local -n _result_array="$1" ; shift

	# Regex targets standard ID markers in various URL styles
	#local yt_regex='(?:v=|/v/|/embed/|/shorts/|youtu\.be/|^)([a-zA-Z0-9_-]{11})'
	# CRITICAL FIX: Ensure the pattern requires standard URL markers,
	# OR requires the string to be *exactly* an 11-character block from start to finish.
	local yt_regex='(?:v=|/v/|/embed/|/shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})|^[a-zA-Z0-9_-]{11}$'
	local found_count=0
	for arg in "$@"; do
		# Skip any command-line options starting with a dash (-)
		if [[ "$arg" == -* ]]; then
			continue
		fi
		# If the argument matches a YouTube URL or standard layout
		if echo "$arg" | grep -Pq "$yt_regex"; then
			# Extract only the 11-character block following the match
			local potential_id=$(echo "$arg" | grep -Po "$yt_regex" | grep -Po '[a-zA-Z0-9_-]{11}' | head -n 1)
			# verify video id:
			if yt_isValidVideoID "$potential_id"; then
				# Check if the ID already exists in the target array
				local is_duplicate=0
				for existing_id in "${_result_array[@]}"; do
					if [[ "$existing_id" == "$potential_id" ]]; then
						is_duplicate=1
						break
					fi
				done
				# Only add if it's a new, unique ID
				if (( is_duplicate == 0 )); then
					_result_array+=("$potential_id")
					((found_count++))
				fi
			fi
		fi
	done
	(( found_count > 0 )) && return 0 # Return success if at least one ID was found
	return 1 # Failure: No valid YouTube ID found
}

yt_lsFilesContainingIDs () {
	for i in $*; do
		msg_info "Files containing ID" "$i" ":"
		ls --time-style=+%Y%m%d\ %H:%M.%S -bvh --color -hsFl *$i*
	done
}

# Get array of subtitle files in current directory, given a Youtube video id, into SUBS_FILES array:
# (this is not a good example of a function, it should probably echo the list, but anyway...)
# Returns true if the array contains at least one value, false otherwise.
yt_getSubsFiles () {
	local VIDID=$1
	shopt -s nullglob
	SUBS_FILES=( *$VIDID*$SUBS_FORMAT )
	shopt -u nullglob
	(( ${#SUBS_FILES[@]} > 0 ))
}

# return true if we found (and attempted to process) at least 1 subs file:
yt_findAndConvertSubsFiles () {
	local next
	yt_getSubsFiles $VIDID && {
		# process all files we found:
		for next in "${SUBS_FILES[@]}"; do
			yt_convertSubsFileToTxt "$next"
		done
		ls -l *$VIDID*
		return 0
	}
	return 1
}

# convert 1 subtext file to text:
yt_convertSubsFileToTxt () {
	local inFile="$1"
	local outFile="$1".txt
	[[ ! -e "$outFile" ]] || {
		msg_warn "Output file " "'$outFile'" "already exists, doing nothing."
		return 1
	}

	# Use perl ("-P") regexp engine, in order to include:
	#  - characters from all languages ("\p{L}")
	#  - as well as all punctuation from all languages ("\p{P}")
	# in the character set to include:
	grep -P "^[\p{L}\p{P}]" "$inFile" > "$outFile"
	msg_info "Converted" ".$SUBS_FORMAT" "files to text, into output files with .txt extension."
}

