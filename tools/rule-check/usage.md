# rule-check 使用与开发

`rule-check` 是随 Potccv 源码仓库发布的独立 Python 只读校验工具。它不依赖 Potccv 的 Python 包或其他本机工具；准备好声明的依赖后，可以从任意工作目录直接调用本目录的入口。仓库检查和工作区事项检查是两个独立命令，报告只输出到终端。

工具的维护边界见 [AGENTS.md](AGENTS.md)。源码仓库的通用文档和测试约定见 [源码文档规则](../../rules/repo/docs.md)、[源码测试规则](../../rules/repo/testing.md) 和 [工作区测试规则](../../rules/workspace/testing/execution.md)。

## 环境与依赖

- Python 3.10 或更新版本。`rules` 命令还需要调用者环境中的 Git，用于读取仓库跟踪清单；`tasks` 命令不需要 Git 命令。
- 精确依赖以 [requirements.txt](requirements.txt) 为准。依赖可以安装到调用者已经准备好的虚拟环境或其他独立解释器中。
- 源码仓库版本不包含 `venv`、Python 缓存、pip 缓存、个人 profile 或凭据。解释器和依赖环境放在源码仓库之外，并由调用者选择；不要把这些内容作为发布文件加入版本控制。
- 普通校验不需要预建 `build/`、`tmp/` 或任何工作区分类目录，也不会写入这些目录。只有显式安装或测试时，调用者才按工作区规则准备对应位置。
- 校验过程不请求网络、不自动安装依赖、不自动创建目录。若依赖缺失，命令报告环境问题并退出；依赖安装是调用者单独执行的准备步骤。

例如，准备好源码仓库之外的独立环境后，可在源码仓库根目录运行：

```powershell
python -B -m pip install --no-cache-dir --no-compile --disable-pip-version-check -r tools/rule-check/requirements.txt
python -B tools/rule-check/rule_check.py --version
```

也可以把 `python` 换成调用者指定的 Python 3.10+ 解释器完整路径。`-B` 和入口中的设置会阻止在工具目录写入 `__pycache__`。

## 命令

### 检查源码仓库规则

`rules` 检查显式源码仓库中的 Git 跟踪 Markdown 链接、标题锚点、规则入口和公开配置示例，并报告被跟踪的私人路径。它读取当前工作树和必要的 Git 元数据，不读取真实个人 profile 内容，不检查外部网站。

执行入口检查覆盖所有目录级 AGENTS.md、`rules/` 下除 README.md 外的 Markdown，以及 `profile/configuration.md`、`profile/fields.md`、`profile/maintenance.md`。这些文件必须从根 AGENTS.md 经分层目录入口与主题文档的执行链接可达，例如 `rules/AGENTS.md` 经 `repo/AGENTS.md` 进入源码主题、`profile/AGENTS.md` 进入配置主题、`tools/AGENTS.md` 进入工具专用约定。README 的链接仍会校验目标与锚点，但不传递执行可达性。`rules/scope.md` 与 `rules/maintenance.md` 是共享规则，其他详细规则仍归入 `rules/repo/` 或 `rules/workspace/`。

`profile/` 公开文件仅包括 AGENTS.md、README.md、configuration.md、fields.md、maintenance.md 和 example.json；其他被跟踪路径仅报告路径，不读取内容。JSON 报告保留 `agents_files`、`agents_reachable` 和 `agents_unreachable`，分别统计和报告目录级 AGENTS；主题规则使用 `rule_files`、`rules_reachable` 和 `rule_unreachable`。

```powershell
python -B tools/rule-check/rule_check.py rules <source-repo>
python -B tools/rule-check/rule_check.py rules <source-repo> --format json
```

`<source-repo>` 必须替换为待检查源码仓库根目录；命令不会修复发现的问题，也不会写报告文件。验证结果在原事项内简短记录；一次性且无事项的任务在回复中说明即可，不为留证另存 JSON 或额外报告。

### 检查工作区事项

`tasks` 需要显式提供工作区和至少一个源码仓库，用来确保事项目录位于工作区内且位于源码仓库之外：

```powershell
python -B tools/rule-check/rule_check.py tasks `
  --workspace <workspace> `
  --source-repo <source-repo>
```

有多个源码仓库时重复 `--source-repo`。入口先验证工作区、源码仓库和事项目录的完整路径及边界。默认事项目录是 `<workspace>/docs/tasks`；该目录不存在时报告跳过并正常结束，不创建 `docs/` 或 `tasks/`；显式指定的缺失路径仍报告错误。需要检查其他事项目录时显式传入完整路径：

```powershell
python -B tools/rule-check/rule_check.py tasks `
  --workspace <workspace> `
  --source-repo <source-repo> `
  --tasks-dir <workspace>/docs/tasks
```

事项目录下的状态目录按需存在即可，不要求同时创建；使用精确小写名称：

```text
<workspace>/docs/tasks/todo/
<workspace>/docs/tasks/doing/
<workspace>/docs/tasks/done/
<workspace>/docs/tasks/drop/
```

事项正文的状态也必须精确写成以下值之一：`todo`、`doing`、`done`、`drop`，例如：

```markdown
状态：todo
```

其他大小写、旧名称或中文别名都会报告错误，工具不会读取其中的事项，也不会自动改名、迁移或补建目录。`todo` 表示待领取，`doing` 表示已领取实施中，`done` 表示已完成，`drop` 表示已明确取消或决定不继续；对应的事项时间和终止原因仍按源码仓库发布时采用的事项契约检查。

事项正文必须在状态后提供一行不超过 120 个字符的 `摘要：`；标题和摘要用动词、对象和具体新增或变化效果说明要改什么，例如“将日志级别由数字改为名称”，便于像查看 commit 一样快速识别。正文至少包含变更边界、工作清单、验收条件和当前进展与接续；拆分依据和关联资料按需追加，避免复制背景规则。需要跟踪时在原事项中简短更新实际变化、结果、必要验证及未完成项，完成或取消后迁移原文件，不另建证据文件、归档副本或验收报告。

事项扫描只读取已识别状态目录中的 Markdown；README 不按事项格式解析。

`--format json` 可用于机器读取报告：

```powershell
python -B tools/rule-check/rule_check.py tasks `
  --workspace <workspace> `
  --source-repo <source-repo> `
  --format json
```

退出码为 `0` 表示没有错误级问题，`1` 表示校验未通过，`2` 表示参数、路径或运行环境导致无法执行。警告、信息和跳过项仍应结合报告内容复核。

## 只读边界与路径安全

- 两个命令都只读取显式目标；不会修改、移动、删除、暂存或生成目标文件。
- 运行时只读取调用者显式提供的目标路径和规则检查所需的 Git 元数据；不读取真实个人配置、凭据或个人 `profile` 内容。规则检查可以验证公开示例的结构；发现被跟踪的私人路径时只报告路径，不打开其内容。
- `tasks` 会拒绝越出工作区、进入源码仓库、经过符号链接或 junction、进入未声明嵌套 Git 仓库的事项目录。显式目标无效时报告错误，不用创建目录来掩盖输入错误。
- Markdown 链接只按解析后的本地仓库范围检查；代码块和行内代码中的示例链接不作为真实链接。外部网站和范围外文件不自动读取。
- 报告只写标准输出。普通运行不创建文件、目录、缓存、日志或报告，也不请求网络；工具没有自动修复、自动安装、自动生成日志或自动保存 JSON 的选项。

## 开发与测试

入口是 [rule_check.py](rule_check.py)，检查模块在 [rulecheck](rulecheck)，合成案例在 [tests](tests)。开发工具或执行回归测试时，调用者应先在工作区内创建本批次目录 `<workspace>/tmp/rule-check/<batch>/`，再显式传给 [run_tests.py](run_tests.py)：

```powershell
python -B tools/rule-check/run_tests.py `
  --workspace <workspace> `
  --scratch <workspace>/tmp/rule-check/<batch>
```

测试只使用合成仓库和合成事项，真实项目文档不得作为可修改测试夹具。测试脚本限制临时环境到该批次并清理自身夹具；批次目录由调用者预先准备，脚本不会替调用者补建工作区目录，也不会读取或修改真实项目文档、profile、凭据或网络资源。测试和安装的位置由调用者明确指定，并按工作区目录规则处理；批次目录及测试输出的清理、验证结果的简短记录按工作区测试规则处理，不另存证据或验收报告。普通用户只运行上面的 `rules` 或 `tasks` 命令时，不需要测试目录，也不把真实 `docs/`、真实 profile、个人配置或网络服务作为前置条件。

修改后由负责整体任务的代理统一决定是否执行测试。本目录文档修改不要求在此处运行测试，也不触碰 `MaaWW/`、`refs/` 或真实工作区资料。
