# Citation Export Skill

## 简介

本 Skill 用于根据学术论文标题、DOI 或 PMID 生成引文文件，支持以下格式：

- **EndNote (.enw)** - EndNote 标签格式
- **RIS (.ris)** - Research Information Systems 格式
- **RIS+ (.ris)** - 扩展 RIS 格式（包含摘要、关键词、PMCID 等额外字段）

## 文件结构

```
citation-export-skill/
├── SKILL.md                    # Skill 主文档
├── scripts/
│   ├── citation_export.py      # 引文生成脚本
│   └── example_metadata.json   # 示例元数据文件
└── README.md                   # 本文件
```

## 使用方法

### 1. 准备元数据文件

创建 JSON 格式的元数据文件，包含论文信息：

```json
[
  {
    "title": "论文标题",
    "authors": ["作者1", "作者2"],
    "journal": "期刊名称",
    "year": "2024",
    "volume": "21",
    "issue": "1",
    "pages": "142",
    "issn": "1743-0003",
    "publisher": "出版社",
    "abstract": "摘要",
    "keywords": "关键词",
    "pmid": "39135110",
    "pmcid": "PMC11320866",
    "doi": "10.1186/s12984-024-01420-y",
    "language": "English"
  }
]
```

### 2. 运行脚本生成引文文件

```bash
# 生成 EndNote 格式
python citation_export.py --input metadata.json --format enw --output references.enw

# 生成 RIS 格式
python citation_export.py --input metadata.json --format ris --output references.ris

# 生成 RIS+ 格式（扩展）
python citation_export.py --input metadata.json --format ris+ --output references.ris
```

### 3. 导入到文献管理软件

- **EndNote**: File → Import → Import File → 选择 .enw 文件
- **Zotero**: File → Import → 选择 .ris 文件
- **Mendeley**: File → Import → RIS → 选择 .ris 文件
- **JabRef**: File → Import into new library → 选择文件

## 元数据字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| title | 是 | 论文标题 |
| authors | 是 | 作者列表（数组） |
| journal | 是 | 期刊名称 |
| year | 是 | 出版年份 |
| volume | 否 | 卷号 |
| issue | 否 | 期号 |
| pages | 否 | 页码（支持 "1-10" 格式） |
| issn | 否 | ISSN |
| publisher | 否 | 出版社 |
| abstract | 否 | 摘要 |
| keywords | 否 | 关键词（分号分隔） |
| pmid | 否 | PubMed ID |
| pmcid | 否 | PubMed Central ID |
| doi | 否 | DOI |
| language | 否 | 语言 |

## 输出格式对比

| 特性 | EndNote (.enw) | RIS (.ris) | RIS+ (.ris) |
|------|----------------|------------|-------------|
| 基本字段 | ✓ | ✓ | ✓ |
| 摘要 | ✓ | ✓ | ✓ |
| 关键词 | ✓ | ✓ | ✓ |
| PMID | ✓ | ✗ | ✓ |
| PMCID | ✓ | ✗ | ✓ |
| 兼容性 | EndNote | 通用 | Zotero/Mendeley |

## 示例

使用示例元数据文件生成引文：

```bash
# 生成 EndNote 格式
python scripts/citation_export.py \
  --input scripts/example_metadata.json \
  --format enw \
  --output example_endnote.enw

# 生成 RIS+ 格式
python scripts/citation_export.py \
  --input scripts/example_metadata.json \
  --format ris+ \
  --output example_risplus.ris
```

## 注意事项

1. 作者格式支持 "Last, First" 或 "First Last" 两种形式
2. 页码支持 "起始页-结束页" 格式，会自动拆分
3. 多篇论文会合并到同一个文件中，用空行分隔
4. 对于中文期刊论文，建议提供完整的英文元数据

## 扩展说明

本 Skill 可与以下数据库配合使用：

- **PubMed** - 生物医学文献数据库
- **CrossRef** - DOI 注册机构
- **Semantic Scholar** - 学术搜索引擎
- **Google Scholar** - 通用学术搜索

通过这些数据库可以自动获取论文的完整元数据。
