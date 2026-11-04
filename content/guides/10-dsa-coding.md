# DSA and Coding Rounds

Daily practice from Day 1; focused days 4, 6, 13, 21, 32, 33, 35. Many Indian product companies and global firms still screen on data structures and algorithms; startups often prefer practical tasks. Prepare for both. You already have a LeetCode profile; use it as a log.

## How to solve in an interview (every time)

1. **Restate** the problem and ask about constraints (size, duplicates, negative numbers, sorted?).
2. **Examples**: one normal, one edge (empty, one element, all equal).
3. **Brute force first**, state its complexity.
4. **Improve** using a pattern; say which and why.
5. **Code** cleanly, naming things well, narrating.
6. **Test** by walking an example and one edge; fix.
7. **Complexity**: time and space, and a trade-off you chose.

If stuck: say what you know, try a smaller case, ask for a hint. Silence is worse than a wrong idea explained well.

## Patterns and starter problems

| Pattern | Use when | Starter problems |
|---|---|---|
| Hash map / set | Lookups, counting, duplicates | Two Sum, Valid Anagram, Group Anagrams, Top K Frequent Elements, Contains Duplicate |
| Two pointers | Sorted arrays, pairs, in-place work | 3Sum, Container With Most Water, Remove Duplicates from Sorted Array, Valid Palindrome |
| Sliding window | Contiguous subarray or substring with a condition | Longest Substring Without Repeating Characters, Minimum Window Substring, Maximum Average Subarray |
| Stack / monotonic stack | Matching, next greater element | Valid Parentheses, Daily Temperatures, Min Stack, Largest Rectangle in Histogram |
| Binary search | Sorted or monotonic condition | Binary Search, Search in Rotated Sorted Array, Koko Eating Bananas, Find Peak Element |
| Linked list | Pointer manipulation | Reverse Linked List, Merge Two Sorted Lists, Linked List Cycle, Remove Nth Node From End |
| Trees | Recursion, BFS/DFS | Maximum Depth, Level Order Traversal, Validate BST, Lowest Common Ancestor, Invert Binary Tree |
| Graphs | Connectivity, ordering, shortest path | Number of Islands, Course Schedule (topological sort), Clone Graph, Rotting Oranges |
| Heap / top-K | K largest, merging streams | Kth Largest Element, Top K Frequent, Merge K Sorted Lists, Find Median from Data Stream |
| Intervals | Overlaps, scheduling | Merge Intervals, Insert Interval, Meeting Rooms II |
| Dynamic programming | Overlapping subproblems | Climbing Stairs, House Robber, Coin Change, Longest Increasing Subsequence, Edit Distance |
| Backtracking | Generate combinations | Subsets, Permutations, Combination Sum, Word Search |
| Design | Data structure design | LRU Cache, Time-Based Key-Value Store, Min Stack |

## Templates (Python)

```python
# sliding window: longest substring without repeating characters
def longest_unique(s):
    seen, left, best = {}, 0, 0
    for right, ch in enumerate(s):
        if ch in seen and seen[ch] >= left:
            left = seen[ch] + 1
        seen[ch] = right
        best = max(best, right - left + 1)
    return best

# binary search on the answer space
def first_true(lo, hi, ok):           # ok is monotonic: False..False True..True
    while lo < hi:
        mid = (lo + hi) // 2
        if ok(mid): hi = mid
        else: lo = mid + 1
    return lo

# BFS on a grid
from collections import deque
def bfs(grid, start):
    q, seen = deque([start]), {start}
    while q:
        r, c = q.popleft()
        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < len(grid) and 0 <= nc < len(grid[0]) and (nr, nc) not in seen and grid[nr][nc] != '#':
                seen.add((nr, nc)); q.append((nr, nc))
    return seen

# 1D DP: coin change (min coins)
def coin_change(coins, amount):
    dp = [0] + [float('inf')] * amount
    for a in range(1, amount + 1):
        for c in coins:
            if a - c >= 0:
                dp[a] = min(dp[a], dp[a - c] + 1)
    return dp[amount] if dp[amount] != float('inf') else -1
```

## 45-day pacing (about 100 to 120 problems)

- Days 1 to 7: arrays, hashing, two pointers, sliding window (25 problems, mostly easy).
- Days 8 to 14: stacks, queues, linked lists, binary search (20).
- Days 15 to 21: trees and BFS/DFS (20).
- Days 22 to 35: graphs, heap, intervals, DP intro, backtracking (30), mixed timed sets.
- Days 36 to 45: re-solve the ones you failed, three timed mediums every other day, mock coding rounds.
Rule: if you cannot solve in 25 minutes, read the approach, close it, re-implement from memory the next day, and log it.

## Practical coding rounds (often at startups)
Build a small API or a CLI to a spec, parse and transform a file, write SQL and Python for a messy dataset, add tests, explain choices. Keep functions small, handle errors, write a README line. Practise 90-minute take-home style tasks twice.

## Common mistakes
Coding before understanding; no complexity analysis; unreadable names; not testing; going silent; memorising solutions instead of patterns.
