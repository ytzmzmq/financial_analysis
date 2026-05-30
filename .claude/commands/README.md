# 自定义 Slash Commands

此目录下的 `.md` 文件自动变为 `/文件名` 命令。

示例 `optimize.md`:
```markdown
运行因子优化 $ARGUMENTS，完成后:
```bash
python run_v5_optimizer.py
```
```

使用时输入 `/optimize` 即可触发。个人命令放在 `~/.claude/commands/`。
