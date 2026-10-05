# AGENTS.md

本仓库维护供 AI 使用的跨项目协作约定和个人配置示例，本文件是执行入口。在其他项目中引用本资料时，同时遵循所属项目的实际约定。

本仓库由 Markdown 文档和 JSON 配置示例组成，无需安装依赖或执行构建。

## 开始任务

- 按[个人配置要求](profile/AGENTS.md)读取配置。
- 在其他项目开展任务时，查看该项目及其资料目录的 README、AGENTS 和实际约定；定位方式见[个人配置字段](profile/AGENTS.md#字段职责)。
- 开始项目工作前，阅读并落实[工作区布局](rules/dev/coding/AGENTS.md#工作区布局)。
- 根据任务读取下表中的执行要求，再按目录入口继续读取所需的子领域约定。

| 任务 | 执行要求 |
|---|---|
| 开发与测试、demo 交付、连接环境、消息任务 | [开发协作](rules/dev/AGENTS.md) |
| 版本确认、配置签名、提交与推送 | [版本与提交](rules/git/AGENTS.md) |
| 保存项目资料、维护文档和记录状态 | [文档与资料](rules/dev/doc/AGENTS.md) |

## 操作与授权

- 修改正在运行的项目代码前，应取得明确授权，并遵守已有授权范围。设备可发现、可连接或出现在配置中，不代表自动获得操作许可。
- 消息任务的发送范围由当前任务授权决定。

## 维护本项目

本节仅适用于 Potccv，其文档分工优先于[通用文档规则](rules/dev/doc/AGENTS.md#文档职责)。

- 根目录和各公开资料目录必须同时维护 AGENTS.md 与 README.md；新增公开资料目录时一并创建这两份文件。
- 本仓库的执行规则、配置语义和操作步骤在所属 AGENTS 中完整维护；README 仅面向人介绍用途和提供导航，AI 执行不依赖 README。
- 维护任何文档前，阅读[文档与资料要求](rules/dev/doc/AGENTS.md)。
- 修改 `rules/` 前阅读 [rules/AGENTS.md](rules/AGENTS.md)，并继续读取目标目录的 AGENTS；修改 `profile/` 或其忽略规则前阅读 [profile/AGENTS.md](profile/AGENTS.md)。
