import os
import argparse
import time
import sys
import threading
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from PIL import Image
from pillow_heif import register_heif_opener
from tqdm import tqdm
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import imageio_ffmpeg

# Register HEIF opener with Pillow
register_heif_opener()

def get_ffmpeg_path():
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

def convert_image(args):
    """
    Worker function to convert a single image.
    args: tuple containing (source_path, output_folder, quality)
    """
    file_path, output_folder, quality = args
    try:
        path_obj = Path(file_path)
        output_filename = path_obj.stem + ".jpg"
        output_path = Path(output_folder) / output_filename
        
        image = Image.open(file_path)
        image.save(output_path, "JPEG", quality=quality)
        return True, file_path
    except Exception as e:
        return False, f"{file_path}: {e}"

def convert_video(args):
    """
    Worker function to convert a single video.
    args: tuple containing (source_path, output_folder, quality/codec settings)
    """
    file_path, output_folder, ffmpeg_path = args
    if not ffmpeg_path:
        return False, f"{file_path}: FFmpeg not found."

    try:
        path_obj = Path(file_path)
        output_filename = path_obj.stem + ".mp4"
        output_path = Path(output_folder) / output_filename
        
        # Simple FFmpeg command: convert to h264/aac
        cmd = [
            ffmpeg_path,
            '-y', # Overwrite
            '-i', file_path,
            '-vcodec', 'libx264',
            '-preset', 'ultrafast', # Speed up conversion significantly
            '-threads', '1', # Use 1 thread per worker to allow parallel workers
            '-acodec', 'aac',
            '-strict', 'experimental',
            str(output_path)
        ]
        
        # Run subprocess, suppress output
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if result.returncode == 0:
            return True, file_path
        else:
            return False, f"{file_path}: FFmpeg exited with code {result.returncode}"
            
    except Exception as e:
        return False, f"{file_path}: {e}"

def run_conversion(input_path, output_path, quality, workers, progress_callback=None):
    # Scan for files
    img_extensions = {'.heic', '.HEIC'}
    vid_extensions = {'.mov', '.MOV', '.qt', '.QT', '.mp4', '.MP4', '.m4v', '.M4V'} # Treat input mp4 as re-encode request if needed? Usually users want mov->mp4.
    
    # We will just convert what we find.
    
    files_to_process = []
    
    # Check if FFmpeg is available
    ffmpeg_exe = get_ffmpeg_path()
    
    for f in input_path.iterdir():
        if not f.is_file():
            continue
            
        if f.suffix in img_extensions:
            files_to_process.append(('img', (str(f), str(output_path), quality)))
        elif f.suffix in vid_extensions:
            if ffmpeg_exe:
                files_to_process.append(('vid', (str(f), str(output_path), ffmpeg_exe)))
            else:
                 # Skipping video if no ffmpeg, or simple log?
                 pass 

    count = len(files_to_process)
    if count == 0:
        return 0, [], "No convertible media files found."

    output_path.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    results = []
    
    # Process in parallel
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = []
        for kind, args in files_to_process:
            if kind == 'img':
                futures.append(executor.submit(convert_image, args))
            elif kind == 'vid':
                futures.append(executor.submit(convert_video, args))
                
        for i, future in enumerate(futures):
            res = future.result()
            results.append(res)
            if progress_callback:
                progress_callback(i + 1, count)

    duration = time.time() - start_time
    success_count = sum(1 for success, _ in results if success)
    errors = [msg for success, msg in results if not success]
    
    return success_count, errors, duration

class ConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Media Converter (HEIC/Video)")
        self.root.geometry("500x350")

        # Variables
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.status = tk.StringVar(value="Ready")
        
        # Styles
        padding = {'padx': 10, 'pady': 5}
        
        # Input
        frame_input = tk.Frame(root)
        frame_input.pack(fill='x', **padding)
        tk.Label(frame_input, text="Input Directory:").pack(anchor='w')
        tk.Entry(frame_input, textvariable=self.input_dir, width=50).pack(side='left', fill='x', expand=True)
        tk.Button(frame_input, text="Browse...", command=self.browse_input).pack(side='right')

        # Output
        frame_output = tk.Frame(root)
        frame_output.pack(fill='x', **padding)
        tk.Label(frame_output, text="Output Directory:").pack(anchor='w')
        tk.Entry(frame_output, textvariable=self.output_dir, width=50).pack(side='left', fill='x', expand=True)
        tk.Button(frame_output, text="Browse...", command=self.browse_output).pack(side='right')

        # Convert Button
        self.btn_convert = tk.Button(root, text="Start Conversion", command=self.start_thread, bg="#4CAF50", fg="white", font=("Arial", 12))
        self.btn_convert.pack(pady=20)

        # Progress
        self.progress = ttk.Progressbar(root, orient='horizontal', length=400, mode='determinate')
        self.progress.pack(**padding)
        
        # Status Label
        tk.Label(root, textvariable=self.status, fg="blue").pack(**padding)

    def browse_input(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_dir.set(folder)
            if not self.output_dir.get():
                self.output_dir.set(str(Path(folder) / "converted"))

    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir.set(folder)

    def start_thread(self):
        if not self.input_dir.get():
            messagebox.showerror("Error", "Please select an input directory.")
            return
        
        self.btn_convert.config(state='disabled')
        threading.Thread(target=self.process, daemon=True).start()

    def process(self):
        input_path = Path(self.input_dir.get())
        output_path = Path(self.output_dir.get())
        
        self.status.set("Scanning...")
        
        def update_progress(current, total):
            self.progress['maximum'] = total
            self.progress['value'] = current
            self.status.set(f"Converting: {current}/{total}")
            self.root.update_idletasks()

        try:
            success, errors, duration = run_conversion(
                input_path, output_path, 95, os.cpu_count(), update_progress
            )
            
            if isinstance(duration, str):
                 messagebox.showwarning("Result", duration)
                 self.status.set(duration)
            else:
                msg = f"Completed in {duration:.2f}s\nConverted: {success}"
                if errors:
                    msg += f"\nErrors: {len(errors)}"
                    print(errors)
                self.status.set("Done!")
                messagebox.showinfo("Success", msg)
                
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status.set("Error occurred")
            
        self.btn_convert.config(state='normal')

def main():
    # If no arguments provided (or just the script name), launch GUI
    if len(sys.argv) == 1:
        root = tk.Tk()
        app = ConverterGUI(root)
        root.mainloop()
        return

    # CLI Handling
    parser = argparse.ArgumentParser(description="Bulk HEIC to JPEG & Video Converter")
    parser.add_argument("input_dir", nargs='?', default=".", help="Directory containing media files (default: current directory)")
    parser.add_argument("-o", "--output_dir", help="Output directory (optional, defaults to input_dir/converted)")
    parser.add_argument("-q", "--quality", type=int, default=95, help="JPEG Quality (1-100, default 95)")
    parser.add_argument("-w", "--workers", type=int, default=os.cpu_count(), help="Number of parallel workers")

    args = parser.parse_args()

    input_path = Path(args.input_dir)
    if not input_path.exists():
        print(f"Error: Input directory '{args.input_dir}' does not exist.")
        return

    # Determine output directory
    if args.output_dir:
        output_path = Path(args.output_dir)
    else:
        output_path = input_path / "converted"

    print(f"Scanning {input_path}...")
    
    # CLI Logic Integration
    # We reuse run_conversion logic but need to adapt it slightly to show tqdm progress bar
    # Since run_conversion now does the futures execution internally with a simple callback, 
    # we can pass a tqdm updater as callback.
    
    img_extensions = {'.heic', '.HEIC'}
    vid_extensions = {'.mov', '.MOV', '.qt', '.QT', '.mp4', '.MP4', '.m4v', '.M4V'}
    ffmpeg_exe = get_ffmpeg_path()
    
    files_to_process = []
    for f in input_path.iterdir():
        if not f.is_file():
            continue
        if f.suffix in img_extensions:
            files_to_process.append(('img', (str(f), str(output_path), args.quality)))
        elif f.suffix in vid_extensions:
            if ffmpeg_exe:
                files_to_process.append(('vid', (str(f), str(output_path), ffmpeg_exe)))

    if not files_to_process:
        print(f"No files found in {input_path}")
        return

    print(f"Found {len(files_to_process)} media files. Converting to {output_path}...")
    output_path.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    
    # We can just use run_conversion logic inline for CLI to keep the fancy TPAQ bar on logic
    # Or cleaner: map callback to tqdm update
    
    pbar = tqdm(total=len(files_to_process), unit="file")
    
    def cli_callback(current, total):
        pbar.update(1)
        
    start_time = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = []
        for kind, task_args in files_to_process:
            if kind == 'img':
                futures.append(executor.submit(convert_image, task_args))
            elif kind == 'vid':
                futures.append(executor.submit(convert_video, task_args))
        
        results = []
        for future in futures:
            res = future.result()
            results.append(res)
            pbar.update(1)
            
    pbar.close()

    success_count = sum(1 for success, _ in results if success)
    errors = [msg for success, msg in results if not success]

    duration = time.time() - start_time
    print(f"\nConversion completed inside {duration:.2f} seconds.")
    print(f"Successfully converted: {success_count}/{len(files_to_process)}")
    
    if errors:
        print("\nErrors occurred:")
        for err in errors:
            print(err)

if __name__ == "__main__":
    main()
