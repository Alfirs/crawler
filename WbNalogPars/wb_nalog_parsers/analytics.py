from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


@dataclass(slots=True)
class AnalyticsPipeline:
    """Helper routines for AI-style analytics dashboards."""

    output_dir: Path

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def aggregate_orders(self, orders: Sequence[Dict]) -> pd.DataFrame:
        df = pd.json_normalize(orders)
        if "price" in df and "quantity" in df:
            df["revenue"] = df["price"] * df["quantity"]
        grouped = df.groupby("supplierArticle").agg({"revenue": "sum", "quantity": "sum"}).reset_index()
        grouped.to_csv(self.output_dir / "orders_aggregate.csv", index=False)
        return grouped

    def detect_anomalies(self, metric: pd.Series, z_threshold: float = 3.0) -> pd.Series:
        mean = metric.mean()
        std = metric.std()
        if std == 0:
            return pd.Series(dtype=metric.dtype)
        z_scores = (metric - mean) / std
        return metric[z_scores.abs() > z_threshold]

    def cluster_skus(self, features: pd.DataFrame, n_clusters: int = 3) -> pd.DataFrame:
        scaler = StandardScaler()
        scaled = scaler.fit_transform(features)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(scaled)
        features = features.copy()
        features["cluster"] = labels
        features.to_csv(self.output_dir / "sku_clusters.csv", index=False)
        return features
