#!/bin/bash

FRAMES=${1}
SCRATCH_DIR=${2}
THREADS=10
PIXELS_PER_FRAME=2

for i in `seq 0 ${THREADS} ${FRAMES}`; do
	#echo i $i
	for j in `seq ${i} $(($i+$THREADS))`; do
		printf "circle frame %d\r" $j
		BOUNDARY=$(($PIXELS_PER_FRAME*$j+2047))
		FRAME=$(printf "%05d" $j)
		magick -size 4096x4096 canvas:black -fill white -draw "circle 2047.5,2047.5 ${BOUNDARY}.5,${BOUNDARY}.5" ${SCRATCH_DIR}/frame_${FRAME}.png &
	done

	wait $(jobs -rp)

done

echo ""

ffmpeg -y -r 30 -i ${SCRATCH_DIR}/frame_%05d.png -r 30 -c:v libx265 -x265-params crf=20 -pix_fmt yuv420p -tag:v hvc1 ${SCRATCH_DIR}/white-circle.mp4

rm ${SCRATCH_DIR}/frame_*.png &