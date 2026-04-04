# Weibo CLI Commands

首次使用前建议先初始化 skill 本地虚拟环境：

```bash
npm run skills:venv
```

执行一轮无副作用本地自检：

```bash
npm run smoke
```

## 登录

```bash
scripts/weibo-cli login
scripts/weibo-cli login --check-browser
WEIBO_COOKIE='SUB=...; SUBP=...; SCF=...' WEIBO_UID='1234567890' scripts/weibo-cli login --from-env
```

适用场景：首次登录、登录态过期、切换账号。

说明：如果只想确认本机浏览器自动化和当前登录态读取是否正常，而不执行扫码或发布，可运行 `npm run smoke`。

## 发布微博

```bash
scripts/weibo-cli post --text "test from skill"
```

要求：文本已经确认，不为空。

## 查看最近微博

```bash
scripts/weibo-cli list --limit 5 --page 1
```

适用场景：确认刚发出的微博、查看最近动态、检查转发原文。

## 查询转发

```bash
scripts/weibo-cli reposts --weibo-id 1234567890123456 --limit 20 --page 1
```

要求：必须提供明确的微博 ID。