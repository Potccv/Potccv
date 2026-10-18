# 个人配置字段

## 字段职责

字段结构以[配置示例](example.json)为准，含义如下：

| 字段 | 内容 |
|---|---|
| `schema_version` | 配置结构版本，当前值见[配置示例](example.json) |
| `identity` | 个人显示名称 |
| `paths` | 工作区根目录与 SSH 密钥、签名公钥等本机路径 |
| `credentials.file` | 已有凭据文件的位置 |
| `credentials.values` | 选择直接在个人配置中保存的凭据；与 `credentials.file` 二选一，不混用 |
| `preferences` | 提交、发布偏好与子智能体默认参数 |
| `preferences.auto_commit_and_push` | 修改完成后是否自动提交并推送至 GitHub；布尔值，默认 `false`，缺失时按 `false` 处理，执行规则见[版本与授权](../rules/repo/git/release.md#版本与授权) |
| `preferences.release` | 发布收尾偏好：`create_after_change` 为 `true` 时，在具备可发布版本时收尾生成 release；`auto_push` 为独立于 `auto_commit_and_push` 的 release 推送偏好，默认 `false`，推送授权见[版本与授权](../rules/repo/git/release.md#版本与授权)；`retain_count` 为保留的近期开版数量，取正整数，默认 `3`。有效版本条件、旧版清理的引用与授权检查及失败处理见[发布整理与源码仓库发布目录](../rules/repo/git/release.md#发布整理与源码仓库发布目录) |
| `preferences.subagents` | 子智能体默认参数：`count` 为当前任务的目标并发数量，取正整数且不含主智能体，工作不足时的调度、计数与复用按[子智能体协作](../rules/workspace/collaboration.md)执行；`model`、`reasoning_effort` 分别为每个子智能体必须使用的模型标识与推理强度；缺失字段采用[配置示例](example.json)中的相应默认值 |
| `hosts`、`devices`、`services` | 设备地址、服务入口、连接方式及设备允许操作的范围，可附最后核验日期 |
| `contacts` | 消息任务需要的联系人标识 |
| `project_locations` | 项目工作区与资料目录的定位路径，仅作入口索引，不承载完整项目资料；工作区资料位置遵循[工作区资料存放位置](../rules/workspace/docs.md#资料存放位置) |
