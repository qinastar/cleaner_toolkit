# 文件夹清理工具 (Folder Cleaner)

一个简单而强大的文件夹管理工具，帮助您快速识别和管理大文件夹。

## 功能特点

- 快速扫描文件夹大小
- 支持多选删除
- 自动选择小于20MB的文件夹
- 支持按大小排序
- 支持打开文件夹
- 现代化的用户界面
- 支持中文路径

## 系统要求

- Windows 10 或更高版本
- 不需要安装Python（已打包为exe）

## 下载

从 [Releases](https://github.com/yourusername/folder_cleaner/releases) 页面下载最新版本的exe文件。

## 使用方法

1. 运行 `FolderCleaner.exe`
2. 点击"浏览"选择要扫描的文件夹
3. 点击"扫描"开始分析
4. 使用复选框选择要删除的文件夹
5. 点击"删除选中"执行删除操作

## 开发

如果您想从源代码构建：

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/folder_cleaner.git
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 运行程序：
```bash
python folder_cleaner.py
```

4. 打包exe：
```bash
python build.py
```

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 作者

[您的名字]

## 更新日志

### v1.0.0
- 初始版本发布
- 基本功能实现 