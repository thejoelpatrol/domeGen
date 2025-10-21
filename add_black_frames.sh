#!/bin/bash

set -o xtrace

INFILE=${1}
OUTFILE=${2}
SECONDS_BEGINNING=${3}
SECONDS_END=${4}
TMP_DIR=${5}

magick -size 4096x4096 canvas:black "${TMP_DIR}/black.png"

ffmpeg -y -loop 1 -i "${TMP_DIR}/black.png" -t ${SECONDS_BEGINNING} -r 30 -c:v libx265 -x265-params crf=20 -pix_fmt yuv420p -tag:v hvc1 "${TMP_DIR}/black1.mp4"
ffmpeg -y -loop 1 -i "${TMP_DIR}/black.png" -t ${SECONDS_END} -r 30 -c:v libx265 -x265-params crf=20 -pix_fmt yuv420p -tag:v hvc1 "${TMP_DIR}/black2.mp4"

echo "file ${TMP_DIR}/black1.mp4" > "${TMP_DIR}/black_files.txt"
echo "file ${INFILE}" >> "${TMP_DIR}/black_files.txt"
echo "file ${TMP_DIR}/black2.mp4" >> "${TMP_DIR}/black_files.txt"

ffmpeg -y -f concat -safe 0 -i "${TMP_DIR}/black_files.txt" -c copy "${OUTFILE}"
