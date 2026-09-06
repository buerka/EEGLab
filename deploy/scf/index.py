"""SCF event function. Entry: index.main_handler. No HTTP trigger needed."""
from app.cloud_runtime import scheduled_job
from app.config import get_settings
from app.cos_store import CosStore


def main_handler(event, context):
    # SCF's CAM-authorized console test accepts {}. HTTP bodies are not supported.
    if not isinstance(event, dict) or 'httpMethod' in event or 'requestContext' in event:
        raise ValueError('仅允许 SCF 定时事件或控制台测试事件')
    if event.get('Type') not in (None, 'Timer'):
        raise ValueError('不支持的事件类型')
    try:
        return scheduled_job(CosStore(), get_settings())
    except Exception as exc:
        # Avoid logging upstream exception strings that may contain request keys.
        raise RuntimeError(f'每日任务失败 ({type(exc).__name__})；请检查 COS papers/runs 记录') from None
