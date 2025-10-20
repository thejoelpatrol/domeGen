import argparse
import os
import shutil
import subprocess
import tempfile
import time
import sys
from concurrent.futures import ThreadPoolExecutor

THREADS = 6

def extract_samples(infile: str, intermediate: str, n_frames: int, n_threads: int):
    ffmpeg_args = ["ffmpeg", "-y", "-framerate", "30", "-i",  "pipe:0", "-c:v", "libx265", "-r", "30", "-x265-params", "crf=20", "-pix_fmt", "yuv420p", "-tag:v", "hvc1", intermediate]
    ffmpeg = subprocess.Popen(ffmpeg_args, stdin=subprocess.PIPE)

    i = 0
    while i < n_frames:
        print(f"frames {i}--{i+n_threads}")
        vipses = []
        for j in range(n_threads):
            n = i + j


            vips_args = f"vips crop {infile} .ppm {n} {n} 8192 4096 | vips rotate stdin .ppm 180"
            vipses.append(subprocess.Popen(vips_args, shell=True, stdout=subprocess.PIPE))

        for j in range(n_threads):
            vips = vipses[j]
            (stdout, stderr) = vips.communicate()
            ffmpeg.stdin.write(stdout)
        i += n_threads
    ffmpeg.stdin.close()
    ffmpeg.wait()

def process_frame(p6: bytes, dimensions: bytes, maxval: bytes, data: bytes, tmp_dir: str, enblend: bool = False) -> bytes:
    # honestly this is probably not a Linux or Mac thing, just the specific version of ImageMagick in my distro
    if sys.platform == "linux" or sys.platform == "linux2":
        magick_convert = "convert"
        magick_composite = "composite"
    elif sys.platform == "darwin":
        magick_convert = "magick"
        magick_composite = "magick composite"
    else:
        raise NotImplementedError("not tested on Windows. go ahead, if you like")

    new_dir = os.path.join(tmp_dir, str(time.time()))
    os.mkdir(new_dir)
    tmp_tif = os.path.join(new_dir, f"full.tif")
    magick_args = f"{magick_convert} ppm:-  {tmp_tif}".split()
    with subprocess.Popen(magick_args, stdin=subprocess.PIPE) as magick:
        magick.communicate(p6 + dimensions + maxval + data)

    # split into 4 quadrants
    for i, (offset_x, offset_y) in enumerate([(0,0), (2048,0)]):
        quarter = os.path.join(new_dir, f"q{i+1}.tif")
        vips_cmd = f"vips crop  {tmp_tif} {quarter}  {offset_x} {offset_y} 2048 2048"
        subprocess.check_call(vips_cmd.split())

    # skew top two qudrants
    q1 = os.path.join(new_dir, f"q1.tif")
    q1_skew = os.path.join(new_dir, f"q1_distort.tif")
    q1_args = [magick_convert, q1, "-virtual-pixel", "transparent", "+distort", "Perspective",  "0,0,0,0 \n2047,0,2247,0 \n 0,2047,0,2047 \n2047,2047,2047,2047", "-shave", "1x1", q1_skew]
    subprocess.run(q1_args)

    q2 = os.path.join(new_dir, f"q2.tif")
    q2_skew = os.path.join(new_dir, f"q2_distort.tif")
    q2_args = [magick_convert, q2, "-virtual-pixel", "transparent", "+distort", "Perspective",  "0,0,-200,0 \n2047,0,2047,0 \n 0,2047,0,2047 \n2047,2047,2047,2047", "-shave", "1x1", q2_skew]
    subprocess.run(q2_args)

    blended_outfile = os.path.join(new_dir, 'blended.tif')
    if enblend:
        # this "worked" in the sense that it used enblend to automatically blend the seam, and each frame looked good!
        # it did not "work" in the sense that even with the same control points on every frame, they didn't blend the same between frames, so it was flickering horribly
        pto_file = os.path.join(new_dir, "project.pto")
        shutil.copyfile("project.pto", pto_file)
        hugin_cmd = f"hugin_executor --stitching --prefix {os.path.join(new_dir, 'blended')} {pto_file}"
        subprocess.check_call(hugin_cmd.split())
    else:
        q2_masked = os.path.join(new_dir, "q2_distort_masked.tif")
        mask = os.path.join(new_dir, "q2-mask3.tif")
        shutil.copyfile("q2-mask3.tif", mask)
        subprocess.check_call(f"{magick_convert} {q2_skew} {mask} -alpha Off -compose CopyOpacity -composite {q2_masked}".split())
        top_2_quadrants = os.path.join(new_dir, "q1-2.tif")
        subprocess.check_call(f"{magick_convert} {q1_skew} {q2_masked} +smush -387 {top_2_quadrants}".split())
        subprocess.check_call(f"{magick_composite} {top_2_quadrants} {tmp_tif} -gravity NorthWest {blended_outfile}".split())

    # feed the frame back into the final video
    read_ppm = subprocess.Popen(f"vips copy {blended_outfile} .ppm".split(), stdout=subprocess.PIPE)
    ppm, _ = read_ppm.communicate()
    shutil.rmtree(new_dir)
    return ppm

def domify(intermediate: str, dome_intermediate: str, outfile: str, n_frames: int, n_threads: int, scratch_dir: str):
    if dome_intermediate:
        raise NotImplementedError("this part wasn't fleshed out because it was better to do it in memory one frame at a time")
        ffmpeg_args = f"ffmpeg -i {intermediate} -lavfi format=pix_fmts=rgb24,v360=input=equirect:output=fisheye:h_fov=180:v_fov=180:pitch=90 -y -c:v libx264 -r 30 -crf 18 -pix_fmt yuv420p {dome_intermediate}"
        with subprocess.Popen(ffmpeg_args.split()) as p:
            print(f"domifying to {outfile}")
    else:
        # this one makes the initial domification
        ffmpeg_args = f"ffmpeg -i {intermediate} -lavfi format=pix_fmts=rgb24,v360=input=equirect:output=fisheye:h_fov=180:v_fov=180:pitch=90 -f image2pipe -vcodec ppm pipe:1"
        ffmpeg = subprocess.Popen(ffmpeg_args.split(), stdout=subprocess.PIPE)

        # this one makes the blended output
        final_ffmpeg_args = f"ffmpeg -framerate 30 -i pipe:0 -y -r 30 -c:v libx265 -x265-params crf=20 -pix_fmt yuv420p -tag:v hvc1 {outfile}"
        final_ffmpeg = subprocess.Popen(final_ffmpeg_args.split(), stdin=subprocess.PIPE)

        with ThreadPoolExecutor(max_workers=n_threads) as thread_pool:
            i = 0
            while True:
                future_results = []
                for _ in range(n_threads):
                    #if i == n_frames:
                    #    print("## did all the frames!")
                    #    final_ffmpeg.stdin.close()
                    #    final_ffmpeg.wait()
                    #    #final_ffmpeg.terminate()
                    #    return
                    if ffmpeg.poll() is not None:
                        print("## domifier pipe output exited...")
                        final_ffmpeg.stdin.close()
                        final_ffmpeg.wait()
                        #final_ffmpeg.terminate()
                        return
                    # save ffmpeg frame as tif
                    # i don't want ffmpeg to do this itself because it will make too many, i rate limit it by reading from it
                    p6 =  ffmpeg.stdout.readline()
                    if len(p6) == 0:
                        print("didn't get anything from ffmpeg")
                        time.sleep(0.5)
                        continue
                    dimensions = ffmpeg.stdout.readline()
                    maxval = ffmpeg.stdout.readline()
                    width, height = dimensions.split()
                    width = int(width)
                    height = int(height)
                    size = width * height * 3
                    data = ffmpeg.stdout.read(size)

                    #ppm = process_frame(p6, dimensions, maxval, data)
                    future_results.append(thread_pool.submit(process_frame, p6, dimensions, maxval, data, scratch_dir, False))
                    i += 1

                for future in future_results:
                    ppm = future.result()
                    final_ffmpeg.stdin.write(ppm)



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, default=THREADS)
    parser.add_argument("--dome-intermediate", default=None, help="first 360 mp4 file path (deprecated, do not use); if omitted, uses pipe to next step")
    parser.add_argument("--scratch-dir", default=tempfile.gettempdir(), help="directory to save tiff frames for blending; RAM disk recommended")
    parser.add_argument("infile", help="Input tiff file path")
    parser.add_argument("frames", type=int, help="number of frames to extract from tiff")
    parser.add_argument("linear_intermediate", help="Linear mp4 file path")
    parser.add_argument("outfile", help="final 360 mp4 file path")

    args = parser.parse_args()

    start = time.time()

    extract_samples(args.infile, args.linear_intermediate, args.frames, args.threads)
    domify(args.linear_intermediate, args.dome_intermediate, args.outfile, args.frames, args.threads, args.scratch_dir)

    end = time.time()
    print(f"finished in {end - start} seconds")

if __name__ == "__main__":
    main()