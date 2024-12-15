import os
import sys
import re
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter import font as tkfont
from PIL import Image, ImageTk
import platform
import ctypes
from tkinterdnd2 import DND_FILES, TkinterDnD

try:
    from packaging import version
except ImportError:
    messagebox.showerror("错误", "缺少依赖库 'packaging'。请运行 'pip install packaging' 安装。")
    sys.exit(1)

PIL_VERSION = version.parse(Image.__version__)
if PIL_VERSION >= version.parse("10.0.0"):
    RESAMPLING_FILTER = Image.Resampling.LANCZOS
elif hasattr(Image, 'LANCZOS'):
    RESAMPLING_FILTER = Image.LANCZOS
else:
    RESAMPLING_FILTER = Image.ANTIALIAS

def set_fullscreen(root):
    system = platform.system()
    if system == "Windows":
        root.state('zoomed')
    elif system == "Darwin":
        root.attributes('-zoomed', True)
    else:
        root.attributes('-zoomed', True)
    root.resizable(True, True)

def natural_keys(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', os.path.basename(text))]

class ImageSlideshow:
    def __init__(self, root, folder_paths, interval, font_path, fullscreen=False):
        self.root = root
        self.folder_paths = folder_paths
        self.interval_seconds = tk.IntVar(value=interval // 1000)
        self.interval = self.interval_seconds.get() * 1000
        self.image_paths = []
        self.current_image_index = 0
        self.fullscreen = fullscreen
        self.is_running = True
        self.paused = False
        self.is_looping = True
        self.after_id = None
        self.operation_panel_visible = False

        self.default_font = self.load_custom_font(font_path, size=11)

        self.label = tk.Label(root, bg='black', font=self.default_font)
        self.label.pack(fill=tk.BOTH, expand=True)

        self.collect_images_from_folders()
        if not self.image_paths:
            messagebox.showerror("错误", "指定的文件夹中没有找到图片。")
            self.root.destroy()
            return

        self.root.update_idletasks()

        # 先创建操作面板，确保 current_image_label 已存在
        self.add_operation_panel()

        # 再显示第一张图片，以便 update_current_image_label() 可以正常工作
        self.show_image()

        self.root.bind("<Escape>", self.exit_slideshow)
        self.bind_keyboard_shortcuts()
        self.root.bind("<Motion>", self.on_mouse_move)
        self.operation_panel.bind("<Motion>", self.on_mouse_move)

    def load_custom_font(self, font_path, size=12):
        if font_path and platform.system() == "Windows":
            try:
                FR_PRIVATE = 0x10
                ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)
            except Exception as e:
                messagebox.showwarning("警告", f"无法加载字体文件: {e}")
        return tkfont.Font(family="Microsoft YaHei", size=size) if font_path else tkfont.Font(size=size)

    def collect_images_from_folders(self):
        for folder_path in self.folder_paths:
            self.collect_images_dfs(folder_path)

    def collect_images_dfs(self, current_path):
        try:
            entries = os.listdir(current_path)
        except PermissionError:
            return

        files = [entry for entry in entries if os.path.isfile(os.path.join(current_path, entry))]
        folders = [entry for entry in entries if os.path.isdir(os.path.join(current_path, entry))]

        for folder in sorted(folders, key=lambda x: natural_keys(os.path.join(current_path, x))):
            self.collect_images_dfs(os.path.join(current_path, folder))

        if not folders:
            for file in sorted(files, key=lambda x: natural_keys(x)):
                if self.is_image_file(file):
                    full_path = os.path.normpath(os.path.join(current_path, file))
                    folder_name = os.path.basename(os.path.normpath(current_path))
                    self.image_paths.append((full_path, folder_name))

    def is_image_file(self, filename):
        supported_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')
        return filename.lower().endswith(supported_extensions)

    def show_image(self):
        if not self.is_running:
            return

        if self.current_image_index >= len(self.image_paths):
            if self.is_looping:
                self.current_image_index = 0
            else:
                self.exit_slideshow()
                return

        image_path, folder_name = self.image_paths[self.current_image_index]
        try:
            img = Image.open(image_path)
            img = self.resize_image(img, self.root.winfo_width(), self.root.winfo_height())
            photo = ImageTk.PhotoImage(img)
            self.label.config(image=photo)
            self.label.image = photo

            image_name = os.path.basename(image_path)
            self.root.title(f"{folder_name} | {image_name}")

        except Exception as e:
            self.current_image_index += 1
            self.schedule_show_image()
            return

        self.current_image_index += 1

        if not self.paused:
            self.schedule_show_image()

        # 更新当前图片计数
        self.update_current_image_label()

    def schedule_show_image(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if self.is_running and not self.paused:
            self.after_id = self.root.after(self.interval, self.show_image)

    def resize_image(self, image, max_width, max_height):
        width, height = image.size
        ratio = min(max_width / width, max_height / height)
        if ratio <= 0:
            ratio = 1
        new_size = (int(width * ratio), int(height * ratio))
        return image.resize(new_size, RESAMPLING_FILTER)

    def exit_slideshow(self, event=None):
        self.is_running = False
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.root.destroy()

    def add_operation_panel(self):
        self.operation_panel = tk.Toplevel(self.root)
        self.operation_panel.overrideredirect(True)
        self.operation_panel.attributes('-topmost', True)
        self.operation_panel.attributes('-alpha', 0.8)
        self.operation_panel.configure(bg='black')

        main_frame = tk.Frame(self.operation_panel, bg='black')
        main_frame.pack(expand=True, pady=10, padx=10)

        # 当前放映张数 / 总张数标签
        self.current_image_label = tk.Label(main_frame, text="", font=self.default_font, bg='black', fg='white')
        self.current_image_label.pack(side=tk.LEFT, padx=5)

        # 间隔数字标签
        self.interval_label = tk.Label(main_frame, text=f"延迟 = {self.interval_seconds.get()}", font=self.default_font, bg='black', fg='white', width=8, anchor='w')
        self.interval_label.pack(side=tk.LEFT, padx=5)

        # 间隔滑条
        self.interval_scale = tk.Scale(
            main_frame,
            from_=1,
            to=60,
            orient=tk.HORIZONTAL,
            command=self.update_interval,
            font=self.default_font,
            bg='black',
            fg='white',
            highlightbackground='black',
            troughcolor='gray',
            length=100,
            showvalue = False
        )
        self.interval_scale.set(self.interval_seconds.get())
        self.interval_scale.pack(side=tk.LEFT, padx=5)

        self.prev_button = tk.Button(main_frame, text="上一张", command=self.show_previous, width=8, bg='lightgray', font=self.default_font)
        self.prev_button.pack(side=tk.LEFT, padx=5)

        self.pause_button = tk.Button(main_frame, text="暂停", command=self.toggle_pause, width=8, bg='lightgray', font=self.default_font)
        self.pause_button.pack(side=tk.LEFT, padx=5)

        self.next_button = tk.Button(main_frame, text="下一张", command=self.show_next, width=8, bg='lightgray', font=self.default_font)
        self.next_button.pack(side=tk.LEFT, padx=5)

        self.loop_button = tk.Button(main_frame, text="循环播放", command=self.toggle_loop, width=8, bg='lightgray', font=self.default_font)
        self.loop_button.pack(side=tk.LEFT, padx=5)

        self.exit_button = tk.Button(main_frame, text="退出播放", command=self.exit_slideshow, width=8, bg='lightgray', font=self.default_font)
        self.exit_button.pack(side=tk.LEFT, padx=5)

        self.update_operation_panel_position()
        self.root.bind("<Configure>", self.update_operation_panel_position)
        self.operation_panel.withdraw()

    def update_operation_panel_position(self, event=None):
        self.operation_panel.update_idletasks()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()

        panel_width = self.operation_panel.winfo_width()
        panel_height = self.operation_panel.winfo_height()

        panel_x = root_x + (root_width - panel_width) // 2
        panel_y = root_y + root_height - panel_height - 10
        self.operation_panel.geometry(f"+{panel_x}+{panel_y}")

    def toggle_loop(self):
        self.is_looping = not self.is_looping
        if self.is_looping:
            self.loop_button.config(text="循环播放")
        else:
            self.loop_button.config(text="播完退出")

    def toggle_pause(self):
        if self.paused:
            self.paused = False
            self.pause_button.config(text="暂停")
            self.schedule_show_image()
        else:
            self.paused = True
            self.pause_button.config(text="继续")
            if self.after_id:
                self.root.after_cancel(self.after_id)
                self.after_id = None

    def show_previous(self):
        if self.current_image_index > 0:
            self.current_image_index -= 2
            if self.current_image_index < 0:
                self.current_image_index = 0
            self.show_image()

    def show_next(self):
        self.show_image()

    def update_interval(self, value):
        try:
            new_interval = int(float(value))
            if new_interval > 0:
                self.interval_seconds.set(new_interval)
                self.interval = new_interval * 1000
                self.interval_label.config(text=f"延迟 = {new_interval}")
                if not self.paused:
                    self.schedule_show_image()
        except ValueError:
            pass

    def update_current_image_label(self):
        total = len(self.image_paths)
        current = self.current_image_index
        self.current_image_label.config(text=f"{current}/{total}")

    def bind_keyboard_shortcuts(self):
        self.root.bind("<Left>", lambda event: self.show_previous())
        self.root.bind("<Right>", lambda event: self.show_next())
        self.root.bind("<space>", lambda event: self.toggle_pause())
        self.root.bind("q", lambda event: self.exit_slideshow())

    def on_mouse_move(self, event):
        x_root, y_root = event.x_root, event.y_root
        window_x = self.root.winfo_rootx()
        window_y = self.root.winfo_rooty()
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()

        panel_x = self.operation_panel.winfo_rootx()
        panel_y = self.operation_panel.winfo_rooty()
        panel_width = self.operation_panel.winfo_width()
        panel_height = self.operation_panel.winfo_height()

        over_bottom = (window_x <= x_root <= window_x + window_width) and (y_root >= window_y + window_height - 50)
        over_panel = (panel_x <= x_root <= panel_x + panel_width) and (panel_y <= y_root <= panel_y + panel_height)

        if over_bottom or over_panel:
            self.show_operation_panel()
        else:
            self.hide_operation_panel()

    def show_operation_panel(self):
        if not self.operation_panel_visible:
            self.operation_panel.deiconify()
            self.operation_panel_visible = True

    def hide_operation_panel(self):
        if self.operation_panel_visible:
            self.operation_panel.withdraw()
            self.operation_panel_visible = False

class SlideshowApp:
    def __init__(self, root):
        self.root = root
        self.root.title("图片放映")
        self.root.geometry("600x600")
        self.root.minsize(600, 600)
        self.root.resizable(True, True)

        icon_path = self.resource_path("icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception as e:
                messagebox.showwarning("警告", f"无法加载图标文件: {e}")

        self.folder_paths = []
        self.interval = tk.IntVar(value=8)

        self.create_widgets()

        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)

    def resource_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def create_widgets(self):
        padding = {'padx': 10, 'pady': 10}
        default_font = ("微软雅黑", 11)

        folder_frame = tk.Frame(self.root)
        folder_frame.pack(fill=tk.BOTH, expand=True, **padding)

        folder_label = tk.Label(folder_frame, text="图片文件夹:", font=default_font)
        folder_label.pack(side=tk.TOP, anchor='w')

        self.folder_listbox = tk.Listbox(folder_frame, selectmode=tk.MULTIPLE, height=15, font=default_font)
        self.folder_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))

        button_frame = tk.Frame(folder_frame)
        button_frame.pack(side=tk.LEFT, fill=tk.Y)

        add_button = tk.Button(button_frame, text="添加文件夹", command=self.add_folder, font=default_font)
        add_button.pack(fill=tk.X, pady=(0,5))

        remove_button = tk.Button(button_frame, text="移除选中", command=self.remove_selected_folders, font=default_font)
        remove_button.pack(fill=tk.X, pady=(0,5))

        clear_button = tk.Button(button_frame, text="清空文件夹", command=self.clear_folders, font=default_font)
        clear_button.pack(fill=tk.X)

        interval_frame = tk.Frame(self.root)
        interval_frame.pack(fill=tk.X, **padding)

        interval_label = tk.Label(interval_frame, text="切换间隔 (秒):", font=default_font)
        interval_label.pack(side=tk.LEFT)

        interval_spinbox = tk.Spinbox(
            interval_frame,
            from_=1,
            to=60,
            increment=1,
            textvariable=self.interval,
            width=5,
            validate='all',
            validatecommand=(self.root.register(self.validate_interval), '%P'),
            font=default_font
        )
        interval_spinbox.pack(side=tk.LEFT, padx=5)

        start_button = tk.Button(
            self.root,
            text="开始播放",
            command=self.start_slideshow,
            bg='green',
            fg='white',
            font=("微软雅黑", 14)
        )
        start_button.pack(pady=20)

    def handle_drop(self, event):
        paths = self.root.splitlist(event.data)
        for path in paths:
            path = path.strip('{}')
            if os.path.isdir(path):
                if path not in self.folder_paths:
                    self.folder_paths.append(path)
                    self.folder_listbox.insert(tk.END, path)
                else:
                    messagebox.showinfo("信息", f"文件夹已添加: {path}")
            else:
                messagebox.showwarning("警告", f"已忽略非文件夹路径: {path}")

    def validate_interval(self, P):
        if P.isdigit() and int(P) > 0:
            return True
        elif P == "":
            return True
        else:
            return False

    def add_folder(self):
        selected_folder = filedialog.askdirectory(title="选择图片文件夹")
        if selected_folder:
            if selected_folder not in self.folder_paths:
                self.folder_paths.append(selected_folder)
                self.folder_listbox.insert(tk.END, selected_folder)
            else:
                messagebox.showinfo("信息", "文件夹已添加。")

    def remove_selected_folders(self):
        selected_indices = self.folder_listbox.curselection()
        if not selected_indices:
            return
        for index in reversed(selected_indices):
            self.folder_listbox.delete(index)
            del self.folder_paths[index]

    def clear_folders(self):
        self.folder_paths.clear()
        self.folder_listbox.delete(0, tk.END)

    def start_slideshow(self):
        if not self.folder_paths:
            messagebox.showerror("错误", "请先选择至少一个图片文件夹。")
            return

        interval_seconds = self.interval.get()
        if interval_seconds <= 0:
            messagebox.showerror("错误", "请输入一个有效的正整数作为时间间隔。")
            return

        sorted_folders = sorted(self.folder_paths, key=lambda x: natural_keys(x))
        slideshow_window = tk.Toplevel(self.root)
        set_fullscreen(slideshow_window)
        slideshow_window.configure(bg='black')

        font_path = self.resource_path("yahei.ttf")
        if not os.path.exists(font_path):
            font_path = None

        slideshow = ImageSlideshow(slideshow_window, sorted_folders, interval_seconds * 1000, font_path, fullscreen=True)

def main():
    try:
        import PIL
        from packaging import version
    except ImportError:
        messagebox.showerror("错误", "缺少依赖库。请确保已安装 Pillow 和 packaging。")
        sys.exit(1)

    root = TkinterDnD.Tk()
    app = SlideshowApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
