import argparse
import os
import shutil
import subprocess
import tempfile
import time

THREADS = 6

def extract_samples(infile: str, intermediate: str, n_frames: int, n_threads: int):
    ffmpeg_args = ["ffmpeg", "-y", "-i",  "pipe:0","-c:v", "libx264", "-r", "30", "-crf", "18", "-pix_fmt", "yuv420p", intermediate]
    ffmpeg = subprocess.Popen(ffmpeg_args, stdin=subprocess.PIPE)

    i = 0
    while i < n_frames:
        print(f"frames {i}--{i+n_threads}")
        vipses = []
        for j in range(n_threads):
            n = i + j


            vips_args = f"vips crop {infile} .ppm {n} {n} 8192 4096 | vips rotate stdin .ppm 180"
           # magick_args = ["magick", "infile",  "-crop", f"8192x4096+{n}+{n}", "ppm:-"]
            vipses.append(subprocess.Popen(vips_args, shell=True, stdout=subprocess.PIPE))

        for j in range(n_threads):
            vips = vipses[j]
            (stdout, stderr) = vips.communicate()
            ffmpeg.stdin.write(stdout)
        i += n_threads
    ffmpeg.stdin.close()
    ffmpeg.wait()


def domify(intermediate: str, dome_intermediate: str, outfile: str):
    if dome_intermediate:
        ffmpeg_args = f"ffmpeg -i {intermediate} -lavfi format=pix_fmts=rgb24,v360=input=equirect:output=fisheye:h_fov=180:v_fov=180:pitch=90 -y -c:v libx264 -r 30 -crf 18 -pix_fmt yuv420p {outfile}"
        with subprocess.Popen(ffmpeg_args.split()) as p:
            print(f"domifying to {outfile}")

    else:
        final_ffmpeg_args = f"ffmpeg -i pipe:0 -y -c:v libx264 -r 30 -crf 18 -pix_fmt yuv420p {outfile}"
        final_ffmpeg = subprocess.Popen(final_ffmpeg_args.split(), stdin=subprocess.PIPE)

        ffmpeg_args = f"ffmpeg -i {intermediate} -lavfi format=pix_fmts=rgb24,v360=input=equirect:output=fisheye:h_fov=180:v_fov=180:pitch=90 -f image2pipe -vcodec ppm pipe:1"
        ffmpeg = subprocess.Popen(ffmpeg_args.split(), stdout=subprocess.PIPE)
        while True:

            # save ffmpeg frame as tif
            # i don't want ffmpeg to do this itself because it will make too many, i rate limit it by reading from it
            p6 =  ffmpeg.stdout.readline()
            dimensions = ffmpeg.stdout.readline()
            maxval = ffmpeg.stdout.readline()
            width, height = dimensions.split()
            width = int(width)
            height = int(height)
            size = width * height * 3
            data = ffmpeg.stdout.read(size)
            tmp_dir = tempfile.gettempdir()
            new_dir = os.path.join(tmp_dir, str(time.time()))
            os.mkdir(new_dir)
            tmp_tif = os.path.join(new_dir, f"full.tif")
            magick_args = ["magick", "ppm:-", tmp_tif]
            with subprocess.Popen(magick_args, stdin=subprocess.PIPE) as magick:
                magick.communicate(p6 + dimensions + maxval + data)

            # split into 4 quadrants
            for i, (offset_x, offset_y) in enumerate([(0,0), (2048,0), (0,2048), (2048,2048)]):
                quarter = os.path.join(new_dir, f"q{i+1}.tif")
                vips_cmd = f"vips crop  {tmp_tif} {quarter}  {offset_x} {offset_y} 2048 2048"
                subprocess.check_call(vips_cmd.split())

            # skew top two qudrants
            q1 = os.path.join(new_dir, f"q1.tif")
            q1_skew = os.path.join(new_dir, f"q1_distort.tif")
            q1_args = ["magick", q1, "-virtual-pixel", "transparent", "+distort", "Perspective",  "0,0,0,0 \n2047,0,2247,0 \n 0,2047,0,2047 \n2047,2047,2047,2047", "-shave", "1x1", q1_skew]
            subprocess.check_call(q1_args)
            q2 = os.path.join(new_dir, f"q2.tif")
            q2_skew = os.path.join(new_dir, f"q2_distort.tif")
            q2_args = ["magick", q2, "-virtual-pixel", "transparent", "+distort", "Perspective",  "0,0,-200,0 \n2047,0,2047,0 \n 0,2047,0,2047 \n2047,2047,2047,2047", "-shave", "1x1", q2_skew]
            subprocess.check_call(q2_args)

            pto_file = os.path.join(new_dir, "project.pto")
            shutil.copyfile("project.pto", pto_file)
            hugin_cmd = f"hugin_executor --stitching --prefix {os.path.join(new_dir, 'blended')} {pto_file}"
            subprocess.check_call(hugin_cmd.split())

            read_ppm = subprocess.Popen(f"magick {os.path.join(new_dir, 'blended.tif')} ppm:-".split(), stdout=subprocess.PIPE)
            ppm, _ = read_ppm.communicate()
            final_ffmpeg.stdin.write(ppm)

            shutil.rmtree(new_dir)





def main():
    parser = argparse.ArgumentParser()
    #parser.add_argument("--from-macpaint", "-m", action="store_true", help="Convert from MacPaint to PNG")
    #parser.add_argument("--to-macpaint", "-p", action="store_true", help="Convert from PNG to MacPaint")
    parser.add_argument("--threads", type=int, default=THREADS)
    parser.add_argument("--dome-intermediate", default=None, help="first 360 mp4 file path; if omitted, uses pipe to next step")
    parser.add_argument("infile", help="Input tiff file path")
    parser.add_argument("frames", type=int, help="number of frames to extract from tiff")
    parser.add_argument("linear_intermediate", help="Linear mp4 file path")
    parser.add_argument("outfile", help="final 360 mp4 file path")

    args = parser.parse_args()

    #extract_samples(args.infile, args.intermediate, args.frames, args.threads)
    domify(args.linear_intermediate, args.dome_intermediate, args.outfile)

if __name__ == "__main__":
    main()