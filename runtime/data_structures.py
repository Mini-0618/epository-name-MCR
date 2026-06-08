"""
Data Structures & Utilities — MCR 基础工具库。

10 个核心组件，全部可直接用于 MCR 各子系统：

1. LRUCache          → 记忆系统：高频记忆缓存
2. RingBuffer         → 事件系统：最近事件窗口
3. BloomFilter        → 免疫系统：重复事件去重
4. RateLimiter        → 呼吸系统：API 调用限流
5. retry              → 全局：指数退避重试
6. INIParser          → 配置系统：配置文件解析
7. render             → 输出系统：模板渲染
8. traverse           → 感觉系统：目录树遍历
9. SnowflakeGenerator → 全局：分布式唯一 ID
10. TaskScheduler     → 执行系统：优先级任务调度
"""

from __future__ import annotations

import asyncio
import hashlib
import heapq
import inspect
import math
import random
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional


# ============================================================
# 1. LRU Cache — 记忆系统：高频记忆缓存
# ============================================================

class _LRUNode:
    def __init__(self, key: int = 0, value: int = 0) -> None:
        self.key = key
        self.value = value
        self.prev: Optional["_LRUNode"] = None
        self.next: Optional["_LRUNode"] = None


class LRUCache:
    """LRU 缓存。get/put 均为 O(1)。"""

    def __init__(self, capacity: int) -> None:
        if not 1 <= capacity <= 10000:
            raise ValueError("capacity must be in range 1~10000")

        self.capacity = capacity
        self.cache: dict[int, _LRUNode] = {}

        self.head = _LRUNode()
        self.tail = _LRUNode()
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: _LRUNode) -> None:
        prev_node = node.prev
        next_node = node.next
        if prev_node is not None:
            prev_node.next = next_node
        if next_node is not None:
            next_node.prev = prev_node

    def _add_to_front(self, node: _LRUNode) -> None:
        first = self.head.next
        node.prev = self.head
        node.next = first
        self.head.next = node
        if first is not None:
            first.prev = node

    def get(self, key: int) -> int:
        node = self.cache.get(key)
        if node is None:
            return -1

        self._remove(node)
        self._add_to_front(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        node = self.cache.get(key)

        if node is not None:
            node.value = value
            self._remove(node)
            self._add_to_front(node)
            return

        new_node = _LRUNode(key, value)
        self.cache[key] = new_node
        self._add_to_front(new_node)

        if len(self.cache) > self.capacity:
            old = self.tail.prev
            if old is not None and old is not self.head:
                self._remove(old)
                del self.cache[old.key]


# ============================================================
# 2. Ring Buffer — 事件系统：最近事件窗口
# ============================================================

class RingBuffer:
    """线程安全环形缓冲区，满了覆盖最旧数据。"""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")

        self.capacity = capacity
        self.data: list[Any] = [None] * capacity
        self.head = 0
        self.tail = 0
        self.count = 0
        self.lock = threading.Lock()

    def put(self, item: Any) -> None:
        with self.lock:
            self.data[self.tail] = item
            self.tail = (self.tail + 1) % self.capacity

            if self.count == self.capacity:
                self.head = (self.head + 1) % self.capacity
            else:
                self.count += 1

    def get(self) -> Any:
        with self.lock:
            if self.count == 0:
                raise IndexError("ring buffer is empty")

            item = self.data[self.head]
            self.data[self.head] = None
            self.head = (self.head + 1) % self.capacity
            self.count -= 1
            return item

    def peek(self) -> Any:
        with self.lock:
            if self.count == 0:
                raise IndexError("ring buffer is empty")
            return self.data[self.head]

    def is_full(self) -> bool:
        with self.lock:
            return self.count == self.capacity

    def is_empty(self) -> bool:
        with self.lock:
            return self.count == 0

    def __len__(self) -> int:
        with self.lock:
            return self.count


# ============================================================
# 3. Bloom Filter — 免疫系统：重复事件去重
# ============================================================

class BloomFilter:
    """布隆过滤器。可能误判存在，不会误判不存在。"""

    def __init__(self, expected_items: int, false_positive_rate: float) -> None:
        if expected_items < 100:
            raise ValueError("expected_items must be >= 100")
        if not 0.001 <= false_positive_rate <= 0.1:
            raise ValueError("false_positive_rate must be in range 0.001~0.1")

        self.expected_items = expected_items
        self.false_positive_rate = false_positive_rate

        m = -expected_items * math.log(false_positive_rate) / (math.log(2) ** 2)
        k = (m / expected_items) * math.log(2)

        self.bit_size = max(1, int(m))
        self.hash_count = max(1, int(k))
        self.bytes = bytearray((self.bit_size + 7) // 8)
        self.count = 0

    def _hashes(self, item: Any) -> list[int]:
        raw = str(item).encode("utf-8")

        h1 = int.from_bytes(hashlib.sha256(raw).digest(), "big")
        h2 = int.from_bytes(hashlib.md5(raw).digest(), "big")

        return [(h1 + i * h2) % self.bit_size for i in range(self.hash_count)]

    def _set_bit(self, index: int) -> None:
        byte_index = index // 8
        bit_index = index % 8
        self.bytes[byte_index] |= 1 << bit_index

    def _get_bit(self, index: int) -> bool:
        byte_index = index // 8
        bit_index = index % 8
        return bool(self.bytes[byte_index] & (1 << bit_index))

    def add(self, item: Any) -> None:
        for index in self._hashes(item):
            self._set_bit(index)
        self.count += 1

    def contains(self, item: Any) -> bool:
        return all(self._get_bit(index) for index in self._hashes(item))

    def size(self) -> int:
        return self.count


# ============================================================
# 4. Rate Limiter — 呼吸系统：API 调用限流
# ============================================================

class RateLimiter:
    """线程安全令牌桶限流器。"""

    def __init__(self, rate: float, capacity: int) -> None:
        if not 0.1 <= rate <= 10000:
            raise ValueError("rate must be in range 0.1~10000")
        if not 1 <= capacity <= 100000:
            raise ValueError("capacity must be in range 1~100000")

        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def allow(self) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.last_refill = now

            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if self.tokens >= 1:
                self.tokens -= 1
                return True

            return False


# ============================================================
# 5. Retry Decorator — 全局：指数退避重试
# ============================================================

def retry(
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 30.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
    """支持同步/异步函数的指数退避重试装饰器。"""

    if not 1 <= max_retries <= 10:
        raise ValueError("max_retries must be in range 1~10")

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_error = None

                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as exc:
                        last_error = exc

                        if attempt == max_retries:
                            raise

                        delay = min(base_delay * (2 ** attempt), max_delay)
                        delay += random.uniform(0, delay * 0.1)
                        await asyncio.sleep(delay)

                raise last_error  # type: ignore[misc]

            return async_wrapper

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_error = exc

                    if attempt == max_retries:
                        raise

                    delay = min(base_delay * (2 ** attempt), max_delay)
                    delay += random.uniform(0, delay * 0.1)
                    time.sleep(delay)

            raise last_error  # type: ignore[misc]

        return sync_wrapper

    return decorator


# ============================================================
# 6. INI Parser — 配置系统：配置文件解析
# ============================================================

class INIParser:
    """简易 INI 配置解析器，不依赖 configparser。"""

    def __init__(self, content: str) -> None:
        self.data: dict[str, dict[str, str]] = {"DEFAULT": {}}
        self._parse(content)

    def _strip_comment(self, line: str) -> str:
        in_quote = False
        quote_char = ""

        for i, ch in enumerate(line):
            if ch in ("'", '"'):
                if not in_quote:
                    in_quote = True
                    quote_char = ch
                elif quote_char == ch:
                    in_quote = False

            if ch == "#" and not in_quote:
                return line[:i]

        return line

    def _unescape(self, value: str) -> str:
        result = ""
        i = 0

        while i < len(value):
            if value[i] == "\\" and i + 1 < len(value):
                nxt = value[i + 1]
                if nxt == "n":
                    result += "\n"
                elif nxt == "t":
                    result += "\t"
                elif nxt == "\\":
                    result += "\\"
                elif nxt == '"':
                    result += '"'
                else:
                    result += nxt
                i += 2
            else:
                result += value[i]
                i += 1

        return result

    def _parse_value(self, value: str) -> str:
        value = value.strip()

        if len(value) >= 2:
            if value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]

        return self._unescape(value)

    def _parse(self, content: str) -> None:
        current_section = "DEFAULT"

        for raw_line in content.splitlines():
            line = self._strip_comment(raw_line).strip()

            if not line:
                continue

            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                if not current_section:
                    raise ValueError("empty section name")
                self.data.setdefault(current_section, {})
                continue

            if "=" not in line:
                raise ValueError(f"invalid line: {raw_line}")

            key, value = line.split("=", 1)
            key = key.strip()

            if not key:
                raise ValueError("empty key")

            self.data.setdefault(current_section, {})
            self.data[current_section][key] = self._parse_value(value)

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self.data.get(section, {}).get(key, default)

    def getint(self, section: str, key: str, default: Any = None) -> Optional[int]:
        value = self.get(section, key, default)
        if value is default:
            return default
        return int(value)

    def getfloat(self, section: str, key: str, default: Any = None) -> Optional[float]:
        value = self.get(section, key, default)
        if value is default:
            return default
        return float(value)

    def getbool(self, section: str, key: str, default: Any = None) -> Optional[bool]:
        value = self.get(section, key, default)
        if value is default:
            return default

        text = str(value).strip().lower()

        if text in ("true", "yes", "1", "on"):
            return True
        if text in ("false", "no", "0", "off"):
            return False

        raise ValueError(f"invalid bool value: {value}")


# ============================================================
# 7. Template Engine — 输出系统：模板渲染
# ============================================================

_TOKEN_RE = re.compile(r"(?<!\\)\{\{\s*(.*?)\s*\}\}", re.DOTALL)
_IF_RE = re.compile(
    r"(?<!\\)\{\{\s*#if\s+([a-zA-Z_][\w.\[\]0-9]*)\s*\}\}(.*?)(?<!\\)\{\{\s*/if\s*\}\}",
    re.DOTALL,
)


def _resolve_path(path: str, context: dict[str, Any]) -> Any:
    current: Any = context

    parts = re.split(r"\.(?![^\[]*\])", path)

    for part in parts:
        match = re.match(r"^([a-zA-Z_]\w*)((?:\[\d+\])*)$", part)
        if not match:
            return ""

        name = match.group(1)
        indexes = match.group(2)

        if isinstance(current, dict):
            current = current.get(name, "")
        else:
            current = getattr(current, name, "")

        if current == "":
            return ""

        for index_text in re.findall(r"\[(\d+)\]", indexes):
            index = int(index_text)
            if isinstance(current, (list, tuple)) and 0 <= index < len(current):
                current = current[index]
            else:
                return ""

    return current


def render(template: str, context: dict[str, Any]) -> str:
    """简单模板渲染，支持变量、点号、列表索引、一层 if。"""

    def replace_if(match: re.Match) -> str:
        condition_name = match.group(1)
        body = match.group(2)
        value = _resolve_path(condition_name, context)
        return body if bool(value) else ""

    result = _IF_RE.sub(replace_if, template)

    def replace_var(match: re.Match) -> str:
        name = match.group(1)
        value = _resolve_path(name, context)
        return "" if value is None else str(value)

    result = _TOKEN_RE.sub(replace_var, result)

    return result.replace(r"\{{", "{{")


# ============================================================
# 8. Directory Tree Traverser — 感觉系统：目录树遍历
# ============================================================

def traverse(path: str | Path, max_depth: int = 0, pattern: str = "") -> dict[str, Any]:
    """迭代遍历目录，返回树形结构。不跟随符号链接。"""

    root_path = Path(path)

    if not root_path.exists():
        raise FileNotFoundError(str(root_path))

    if not root_path.is_dir():
        raise NotADirectoryError(str(root_path))

    if not 0 <= max_depth <= 20:
        raise ValueError("max_depth must be in range 0~20")

    root: dict[str, Any] = {
        "name": root_path.name,
        "type": "dir",
        "size": 0,
        "children": [],
    }

    stack: list[tuple[Path, dict[str, Any], int]] = [(root_path, root, 0)]

    while stack:
        current_path, current_node, depth = stack.pop()

        if max_depth != 0 and depth >= max_depth:
            continue

        try:
            entries = sorted(current_path.iterdir(), key=lambda p: p.name.lower())
        except PermissionError:
            continue

        for entry in entries:
            try:
                if entry.is_symlink():
                    continue

                if entry.is_dir():
                    child = {
                        "name": entry.name,
                        "type": "dir",
                        "size": 0,
                        "children": [],
                    }
                    current_node["children"].append(child)
                    stack.append((entry, child, depth + 1))

                elif entry.is_file():
                    if pattern and not entry.match(pattern):
                        continue

                    child = {
                        "name": entry.name,
                        "type": "file",
                        "size": entry.stat().st_size,
                    }
                    current_node["children"].append(child)

            except PermissionError:
                continue

    return root


# ============================================================
# 9. Snowflake ID Generator — 全局：分布式唯一 ID
# ============================================================

class SnowflakeGenerator:
    """Snowflake 风格分布式 ID 生成器。"""

    EPOCH = 1704067200000

    SEQUENCE_BITS = 12
    WORKER_BITS = 5
    DATACENTER_BITS = 5

    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1
    MAX_WORKER_ID = (1 << WORKER_BITS) - 1
    MAX_DATACENTER_ID = (1 << DATACENTER_BITS) - 1

    WORKER_SHIFT = SEQUENCE_BITS
    DATACENTER_SHIFT = SEQUENCE_BITS + WORKER_BITS
    TIMESTAMP_SHIFT = SEQUENCE_BITS + WORKER_BITS + DATACENTER_BITS

    def __init__(self, worker_id: int, datacenter_id: int) -> None:
        if not 0 <= worker_id <= self.MAX_WORKER_ID:
            raise ValueError("worker_id must be in range 0~31")
        if not 0 <= datacenter_id <= self.MAX_DATACENTER_ID:
            raise ValueError("datacenter_id must be in range 0~31")

        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _wait_next_ms(self, last_timestamp: int) -> int:
        timestamp = self._now_ms()
        while timestamp <= last_timestamp:
            timestamp = self._now_ms()
        return timestamp

    def next_id(self) -> int:
        with self.lock:
            timestamp = self._now_ms()

            if timestamp < self.last_timestamp:
                raise RuntimeError("clock moved backwards")

            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE
                if self.sequence == 0:
                    timestamp = self._wait_next_ms(self.last_timestamp)
            else:
                self.sequence = 0

            self.last_timestamp = timestamp

            return (
                ((timestamp - self.EPOCH) << self.TIMESTAMP_SHIFT)
                | (self.datacenter_id << self.DATACENTER_SHIFT)
                | (self.worker_id << self.WORKER_SHIFT)
                | self.sequence
            )


# ============================================================
# 10. Task Scheduler — 执行系统：优先级任务调度
# ============================================================

class TaskScheduler:
    """支持优先级、延迟、取消、超时的任务调度器。"""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.heap: list[tuple[float, int, int, str]] = []
        self.tasks: dict[str, dict[str, Any]] = {}
        self.cancelled: set[str] = set()
        self.seq = 0
        self.lock = threading.Lock()

    def add(self, task: dict[str, Any]) -> None:
        task_id = task["id"]
        priority = int(task.get("priority", 1))
        delay_ms = int(task.get("delay_ms", 0))
        callback = task["callback"]

        if not callable(callback):
            raise ValueError("callback must be callable")
        if not 1 <= priority <= 10:
            raise ValueError("priority must be in range 1~10")
        if delay_ms < 0:
            raise ValueError("delay_ms must be >= 0")

        run_at = time.monotonic() + delay_ms / 1000

        with self.lock:
            self.seq += 1
            self.tasks[task_id] = {
                "id": task_id,
                "priority": priority,
                "delay_ms": delay_ms,
                "callback": callback,
                "run_at": run_at,
            }
            heapq.heappush(self.heap, (run_at, -priority, self.seq, task_id))

    def cancel(self, task_id: str) -> bool:
        with self.lock:
            if task_id not in self.tasks:
                return False

            self.cancelled.add(task_id)
            del self.tasks[task_id]
            return True

    def pending(self) -> int:
        with self.lock:
            return len(self.tasks)

    def _run_callback_with_timeout(self, callback: Callable[[], Any]) -> None:
        error_box: list[BaseException] = []

        def target() -> None:
            try:
                callback()
            except BaseException as exc:
                error_box.append(exc)

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(self.timeout)

        if thread.is_alive():
            return

        if error_box:
            raise error_box[0]

    def run(self) -> None:
        while True:
            with self.lock:
                if not self.heap:
                    return

                run_at, neg_priority, seq, task_id = self.heap[0]
                now = time.monotonic()

                if run_at > now:
                    sleep_time = run_at - now
                    task = None
                else:
                    heapq.heappop(self.heap)

                    if task_id in self.cancelled:
                        self.cancelled.remove(task_id)
                        continue

                    task = self.tasks.pop(task_id, None)
                    sleep_time = 0

            if sleep_time > 0:
                time.sleep(sleep_time)
                continue

            if task is None:
                continue

            callback = task["callback"]
            self._run_callback_with_timeout(callback)


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    print("=== Data Structures Self-Test ===")

    # 1. LRU Cache
    cache = LRUCache(2)
    cache.put(1, 1)
    cache.put(2, 2)
    assert cache.get(1) == 1
    cache.put(3, 3)
    assert cache.get(2) == -1
    print("✅ LRU Cache")

    # 2. Ring Buffer
    rb = RingBuffer(3)
    rb.put(1)
    rb.put(2)
    rb.put(3)
    rb.put(4)
    assert rb.get() == 2  # 1 was overwritten
    print("✅ Ring Buffer")

    # 3. Bloom Filter
    bf = BloomFilter(1000, 0.01)
    bf.add("hello")
    assert bf.contains("hello")
    assert not bf.contains("world")
    print("✅ Bloom Filter")

    # 4. Rate Limiter
    limiter = RateLimiter(10, 5)
    assert limiter.allow()
    print("✅ Rate Limiter")

    # 5. Retry
    call_count = 0

    @retry(max_retries=2, base_delay=0.01)
    def flaky():
        global call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("not yet")
        return "ok"

    assert flaky() == "ok"
    print("✅ Retry Decorator")

    # 6. INI Parser
    config = INIParser("[server]\ndebug = true\nport = 8080")
    assert config.getbool("server", "debug") is True
    assert config.getint("server", "port") == 8080
    print("✅ INI Parser")

    # 7. Template Engine
    result = render("Hello, {{user.name}}! {{#if premium}}VIP{{/if}}", {
        "user": {"name": "Alice"}, "premium": True,
    })
    assert result == "Hello, Alice! VIP"
    print("✅ Template Engine")

    # 8. Directory Traverser
    tree = traverse(".", max_depth=1)
    assert tree["type"] == "dir"
    assert len(tree["children"]) > 0
    print("✅ Directory Traverser")

    # 9. Snowflake ID
    gen = SnowflakeGenerator(worker_id=1, datacenter_id=1)
    id1 = gen.next_id()
    id2 = gen.next_id()
    assert id1 != id2
    print("✅ Snowflake ID Generator")

    # 10. Task Scheduler
    results = []
    scheduler = TaskScheduler()
    scheduler.add({
        "id": "test",
        "priority": 5,
        "delay_ms": 0,
        "callback": lambda: results.append("done"),
    })
    scheduler.run()
    assert results == ["done"]
    print("✅ Task Scheduler")

    print("\n🎉 All 10 components passed!")
