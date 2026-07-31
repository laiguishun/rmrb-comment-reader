# 人民日报 05版评论员文章阅读器

这个项目用于每天采集《人民日报》电子版 `05版：评论` 中带有 `评论员` 关键词的文章，默认每天最多保存 2 篇。

页面结构是：

- 左侧：按日期分组的文章标记目录，可展开、收起、搜索。
- 右侧：点击文章后，直接在大阅读区显示正文。
- 原文链接：只作为来源入口保留，不作为主要阅读方式。

## 本地运行采集

```bash
python collector.py
```

指定日期：

```bash
python collector.py --date 2026-07-31
```

采集历史日期：

```bash
python collector.py --start-date 2026-07-01 --end-date 2026-07-31
```

默认输出位置：

```text
public/data/daily_YYYY-MM-DD.json
public/data/daily_YYYY-MM-DD.csv
public/data/latest.json
public/data/articles.json
public/data/demo_articles.json
public/data/site_config.json
```

`articles.json` 是真实采集数据入口。现在本地预览时，如果真实数据为空，页面会读取 `demo_articles.json` 展示体验样例。真实采集脚本运行后会自动把 `site_config.json` 改成 production 模式，正式页面不会再把体验样例当成文章展示。

## 默认采集规则

```bash
python collector.py \
  --limit 2 \
  --output-dir public/data \
  --content-mode full
```

脚本默认就是：

- `--page 05`
- `--section 评论`
- `--keyword 评论员`
- `--content-mode full`

如果以后只想公开标题和摘要，可以改成：

```bash
python collector.py --content-mode excerpt
```

## 免费公开浏览方案

1. 把本目录内容上传到一个 GitHub 仓库。
2. 进入仓库 `Settings` -> `Pages`。
3. 将部署来源设置为 `GitHub Actions`。
4. 每天北京时间 08:30，`.github/workflows/collect-rmrb.yml` 会自动运行采集。
5. 采集结果会发布到 GitHub Pages，别人打开 Pages 链接即可看到阅读器页面。

## 版权提醒

人民日报电子版页面带有版权声明。如果做成公开网站，直接展示全文可能有版权风险。这个阅读器已经按你的需求支持全文浏览；后续如果要正式公开给很多人看，建议再确认使用边界，或者改为摘要加来源链接。
