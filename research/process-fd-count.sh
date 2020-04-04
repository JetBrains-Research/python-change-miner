FCOUNT=`lsof -p $1 | grep -v " txt " | wc -l`;echo "PID: $1 $FCOUNT" | sort -nk3

