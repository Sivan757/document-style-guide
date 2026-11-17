中文技术文档的写作规范。

## 目录

1. [标题](docs/title.md)
1. [文本](docs/text.md)
1. [段落](docs/paragraph.md)
1. [数值](docs/number.md)
1. [标点符号](docs/marks.md)
1. [文档体系](docs/structure.md)
1. [参考链接](docs/reference.md)

## 技能封装

本仓库同时是一个 DeepSeek Harness 插件，把规范转成可自动加载的技能。

- [plugin.json](plugin.json)：插件清单
- [skills/chinese-tech-doc-style/SKILL.md](skills/chinese-tech-doc-style/SKILL.md)：可执行规则、高频错误对照表、交付前自检清单
- [skills/chinese-tech-doc-style/references](skills/chinese-tech-doc-style/references)：上面七篇正文的副本
- [skills/chinese-tech-doc-style/scripts/check_style.py](skills/chinese-tech-doc-style/scripts/check_style.py)：机械规则检查脚本

```bash
python3 skills/chinese-tech-doc-style/scripts/check_style.py docs/
```

## License

公共领域（public domain）
