#!/bin/bash
set -e
#magick -size 4096x4096 canvas:black black.png
#ffmpeg -loop 1 -i black.png -t 480 -r 30  black.mp4

SCRATCH_DIR=/tmp
#SCRATCH_DIR=/Volumes/RAM_Disk_16GB
MAIN_SECTION_SECONDS=410

./gen_circle_black.sh 1040 ${SCRATCH_DIR}
./gen_circle_white.sh  1040 ${SCRATCH_DIR}

magick -size 4096x4096 canvas:white ${SCRATCH_DIR}/white.png
ffmpeg -loop 1 -i ${SCRATCH_DIR}/white.png -t ${MAIN_SECTION_SECONDS} -r 30 -c:v libx264 -crf 18 -pix_fmt yuv420p ${SCRATCH_DIR}/white.mp4

echo "file ${SCRATCH_DIR}/white-circle.mp4" > ${SCRATCH_DIR}/mask-videos.txt
echo "file ${SCRATCH_DIR}/white.mp4" >> ${SCRATCH_DIR}/mask-videos.txt
echo "file ${SCRATCH_DIR}/black-circle.mp4" >> ${SCRATCH_DIR}/mask-videos.txt

ffmpeg -f concat -safe 0 -i ${SCRATCH_DIR}/mask-videos.txt -c copy mask.mp4
