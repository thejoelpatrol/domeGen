import argparse
import os
import shutil
import signal
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

THREADS = 4
TEXT_FILE = "/tmp/video_files.txt"
VERT_PIXELS=1250
PIXEL_INCREMENT=2
PAUSE_FRAMES=360

def gen_caption_frame(caption1: str, caption2: str, i: int, scratch_dir: str) -> bytes:
    y = 10 + i
    #file = os.path.join(scratch_dir, f"caption_{i}.tif")
    cmd = ["magick", "-size", "8192x4096", "xc:black",  "-font", "Chicago", "-pointsize", "96",  "-fill", "white",  "-draw", f"text 2000,{y} '{caption1}'",  "-draw", f"text 6000,{y} '{caption2}'", "ppm:"]

    read_ppm = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    ppm, _ = read_ppm.communicate()

    return ppm

def concat_videos(infile: str, caption_file: str, outfile: str):
    with open(TEXT_FILE, 'w') as f:
        f.write(f" file {infile}\n")
        f.write(f" file {caption_file}\n")
    cmd = f"ffmpeg -y -f concat -safe 0 -i {TEXT_FILE} -c copy {outfile}".split()
    subprocess.check_call(cmd)

def add_captions(caption1: str, caption2: str, infile: str, outfile: str, scratch_dir: str, n_threads: int, vert_pixels=VERT_PIXELS, increment=PIXEL_INCREMENT, pause_frames=PAUSE_FRAMES):
    tmp_file = os.path.join(scratch_dir, "linear-captions.mp4")
    tmp_file2 = os.path.join(scratch_dir, "dome-captions.mp4")

    ffmpeg_args = f"ffmpeg -framerate 30 -y -i pipe:0 -y -c:v libx265 -x265-params crf=20 -pix_fmt yuv420p -tag:v hvc1 {tmp_file}"
    ffmpeg = subprocess.Popen(ffmpeg_args.split(), stdin=subprocess.PIPE)
    with ThreadPoolExecutor(max_workers=n_threads) as thread_pool:
        i = 0
        while True:
            print(f"Adding vert_pixel {i}/{vert_pixels}")
            if i >= vert_pixels:
                break
            future_results = []
            for _ in range(n_threads):

                future_results.append(thread_pool.submit(gen_caption_frame, caption1, caption2, i, scratch_dir))
                i += increment

            for future in future_results:
                ppm = future.result()
                ffmpeg.stdin.write(ppm)

    for i in range(pause_frames):
        ffmpeg.stdin.write(ppm)
    ffmpeg.stdin.close()
    #ffmpeg.send_signal(signal.SIGINT)
    ffmpeg.wait()

    ffmpeg_args = f"ffmpeg -i {tmp_file} -y -lavfi format=pix_fmts=rgb24,v360=input=equirect:output=fisheye:h_fov=180:v_fov=180:pitch=90 -c:v libx265 -x265-params crf=20 -pix_fmt yuv420p -tag:v hvc1 {tmp_file2}"
    print(ffmpeg_args)
    subprocess.check_call(ffmpeg_args.split())

    concat_videos(infile, tmp_file2, outfile)
    #os.remove(tmp_file)
    print(f"wrote {outfile}")



def main():
    start = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-dir", default=tempfile.gettempdir(), help="directory to save intermediate videos")
    parser.add_argument("--threads", type=int, default=THREADS, help="number of cores to use")
    parser.add_argument("caption1")
    parser.add_argument("caption2")
    parser.add_argument("infile", help="Input domified mp4 file path")
    parser.add_argument("outfile", help="final 360 captioned mp4 file path")

    args = parser.parse_args()

    add_captions(args.caption1, args.caption2, args.infile, args.outfile, args.scratch_dir, args.threads)
    end = time.time()
    print(f"Total time: {int(end - start)} seconds")

if __name__ == "__main__":
    main()

