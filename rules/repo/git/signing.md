# 签名配置

使用本资料处理版本、签名、提交或推送时，遵循本文件及[版本、发布与提交入口](AGENTS.md)。维护本目录文档时，同时遵循[共同写作与核对](../../maintenance.md#共同写作与核对)。

## 签名配置

需要设置或修复签名、获取 GitHub 认证参数时，按[个人配置要求](../../../profile/AGENTS.md#按任务读取)读取所需字段；已有签名配置满足下表时直接沿用。使用已登记的 SSH 公钥进行签名，Git 配置如下：

| 配置项 | 值或来源 |
|---|---|
| `gpg.format` | `ssh` |
| `user.signingkey` | 本机配置中的 SSH 签名公钥路径 |
| `commit.gpgsign` | `true` |
| `gpg.ssh.allowedSignersFile` | 本机配置中的签名者列表文件路径 |
