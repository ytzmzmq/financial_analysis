"""手动数据导入 —— CSV/Excel 模板解析"""
import pandas as pd
import numpy as np
from pathlib import Path
DATA_MANUAL = Path(__file__).resolve().parent.parent.parent / "data" / "manual"


class ManualInput:
    """手动数据导入器，支持标准模板 CSV/Excel"""

    TEMPLATE_COLS = ["date", "ticker", "value", "source"]

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or DATA_MANUAL

    def read_file(self, filepath: str | Path) -> pd.DataFrame:
        """读取单个手动数据文件，自动检测 CSV/Excel"""
        filepath = Path(filepath)
        if filepath.suffix in (".csv",):
            df = pd.read_csv(filepath)
        elif filepath.suffix in (".xlsx", ".xls"):
            df = pd.read_excel(filepath)
        else:
            raise ValueError(f"Unsupported format: {filepath.suffix}")

        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        if "source" not in df.columns:
            df["source"] = str(filepath.name)
        return df[["date", "ticker", "value", "source"]].dropna(subset=["date", "value"])

    def read_all(self) -> pd.DataFrame:
        """读取 data/manual/ 下所有文件并合并"""
        dfs = []
        for f in self.data_dir.glob("*"):
            if f.suffix in (".csv", ".xlsx", ".xls"):
                try:
                    df = self.read_file(f)
                    dfs.append(df)
                    print(f"[ManualInput] Loaded {f.name}: {len(df)} rows")
                except Exception as e:
                    print(f"[ManualInput] Skipped {f.name}: {e}")
        if not dfs:
            return pd.DataFrame(columns=self.TEMPLATE_COLS)
        return pd.concat(dfs, ignore_index=True).sort_values("date")

    @staticmethod
    def create_template(output_path: str | Path = "data/manual/_template.csv"):
        """创建标准模板 CSV"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        template = pd.DataFrame(columns=["date", "ticker", "value", "source"])
        template.loc[0] = ["2025-01-15", "medical_policy_event", 1, "https://example.com/policy1"]
        template.loc[1] = ["2025-02-01", "medical_drug_approval", 3, "CDE官网"]
        template.loc[2] = ["2025-01-10", "gold_search_index", 85.5, "百度指数"]
        template.to_csv(output_path, index=False)
        print(f"Template created at {output_path}")
        return template

    def merge_to_data(self, data_dict: dict) -> dict:
        """将手动数据合并到 data dict 中"""
        manual_df = self.read_all()
        if manual_df.empty:
            return data_dict

        # 按 ticker 分组，每个 ticker 作为一个独立数据源
        for ticker in manual_df["ticker"].unique():
            sub = manual_df[manual_df["ticker"] == ticker]
            # 兼容已有的数据格式
            if ticker in data_dict and not data_dict[ticker].empty:
                existing = data_dict[ticker]
                if "value" in existing.columns:
                    combined = pd.concat([existing, sub[["date", "ticker", "value"]]])
                    data_dict[ticker] = combined.drop_duplicates(subset=["date"]).sort_values("date")
                else:
                    data_dict[ticker] = sub[["date", "ticker", "value"]]
            else:
                data_dict[f"manual_{ticker}"] = sub[["date", "ticker", "value"]]

        return data_dict
