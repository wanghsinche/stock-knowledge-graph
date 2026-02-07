# Stock Knowledge Graph

GitHub Actions 驱动的股票产业链知识图谱系统。

## 架构

```
stock-knowledge-graph/
├── .github/workflows/     # GitHub Actions
├── knowledge_graph/
│   └── scripts/
│       └── extract_relationships.py  # 主脚本
├── data/
│   ├── json/              # 结构化数据 (程序读取)
│   └── markdown/          # Obsidian 可读格式
├── pyproject.toml
└── .env.example
```

## 使用方法

### 1. 安装

```bash
./setup.sh
source .venv/bin/activate
```

### 2. 本地运行

```bash
python knowledge_graph/scripts/extract_relationships.py
```

### 3. GitHub Actions 配置

在仓库 Settings → Secrets 中添加:
- `NVIDIA_API_KEY`: 你的 NVIDIA API Key

## 工作流

1. 每天美股收盘后自动触发（或手动触发）
2. 从 TradingView 获取当日 Most Active 股票
3. 用 AI 提取产业链关系
4. 生成 JSON + Markdown (Obsidian [[链接]] 格式)
5. 自动 commit + push 更新

## Obsidian 可视化

### 方法 1: 直接打开文件夹

```bash
# Obsidian → Open folder as vault → 选择 data/markdown/
```

### 方法 2: 软链接到 Obsidian Vault

```bash
ln -s /path/to/stock-knowledge-graph/data/markdown ~/Obsidian/StockKnowledgeGraph
```

### 图谱效果

- `[[TSMC]]` 会和 `[[NVDA]]` 自动连线
- 即使没有 `TSMC.md` 文件，节点也会显示（灰色）
- 后续研究 `TSMC.md` 时会自动建立双向连接

## 数据格式

### JSON (程序读取)

```json
{
  "ticker": "NVDA",
  "company_name": "NVIDIA Corporation",
  "sector": "Technology",
  "industry": "Semiconductors",
  "upstream": ["TSMC", "Samsung Electronics"],
  "downstream": ["Microsoft", "Amazon Web Services"],
  "competitors": ["AMD", "Intel"],
  "key_products": ["GeForce RTX", "A100 GPU"],
  "extracted_at": "2026-02-07 12:00:00"
}
```

### Markdown (Obsidian 可读)

```markdown
# NVDA - NVIDIA Corporation

### 上游供应商
- [[TSMC]]
- [[Samsung Electronics]]

### 下游客户
- [[Microsoft]]
- [[Amazon Web Services]]

### 竞争对手
- [[AMD]]
- [[Intel]]
```

## 进阶

### 使用 Canvas 可视化

Obsidian Canvas 可以把相关股票卡片拖到一起，AI 生成的内容会显示在卡片里。
