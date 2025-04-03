import PyInstaller.__main__
import os
import shutil

def build_exe():
    # 清理之前的构建文件
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    
    # PyInstaller参数
    params = [
        'folder_cleaner.py',  # 主程序文件
        '--name=FolderCleaner',  # 生成的exe名称
        '--onefile',  # 打包成单个文件
        '--noconsole',  # 不显示控制台窗口
        '--clean',  # 清理临时文件
        '--add-data=README.md;.',  # 添加README文件
        '--hidden-import=customtkinter',  # 添加必要的隐藏导入
        '--hidden-import=concurrent.futures',  # 添加线程池支持
        '--hidden-import=queue',  # 添加队列支持
        '--hidden-import=subprocess',  # 添加子进程支持
        '--hidden-import=re',  # 添加正则表达式支持
        '--hidden-import=os',  # 添加操作系统支持
        '--hidden-import=time',  # 添加时间支持
        '--hidden-import=tkinter',  # 添加tkinter支持
        '--hidden-import=tkinter.messagebox',  # 添加消息框支持
        '--hidden-import=tkinter.filedialog',  # 添加文件对话框支持
        '--collect-all=customtkinter',  # 收集所有customtkinter相关文件
    ]
    
    # 执行打包
    PyInstaller.__main__.run(params)
    
    print("打包完成！exe文件位于dist目录中。")

if __name__ == '__main__':
    build_exe() 