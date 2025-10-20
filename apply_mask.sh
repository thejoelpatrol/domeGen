#!/bin/bash

#diskutil erasevolume APFS RAM_Disk_8GB $(hdiutil attach -nomount ram://16777216)

MAIN_INFILE=${1}
MASK_INFILE=${2}
BLACK_INFILE=${3}
OUTFILE=${4}

ffmpeg -i "${MAIN_INFILE}" -i "${MASK_INFILE}" -i "${BLACK_INFILE}" -filter_complex "[1:v]format=gray[mask];
[0:v][mask]alphamerge[masked_fg];
[2:v][masked_fg]overlay=shortest=1[out]" -map "[out]" -r 30 -c:v libx265 -x265-params crf=20 -pix_fmt yuv420p -tag:v hvc1 "${OUTFILE}"