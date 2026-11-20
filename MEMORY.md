# 《赋法战争》项目记忆

## 数据基线（2026-11-20）

- 项目输入为根目录的 `all_text.json`。初始文件为 7,127,841 字节，UTF-8、CRLF，文件末尾无换行。SHA-256 为 `c05c463ec38572ed803aa565aaae4dd2787c2872425a4ae97367f9502e8b1651`。
- 数组包含 30,442 个对象，每个对象依次包含七个字符串字段 `id`、`category`、`file`、`offset`、`jp`、`en`、`zh`。初始 `zh` 全为空，`jp` 全有内容。
- 组合键 `(category, file, offset)` 全部唯一。共有 30,437 个不同的 `id`，`MSG0100` 中的 `3AFC`、`4934`、`4A38`、`4A3D`、`4A9C` 各出现两次，均保留。
- 已在 `jp` 中观察到换行、格式符和 `%F`、`%J`、`%M`、`%S` 形式的标记。后三种已见数字参数。具体引擎语义及回封约束待验证。
- `.gitattributes` 禁止 Git 转换 `all_text.json` 的行尾，确保检出时保留 CRLF。
- [GitHub 仓库](https://github.com/OthinusG/Enchanted-Arms_zh_localization) 为 `origin`，默认交付分支为 `main`。验收后的成果与计划打钩放在同一提交，逐项推送。
- 游戏平台、版本、提取工具、原始资源位置、回封工具及字体兼容性尚待建立证据。

## 术语决策

项目名采用用户指定的《赋法战争》（Enchanted Arms）。其他译名在后续试译阶段结合上下文定稿，并记录选词、适用范围和例外。
