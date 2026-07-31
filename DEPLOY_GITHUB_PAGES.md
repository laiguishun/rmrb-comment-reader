# 部署到 GitHub Pages

目标：免费公开访问，GitHub Actions 每天自动采集，GitHub Pages 展示阅读器。

## 1. 创建仓库

在 GitHub 新建一个公开仓库，例如：

```text
rmrb-comment-reader
```

## 2. 上传文件

把 `people_daily_collector` 目录里的这些内容上传到仓库根目录：

```text
.github/
collector.py
public/
README.md
scripts/
```

注意：上传后，仓库根目录下应该直接能看到 `collector.py`，不要多套一层 `people_daily_collector/` 文件夹。

## 3. 打开 GitHub Pages

进入仓库：

```text
Settings -> Pages -> Build and deployment -> Source
```

选择：

```text
GitHub Actions
```

## 4. 手动跑第一次采集

进入仓库：

```text
Actions -> Collect Renmin Ribao Comments -> Run workflow
```

第一次运行后，会自动：

- 抓取当天 05版：评论 的评论员文章
- 写入 `public/data/articles.json`
- 关闭体验样例 fallback
- 部署到 GitHub Pages

## 5. 访问公网链接

部署完成后，GitHub Pages 会给出类似这样的地址：

```text
https://你的GitHub用户名.github.io/rmrb-comment-reader/
```

这个地址别人不用登录也能访问。

## 6. 自动更新时间

当前配置是每天北京时间 08:30 自动运行一次：

```text
00:30 UTC = 北京时间 08:30
```

如果当天 05版没有匹配到“评论员”文章，页面会保留之前已经采集到的历史文章。

## 版权提醒

这个版本支持站内阅读全文。公开给很多人访问前，建议确认是否具备转载或展示全文的授权；否则更稳妥的公开方案是只展示标题、摘要和来源链接。
