import time
import functools
from typing import Callable, Any, Optional, Tuple, Type
from app.logger import get_logger

logger = get_logger("retry_helper")

def retry_on_failure(
    max_attempts: int = 3,
    backoff_seconds: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_final_failure: Optional[Callable[..., Any]] = None
) -> Callable:
    """
    Decorator tu dong thu lai ham khi bat duoc exception chi dinh.
    
    Ap dung co che exponential backoff:
    Attempt 1 fail: wait backoff_seconds (2s)
    Attempt 2 fail: wait backoff_seconds * 2 (4s)
    Attempt 3 fail: ghi log ERROR va goi on_final_failure neu co.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            current_backoff = backoff_seconds
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt < max_attempts:
                        logger.warning(
                            f"Ham {func.__name__} that bai lan {attempt}/{max_attempts}: {e}. Thu lai sau {current_backoff}s...",
                            extra={"func": func.__name__, "attempt": attempt, "error": str(e)}
                        )
                        time.sleep(current_backoff)
                        current_backoff *= 2
                    else:
                        logger.error(
                            f"Ham {func.__name__} that bai sau {max_attempts} lan thu lai: {e}",
                            extra={"func": func.__name__, "max_attempts": max_attempts, "error": str(e)},
                            exc_info=True
                        )
                        if on_final_failure and callable(on_final_failure):
                            try:
                                on_final_failure(e, func.__name__, *args, **kwargs)
                            except Exception as notify_err:
                                logger.warning(f"Loi thuc thi callback on_final_failure: {notify_err}")
                        raise e
        return wrapper
    return decorator

