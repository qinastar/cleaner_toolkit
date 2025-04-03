import os
import shutil
import threading
import time
import subprocess
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox
import ctypes
from ctypes import wintypes
import re
import concurrent.futures
import queue

# 设置主题
ctk.set_appearance_mode("System")  # 系统主题
ctk.set_default_color_theme("blue")  # 蓝色主题

# 获取网络路径的函数
def is_network_path(path):
    if path.startswith('\\\\'):
        return True
    if path.startswith('//'):
        return True
    if ':' in path and len(path) >= 2:
        drive = path[0].upper()
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive + ":\\")
        return drive_type == 4  # DRIVE_REMOTE
    return False

# 使用Windows命令获取文件夹大小
def get_folder_size(folder_path):
    try:
        # 使用Windows dir命令获取文件夹大小
        # 使用/a参数显示所有文件（包括隐藏文件）
        # 使用/s参数包含所有子目录
        command = f'dir /a /s "{folder_path}" | findstr "个文件"'
        result = subprocess.run(command, capture_output=True, text=True, encoding='gbk', shell=True, timeout=10)
        
        if result.returncode == 0:
            # 解析输出找到文件大小总和
            output = result.stdout.strip()
            # 匹配类似 "2 个文件 3,456,789 字节" 的行
            matches = re.findall(r'(\d+)\s+个文件\s+([\d,]+)\s+字节', output)
            if matches:
                # 取最后一个匹配（总计行）
                total_size = int(matches[-1][1].replace(',', ''))
                return total_size
    except Exception:
        pass
    
    # 如果命令行方法失败，使用快速扫描方法
    try:
        total_size = 0
        with os.scandir(folder_path) as entries:
            for entry in entries:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total_size += get_folder_size(entry.path)
                except (PermissionError, OSError):
                    continue
        return total_size
    except Exception:
        return 0

# 转换文件大小为人类可读格式
def human_readable_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(size_name) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.2f} {size_name[i]}"

# 将人类可读格式转回字节大小，用于排序
def size_to_bytes(size_str):
    if not size_str or size_str == "扫描中...":
        return 0
    parts = size_str.split()
    if len(parts) != 2:
        return 0
    try:
        size_val = float(parts[0])
        unit = parts[1]
        units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        return size_val * units.get(unit, 0)
    except ValueError:
        return 0

# 截断长文件夹名
def truncate_path(path, max_length=30):
    basename = os.path.basename(path)
    if len(basename) <= max_length:
        return basename
    
    # 截断名称，保留开头和结尾
    half = (max_length - 3) // 2
    return basename[:half] + "..." + basename[-half:]

class FolderCleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 配置窗口
        self.title("文件夹清理工具")
        self.geometry("800x600")
        self.minsize(600, 400)
        
        # 数据成员
        self.scan_thread = None
        self.stop_scan = False
        self.folders_data = []  # [(路径, 大小(字节), 人类可读大小)]
        self.default_min_size = 20 * 1024 * 1024  # 默认20MB
        
        # UI更新队列和事件
        self.ui_queue = queue.Queue()
        self.after_id = None
        
        # 创建UI
        self._create_widgets()
        
        # 启动UI更新检查
        self._check_ui_queue()
        
    def _create_widgets(self):
        # 主框架
        self.grid_rowconfigure(0, weight=0)  # 顶部路径输入区
        self.grid_rowconfigure(1, weight=1)  # 文件夹列表区
        self.grid_rowconfigure(2, weight=0)  # 底部按钮区
        self.grid_columnconfigure(0, weight=1)
        
        # 顶部区域 - 路径选择
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        top_frame.grid_columnconfigure(0, weight=0)
        top_frame.grid_columnconfigure(1, weight=1)
        top_frame.grid_columnconfigure(2, weight=0)
        
        path_label = ctk.CTkLabel(top_frame, text="路径:")
        path_label.grid(row=0, column=0, padx=5, pady=10)
        
        self.path_entry = ctk.CTkEntry(top_frame)
        self.path_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
        browse_button = ctk.CTkButton(top_frame, text="浏览...", command=self._browse_folder)
        browse_button.grid(row=0, column=2, padx=5, pady=10)
        
        scan_button = ctk.CTkButton(top_frame, text="扫描", command=self._start_scan)
        scan_button.grid(row=0, column=3, padx=5, pady=10)
        
        # 状态标签
        self.status_label = ctk.CTkLabel(top_frame, text="就绪")
        self.status_label.grid(row=1, column=0, columnspan=4, padx=5, pady=(0, 5), sticky="w")
        
        # 中间区域 - 文件夹列表
        self.folder_frame = ctk.CTkScrollableFrame(self)
        self.folder_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.folder_frame.grid_columnconfigure(0, weight=10)
        self.folder_frame.grid_columnconfigure(1, weight=2)
        
        # 列表标题
        header_frame = ctk.CTkFrame(self.folder_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
        header_frame.grid_columnconfigure(0, weight=10)
        header_frame.grid_columnconfigure(1, weight=2)
        
        folder_header = ctk.CTkLabel(header_frame, text="文件夹")
        folder_header.grid(row=0, column=0, sticky="w", padx=25)
        
        size_header_frame = ctk.CTkFrame(header_frame)
        size_header_frame.grid(row=0, column=1, sticky="e")
        
        size_header = ctk.CTkLabel(size_header_frame, text="大小")
        size_header.pack(side="left", padx=5)
        
        self.sort_asc = True
        sort_button = ctk.CTkButton(size_header_frame, text="↑", width=20, 
                                   command=self._toggle_sort)
        sort_button.pack(side="left")
        self.sort_button = sort_button
        
        # 底部区域 - 操作按钮
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        select_small_button = ctk.CTkButton(
            bottom_frame, text=f"选择小于20MB的文件夹", 
            command=self._select_small_folders
        )
        select_small_button.pack(side="left", padx=5, pady=10)
        
        delete_button = ctk.CTkButton(
            bottom_frame, text="删除选中", fg_color="darkred",
            command=self._delete_selected
        )
        delete_button.pack(side="right", padx=5, pady=10)
        
        select_all_button = ctk.CTkButton(
            bottom_frame, text="全选", 
            command=self._select_all
        )
        select_all_button.pack(side="right", padx=5, pady=10)
        
        deselect_all_button = ctk.CTkButton(
            bottom_frame, text="取消全选", 
            command=self._deselect_all
        )
        deselect_all_button.pack(side="right", padx=5, pady=10)
        
        # 初始状态设置
        self.row_frames = []
        self.checkboxes = []
        self.folder_labels = []
        self.size_labels = []
    
    def _check_ui_queue(self):
        """检查UI更新队列并处理更新"""
        try:
            # 批量处理队列中的更新
            updates = []
            for _ in range(100):  # 最多一次处理100个更新
                try:
                    updates.append(self.ui_queue.get_nowait())
                except queue.Empty:
                    break
            
            # 按类型分组更新
            size_updates = []
            other_updates = []
            
            for func, args, kwargs in updates:
                if func == self._update_folder_sizes:
                    size_updates.extend(args[0])  # args[0]是结果列表
                else:
                    other_updates.append((func, args, kwargs))
            
            # 批量处理大小更新
            if size_updates:
                self._update_folder_sizes(size_updates)
            
            # 处理其他更新
            for func, args, kwargs in other_updates:
                try:
                    func(*args, **kwargs)
                except Exception:
                    pass
                
        except Exception:
            pass
        
        # 继续检查队列
        self.after(50, self._check_ui_queue)  # 降低检查频率到50ms
    
    def _add_to_ui_queue(self, func, *args, **kwargs):
        """添加任务到UI更新队列"""
        self.ui_queue.put((func, args, kwargs))
    
    def _update_status(self, text):
        """更新状态标签"""
        self._add_to_ui_queue(self.status_label.configure, text=text)
    
    def _browse_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder_path)
    
    def _start_scan(self):
        # 清除之前的结果
        for widget in self.row_frames:
            widget.destroy()
        self.row_frames = []
        self.checkboxes = []
        self.folder_labels = []
        self.size_labels = []
        self.folders_data = []
        
        # 获取输入路径
        folder_path = self.path_entry.get().strip()
        if not folder_path:
            messagebox.showerror("错误", "请输入有效路径")
            return
        
        if not os.path.exists(folder_path):
            messagebox.showerror("错误", "路径不存在")
            return
        
        # 停止之前的扫描线程
        if self.scan_thread and self.scan_thread.is_alive():
            self.stop_scan = True
            self.scan_thread.join(0.5)  # 等待最多0.5秒让线程结束
        
        self._update_status("正在扫描...")
        self.stop_scan = False
        self.scan_thread = threading.Thread(target=self._scan_folders, args=(folder_path,))
        self.scan_thread.daemon = True
        self.scan_thread.start()
    
    def _scan_folders(self, folder_path):
        try:
            # 获取所有子文件夹
            subfolders = []
            self._update_status("正在获取子文件夹...")
            
            try:
                # 使用os.scandir而不是os.walk来提高性能
                with os.scandir(folder_path) as entries:
                    subfolders = [entry.path for entry in entries if entry.is_dir()]
            except PermissionError:
                self._add_to_ui_queue(messagebox.showerror, "错误", f"无法访问文件夹: {folder_path}")
                self._update_status("扫描失败")
                return
                
            if not subfolders:
                self._add_to_ui_queue(messagebox.showinfo, "提示", "未找到子文件夹")
                self._update_status("未找到子文件夹")
                return
                
            self._update_status(f"找到 {len(subfolders)} 个子文件夹，准备扫描...")
            
            # 批量创建UI元素
            self._add_to_ui_queue(self._create_folder_rows, subfolders)
            
            # 并行获取文件夹大小
            self._update_status("正在计算文件夹大小...")
            completed = 0
            total = len(subfolders)
            
            # 优化线程池配置
            max_workers = min(8, (os.cpu_count() or 2) * 2)  # 增加线程数，但不超过8个
            chunk_size = max(1, total // (max_workers * 2))  # 动态调整批处理大小
            
            def process_size(idx, folder_path):
                if self.stop_scan:
                    return idx, 0, "已取消"
                try:
                    size_bytes = get_folder_size(folder_path)
                    readable_size = human_readable_size(size_bytes)
                    return idx, size_bytes, readable_size
                except Exception:
                    return idx, 0, "无法计算"
            
            # 使用队列收集结果
            results_queue = queue.Queue()
            update_threshold = max(5, total // 20)  # 每5%更新一次UI
            last_update_count = 0
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_idx = {
                    executor.submit(process_size, i, subfolder): i 
                    for i, subfolder in enumerate(subfolders)
                }
                
                # 设置整体超时
                overall_timeout = max(60, total // 10)  # 根据文件夹数量动态调整超时时间
                start_time = time.time()
                
                # 处理完成的任务
                for future in concurrent.futures.as_completed(future_to_idx):
                    if self.stop_scan or time.time() - start_time > overall_timeout:
                        if not self.stop_scan:
                            self.stop_scan = True
                        executor.shutdown(wait=False)
                        break
                    
                    try:
                        idx, size_bytes, readable_size = future.result(timeout=1)
                        results_queue.put((idx, size_bytes, readable_size))
                        completed += 1
                        
                        # 批量更新UI
                        if completed - last_update_count >= update_threshold:
                            results = []
                            while not results_queue.empty():
                                results.append(results_queue.get())
                            if results:
                                self._add_to_ui_queue(self._update_folder_sizes, results)
                                last_update_count = completed
                            self._update_status(f"已完成 {completed}/{total}")
                    except Exception:
                        idx = future_to_idx[future]
                        results_queue.put((idx, 0, "错误"))
                        completed += 1
            
            # 处理剩余结果
            remaining_results = []
            while not results_queue.empty():
                remaining_results.append(results_queue.get())
            if remaining_results:
                self._add_to_ui_queue(self._update_folder_sizes, remaining_results)
            
            # 更新最终状态
            if self.stop_scan:
                self._update_status(f"扫描已中止，完成 {completed}/{total}")
            else:
                self._update_status(f"扫描完成，共 {total} 个文件夹")
                self._add_to_ui_queue(self._sort_folders)
            
        except Exception as e:
            self._add_to_ui_queue(messagebox.showerror, "错误", f"扫描过程中出错: {str(e)}")
            self._update_status("扫描出错")
    
    def _create_folder_rows(self, subfolders):
        """一次性批量创建所有文件夹行"""
        # 创建临时frame来存储所有行
        temp_frame = ctk.CTkFrame(self.folder_frame)
        temp_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        temp_frame.grid_columnconfigure(1, weight=1)
        
        for i, subfolder in enumerate(subfolders):
            truncated_name = truncate_path(subfolder)
            
            # 使用自定义框架为每一行
            row_frame = ctk.CTkFrame(temp_frame)
            row_frame.grid(row=i, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
            row_frame.grid_columnconfigure(1, weight=1)
            
            checkbox_var = ctk.BooleanVar()
            checkbox = ctk.CTkCheckBox(row_frame, text="", variable=checkbox_var, width=20, height=20)
            checkbox.grid(row=0, column=0, padx=5)
            
            folder_label = ctk.CTkLabel(row_frame, text=truncated_name, anchor="w", cursor="hand2")
            folder_label.grid(row=0, column=1, sticky="w", padx=5)
            folder_label.bind("<Button-1>", lambda e, path=subfolder: self._open_folder(path))
            
            size_label = ctk.CTkLabel(row_frame, text="扫描中...")
            size_label.grid(row=0, column=2, sticky="e", padx=5)
            
            self.row_frames.append(row_frame)
            self.checkboxes.append(checkbox)
            self.folder_labels.append(folder_label)
            self.size_labels.append(size_label)
            self.folders_data.append([subfolder, 0, "扫描中...", checkbox_var])
        
        # 一次性更新UI
        self.update_idletasks()
    
    def _update_folder_sizes(self, results):
        """批量更新文件夹大小"""
        for idx, size_bytes, readable_size in results:
            if idx < len(self.folders_data):
                self.folders_data[idx][1] = size_bytes
                self.folders_data[idx][2] = readable_size
                self.size_labels[idx].configure(text=readable_size)
    
    def _mark_incomplete(self, incomplete_items):
        """标记未完成的项目"""
        for idx, status in incomplete_items:
            if idx < len(self.folders_data):
                self.folders_data[idx][1] = 0
                self.folders_data[idx][2] = status
                self.size_labels[idx].configure(text=status)
    
    def _toggle_sort(self):
        self.sort_asc = not self.sort_asc
        self.sort_button.configure(text="↑" if self.sort_asc else "↓")
        self._sort_folders()
    
    def _sort_folders(self):
        if not self.folders_data:
            return
        
        # 根据大小排序
        self.folders_data.sort(key=lambda x: x[1], reverse=not self.sort_asc)
        
        # 记录新顺序
        new_order = []
        for i, (folder_path, _, readable_size, checkbox_var) in enumerate(self.folders_data):
            truncated_name = truncate_path(folder_path)
            
            # 更新标签而不是重建
            self.folder_labels[i].configure(text=truncated_name)
            self.size_labels[i].configure(text=readable_size)
            self.checkboxes[i].configure(variable=checkbox_var)
            
            # 重新绑定点击事件
            self.folder_labels[i].unbind("<Button-1>")
            self.folder_labels[i].bind("<Button-1>", lambda e, path=folder_path: self._open_folder(path))
    
    def _select_small_folders(self):
        for folder_data in self.folders_data:
            size_bytes = folder_data[1]
            checkbox_var = folder_data[3]
            
            if size_bytes < self.default_min_size:  # 小于20MB
                checkbox_var.set(True)
            else:
                checkbox_var.set(False)
    
    def _select_all(self):
        for folder_data in self.folders_data:
            checkbox_var = folder_data[3]
            checkbox_var.set(True)
    
    def _deselect_all(self):
        for folder_data in self.folders_data:
            checkbox_var = folder_data[3]
            checkbox_var.set(False)
    
    def _delete_selected(self):
        selected_folders = [
            folder_data[0] for folder_data in self.folders_data
            if folder_data[3].get()
        ]
        
        if not selected_folders:
            messagebox.showinfo("提示", "未选择任何文件夹")
            return
        
        confirm = messagebox.askyesno(
            "确认删除", 
            f"确定要删除选中的 {len(selected_folders)} 个文件夹吗？此操作不可恢复！"
        )
        
        if not confirm:
            return
        
        deleted = 0
        failed = 0
        for folder in selected_folders:
            try:
                shutil.rmtree(folder)
                deleted += 1
            except Exception:
                failed += 1
        
        messagebox.showinfo(
            "删除结果", 
            f"成功删除 {deleted} 个文件夹, 失败 {failed} 个"
        )
        
        # 重新扫描更新列表
        if deleted > 0:
            self._start_scan()
    
    def _open_folder(self, folder_path):
        """打开资源管理器显示指定文件夹"""
        try:
            # 使用Windows资源管理器打开文件夹
            if os.path.exists(folder_path):
                os.startfile(folder_path)
            else:
                messagebox.showerror("错误", f"文件夹不存在: {folder_path}")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件夹: {str(e)}")

if __name__ == "__main__":
    # 减少CTk的动画效果以提高流畅度
    ctk.deactivate_automatic_dpi_awareness()  # 禁用DPI自动调整
    
    app = FolderCleanerApp()
    app.mainloop() 