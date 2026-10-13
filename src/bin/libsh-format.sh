
format_bytes() {
    local bytes=$1
    local suffixes=('B' 'K' 'M' 'G' 'T' 'P')
    local i=0

    # Scale down by 1024 until the value fits neatly
    while (( bytes >= 1024 && i < 5 )); do
        (( bytes /= 1024 ))
        (( i++ ))
    done

    echo "${bytes}${suffixes[$i]}"
}

