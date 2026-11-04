"""Reference solutions, used only by the tests to prove every problem's tests are correct.

These are written independently of the expected values in content/problems. They are never served
by the API.
"""

PYTHON: dict[str, str] = {
    "two-sum": """
def two_sum(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        if target - n in seen:
            return [seen[target - n], i]
        seen[n] = i
""",
    "valid-parentheses": """
def is_valid(s):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for ch in s:
        if ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
        else:
            stack.append(ch)
    return not stack
""",
    "valid-palindrome": """
def is_palindrome(s):
    i, j = 0, len(s) - 1
    while i < j:
        if not s[i].isalnum():
            i += 1
        elif not s[j].isalnum():
            j -= 1
        else:
            if s[i].lower() != s[j].lower():
                return False
            i += 1
            j -= 1
    return True
""",
    "roman-to-integer": """
def roman_to_int(s):
    value = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    for i, ch in enumerate(s):
        if i + 1 < len(s) and value[ch] < value[s[i + 1]]:
            total -= value[ch]
        else:
            total += value[ch]
    return total
""",
    "binary-search": """
def search(nums, target):
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        if nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
""",
    "maximum-subarray": """
def max_subarray(nums):
    best = current = nums[0]
    for n in nums[1:]:
        current = max(n, current + n)
        best = max(best, current)
    return best
""",
    "merge-intervals": """
def merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
""",
    "group-anagrams": """
def group_anagrams(strs):
    groups = {}
    for word in strs:
        groups.setdefault("".join(sorted(word)), []).append(word)
    return list(groups.values())
""",
    "longest-unique-substring": """
def length_of_longest_substring(s):
    last = {}
    start = best = 0
    for i, ch in enumerate(s):
        if ch in last and last[ch] >= start:
            start = last[ch] + 1
        last[ch] = i
        best = max(best, i - start + 1)
    return best
""",
    "top-k-frequent": """
from collections import Counter

def top_k_frequent(nums, k):
    counts = Counter(nums)
    return sorted(counts, key=lambda n: (-counts[n], n))[:k]
""",
    "product-except-self": """
def product_except_self(nums):
    result = [1] * len(nums)
    left = 1
    for i, n in enumerate(nums):
        result[i] = left
        left *= n
    right = 1
    for i in range(len(nums) - 1, -1, -1):
        result[i] *= right
        right *= nums[i]
    return result
""",
    "climbing-stairs": """
def climb_stairs(n):
    a, b = 1, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b
""",
    "coin-change": """
def coin_change(coins, amount):
    inf = amount + 1
    best = [0] + [inf] * amount
    for total in range(1, amount + 1):
        for coin in coins:
            if coin <= total:
                best[total] = min(best[total], best[total - coin] + 1)
    return best[amount] if best[amount] != inf else -1
""",
    "number-of-islands": """
def num_islands(grid):
    seen = set()
    count = 0
    for r in range(len(grid)):
        for c in range(len(grid[r])):
            if grid[r][c] == "1" and (r, c) not in seen:
                count += 1
                stack = [(r, c)]
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < len(grid) and 0 <= nx < len(grid[ny]) and grid[ny][nx] == "1" and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
    return count
""",
    "course-schedule": """
from collections import deque

def can_finish(n, prerequisites):
    indegree = [0] * n
    after = [[] for _ in range(n)]
    for course, before in prerequisites:
        after[before].append(course)
        indegree[course] += 1
    ready = deque(i for i in range(n) if indegree[i] == 0)
    done = 0
    while ready:
        node = ready.popleft()
        done += 1
        for nxt in after[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
    return done == n
""",
    "word-break": """
def word_break(s, words):
    words = set(words)
    ok = [True] + [False] * len(s)
    for end in range(1, len(s) + 1):
        ok[end] = any(ok[start] and s[start:end] in words for start in range(end))
    return ok[len(s)]
""",
    "rotate-matrix": """
def rotate(matrix):
    return [list(row) for row in zip(*matrix[::-1])]
""",
    "flatten-nested-list": """
def flatten(nested):
    out = []
    for item in nested:
        if isinstance(item, list):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out
""",
    "merge-k-sorted-lists": """
import heapq

def merge_k_sorted(lists):
    return list(heapq.merge(*lists))
""",
    "rate-limit-decisions": """
from collections import deque

def rate_limit(timestamps, limit, window):
    allowed = deque()
    decisions = []
    for t in timestamps:
        while allowed and allowed[0] <= t - window:
            allowed.popleft()
        if len(allowed) < limit:
            allowed.append(t)
            decisions.append(True)
        else:
            decisions.append(False)
    return decisions
""",
    "latest-per-key": """
def latest_per_key(records):
    newest = {}
    for key, version, value in records:
        if key not in newest or version >= newest[key][0]:
            newest[key] = (version, value)
    return [[key, newest[key][0], newest[key][1]] for key in sorted(newest)]
""",
    "backoff-schedule": """
def backoff_schedule(base, factor, cap, attempts):
    return [min(cap, base * factor**i) for i in range(attempts)]
""",
}

SQL: dict[str, str] = {
    "second-highest-salary": """
SELECT (SELECT DISTINCT salary FROM employees ORDER BY salary DESC LIMIT 1 OFFSET 1) AS second_highest
""",
    "duplicate-emails": """
SELECT email FROM users GROUP BY email HAVING COUNT(*) > 1
""",
    "running-total": """
SELECT day, SUM(amount) OVER (ORDER BY day) AS running_total FROM sales ORDER BY day
""",
    "top-two-salaries-per-department": """
SELECT department, employee, salary FROM (
  SELECT d.name AS department, e.name AS employee, e.salary,
         DENSE_RANK() OVER (PARTITION BY d.id ORDER BY e.salary DESC) AS rnk
  FROM employees e JOIN departments d ON d.id = e.department_id
) ranked WHERE rnk <= 2
""",
    "customers-without-orders": """
SELECT c.name FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)
""",
    "longest-login-streak": """
WITH days AS (SELECT DISTINCT user_id, day FROM logins),
numbered AS (
  SELECT user_id, day, day - (ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY day))::int AS island
  FROM days
),
streaks AS (SELECT user_id, island, COUNT(*) AS days FROM numbered GROUP BY user_id, island)
SELECT user_id, MAX(days) AS longest_streak FROM streaks GROUP BY user_id
""",
}
