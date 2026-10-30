# TodooCard 每日看板

基于 TodooCard Studio 的 528×792 六色电子纸处理与传输能力，新增“每日看板”模板：

- Codex / GPT 5 小时与每周用量比例、刷新时间
- 今日午饭、晚饭与一句备注
- 浏览器本地保存，六色预览、PNG、QLZ 导出
- Android Chrome / Edge 可继续使用 Web Bluetooth 发送
- iPhone 可保存 PNG，再导入官方 App Store 应用发送

## 使用

直接打开发布地址或用静态服务器打开 `dist/index.html`，选择“模板制卡 → 每日看板”。

手动填写在手机和电脑上都可用。自动读取本机 Codex 用量时，在项目目录运行：

```powershell
python usage_bridge.py
```

桥接服务只监听 `127.0.0.1:8765`，只返回额度百分比、窗口长度和刷新时间，不读取或返回对话正文、API Key、Cookie。

快速验证：

```powershell
python usage_bridge.py --once
python -m unittest discover -s tests -v
```

## 数据来源说明

本机 Codex 用量通过 `codex app-server --stdio` 的 `account/rateLimits/read` 获取。OpenAI API 组织用量与费用是另一套数据，可通过管理员 Usage/Costs API 接入；不要把 Admin Key 写入静态网页。

## 上游项目

- <https://github.com/XDS9314/todoocard>
- <https://github.com/silverthiefs/todoocard-agent-board>

请同时遵守上游仓库和设备厂商的许可与安全说明。首次真机发送前先确认预览方向和裁切，传输过程中不要关闭页面或断开蓝牙。
