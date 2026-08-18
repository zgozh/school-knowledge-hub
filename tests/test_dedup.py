import hashlib

from collector.dedup import content_hash, near_duplicate, url_hash


def test_url_hash_stable():
    assert url_hash("https://www.gzhu.edu.cn/info/1087/33327.htm") == \
        hashlib.sha256("https://www.gzhu.edu.cn/info/1087/33327.htm".encode()).hexdigest()[:16]


def test_content_hash_differs():
    assert content_hash("<html>a</html>") != content_hash("<html>b</html>")
    assert content_hash("<html>a</html>") == content_hash("<html>a</html>")


def test_near_duplicate_similar_titles():
    assert near_duplicate("关于2026年暑假放假安排的通知", "关于2026年暑假放假安排的通知（修订）")
    assert not near_duplicate("关于2026年暑假放假安排的通知", "关于研究生复试录取工作的通知")
