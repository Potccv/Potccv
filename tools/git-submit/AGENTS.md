# git-submit 执行与维护入口

本目录维护随 Potccv 发布的 Git 提交与验证工具，遵循[根目录要求](../../AGENTS.md)。

- 使用工具前，按[版本与授权](../../rules/repo/git/release.md#版本与授权)确认本次提交和推送授权，并按[提交与核验步骤](../../rules/repo/git/commits.md#提交与核验步骤)审阅暂存内容。工具不读取个人配置来决定授权。
- 工具只封装 Git 签名提交、常规分支推送和 GitHub 验签；沿用目标仓库的签名与 Git 认证配置，不自动暂存、补签、改配置或发布 release。
- 命令、输出、失败处理和测试方式见[使用说明](usage.md)。失败时保留已完成阶段，不自动重试或回滚，不把已推送但未验签报告为成功。
- 维护时遵循[编程规范](../../rules/repo/coding.md)、[源码测试规则](../../rules/repo/testing.md)和[工作区测试规则](../../rules/workspace/testing/execution.md)。普通测试使用合成仓库、临时签名密钥和模拟 API，不读取真实凭据或推送真实仓库。
