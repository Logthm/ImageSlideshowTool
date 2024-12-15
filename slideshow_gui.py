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

# 检查 Pillow 版本并设置重采样过滤器
try:
    from packaging import version
except ImportError:
    messagebox.showerror("错误", "缺少依赖库 'packaging'。请运行 'pip install packaging' 安装。")
    sys.exit(1)

# 设置重采样过滤器
PIL_VERSION = version.parse(Image.__version__)
if PIL_VERSION >= version.parse("10.0.0"):
    RESAMPLING_FILTER = Image.Resampling.LANCZOS
elif hasattr(Image, 'LANCZOS'):
    RESAMPLING_FILTER = Image.LANCZOS  # Pillow 版本 < 10
else:
    RESAMPLING_FILTER = Image.ANTIALIAS  # 最后保底

def set_fullscreen(root):
    """
    将窗口设置为全屏模式，并允许调整大小
    """
    system = platform.system()
    if system == "Windows":
        root.state('zoomed')  # 最大化窗口
    elif system == "Darwin":  # macOS
        root.attributes('-zoomed', True)
    else:  # 其他系统，如Linux
        root.attributes('-zoomed', True)
    # 允许窗口调整大小
    root.resizable(True, True)

def natural_keys(text):
    """
    Splits the text into a list of strings and integers to achieve natural sorting.
    Example: "folder2" < "folder10"
    """
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', os.path.basename(text))]

class ImageSlideshow:
    def __init__(self, root, folder_paths, interval, font_path, fullscreen=False):
        self.root = root
        self.folder_paths = folder_paths  # 已排序的文件夹列表
        self.interval = int(interval * 1000)  # 转换为整数毫秒
        self.image_paths = []  # 存储 (image_path, folder_name) 的元组
        self.current_image_index = 0
        self.fullscreen = fullscreen
        self.is_running = True
        self.paused = False
        self.is_looping = True  # 默认启用循环播放
        self.after_id = None  # 跟踪调度ID
        self.operation_panel_visible = False  # 初始化操作面板可见性

        # 定义统一的字体
        self.default_font = self.load_custom_font(font_path, size=11)

        # 创建用于显示图片的标签
        self.label = tk.Label(root, bg='black', font=self.default_font)
        self.label.pack(fill=tk.BOTH, expand=True)

        # 收集图片
        self.collect_images_from_folders()
        if not self.image_paths:
            messagebox.showerror("错误", "指定的文件夹中没有找到图片。")
            self.root.destroy()
            return

        # 确保窗口已渲染，获取正确的宽度和高度
        self.root.update_idletasks()

        # 显示第一张图片
        self.show_image()

        # 绑定按键事件，允许用户在幻灯片模式下按 Esc 退出全屏
        self.root.bind("<Escape>", self.exit_slideshow)

        # 绑定键盘快捷键
        self.bind_keyboard_shortcuts()

        # 添加操作面板
        self.add_operation_panel()

        # 初始化鼠标活动监测，绑定到主窗口和操作面板
        self.root.bind("<Motion>", self.on_mouse_move)
        self.operation_panel.bind("<Motion>", self.on_mouse_move)

    def load_custom_font(self, font_path, size=12):
        """
        加载自定义字体文件并返回一个tkinter字体对象。
        """
        if platform.system() == "Windows":
            try:
                # 使用Windows API加载字体
                FR_PRIVATE = 0x10
                ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)
            except Exception as e:
                messagebox.showwarning("警告", f"无法加载字体文件: {e}")

        # 创建一个Tkinter字体对象
        return tkfont.Font(family="Microsoft YaHei", size=size)

    def collect_images_from_folders(self):
        """
        从多个文件夹收集图片路径，并记录每张图片所在的最小子文件夹名称
        """
        for folder_path in self.folder_paths:
            self.collect_images_dfs(folder_path)

    def collect_images_dfs(self, current_path):
        """
        深度优先收集图片路径，并记录每张图片所在的最小子文件夹名称
        """
        try:
            entries = os.listdir(current_path)
        except PermissionError:
            # 如果没有权限访问某个文件夹，则跳过
            return

        # 分离文件和文件夹，并按自然排序排序
        files = [entry for entry in entries if os.path.isfile(os.path.join(current_path, entry))]
        folders = [entry for entry in entries if os.path.isdir(os.path.join(current_path, entry))]

        # 按文件夹名称自然排序
        for folder in sorted(folders, key=lambda x: natural_keys(os.path.join(current_path, x))):
            self.collect_images_dfs(os.path.join(current_path, folder))

        # 如果没有子文件夹，收集当前文件夹中的图片
        if not folders:
            for file in sorted(files, key=lambda x: natural_keys(x)):
                if self.is_image_file(file):
                    full_path = os.path.normpath(os.path.join(current_path, file))
                    folder_name = os.path.basename(os.path.normpath(current_path))
                    self.image_paths.append((full_path, folder_name))
                    # 可选调试日志
                    # print(f"Collected image: {full_path} from folder: {folder_name}")

    def is_image_file(self, filename):
        """
        判断文件是否是支持的图片格式
        """
        supported_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')
        return filename.lower().endswith(supported_extensions)

    def show_image(self):
        """
        显示当前图片并安排下一张图片的显示
        """
        if not self.is_running:
            return

        if self.current_image_index >= len(self.image_paths):
            if self.is_looping:
                self.current_image_index = 0
                # 可选调试日志
                # print("循环播放启用，重置到第一张图片")
            else:
                self.exit_slideshow()
                return

        image_path, folder_name = self.image_paths[self.current_image_index]
        try:
            img = Image.open(image_path)
            # 调整图片大小以适应窗口，同时保持纵横比
            img = self.resize_image(img, self.root.winfo_width(), self.root.winfo_height())
            photo = ImageTk.PhotoImage(img)
            self.label.config(image=photo)
            self.label.image = photo
            # 可选调试日志
            # print(f"Displaying image: {image_path}")

            # 更新窗口标题为 "{folder_name} | {image_name}"
            image_name = os.path.basename(image_path)
            self.root.title(f"{folder_name} | {image_name}")

        except Exception as e:
            # 可选调试日志
            # print(f"无法打开图片 {image_path}: {e}")
            # 跳过此图片，继续播放下一张
            self.current_image_index += 1
            self.schedule_show_image()
            return

        self.current_image_index += 1

        if not self.paused:
            self.schedule_show_image()

    def schedule_show_image(self):
        """
        调度下一张图片的显示，防止多次调度
        """
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if self.is_running and not self.paused:
            self.after_id = self.root.after(self.interval, self.show_image)

    def resize_image(self, image, max_width, max_height):
        """
        调整图片大小以适应指定的最大宽度和高度，同时保持纵横比
        """
        width, height = image.size
        ratio = min(max_width / width, max_height / height)
        if ratio <= 0:
            ratio = 1  # 防止比率为零或负数
        new_size = (int(width * ratio), int(height * ratio))
        return image.resize(new_size, RESAMPLING_FILTER)

    def exit_slideshow(self, event=None):
        """
        退出幻灯片播放
        """
        self.is_running = False
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.root.destroy()

    def add_operation_panel(self):
        """
        在幻灯片窗口添加一个底部的浮动操作面板
        """
        # 创建操作面板 (Operation Panel) 作为独立的 Toplevel 窗口
        self.operation_panel = tk.Toplevel(self.root)
        self.operation_panel.overrideredirect(True)  # 移除窗口装饰
        self.operation_panel.attributes('-topmost', True)  # 确保操作面板在最前面
        self.operation_panel.attributes('-alpha', 0.8)  # 设置透明度为80%
        self.operation_panel.configure(bg='black')  # 背景色为黑色

        # 创建一个内部框架来承载按钮
        button_frame = tk.Frame(self.operation_panel, bg='black')
        button_frame.pack(expand=True, pady=10)

        # 创建按钮
        self.prev_button = tk.Button(button_frame, text="上一张", command=self.show_previous, width=10, bg='lightgray', font=self.default_font)
        self.pause_button = tk.Button(button_frame, text="暂停", command=self.toggle_pause, width=10, bg='lightgray', font=self.default_font)
        self.next_button = tk.Button(button_frame, text="下一张", command=self.show_next, width=10, bg='lightgray', font=self.default_font)
        self.set_interval_button = tk.Button(button_frame, text="切换间隔", command=self.set_interval, width=12, bg='lightgray', font=self.default_font)
        self.loop_button = tk.Button(button_frame, text="循环播放", command=self.toggle_loop, width=12, bg='lightgray', font=self.default_font)
        self.exit_button = tk.Button(button_frame, text="退出放映", command=self.exit_slideshow, width=12, bg='lightgray', font=self.default_font)

        # 布局按钮，使用水平排列并添加间距
        self.prev_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.pause_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.next_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.set_interval_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.loop_button.pack(side=tk.LEFT, padx=5, pady=5)  # 新增布局循环播放按钮
        self.exit_button.pack(side=tk.LEFT, padx=5, pady=5)

        # 定位操作面板在主窗口底部中央
        self.update_operation_panel_position()

        # 绑定主窗口移动和调整大小事件，以同步操作面板的位置
        self.root.bind("<Configure>", self.update_operation_panel_position)

        # 初始隐藏操作面板
        self.operation_panel.withdraw()

    def update_operation_panel_position(self, event=None):
        """
        更新操作面板的位置，使其位于主窗口底部中央
        """
        # 获取主窗口的位置和大小
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()

        # 获取操作面板的大小
        self.operation_panel.update_idletasks()  # 确保获取到正确的宽度和高度
        panel_width = self.operation_panel.winfo_width()
        panel_height = self.operation_panel.winfo_height()

        # 计算操作面板的位置
        panel_x = root_x + (root_width - panel_width) // 2
        panel_y = root_y + root_height - panel_height - 10  # 距离底部10像素

        # 设置操作面板的位置
        self.operation_panel.geometry(f"+{panel_x}+{panel_y}")

    def toggle_loop(self):
        """
        切换循环播放状态，并更新按钮文本
        """
        self.is_looping = not self.is_looping
        if self.is_looping:
            self.loop_button.config(text="循环播放")
            # 可选调试日志
            # print("循环播放已启用")
        else:
            self.loop_button.config(text="播完退出")
            # 可选调试日志
            # print("循环播放已禁用，播完将退出")

    def toggle_pause(self):
        """
        切换暂停和继续播放
        """
        if self.paused:
            self.paused = False
            self.pause_button.config(text="暂停")
            # 可选调试日志
            # print("播放已继续")
            self.schedule_show_image()
        else:
            self.paused = True
            self.pause_button.config(text="继续")
            if self.after_id:
                self.root.after_cancel(self.after_id)
                self.after_id = None
            # 可选调试日志
            # print("播放已暂停")

    def show_previous(self):
        """
        显示上一张图片
        """
        if self.current_image_index > 0:
            self.current_image_index -= 2  # 因为 show_image 会增加1
            if self.current_image_index < 0:
                self.current_image_index = 0
            self.show_image()
            # 可选调试日志
            # print("显示上一张图片")

    def show_next(self):
        """
        显示下一张图片
        """
        self.show_image()
        # 可选调试日志
        # print("显示下一张图片")

    def set_interval(self):
        """
        设置新的播放间隔
        """
        new_interval = simpledialog.askinteger("设置间隔", "请输入播放间隔（秒）：", minvalue=1, parent=self.root)
        if new_interval is not None:
            try:
                new_interval = int(new_interval)
                if new_interval < 1:
                    raise ValueError
                self.interval = new_interval * 1000
                if not self.paused:
                    self.schedule_show_image()
            except ValueError:
                messagebox.showerror("无效输入", "播放间隔必须为正整数。")

    def bind_keyboard_shortcuts(self):
        """
        绑定键盘快捷键：
        - 左箭头：上一张
        - 右箭头：下一张
        - 空格键：暂停/继续
        - 'q'键：退出幻灯片
        """
        self.root.bind("<Left>", lambda event: self.show_previous())
        self.root.bind("<Right>", lambda event: self.show_next())
        self.root.bind("<space>", lambda event: self.toggle_pause())
        self.root.bind("q", lambda event: self.exit_slideshow())

    def on_mouse_move(self, event):
        """
        处理鼠标移动事件，显示操作面板当鼠标在窗口底部区域或操作面板
        """
        # 获取鼠标的绝对屏幕位置
        x_root, y_root = event.x_root, event.y_root

        # 获取主窗口的位置和大小
        window_x = self.root.winfo_rootx()
        window_y = self.root.winfo_rooty()
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()

        # 获取操作面板的位置和大小
        panel_x = self.operation_panel.winfo_rootx()
        panel_y = self.operation_panel.winfo_rooty()
        panel_width = self.operation_panel.winfo_width()
        panel_height = self.operation_panel.winfo_height()

        # 检查鼠标是否在主窗口底部50像素内
        over_bottom = (window_x <= x_root <= window_x + window_width) and (y_root >= window_y + window_height - 50)

        # 检查鼠标是否在操作面板上
        over_panel = (panel_x <= x_root <= panel_x + panel_width) and (panel_y <= y_root <= panel_y + panel_height)

        if over_bottom or over_panel:
            self.show_operation_panel()
        else:
            self.hide_operation_panel()

    def show_operation_panel(self):
        """
        显示操作面板
        """
        if not self.operation_panel_visible:
            self.operation_panel.deiconify()
            self.operation_panel_visible = True
            # 可选调试日志
            # print("操作面板已显示")

    def hide_operation_panel(self):
        """
        隐藏操作面板
        """
        if self.operation_panel_visible:
            self.operation_panel.withdraw()
            self.operation_panel_visible = False
            # 可选调试日志
            # print("操作面板已隐藏")

class SlideshowApp:
    def __init__(self, root):
        self.root = root
        self.root.title("图片放映")
        self.root.geometry("800x600")  # 初始大小800x600
        self.root.minsize(600, 600)    # 设置最小尺寸为600x600
        self.root.resizable(True, True)  # 允许窗口调整大小

        # 设置窗口图标
        icon_path = self.resource_path("icon.ico")
        try:
            self.root.iconbitmap(icon_path)
        except Exception as e:
            messagebox.showwarning("警告", f"无法加载图标文件: {e}")

        self.folder_paths = []  # 存储多个文件夹路径
        self.interval = tk.IntVar(value=8)  # 默认8秒，使用整数

        self.create_widgets()

        # 绑定拖放事件
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)

    def resource_path(self, relative_path):
        """ 获取资源文件的绝对路径，兼容打包后的环境 """
        try:
            # PyInstaller打包后的临时文件夹
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def create_widgets(self):
        padding = {'padx': 10, 'pady': 10}
        default_font = ("微软雅黑", 11)

        # 选择文件夹框架
        folder_frame = tk.Frame(self.root)
        folder_frame.pack(fill=tk.BOTH, expand=True, **padding)

        folder_label = tk.Label(folder_frame, text="图片文件夹:", font=default_font)
        folder_label.pack(side=tk.TOP, anchor='w')

        # Listbox显示已选择的文件夹
        self.folder_listbox = tk.Listbox(folder_frame, selectmode=tk.MULTIPLE, height=15, font=default_font)
        self.folder_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))

        # 添加、移除和清空按钮框架
        button_frame = tk.Frame(folder_frame)
        button_frame.pack(side=tk.LEFT, fill=tk.Y)

        # 创建按钮
        add_button = tk.Button(button_frame, text="添加文件夹", command=self.add_folder, font=default_font)
        add_button.pack(fill=tk.X, pady=(0,5))

        remove_button = tk.Button(button_frame, text="移除选中", command=self.remove_selected_folders, font=default_font)
        remove_button.pack(fill=tk.X, pady=(0,5))

        clear_button = tk.Button(button_frame, text="清空文件夹", command=self.clear_folders, font=default_font)
        clear_button.pack(fill=tk.X)

        # 设置时间间隔框架
        interval_frame = tk.Frame(self.root)
        interval_frame.pack(fill=tk.X, **padding)

        interval_label = tk.Label(interval_frame, text="切换间隔 (秒):", font=default_font)
        interval_label.pack(side=tk.LEFT)

        # 修改 Spinbox 以只接受整数
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

        # 启动幻灯片按钮
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
        """
        处理拖放事件，将拖入的文件夹添加到列表中
        """
        # event.data 包含拖入的文件路径，多个路径以空格分隔，路径中包含空格时会被大括号包裹
        paths = self.root.splitlist(event.data)
        for path in paths:
            # 移除大括号
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
        """
        验证 Spinbox 输入是否为正整数
        """
        if P.isdigit() and int(P) > 0:
            return True
        elif P == "":
            return True
        else:
            return False

    def add_folder(self):
        """
        打开文件夹选择对话框，允许用户逐个选择文件夹
        """
        selected_folder = filedialog.askdirectory(title="选择图片文件夹")
        if selected_folder:
            if selected_folder not in self.folder_paths:
                self.folder_paths.append(selected_folder)
                self.folder_listbox.insert(tk.END, selected_folder)
            else:
                messagebox.showinfo("信息", "文件夹已添加。")

    def remove_selected_folders(self):
        """
        移除选中的文件夹，无需弹窗确认和强调色
        """
        selected_indices = self.folder_listbox.curselection()
        if not selected_indices:
            return  # 无选中项，无需提示
        # 从后往前移除，以避免索引错乱
        for index in reversed(selected_indices):
            self.folder_listbox.delete(index)
            del self.folder_paths[index]

    def clear_folders(self):
        """
        清空所有已添加的文件夹，无需弹窗确认和强调色
        """
        self.folder_paths.clear()
        self.folder_listbox.delete(0, tk.END)

    def start_slideshow(self):
        """
        启动幻灯片播放
        """
        if not self.folder_paths:
            messagebox.showerror("错误", "请先选择至少一个图片文件夹。")
            return

        interval = self.interval.get()
        if interval <= 0:
            messagebox.showerror("错误", "请输入一个有效的正整数作为时间间隔。")
            return

        # 按子文件夹名称自然排序，无论是否共享父文件夹
        sorted_folders = sorted(self.folder_paths, key=lambda x: natural_keys(x))

        # 创建一个新的顶级窗口用于幻灯片
        slideshow_window = tk.Toplevel(self.root)
        set_fullscreen(slideshow_window)
        slideshow_window.configure(bg='black')

        # 获取字体文件路径
        font_path = self.resource_path("yahei.ttf")

        # 运行幻灯片
        slideshow = ImageSlideshow(slideshow_window, sorted_folders, interval, font_path, fullscreen=True)

def main():
    # 检查 Pillow 和 packaging 版本
    try:
        import PIL
        from packaging import version
    except ImportError:
        messagebox.showerror("错误", "缺少依赖库。请确保已安装 Pillow 和 packaging。")
        sys.exit(1)

    # 初始化 TkinterDnD 窗口
    root = TkinterDnD.Tk()
    app = SlideshowApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
