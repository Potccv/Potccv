# AGENTS.md

本仓库维护供 AI 使用的跨项目协作约定和个人配置示例，本文件是执行入口。在其他项目中引用本资料时，同时遵循所属项目的实际约定。

本仓库由 Markdown 文档和 JSON 配置示例组成，无需安装依赖或执行构建。

## 开始任务

- 先确认任务和目标目录，遵循所属项目及目标目录适用的 AGENTS；已有信息不足时，再查阅相关 README 或项目资料。
- 按下表选择任务入口，先掌握适用的常驻约束，再读取相关章节；引用链接用于定位，不要求递归读完所有文档。
- 已由工具载入或主动读取、仍在上下文且确认未变化的内容直接沿用；文件变化、任务范围扩大或上下文缺失时，补读受影响部分。

| 任务 | 执行要求 |
|---|---|
| 启动项目、准备工作区、生成开发测试文件或参考其他仓库与项目 | [工作区布局](rules/workspace/AGENTS.md) |
| 编写或修改源码 | [工作区布局](rules/workspace/AGENTS.md)、[编程规范](rules/coding/AGENTS.md)、[测试与验证](rules/testing/AGENTS.md) |
| 开展验证或测试、清理测试临时文件 | [工作区布局](rules/workspace/AGENTS.md)、[测试与验证](rules/testing/AGENTS.md) |
| 用户要求生成 demo | [demo 交付](rules/demo/AGENTS.md) |
| 连接环境、消息任务 | [环境连接与消息](rules/communication/AGENTS.md) |
| 版本确认、配置签名、提交与推送 | [版本与提交](rules/git/AGENTS.md) |
| 编写文档、保存项目资料、记录状态或说明交付结果 | [文档与资料](rules/docs/AGENTS.md) |
| 需要个人环境参数或维护配置 | [个人配置](profile/AGENTS.md#按任务读取) |

## 操作与授权

- 修改正在运行的项目代码前，应取得明确授权，并遵守已有授权范围。设备可发现、可连接或出现在配置中，不代表自动获得操作许可。
- 消息任务的发送范围由当前任务授权决定。
- 每次修改完成后的提交与推送按[版本与授权](rules/git/AGENTS.md#版本与授权)执行。

## 维护本项目

本节仅适用于 Potccv，其文档分工优先于[通用文档规则](rules/docs/AGENTS.md#文档职责)。

- 仓库根目录（第 1 层）及其直接下属的公开资料目录（第 2 层）同时维护 AGENTS.md 与 README.md；更深的公开资料目录默认只维护 AGENTS.md。
- 深层目录需要独立的人类阅读入口（例如独立工具或模块）时，可按需增加 README.md；上层 README 提供直达相应 AGENTS 或 README 的导航。
- 本仓库的执行规则、配置语义和操作步骤在所属 AGENTS 中完整维护；README 仅面向人介绍用途和提供导航，AI 执行不依赖 README。
- 维护任何文档前，阅读[文档与资料要求](rules/docs/AGENTS.md)。
- 修改 `rules/` 前阅读 [rules/AGENTS.md](rules/AGENTS.md)，并继续读取目标目录的 AGENTS；修改 `profile/` 或其忽略规则前阅读 [profile/AGENTS.md](profile/AGENTS.md)。
