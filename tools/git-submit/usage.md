# git-submit 使用说明

本工具实现[提交与核验步骤](../../rules/repo/git/commits.md#提交与核验步骤)，使用 Python 3.10+ 标准库和 Git；无需安装 Python 包或 GitHub CLI。入口为 [git_submit.py](git_submit.py)，可用完整路径从其他工作目录调用。

## 准备与认证

- 调用方先完成必要测试，确认本次授权，暂存本次要提交的文件并审阅 `git diff --cached` 及 `git diff --cached --name-only`。
- 目标仓库按[签名配置](../../rules/repo/git/signing.md#签名配置)准备好签名密钥和本地验签配置；工具通过 Git 使用它们，不自行配置密钥或读取个人 profile。
- `--repo` 指定目标仓库，`--remote` 指定其中已有的远端名称，`--branch` 指定远端分支短名。工具读取该远端的实际推送地址，支持当前约定中的 GitHub.com HTTPS 和 SSH 地址；配置了多个推送地址时逐一验证。
- 推送认证沿用 Git 的现有配置。GitHub API 对公开仓库可匿名调用；需要 API 认证时，由调用方在进程环境提供 `GITHUB_TOKEN`，工具只在请求头使用，不保存或输出。Git 的推送凭据与 API 令牌分别由各自入口使用。

## 命令

以下命令在 Potccv 源码仓库根运行；其他位置使用工具及目标仓库的完整路径，远端和分支替换为目标仓库的实际配置。

```powershell
python -B tools/git-submit/git_submit.py submit --repo . --remote origin --branch main --message "提交说明" --format json
python -B tools/git-submit/git_submit.py push --repo . --remote origin --branch main --commit HEAD --format json
python -B tools/git-submit/git_submit.py verify --repo . --remote origin --branch main --commit HEAD --format json
```

| 命令 | 行为 |
|---|---|
| `submit` | 对已暂存内容执行 `git commit -S`，本地验签，推送该提交并核验远端 |
| `push` | 对 `--commit` 指定的已有提交本地验签，再推送并核验；默认 `HEAD` |
| `verify` | 只读核验指定提交的本地签名、远端分支和 GitHub 签名；默认 `HEAD` |

`submit` 的 `--message` 可换为 `--message-file`，相对文件路径按调用时的工作目录解析；多行说明使用文件保留换行。命令直接执行其声明的操作，未暂存内容保留在工作树中。工具不执行 `git add`、强制推送、补签、标签或 release 发布，也不自动改用另一传输方式。

## 验证与输出

工具先用 `git verify-commit` 验证指定提交，再通过 `git ls-remote` 核对每个推送地址的目标分支是否指向同一个完整 SHA；随后查询 GitHub 对该 SHA 的签名结果。成功要求 API 返回同一 SHA、`verified=true` 且 `reason=valid`。提交只验本次指定的 SHA，不声明其他历史提交均已验签。

`--format json` 输出一个对象，字段如下；默认文本格式供人工阅读。

| 字段 | 含义 |
|---|---|
| `ok` | 全部适用步骤是否完成 |
| `command`、`repo`、`remote`、`branch` | 本次操作和目标 |
| `commit` | 已解析的完整提交 SHA；尚未确定时为 `null` |
| `step` | 当前或失败阶段；全部完成为 `complete` |
| `completed_steps` | 已确认完成的阶段 |
| `targets` | 各 GitHub 仓库的远端 SHA、远端核对结果和签名验证结果 |
| `errors` | 失败时的错误代码与说明 |

退出码为 `0` 表示提交与验证流程全部成功，`1` 表示操作或验证失败，`2` 表示命令参数错误。`verify` 的成功只表示验证通过，不表示本次创建了提交或执行了推送。

失败后按[操作失败与重试](../../rules/workspace/operations.md#操作失败与重试)核对实际状态。`completed_steps` 和各目标结果保留已确认事实，失败不代表回滚；网络中断也不证明远端未更新。已有提交可先用 `verify --commit <SHA>` 核对，确需推送时再用 `push --commit <SHA>`；不要为重复核验再次执行 `submit`。GitHub 暂未确认签名时本次报告失败，后续单独验证，不自动轮询或重试。

## 测试

调用方按工作区测试规则准备专用批次目录，再运行：

```powershell
python -B tools/git-submit/test_git_submit.py --scratch <工作区>/tmp/git-submit/<批次>
```

测试使用标准库 `unittest`、Git 和 `ssh-keygen`。合成仓库、裸仓库和测试密钥只写入指定批次，GitHub API 使用模拟响应；不依赖个人配置、不连接 GitHub、不操作真实远端。测试清理自身夹具，调用方在完成后删除空批次目录。

接口依据：[Git 推送](https://git-scm.com/docs/git-push)、[Git 远端地址](https://git-scm.com/docs/git-remote)、[GitHub 提交对象及签名验证](https://docs.github.com/en/rest/git/commits#get-a-commit-object)。
