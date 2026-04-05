# Iteration 1 Workspace Template

这个目录是第一轮评估结果的模板位置。

建议把这个目录放在 skill 目录旁边的独立 workspace 中，并为每个 case 使用 `eval-<slug>/` 目录名。

每个 case 建议各自保存：

- `with_skill/outputs/response.md`
- `with_skill/timing.json`
- `with_skill/grading.json`
- `without_skill/outputs/response.md`
- `without_skill/timing.json`
- `without_skill/grading.json`

整轮共用：

- `benchmark.json`
- `feedback.json`

建议 case 目录命名与 `evals.json` 中的 `slug` 保持一致，并统一加上 `eval-` 前缀，例如：

- `eval-login-guidance/`
- `eval-list-recent-weibos/`
- `eval-inspect-reposts/`