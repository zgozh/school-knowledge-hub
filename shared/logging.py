"""结构化日志：任务/请求 ID 贯穿。"""
import contextvars
import logging
import sys

_task_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("task_id", default=None)
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


class CtxFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.task_id = _task_id.get() or "-"
        record.request_id = _request_id.get() or "-"
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s [task=%(task_id)s req=%(request_id)s] %(message)s"))
        handler.addFilter(CtxFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
