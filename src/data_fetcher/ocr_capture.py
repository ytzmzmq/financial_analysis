"""OCR 数据提取 —— 通过 clipboard-vision MCP 从截图提取结构化数据"""
import pandas as pd
import subprocess
import json
import tempfile
from pathlib import Path


class OCRCapture:
    """从截图/剪贴板中提取数据表，需 clipboard-vision MCP 支持"""

    def __init__(self):
        pass

    def from_clipboard(self) -> str:
        """从剪贴板截图提取文本（需要 MCP 工具）"""
        # 此函数通过 MCP 调用 clipboard-vision 的 extract_text_from_clipboard
        # 在实际使用中，由 Claude Code 的 MCP 协议处理
        print("调用 clipboard-vision MCP: extract_text_from_clipboard")
        print("请在 Claude Code 中使用 mcp__clipboard-vision__extract_text_from_clipboard 工具")
        return ""

    def from_screenshot(self, image_path: str) -> str:
        """从截图文件提取文本"""
        print(f"调用 clipboard-vision MCP: extract_text from {image_path}")
        print("请在 Claude Code 中使用 mcp__clipboard-vision__extract_text 工具")
        return ""

    def parse_table(self, ocr_text: str) -> pd.DataFrame | None:
        """尝试从 OCR 文本中解析表格数据。

        支持格式：
        - 逗号/制表符分隔的表格
        - Markdown 表格
        - 空格对齐的表格
        """
        if not ocr_text.strip():
            return None

        lines = [l.strip() for l in ocr_text.strip().split("\n") if l.strip()]

        # Markdown 表格
        if any("|" in l for l in lines):
            return self._parse_markdown_table(lines)

        # 制表符分隔
        if "\t" in lines[0]:
            rows = [l.split("\t") for l in lines]
        # 逗号分隔
        elif "," in lines[0] and lines[0].count(",") >= 2:
            rows = [l.split(",") for l in lines]
        else:
            # 尝试空格分隔
            rows = [l.split() for l in lines]

        if not rows or len(rows) < 2:
            return None

        # 第一行作为列名
        cols = [c.strip() for c in rows[0]]
        data = [[v.strip() for v in row] for row in rows[1:]]

        df = pd.DataFrame(data, columns=cols)

        # 自动检测日期列
        for c in df.columns:
            if any(kw in c.lower() for kw in ["date", "日期", "时间"]):
                try:
                    df[c] = pd.to_datetime(df[c])
                except Exception:
                    pass

        return df

    @staticmethod
    def _parse_markdown_table(lines: list[str]) -> pd.DataFrame:
        """解析 Markdown 表格"""
        # 过滤分隔符行（| --- | --- |）
        data_lines = [l for l in lines if "---" not in l and l.count("|") >= 2]
        if not data_lines:
            return pd.DataFrame()

        header = [c.strip() for c in data_lines[0].split("|") if c.strip()]
        rows = []
        for line in data_lines[1:]:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells:
                rows.append(cells)

        return pd.DataFrame(rows, columns=header[:len(rows[0])] if rows else header)

    def to_manual_format(self, df: pd.DataFrame, source: str = "ocr") -> pd.DataFrame:
        """将解析出的表格转为标准手动数据格式 (date, ticker, value)"""
        result = pd.DataFrame()
        result["date"] = pd.to_datetime(df.iloc[:, 0])
        result["ticker"] = "ocr_data"
        result["value"] = pd.to_numeric(df.iloc[:, 1], errors="coerce")
        result["source"] = source
        return result.dropna(subset=["date", "value"])
