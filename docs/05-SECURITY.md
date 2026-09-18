# 05 安全模型与权限矩阵验证（阶段 5 完成存档）

本文档是项目的安全声明。所有断言都有对应测试（tests/test_isolation.py 及此前各阶段测试），共 57 个测试全绿。

## 一、权限矩阵（六格逐格验证）

| 主体 \ 区域 | user_private.db | ai_private.db | shared.db |
|---|---|---|---|
| 用户（CLI） | ✅ 读写（口令派生密钥） | ❌ 必拒 | ✅ 读写（author=user） |
| AI（MCP） | ❌ 必拒 | ✅ 读写（服务端密钥） | ✅ 读写（author=ai） |

验证方式：

| 格 | 测试 | 验证内容 |
|---|---|---|
| user × user_private | test_matrix_user_opens_user_private | 读写往返 |
| user × shared | test_matrix_user_opens_shared | 读写往返 |
| ai × ai_private | test_matrix_ai_opens_ai_private | 读写往返 |
| ai × shared | test_matrix_ai_opens_shared | 读写往返 |
| ai × user_private | test_matrix_ai_cannot_open_user_private | assert_zone_allowed 抛 PermissionError |
| user × ai_private | test_matrix_user_cannot_open_ai_private | 同上 |

另有 test_unknown_principal_rejected：未知主体（如 "attacker"）连公共区都进不去。

## 二、三道闸门（全部代码层，零提示词依赖）

1. **句柄隔离**：MCP Server 进程只构造 ai_private 与 shared 两个存储句柄（server.py 启动代码），用户区路径与口令不进入该进程内存。CLI 对称。测试：server/cli 源码静态扫描（阶段 3/4）。
2. **接口最小化**：DiaryStore 单区域单实例，无任何跨区接口。测试：test_one_store_instance_only_owns_one_file。
3. **纵深加密**：AES-256-GCM（scrypt N=2^15 派生用户密钥；服务端随机密钥）。跨区密钥互用必失败：
   - test_user_passphrase_key_cannot_decrypt_ai_zone：用户密钥解 AI 库密文 → WrongPassphraseError
   - test_ai_server_key_cannot_decrypt_user_zone：AI 密钥解用户库密文 → WrongPassphraseError

即使攻击者拿到全部三个库文件，没有对应密钥也只能看到密文。每篇日记的密文带独立随机 nonce 与 GCM tag，篡改必失败。

## 三、渗透测试（双向）

- **MCP 侧**（test_server_tools.py::test_pentest_user_content_never_leaks）：预写用户明文标记 → 调用全部 8 个工具 + 恶意探测（明文当关键词、猜 id、limit 拉满）→ 输出零泄露。
- **CLI 侧**（test_cli.py::test_pentest_ai_content_never_leaks）：预写 AI 明文标记 → CLI 全命令 + 恶意探测 → 输出零泄露。

## 四、威胁模型与诚实边界

防得住的：
- AI（含被提示词注入操纵的 AI）读用户日记：无工具、无路径、无密钥，三重不可达。
- 用户界面上看到 AI 私密日记：CLI 无入口，源码静态扫描保证。
- 数据库文件被拷走：密文 + GCM 认证，无口令/密钥不可读、不可篡改。

防不住的（本地单机架构的物理边界，README 同步声明）：
- 有本机文件系统权限的技术用户能看到 ai_private.db 文件的存在与元数据（条目数、时间戳、大小）。
- 有同等权限且能读到密钥文件（data/keys/ai_private.key）的人可以解密 AI 区。AI 区密钥必须留在本机服务端，这是"AI 自己的日记"在单机场景下的理论上限。
- 用户口令遗忘等于用户区数据永久不可恢复（口令不落盘，无后门）。
- 进程内存中的明文（运行时状态）对有内存读取能力的攻击者可见。防这个需要 TEE/secure enclave，超出本项目范围。

## 五、运行验证命令

```bash
PY="C:/Users/26627/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd "E:/work space/mcp-diary"
"$PY" -m pytest tests/ -q --basetemp="$TEMP/mcp-diary-pytest-$$RANDOM"   # 57 passed
"$PY" scripts/smoke_stdio.py                                             # SMOKE PASSED
```

## 下一步：阶段 6

Dockerfile / docker-compose.yml、.env 文档补全、README 完善安装运行说明、（可选）.mcpb 打包。
