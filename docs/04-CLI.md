# 04 用户端 CLI（阶段 4 完成存档）

按 docs/01-ARCHITECTURE.md 第七节实现。与阶段 3 对称的隔离验证。本文档记录命令集、实现决策、测试结果。

## 交付物

| 文件 | 内容 |
|---|---|
| `src/mcp_diary/cli.py` | argparse CLI，用户私密区 6 命令 + 公共区 4 命令 |
| `tests/test_cli.py` | 10 个测试：源码静态扫描、功能主流程、对称渗透 |
| `src/mcp_diary/storage.py` | 增强：get/delete 支持短 id 前缀解析；update 修复 WHERE 主键 bug |

## 命令集

```
diary [--data-dir DIR] <command>

用户私密区（口令加密，口令优先级 DIARY_USER_PASSPHRASE > 交互 getpass）：
  diary write  [--title T] [-t tag1,tag2]     正文走 stdin；交互模式单独一行 . 结束
  diary read   <id>                            支持短 id 前缀
  diary list   [--limit N] [--all]
  diary search <keyword> [--limit N]
  diary edit   <id> [--title T] [--body B]     无参数时进入交互编辑
  diary delete <id>                            软删除

公共区（author 固定 user，明文可被 AI 侧 MCP 工具读写）：
  diary shared write|read|list|search ...
```

安装后入口命令为 `diary`（pyproject 已定义）。

## 测试结果（44 passed 全绿，含此前 34 个）

CLI 侧 10 个测试：

1. **源码静态扫描**：cli.py 中不出现 AI_PRIVATE / ai_private.db / ai_private.key / AI 区密钥管理函数名。这个扫描真的咬人：我自己在 cli.py 文档字符串里写了那个函数名当红线声明，立刻被扫出来，改写措辞后通过。
2. **功能主流程**：写读往返、搜索、带参编辑、软删除与 --all 展示、公共区全命令、读不存在条目报错退出码 1。
3. **对称渗透**：预写一条 AI 私密日记（走 storage 层），CLI 全命令 + 恶意探测（用 AI 明文当关键词、猜 id、拉大 limit）输出中无任何 AI 区明文。

## 本阶段修复的两个存储层 bug（阶段 2 遗留）

1. **update() WHERE 子句用错主键**：传入短 id 时 UPDATE 匹配不到任何行，内存改了库里没写，且不报错。已改为 WHERE id=existing.id 并检查 rowcount。
2. **get()/delete() 不认短 id**：CLI 列表显示 8 位短 id 但读删按完整 id 匹配。现在 get/delete 支持前缀解析，唯一命中才返回，歧义视为未找到（防误读）。

教训：阶段 2 的测试没覆盖"update 用非完整 id"的路径，因为当时不存在短 id 概念。边界条件是跟着 CLI 引入的，测试同步补上。

## 实现决策

1. CLI 每条命令独立开关存储句柄（open → 操作 → close），无长驻进程，简单可靠。
2. 口令只在进程内存中存在，不落盘、不进命令行历史（getpass 而非参数）。
3. 输出格式：`[短id] 时间 · author [已删除] 标题`，正文只在 read 时全量展示。
4. 公共区写入 author 恒为 "user"，与 MCP 侧默认 "ai" 形成对照，双方一目了然谁写的。

## 运行示例（本机）

```bash
PY="C:/Users/26627/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd "E:/work space/mcp-diary"
echo "今天写了CLI" | DIARY_DATA_DIR=./data "$PY" -m mcp_diary.cli write --title 随笔
"$PY" -m mcp_diary.cli list
```

## 下一步：阶段 5

隔离加固与集成测试：权限矩阵逐格验证的汇总测试（user×user_private/shared、ai×ai_private/shared 四格全过 + 两个越界格必拒）、zones.assert_zone_allowed 的越界用例、加密边界条件（空口令、篡改、跨区密钥互用）。
