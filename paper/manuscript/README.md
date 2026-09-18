# 稿件源文件

本目录存放 ICLR 2027 匿名投稿的 LaTeX 源文件。

## 当前约定

- 正式入口：`iclr2027_conference.tex`。
- 原始模板：`iclr2027_conference_template.tex`，仅用于对照，不在其中撰写论文。
- 样式和参考文献格式：`iclr2027_conference.sty`、`iclr2027_conference.bst` 及模板附带依赖。
- 正文章节：后续拆分到 `sections/` 并由正式入口通过 `\input{}` 引入。
- 参考文献：当前模板示例使用 `iclr2027_conference.bib`；正式写作时继续使用该文件或在确定迁移方案后统一更名，不并行维护两份 bibliography。
- 编译：当前本地环境未检测到 `latexmk` 或 `pdflatex`，暂时使用 Overleaf，并将主文档设置为 `iclr2027_conference.tex`。

在匿名投稿阶段，不将作者身份信息写入提交版本。
保持 `\iclrfinalcopy` 注释；只有 camera-ready 阶段才按官方要求启用。
