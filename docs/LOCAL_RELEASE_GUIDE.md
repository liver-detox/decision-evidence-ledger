# 本地发布准备指南

本文面向第一次使用 GitHub 的维护者。当前版本为 `0.2.0`。项目已获授权将经过
审查的源码发布到 `liver-detox/decision-evidence-ledger` 公共 GitHub 仓库，并创建
`v0.2.0` 标签和托管 GitHub 源码 Release；该授权不包括软件包索引上传。

## 先理解几个词

- **仓库（repository）**：由 Git 管理的一组文件和历史记录。
- **提交（commit）**：保存在本机仓库中的一次快照。
- **远程仓库（remote）**：GitHub 等服务器上的仓库副本。
- **推送（push）**：把本地提交发送到远程仓库；这会发生外部上传。
- **标签（tag）**：给某个提交加上版本标记。
- **发布（release）**：面向外部用户提供的版本和说明。
- **源码包（sdist）**：包含可再构建源码的分发文件。
- **wheel**：供 Python 安装工具使用的构建产物。
- **CI**：服务器自动执行测试的流程，全称持续集成。

本地 `git init` 和 `git commit` 不会上传文件；`git push` 会上传。不要因为
完成了本地提交就默认拥有推送授权。

## 一、当前允许做的本地检查

在项目根目录运行：

```sh
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/decision-evidence-ledger-pycache"
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests scripts
PYTHONPATH=src python3 -m decision_evidence_ledger.cli --help
```

设置第一行环境变量后，后三条命令分别运行全部单元测试、检查 Python 语法和查看本地命令帮助。
记录命令、日期、Python 版本、退出状态和失败数量。旧结果不能代替发布前的新结果。

随后人工检查：

1. README 的示例是否仍与真实接口一致；
2. 例子是否全部为合成数据和不透明标识；
3. 是否出现真实账户、持仓、成交、收益、行情、截图、服务地址或凭据；
4. 是否出现个人邮箱、私人路径或其他项目的内部名称；
5. `MANIFEST.in` 是否只允许明确公开的文件进入源码包；
6. `LICENSE` 与 `THIRD_PARTY_NOTICES.md` 是否符合实际内容。
7. `PROVENANCE.json` 是否为每个路径记录维护者提供的来源说明和纳入决定；
   这不是独立的权利证明。

在干净候选目录中还可运行：

```sh
python3 scripts/verify_provenance.py .
```

该检查只接受真实根目录 `.git` 控制目录以外的已记录路径；缓存、构建产物、环境和其
他额外文件都会导致失败。`publication_authorization` 为
`GRANTED_FOR_GITHUB_V0_2_0_TAG_AND_HOSTED_SOURCE_RELEASE_ONLY`，只授权
`v0.2.0` GitHub 标签和托管源码 Release，不授权软件包索引上传。
`.gitignore` 只能避免 Git 意外关注这些文件，不能放宽 provenance 的严格检查。

如需本地虚拟环境，也把它放在候选目录外：

```sh
python3 -m venv "${TMPDIR:-/tmp}/decision-evidence-ledger-venv"
source "${TMPDIR:-/tmp}/decision-evidence-ledger-venv/bin/activate"
```

如需在发布前演练安装，只能使用一次性副本（disposable copy），以免构建生成的文件
污染严格候选树：

```sh
install_root="$(mktemp -d "${TMPDIR:-/tmp}/decision-evidence-ledger-install.XXXXXX")"
cp -R . "$install_root/project"
cd "$install_root/project"
python3 -m venv "$install_root/venv"
source "$install_root/venv/bin/activate"
python -m pip install --no-deps --no-build-isolation .
decision-evidence --help
```

`--no-deps` 表示不请求运行时依赖；`--no-build-isolation` 表示使用环境中已有的构建工具。
如果缺少兼容的构建工具，应停止并先核对本指南，而不是允许临时下载。

## 二、已确认的身份事实与剩余发布闸门

以下身份事实已经确认：

- 公开版权主体和维护者身份均为 `liver-detox`；
- 已选择并在本地 Git 配置中设置 `noreply` 提交地址；本文不打印该地址；
- 仅使用该别名的 `CITATION.cff` 已获批准，且不含未经批准的仓库或发布标识。

以下正式发布事项仍待确认，不能凭猜测填写：

- 私密安全报告和执行渠道；
- `v0.2.0` 发布提交在全部已配置 Python 版本上的托管 CI 结果；
- `v0.2.0` 标签和托管 GitHub 源码 Release 的执行日期。

项目已实现 Python 3.11、3.12、3.13 和 3.14 的 CI 配置。本次托管运行结果只能
在发布提交推送后确认。分支保护和工作流审查所有权目前均未提供。`0.2.0`、`v0.2.0`
标签和托管 GitHub 源码 Release 已获授权；软件包索引上传仍未获授权。

## 三、本地 Git 历史

本项目已在独立洁净目录建立本地 Git 历史。以后重做时，先检查当前目录确实是
洁净公开项目，而不是私人源仓库，然后才可以运行：

```sh
git init -b main
git config --get user.name
git config --get user.email
```

`git init -b main` 只在当前目录创建本地 Git 仓库。后两条只读取提交身份。如果
姓名或地址为空、含私人邮箱，或不是已确认的公开身份，应停止；先核对本地已配置
的公开名称和 GitHub 提供的 `noreply` 地址。

不要运行 `git add .`，也不要使用 `git add docs examples scripts src tests` 这类
宽泛命令；它们会把未审查文件一起加入。只有在获得单独暂存授权后，才从当时通过
`PROVENANCE.json` 验证的精确路径列表生成并人工复核暂存命令。核对其中没有
`progress.md`、任务报告、缓存、凭据、私人材料或其他文档。确认后，本地提交示例为：

```sh
git commit -m "chore: prepare local development snapshot"
```

这仍然只是本机快照。版本 `0.2.0` 已为已授权的 GitHub 源码 Release 准备完毕，
但本地提交本身不会创建标签或托管 Release，也不构成软件包索引发布。

## 四、公共源码仓库（本次已授权）

1. 在 GitHub 确认登录的是公开身份 `liver-detox`。
2. 核对仓库为 `liver-detox/decision-evidence-ledger`、可见性为 Public、默认
   分支为 `main`。
3. 创建空仓库，不让网页自动加入 README、许可证或其他文件，以免制造冲突。
4. 从 GitHub 页面复制该仓库的精确远程命令；不要手写或猜测地址。
5. 添加远程后先运行 `git remote -v`，人工核对所有者与仓库名。
6. 只把经过验证的源码推送到这个已批准仓库；软件包索引上传仍不在授权范围内。

GitHub 页面通常会给出添加 `origin` 的命令。`origin` 只是本地对远程地址的常用
简称，不表示该地址已经经过批准。

## 五、本次版本推送（已授权）

推送前重新执行测试、语法检查、敏感信息扫描和暂存文件检查。再由另一轮人工
复核远程地址与提交内容。版本提交后、推送前，对该提交执行
`.github/workflows/ci.yml` 中固定的 `git archive` 步骤（固定 prefix、`-- .` 和
四个 top exclusion），再用 provenance verifier 确认有 39 个普通项目成员。工作流
是该命令的唯一事实来源。全部证据通过后，推送命令是：

```sh
git push origin main
```

本次授权只允许把已审查源码上传到上述公共仓库。

本次推送不等于软件包索引发布。`v0.2.0` 标签和托管 GitHub 源码 Release 已获
授权，但在执行前仍须核对标签所指提交和发布页面内容；源码包、wheel 和软件包
索引上传需要各自的检查，且软件包索引上传仍需单独授权。

## 六、执行已授权的 v0.2.0 GitHub 源码 Release 前

使用 [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) 逐项核验。必须重新核验或如实记录：

- 私密安全报告渠道（目前未提供，不能虚构为已启用）；
- 全部承诺支持的 Python 版本的 CI；
- 全新环境安装；
- 源码包与 wheel 的完整文件清单；
- README 中每条命令的实际运行结果；
- `0.2.0`、变更日志、`v0.2.0` 标签和发布说明的一致性。

没有公开用户、下载、采用、贡献或维护记录时，应如实写“尚无证据”，不能用计划
替代事实。
