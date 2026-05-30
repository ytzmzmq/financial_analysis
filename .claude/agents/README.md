# Agents (子智能体)

每个 `.md` 文件定义一个专属子智能体，有独立系统提示词和工具权限。
示例 agent 文件:
```markdown
---
name: code-reviewer
tools: Read, Grep, Glob
model: haiku
---
你是代码审查专家。检查 Python 代码中的:
1. 数据泄露风险
2. 类型错误
3. 性能问题
```
