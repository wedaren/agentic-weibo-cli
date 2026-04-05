# Weibo CLI Commands

首次使用前建议先初始化 skill 本地虚拟环境：

```bash
npm run skills:venv
```

如果直接运行 `scripts/weibo-cli` 且本地 `.venv` 尚未准备好，包装脚本也会尝试自动创建虚拟环境并安装 `requirements.txt`。

执行一轮无副作用本地自检：

```bash
npm run smoke
```

## 查看当前登录态状态

```bash
scripts/weibo-cli status
```

适用场景：先确认当前是否已登录、登录态是否还可直接使用，避免重复执行 `login`。

## 登录

```bash
scripts/weibo-cli login
scripts/weibo-cli login --force
scripts/weibo-cli login --check-browser
scripts/weibo-cli login --browser-user-data-dir .local/browser-profile
scripts/weibo-cli login --prompt
WEIBO_COOKIE='SUB=...; SUBP=...; SCF=...' WEIBO_UID='1234567890' scripts/weibo-cli login --from-env
```

适用场景：首次登录、登录态过期、切换账号。

说明：`login` 默认会先检查当前是否已有可用登录态；如果登录态仍有效，会直接返回状态提示而不是重复登录。只有显式传入 `--force` 时，才会忽略当前登录态并重新执行登录流程。`login` 默认复用 `.local/browser-profile` 作为自动化浏览器资料目录，因此同一套 CLI 登录链路在多数情况下不需要每次重新扫码。只有显式传入新的 `--browser-user-data-dir`，或删除该目录后，才会像第一次登录那样从空白浏览器开始。`login` 同时保持非交互默认值，扫码失败时会直接报错并退出，不会卡在终端等待输入。只有显式传入 `--prompt` 时，才会要求手动粘贴 cookie。

说明：如果只想确认本机浏览器自动化和当前登录态读取是否正常，而不执行扫码或发布，可运行 `npm run smoke`。

## 发布微博

```bash
scripts/weibo-cli post --text "test from skill"
```

要求：文本已经确认，不为空。

## 查看指定微博详情

```bash
scripts/weibo-cli show --weibo-id 1234567890123456
```

适用场景：查看某条微博正文、来源、作者和互动计数，确认要评论、点赞或删除的目标是否正确。

## 查看最近微博

```bash
scripts/weibo-cli list --limit 5 --page 1
scripts/weibo-cli list --limit 20 --only-reposts
scripts/weibo-cli list --limit 20 --only-originals
```

适用场景：确认刚发出的微博、查看最近动态、检查转发原文。

补充说明：

- `--only-reposts` 适合直接查看“最近转发的微博”，避免让上层 agent 先拉全量再自行筛选。
- `--only-originals` 适合排除转发，只看自己原创内容。

## 查询转发

```bash
scripts/weibo-cli reposts --weibo-id 1234567890123456 --limit 20 --page 1
```

要求：必须提供明确的微博 ID。

## 查询评论

```bash
scripts/weibo-cli comments --weibo-id 1234567890123456 --limit 20 --page 1
```

适用场景：查看指定微博下的最新评论，确认某条互动是否已经出现。

## 发表评论

```bash
scripts/weibo-cli comment --weibo-id 1234567890123456 --text "收到，支持你"
```

要求：必须提供明确的微博 ID，且评论文本已经确认。

## 点赞与取消点赞

```bash
scripts/weibo-cli like --weibo-id 1234567890123456
scripts/weibo-cli unlike --weibo-id 1234567890123456
```

适用场景：对指定微博表达支持，或撤销此前的点赞操作。

## 删除自己发布的微博

```bash
scripts/weibo-cli delete --weibo-id 1234567890123456
```

要求：只在用户明确要求删除时执行；删除属于不可逆操作，执行前应再次确认目标微博 ID。