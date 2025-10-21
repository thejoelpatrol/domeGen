#!/bin/bash
set -e

OUTFILE=${1}
MAIN_SECTION_SECONDS=${2}
SCRATCH_DIR=${3}
#SCRATCH_DIR=/Volumes/RAM_Disk_16GB
FADE_IN_SECONDS=35
FADE_IN_FRAMES=$((FADE_IN_SECONDS*30))
FADE_OUT_SECONDS=25
FADE_OUT_FRAMES=$((FADE_OUT_SECONDS*30))
TOTAL_LEN=$((FADE_IN_SECONDS+FADE_OUT_SECONDS+MAIN_SECTION_SECONDS))

./gen_circle_white.sh  ${FADE_IN_FRAMES} ${SCRATCH_DIR}
./gen_circle_black.sh ${FADE_OUT_FRAMES} ${SCRATCH_DIR}

magick -size 4096x4096 canvas:white ${SCRATCH_DIR}/white.png
ffmpeg -y -loop 1 -i ${SCRATCH_DIR}/white.png -t ${MAIN_SECTION_SECONDS} -r 30 -c:v libx265 -x265-params crf=20 -pix_fmt yuv420p -tag:v hvc1 "${SCRATCH_DIR}/white.mp4"

magick -size 4096x4096 canvas:black "${SCRATCH_DIR}/black.png"
ffmpeg -y -loop 1 -i "${SCRATCH_DIR}/black.png" -t ${TOTAL_LEN} -r 30 -c:v libx265 -x265-params crf=20 -pix_fmt yuv420p -tag:v hvc1 "${SCRATCH_DIR}/black.mp4"

echo "file ${SCRATCH_DIR}/white-circle.mp4" > ${SCRATCH_DIR}/mask-videos.txt
echo "file ${SCRATCH_DIR}/white.mp4" >> ${SCRATCH_DIR}/mask-videos.txt
echo "file ${SCRATCH_DIR}/black-circle.mp4" >> ${SCRATCH_DIR}/mask-videos.txt

ffmpeg -y -f concat -safe 0 -i "${SCRATCH_DIR}/mask-videos.txt" -c copy "${OUTFILE}"
