from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from tcpainfinder.models import Category, ChatMessage, PainCluster
from tcpainfinder.text import to_one_line
from tcpainfinder.user_profile import CATEGORY_PRICE_RANGES, CATEGORY_QUICK_SOLUTIONS
from tcpainfinder.utils import stable_id


@dataclass
class _ClusterState:
    category: Category
    messages: list[ChatMessage] = field(default_factory=list)
    token_freq: dict[str, int] = field(default_factory=dict)

    def centroid_tokens(self, *, max_tokens: int = 28) -> set[str]:
        items = sorted(self.token_freq.items(), key=lambda kv: (-kv[1], kv[0]))[:max_tokens]
        return {t for t, _ in items}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return 0.0 if union == 0 else inter / union


def _recency_score(latest_dt: datetime) -> float:
    now = datetime.now(tz=timezone.utc)
    age_days = max(0.0, (now - latest_dt).total_seconds() / 86_400.0)
    score = math.exp(-age_days / 30.0)
    return max(0.0, min(score, 1.0))


def _rank_score(freq: int, money_avg: float, fit_avg: float, recency: float) -> float:
    # money_avg/fit_avg/recency are expected 0..1.
    frequency_score = min(1.0, math.sqrt(max(1, freq)) / 8.0)
    return (frequency_score * 0.35) + (money_avg * 0.25) + (fit_avg * 0.30) + (recency * 0.10)


def _add_to_cluster(state: _ClusterState, message: ChatMessage) -> None:
    state.messages.append(message)
    for t in set(message.tokens):
        state.token_freq[t] = state.token_freq.get(t, 0) + 1


def _representative_title(messages: list[ChatMessage]) -> str:
    if not messages:
        return "Запрос"

    def key(m: ChatMessage) -> float:
        return (m.fit_for_me_score * 2.0) + (m.money_signal_score * 1.5) + (m.dt.timestamp() / 1e9)

    rep = max(messages, key=key)
    title = to_one_line(rep.text_redacted, max_len=120)
    words = title.split()
    if len(words) > 14:
        title = " ".join(words[:14]).rstrip() + "..."
    return title or "Запрос"


def _best_example(messages: list[ChatMessage]) -> str:
    if not messages:
        return ""

    def key(m: ChatMessage) -> float:
        return (m.money_signal_score * 2.0) + (m.fit_for_me_score * 1.5) + (m.dt.timestamp() / 1e9)

    best = max(messages, key=key)
    return to_one_line(best.text_redacted, max_len=180)


def cluster_messages(messages: list[ChatMessage], *, cluster_prefix: str = "P") -> list[PainCluster]:
    if not messages:
        return []

    by_cat: dict[Category, list[ChatMessage]] = {}
    for m in messages:
        by_cat.setdefault(m.category, []).append(m)

    states: list[_ClusterState] = []
    for cat, group in by_cat.items():
        for m in sorted(group, key=lambda x: x.dt, reverse=True):
            token_set = set(m.tokens)
            if not token_set:
                continue

            best_idx = -1
            best_sim = 0.0
            for i, st in enumerate(states):
                if st.category != cat:
                    continue
                sim = _jaccard(token_set, st.centroid_tokens())
                if sim > best_sim:
                    best_sim = sim
                    best_idx = i

            threshold = 0.30 if len(token_set) <= 4 else 0.22
            if best_idx >= 0 and best_sim >= threshold:
                _add_to_cluster(states[best_idx], m)
            else:
                st = _ClusterState(category=cat)
                _add_to_cluster(st, m)
                states.append(st)

    clusters: list[PainCluster] = []
    for st in states:
        msgs = st.messages
        if not msgs:
            continue
        freq = len(msgs)
        money_avg = sum(m.money_signal_score for m in msgs) / freq
        fit_avg = sum(m.fit_for_me_score for m in msgs) / freq
        latest_dt = max(m.dt for m in msgs)
        recency = _recency_score(latest_dt)

        title = _representative_title(msgs)
        pain_id = f"tmp_{stable_id(st.category + '|' + title)}"
        clusters.append(
            PainCluster(
                pain_id=pain_id,
                category=st.category,
                title=title,
                messages=msgs,
                frequency=freq,
                money_signal_score=round(money_avg, 3),
                fit_for_me_score=round(fit_avg, 3),
                recency_score=round(recency, 3),
                example_phrase=_best_example(msgs),
                quick_solution_1_2_days=CATEGORY_QUICK_SOLUTIONS.get(st.category, ""),
                suggested_price_range=CATEGORY_PRICE_RANGES.get(st.category, ""),
            )
        )

    clusters.sort(
        key=lambda c: _rank_score(c.frequency, c.money_signal_score, c.fit_for_me_score, c.recency_score),
        reverse=True,
    )
    for idx, c in enumerate(clusters, start=1):
        c.pain_id = f"{cluster_prefix}{idx:03d}"
    return clusters

