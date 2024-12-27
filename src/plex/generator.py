# src/plex/generator.py

import os
import re
import subprocess
import shutil
import glob
import sys
import struct
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import requests
from plexapi.server import PlexServer
from pymediainfo import MediaInfo
import gpustat

from src.config.settings import settings
from src.config.logger import logger
from src.metrics.db import insert_metric

FFMPEG_PATH = shutil.which("ffmpeg")
if not FFMPEG_PATH:
    logger.error('FFmpeg not found. Please install FFmpeg and ensure it is in your PATH.')
    sys.exit(1)

class PlexPreviewGenerator:
    def __init__(self):
        self.plex = self._connect_plex()

    def _connect_plex(self):
        """Connect to the Plex server."""
        sess = requests.Session()
        sess.verify = False
        try:
            plex = PlexServer(settings.PLEX_URL, settings.PLEX_TOKEN, timeout=settings.PLEX_TIMEOUT, session=sess)
            logger.info('Successfully connected to Plex server.')
            return plex
        except Exception as e:
            logger.error(f'Failed to connect to Plex Server: {e}')
            sys.exit(1)

    def detect_gpu(self):
        """Detect available GPUs (NVIDIA or AMD)."""
        # Detect NVIDIA GPUs
        try:
            import pynvml
            pynvml.nvmlInit()
            num_nvidia_gpus = pynvml.nvmlDeviceGetCount()
            pynvml.nvmlShutdown()
            if num_nvidia_gpus > 0:
                logger.info(f'Detected {num_nvidia_gpus} NVIDIA GPU(s).')
                return 'NVIDIA'
        except ImportError:
            logger.warning("NVIDIA GPU detection library (pynvml) not found.")
        except Exception as e:
            logger.warning(f"Error detecting NVIDIA GPUs: {e}")

        # Detect AMD GPUs
        try:
            from amdsmi import amdsmi_interface
            amdsmi_interface.amdsmi_init()
            devices = amdsmi_interface.amdsmi_get_processor_handles()
            found = False
            for device in devices:
                processor_type = amdsmi_interface.amdsmi_get_processor_type(device)
                if processor_type == amdsmi_interface.AMDSMI_PROCESSOR_TYPE_GPU:
                    found = True
                    break
            amdsmi_interface.amdsmi_shut_down()
            if found:
                vaapi_device_dir = "/dev/dri"
                if os.path.exists(vaapi_device_dir):
                    for entry in os.listdir(vaapi_device_dir):
                        if entry.startswith("renderD"):
                            logger.info(f'Detected AMD GPU device at {os.path.join(vaapi_device_dir, entry)}.')
                            return os.path.join(vaapi_device_dir, entry)
        except ImportError:
            logger.warning("AMD GPU detection library (amdsmi) not found.")
        except Exception as e:
            logger.warning(f"Error detecting AMD GPUs: {e}")

        logger.warning('No GPUs detected. Defaulting to CPU only.')
        return None

    def get_amd_ffmpeg_processes(self):
        """Retrieve running ffmpeg processes on AMD GPUs."""
        from amdsmi import amdsmi_interface
        try:
            amdsmi_interface.amdsmi_init()
            gpu_handles = amdsmi_interface.amdsmi_get_processor_handles()
            ffmpeg_processes = []

            for gpu in gpu_handles:
                processes = amdsmi_interface.amdsmi_get_gpu_process_list(gpu)
                for process in processes:
                    if process['name'].lower().startswith('ffmpeg'):
                        ffmpeg_processes.append(process)

            return ffmpeg_processes
        finally:
            amdsmi_interface.amdsmi_shut_down()

    def generate_images(self, video_file: str, output_folder: str, gpu: str):
        """Generate preview images using FFmpeg."""
        media_info = MediaInfo.parse(video_file)
        vf_parameters = f"fps=fps={round(1 / settings.PLEX_BIF_FRAME_INTERVAL, 6)},scale=w=320:h=240:force_original_aspect_ratio=decrease"

        # Adjust parameters for HDR formats
        if media_info.video_tracks:
            if media_info.video_tracks[0].hdr_format not in [None, "None"]:
                vf_parameters = (
                    f"fps=fps={round(1 / settings.PLEX_BIF_FRAME_INTERVAL, 6)},"
                    "zscale=t=linear:npl=100,format=gbrpf32le,"
                    "zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
                    "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"
                    "scale=w=320:h=240:force_original_aspect_ratio=decrease"
                )

        args = [
            FFMPEG_PATH, "-loglevel", "info", "-skip_frame:v", "nokey",
            "-threads:0", "1", "-i", video_file, "-an", "-sn", "-dn",
            "-q:v", str(settings.THUMBNAIL_QUALITY),
            "-vf", vf_parameters,
            f'{output_folder}/img-%06d.jpg'
        ]

        start_time = time.time()
        hw_accel_used = False

        if gpu == 'NVIDIA':
            gpu_stats = gpustat.new_query()
            ffmpeg_count = sum(1 for gpu_stat in gpu_stats for process in gpu_stat.processes if 'ffmpeg' in process.command.lower())
            logger.debug(f'FFmpeg GPU threads running: {ffmpeg_count}')
            if ffmpeg_count < settings.GPU_THREADS or settings.CPU_THREADS == 0:
                hw_accel_used = True
                args.insert(5, "-hwaccel")
                args.insert(6, "cuda")
        elif gpu:
            ffmpeg_processes = self.get_amd_ffmpeg_processes()
            logger.debug(f'FFmpeg GPU threads running: {len(ffmpeg_processes)}')
            if len(ffmpeg_processes) < settings.GPU_THREADS or settings.CPU_THREADS == 0:
                hw_accel_used = True
                args.extend(["-hwaccel", "vaapi", "-vaapi_device", gpu])
                # Adjust vf_parameters for AMD VAAPI
                vf_parameters = vf_parameters.replace(
                    "scale=w=320:h=240:force_original_aspect_ratio=decrease",
                    "format=nv12|vaapi,hwupload,scale_vaapi=w=320:h=240:force_original_aspect_ratio=decrease"
                )
                args[args.index("-vf") + 1] = vf_parameters

        logger.debug(f'Running FFmpeg command: {" ".join(args)}')
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Allow FFmpeg to start
        time.sleep(1)

        out, err = proc.communicate()
        if proc.returncode != 0:
            err_lines = err.decode('utf-8', 'ignore').split('\n')[-5:]
            logger.error(f'Error generating images for {video_file}: {err_lines}')
            return

        logger.debug('FFmpeg command output:')
        logger.debug(out)

        end_time = time.time()
        duration = round(end_time - start_time, 1)
        speed_matches = re.findall(r'speed= ?([0-9]+\.?[0-9]*|\.[0-9]+)x', err.decode('utf-8', 'ignore'))
        speed = float(speed_matches[-1]) if speed_matches else 1.0

        # Rename images
        for image in glob.glob(f'{output_folder}/img*.jpg'):
            frame_no = int(os.path.basename(image).strip('img-').strip('.jpg')) - 1
            frame_second = frame_no * settings.PLEX_BIF_FRAME_INTERVAL
            os.rename(image, os.path.join(output_folder, f'{frame_second:010d}.jpg'))

        logger.info(f'Generated Video Preview for {video_file} | HW Accel: {hw_accel_used} | Time: {duration}s | Speed: {speed}x')
        insert_metric(video_file, hw_accel_used, duration, speed)

    def generate_bif(self, bif_filename: str, images_path: str):
        """Build a .bif file from generated images."""
        magic = [0x89, 0x42, 0x49, 0x46, 0x0d, 0x0a, 0x1a, 0x0a]
        version = 0

        images = sorted([img for img in os.listdir(images_path) if img.endswith('.jpg')])

        with open(bif_filename, "wb") as f:
            f.write(bytearray(magic))
            f.write(struct.pack("<I", version))
            f.write(struct.pack("<I", len(images)))
            f.write(struct.pack("<I", 1000 * settings.PLEX_BIF_FRAME_INTERVAL))
            f.write(bytes([0x00] * 56))  # Padding to reach 64 bytes

            bif_table_size = 8 + (8 * len(images))
            image_index = 64 + bif_table_size
            timestamp = 0

            for image in images:
                image_path = os.path.join(images_path, image)
                statinfo = os.stat(image_path)
                f.write(struct.pack("<I", timestamp))
                f.write(struct.pack("<I", image_index))
                timestamp += 1
                image_index += statinfo.st_size

            f.write(struct.pack("<I", 0xffffffff))
            f.write(struct.pack("<I", image_index))

            for image in images:
                image_path = os.path.join(images_path, image)
                with open(image_path, "rb") as img_f:
                    f.write(img_f.read())

    def sanitize_path(self, path: str) -> str:
        """Sanitize file paths based on operating system."""
        return path.replace('\\', '/') if os.name == 'nt' else path

    def process_item(self, item_key: str, gpu: str):
        """Process a single Plex media item to generate previews."""
        data = self.plex.query(f'{item_key}/tree')

        for media_part in data.findall('.//MediaPart'):
            if 'hash' not in media_part.attrib:
                continue

            # Optional filtering by file path
            if len(sys.argv) > 1 and sys.argv[1] not in media_part.attrib['file']:
                continue

            bundle_hash = media_part.attrib['hash']
            media_file = self.sanitize_path(media_part.attrib['file'].replace(
                settings.PLEX_VIDEOS_PATH_MAPPING, settings.PLEX_LOCAL_VIDEOS_PATH_MAPPING
            ))

            if not os.path.isfile(media_file):
                logger.error(f'Skipping as file not found: {media_file}')
                continue

            try:
                bundle_file = f"{bundle_hash[0]}/{bundle_hash[1:]}.bundle"
            except Exception as e:
                logger.error(f'Error generating bundle file for {media_file}: {e}')
                continue

            bundle_path = self.sanitize_path(os.path.join(settings.PLEX_LOCAL_MEDIA_PATH, 'localhost', bundle_file))
            indexes_path = self.sanitize_path(os.path.join(bundle_path, 'Contents', 'Indexes'))
            index_bif = self.sanitize_path(os.path.join(indexes_path, 'index-sd.bif'))
            tmp_path = self.sanitize_path(os.path.join(settings.TMP_FOLDER, bundle_hash))

            if not os.path.isfile(index_bif):
                logger.debug(f'Generating bundle file for {media_file} at {index_bif}')

                os.makedirs(indexes_path, exist_ok=True)
                os.makedirs(tmp_path, exist_ok=True)

                try:
                    self.generate_images(media_file, tmp_path, gpu)
                except Exception as e:
                    logger.error(f'Error generating images for {media_file}: {e}')
                    shutil.rmtree(tmp_path, ignore_errors=True)
                    continue

                try:
                    self.generate_bif(index_bif, tmp_path)
                except Exception as e:
                    if os.path.exists(index_bif):
                        os.remove(index_bif)
                    logger.error(f'Error generating BIF for {media_file}: {e}')
                    continue
                finally:
                    shutil.rmtree(tmp_path, ignore_errors=True)

    def run(self, gpu: str):
        """Run the preview generation process for all media in Plex libraries."""
        for section in self.plex.library.sections():
            logger.info(f"Processing library: '{section.title}'")

            if section.type == 'episode':
                media = [m.key for m in section.search(libtype='episode')]
            elif section.type == 'movie':
                media = [m.key for m in section.search()]
            else:
                logger.info(f"Skipping unsupported library type '{section.type}' in library '{section.title}'.")
                continue

            logger.info(f"Found {len(media)} media file(s) in library '{section.title}'.")

            with ProcessPoolExecutor(max_workers=settings.CPU_THREADS + settings.GPU_THREADS) as executor:
                futures = [executor.submit(self.process_item, key, gpu) for key in media]
                for future in futures:
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Error processing media item: {e}")
