# textport-check

同一组字节，对不同使用方可能有不同结论。本工具根据明确声明的使用方配置生成编码兼容性矩阵，指出冲突；只读，不修改文件、不猜测旧编码、不显示源码、不执行被检查脚本。

[English](../README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md)

例如，多语言 Windows PowerShell 5.1 脚本通常需要 UTF-8 BOM 才能摆脱旧代码页的影响，而直接执行的 Unix 脚本需要 `#!` 位于第 0 字节。统一“删除所有 BOM”无法表达这两种要求。纯 ASCII 不需要 BOM。

## 安装与使用

Python 3.10+，运行时无第三方依赖。以下从仓库安装，不代表已经发布到 PyPI：

```sh
python -m pip install .
textport-check --profile powershell51-script --profile utf8-no-bom examples/greeting.ps1
textport-check --config examples/textport.json --format json
```

第一个示例故意返回 1，并用 `TPC400` 提示冲突。可选择分别生成适合各使用方的文件，或修改使用方约定；本工具不会自动转换。

## 配置与边界

- `powershell51-script`：ASCII、合法 UTF-8 BOM 通过字节检查。无 BOM 的非 ASCII UTF-8 在默认旧 ANSI 代码页下不具备可移植性，报告不兼容，但某些系统启用了 UTF-8 代码页，实际结果可能不同。无 BOM 且非法 UTF-8 为未知。UTF-16/32 LE/BE BOM 能识别并严格验证，但不承诺 PowerShell 读取支持，报告未知。解码后的 NUL 也为未知。
- `posix-direct-script`：无 BOM、第 0 字节为 `#!`、非空 ASCII 解释器行且以 LF 结束、正文为 ASCII/UTF-8 且无 NUL，才通过有限检查。BOM、缺少 shebang、首行 CR 为不兼容。非 ASCII 或无 LF 的解释器行、NUL、非 UTF-8 正文为未知。非 UTF-8 正文可能被某些解释器接受，不能擅自判错。
- `utf8-no-bom`：明确声明的项目约定，合法 UTF-8 且无 BOM 才通过；空文件和 NUL 允许。并不是所有文本格式都禁止 BOM。

通过仅表示字节检查通过，不保证语法、解释器存在、权限、shebang 参数/长度、安全性或执行成功。“直接执行”不是 `sh file`，也不是 shell 回退。该配置是保守的可移植约定，不代表所有 POSIX 实现。

UTF-32 签名优先于重叠的 UTF-16 签名；残缺签名不会被猜测。错误偏移以原文件第 0 字节起算，包含 BOM。NUL 字节和解码后的 NUL 分别记录。

```json
{"version":1,"files":[{"path":"greeting.ps1","profiles":["powershell51-script","utf8-no-bom"]}]}
```

命令行文件相对 `--root`（默认当前目录），配置文件中的路径相对配置所在目录。两种输入方式不能混用。只接受明确文件路径，不提供 glob、递归、排除或环境展开。重复规范路径合并配置，输出按文件和配置排序。配置必须使用确切键，重复 JSON 键被拒绝；配置上限 1 MiB、10,000 项。单文件默认上限 1 MiB，`--max-bytes` 范围 1–67,108,864。

拒绝绝对路径、父目录跳转、Windows 驱动器/根限定路径、冒号、符号链接、重解析点和非普通文件。支持空格和多语言文件名。以 `-` 开头的文件前加 `--`。POSIX 逐组件使用不跟随链接的文件描述符遍历；Windows 检查是瞬时的，不能作为对抗恶意并发目录修改的沙箱。请使用稳定的检出目录；并发文件变化不构成一致快照。

相对路径限制适用于被检查文件的条目。`--root` 和 `--config` 可以使用绝对路径或 `..`，例如 `--root ..` 和 `--config ../textport.json`。每个原始目录组件都会被检查：`..` 前的符号链接、不存在的目录或普通文件会被拒绝，不会通过规范化消去这些组件而选中另一个目标。通过正常存在的目录访问其父目录仍受支持。

JSON 模式版本为 1，包含 `files`、`facts`、`results`、`conflicts`、`error`、`summary`、`exit_code`。机器键和诊断保持英文。没有源码预览或绝对根路径，但相对文件名及字节特征仍可能敏感。文本文件名转义控制字符。摘要按使用方结果计数，无法读取的文件增加一个未知。

退出码：0 全部兼容；1 有不兼容且无未知；2 参数/配置错误（stderr，无部分 JSON）；3 存在未知或读取不完整，即使同时有不兼容。冲突提示不单独改变退出码。[稳定诊断编号](diagnostics.md)。

## 依据与测试

[Microsoft 编码说明](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-5.1)、[Linux execve](https://man7.org/linux/man-pages/man2/execve.2.html)、[Unicode BOM FAQ](https://www.unicode.org/faq/utf_bom.html)。Linux 测试不能证明所有 Unix 的行为。工具补充 PSScriptAnalyzer BOM 规则、pre-commit-hooks 和 EditorConfig Checker：重点是多使用方矩阵，而非格式化、语言检查或编码猜测。

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python tests/runtime_fixtures.py
python -m pip install build
python -m build
```

测试覆盖多语言、UTF-16/32、畸形/截断编码、NUL、shebang、冲突、路径/大小限制、确定性 JSON 及源文件不变。专门的 Linux/Windows CI 执行自建无害样例，验证 Linux 直接执行与原生 Windows PowerShell 5.1 ASCII/UTF-8 BOM；无 BOM 行为按实际代码页记录。普通 CLI 不执行用户脚本。另有单元测试及 wheel 安装测试。本地 Linux 通过不等于远程 Windows 已通过，请查看对应提交的 CI。

贡献请保持使用方约定精确、补充官方依据和回归测试，并同步四种语言。安全问题优先使用 GitHub 私密安全报告（如果启用）；否则提交不含敏感内容的问题。MIT 许可；无第三方源码/样例复制。

显式空值 `--config ""` 或 `--config=` 属于无效配置（退出码 2，不生成报告），不等同于省略选项。即使同时提供直接文件或配置档参数，也会在读取文件前拒绝。非空路径中的空白字符按原样保留。
