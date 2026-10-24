# 提交与推送

使用本资料处理提交、核验、补签或推送时，遵循本文件及[版本、发布与提交入口](AGENTS.md)。维护本目录文档时，同时遵循[共同写作与核对](../../maintenance.md#共同写作与核对)。

## 提交与核验步骤

1. 使用 `git diff --cached` 和 `git diff --cached --name-only` 检查暂存内容及文件清单，只纳入应发布内容；个人配置的限制见[凭据与发布要求](../../../profile/maintenance.md#凭据与发布)。
2. 按 [git-submit 执行入口](../../../tools/git-submit/AGENTS.md)准备工具，以目标仓库的实际远端和分支运行 `submit`，由工具完成签名提交、本地验签、推送、远端分支 SHA 核对和 GitHub 验签；命令见[使用说明](../../../tools/git-submit/usage.md#命令)。引用本资料处理其他项目时，使用 Potccv 工具的完整路径，并将 `--repo` 指向实际目标仓库。
3. 读取工具结果，只有退出码为 `0`、`ok=true`，且各目标的远端 SHA 与本次提交一致、`verified=true`、`reason=valid`，才报告提交与推送验证成功。
4. 核验已有提交使用工具的 `verify --commit <SHA>`；已有提交需要推送时使用 `push --commit <SHA>`。失败后依据已完成阶段和实际仓库状态继续，不为重复验证再次创建提交。签名配置仍按[签名配置](signing.md#签名配置)维护。

## 补签与推送

`git commit --amend --no-edit -S` 用于补签最近一次提交，会改变提交 ID；使用前确认操作处于当前任务授权范围。

推送远端和分支以项目实际配置为准。SSH remote 不可用时，可使用 HTTPS 与本机凭据。
