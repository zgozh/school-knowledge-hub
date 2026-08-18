"""增量去重：URL 哈希 + 内容哈希 + simhash 近重复检测。"""
import hashlib

from simhash import Simhash


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def content_hash(html: str) -> str:
    return hashlib.md5(html.encode()).hexdigest()


def near_duplicate(text_a: str, text_b: str, max_distance: int = 3) -> bool:
    """simhash 汉明距离判定近重复（知识治理：合并重复公告用）。"""
    return Simhash(text_a).distance(Simhash(text_b)) <= max_distance
