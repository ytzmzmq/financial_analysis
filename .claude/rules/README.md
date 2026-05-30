# 项目规则 (Rules)

在此目录下创建 `.md` 文件，Claude 会在每次对话自动加载。
规则可添加 YAML frontmatter 中的 `paths:` 限定作用范围。

示例:
```yaml
---
paths: "src/**/*.py"
---
# Python 代码规则
- 类型注解使用 Python 3.10+ 语法
- 优先使用 pathlib 而非 os.path
```
