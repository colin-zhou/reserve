COLS=`cat file.txt | awk '{print NF}'`
COLS=$COLS-0
ROWS=`cat file.txt | wc -l`
ROWS=$ROWS-0
for i in `eval echo {0.."$COLS"}`
do 
    echo "one time enter"
    tstr=""
    j=1
    while read line
    do
        print $i
        one=`echo $line | awk '{print $i}'`
        echo line $line
        echo one $one
        if [ $j = "1" ];then
            tstr="$one"
        elif [ $j = $ROWS ];then
            tstr="$tstr $one\n"
        else
            tstr="$tstr $one"    
        fi
        ((j=j+1))
    done < file.txt
    echo $tstr
done

