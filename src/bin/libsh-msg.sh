# Bash functions to echo errors, warnings etc, with some color

msg_error () { echo -e "ERROR: $1 \033[1;31;40m$2\033[0m ${@:3}" >&2 ; } # color: bold red text, black bg
msg_warn  () { echo -e "WARN:  $1 \033[33;40m$2\033[0m ${@:3}" >&2 ; }   # color: yellow text, black bg
msg_info  () { echo -e "INFO:  $1 \033[32;40m$2\033[0m ${@:3}" >&2 ; }   # color: green text, black bg
msg_debug () { echo -e "DEBUG: $1 \033[36;40m$2\033[0m ${@:3}" >&2 ; }   # color: cyan text, black bg

msg_cmd   () { echo -e "CMD:   \033[30;42m$1\033[0m ${@:2}" >&2 ; }  # color: black text, green bg

msg_usage () { echo -e "$1\033[32;40m$2\033[0m${@:3}" >&2 ; }  # color: green text, black bg

msg_text  () { echo -e "$*" >&2 ; }  # color: default

