# 个人配置选取与建立

本文件规定个人配置的选取和建立方式；按任务选择所需规则见[个人配置入口](AGENTS.md#按任务读取)。

## 选择配置

按以下顺序选择一份 JSON 配置，不自动合并多份配置：

1. 已设置环境变量 `POTCCV_PROFILE`：读取它指定的绝对路径。文件不存在或格式错误时先报告问题，不静默改读其他配置。
2. 未设置环境变量且仓库内存在 `profile/local.json`：读取该文件。
3. 否则读取用户目录下的 `~/.potccv/profile.json`。Windows 上 `~` 对应当前用户目录。
4. 都不存在时，说明个人配置尚未建立；不把示例中的空值当成实际环境或授权。

本仓库不提供自动加载程序，使用本资料的 agent 或工具按此约定查找。

## 建立配置

已有配置时直接编辑现有文件，不用空模板覆盖。首次建立仓库内配置时，可在本项目根目录执行以下 PowerShell 命令；已有同名文件会保留：

```powershell
if (-not (Test-Path -LiteralPath './profile/local.json')) {
    Copy-Item -LiteralPath './profile/example.json' -Destination './profile/local.json'
}
```

随后按需填写配置。配置中的文件路径使用绝对路径或 `~` 开头的用户目录路径。

仓库外配置可由示例复制到[选择配置](#选择配置)约定的用户目录位置，也可以放在其他位置并将 `POTCCV_PROFILE` 指向该文件的绝对路径。
