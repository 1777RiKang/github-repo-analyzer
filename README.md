# GitHub Repo Analyzer · 仓库数据分析系统

> A full-stack Python data pipeline: scrape → analyze → visualize → deploy.  
> Fetch any GitHub user's public repos, run 7-dimension analysis, generate charts & reports — all in an interactive web UI.

**Tech Stack:** Python 3.8+ · requests · pandas · numpy · matplotlib · Streamlit · wordcloud · Pillow

---

## 一键启动

```bash
git clone <repo-url>
cd 24211870223_时航_GitHub仓库数据分析系统
pip install -r requirements.txt
python run_web.py
```

浏览器自动打开 `http://localhost:8501`，完成。

---

## 三种使用方式

### 一键启动（推荐）

```
python run_web.py
```

自动检测依赖、自动安装、自动打开浏览器。

### Web 界面

```
streamlit run app.py
```

三页功能：

| 页面 | 功能 |
|------|------|
| 热门项目 | 按日/周/月查看 GitHub 最火新仓库，支持按语言筛选 |
| 用户分析 | 输入用户名 → 采集 → 9 维度分析 → 9 张图表 + 完整报告 + PDF 导出 |
| 对比分析 | 两个用户并排对比，活跃度、语言趋势一目了然 |

### 命令行

```bash
python main.py                      # 交互菜单
python main.py --user torvalds      # 指定用户
python main.py --user microsoft --token ghp_xxx  # Token 提升限流
python main.py --user google --max-repos 100     # 限制采集数
```

---

## 9 张分析图表

| 编号 | 图表 | 说明 |
|------|------|------|
| 01 | Stars TOP 排行 | 横向柱状图，标注星数 + 语言 |
| 02 | 语言分布饼图 | 使用占比，小比例自动合并 |
| 03 | Stars vs Forks | 对数散点图，标注高星仓库 |
| 04 | 创建趋势 | 双轴图：柱状(新建数) + 折线(累计星数) |
| 05 | Stars 直方图 | 星数区间分布 |
| 06 | 语言均星排行 | 各语言平均 Stars 对比 |
| 07 | Topics 词云 | 主题标签频率（按星数加权） |
| 08 | 活跃度评分 TOP15 | 仓库活跃度 0-100 评分柱状图 |
| 09 | 语言趋势雷达图 | 按年份展示语言偏好变化 |

---

## 分析维度

1. 基础统计 — 总仓库数、总/平均/中位/最高星数、主要语言
2. Stars TOP5 — 高星仓库详情
3. 语言分布 — 各语言仓库数、总星数、平均星数
4. 语言均星排行 — 按平均星数排序
5. 创建时间趋势 — 按年统计，双轴叠加
6. 热门 Topics — 主题标签词频 + 平均星数
7. 许可证分布 — 开源许可证使用统计
8. 仓库活跃度评分 — push 活跃度、星数影响力、Fork 比率、Issue 管理、非归档
9. 语言趋势分析 — 按年份统计语言偏好变化（雷达图）

---

## 项目结构

```
├── run_web.py          # 一键启动 Web 界面
├── main.py             # CLI 入口
├── app.py              # Streamlit Web 界面
├── github_api.py       # GitHub REST API 采集
├── trending.py         # 热门项目发现
├── analyze.py          # Pandas 多维分析
├── visualize.py        # Matplotlib + WordCloud 可视化
├── pdf_export.py       # PDF 报告导出
├── requirements.txt    # 依赖清单
├── data/               # CSV 缓存数据
└── output/             # 图表 + 分析报告 + PDF
```

---

## 数据字段

| 字段 | 说明 |
|------|------|
| name / full_name | 仓库名 |
| description | 描述 |
| stars / forks / watchers | 星数 / Fork数 / 关注数 |
| open_issues | 未关闭 Issue |
| language | 主要语言 |
| topics | 主题标签 |
| license_name | 开源许可证 |
| created_at / updated_at | 创建/更新时间 |
| is_fork / archived | 是否 Fork / 是否归档 |

---

## 功能特性

- 🔐 **Token 支持** — 无 Token 限流 **60次/小时**，建议设置环境变量 `GITHUB_TOKEN`（5000次/小时）
- 💾 **智能缓存** — 数据缓存到 `data/` 目录，Web 界面 `@st.cache_data` 1 小时 TTL
- 📄 **PDF 报告** — 一键导出包含封面、报告、全部图表的 PDF 文件
- 🟢 **活跃度评分** — 综合 push 活跃度、星数、Fork 比率、Issue 管理的 0-100 评分
- 🕸️ **语言趋势雷达** — 按年份展示语言偏好变化
- 🧪 **单元测试** — `python -m pytest tests/ -v`（17 个测试用例）
- 🌐 **中文字体** — 图表使用微软雅黑，Windows/macOS/Linux 兼容
