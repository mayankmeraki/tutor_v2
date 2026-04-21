#!/usr/bin/env python3
"""
Seed MISSING teaching plans into MongoDB.

Generates and upserts teaching plans for all DSA topics and SD concepts/technologies
that have problems in the database but no corresponding teaching plan.

Usage:
    python -m byo.scripts.seed_missing_plans
    python -m byo.scripts.seed_missing_plans --dry-run   # preview without writing
"""

import os
import sys

# ---------------------------------------------------------------------------
# Env setup
# ---------------------------------------------------------------------------
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root, "backend", ".env"), override=False)
except ImportError:
    print("WARN: python-dotenv not installed, relying on shell env")

# ---------------------------------------------------------------------------
# MISSING DSA TEACHING PLANS
# ---------------------------------------------------------------------------

DSA_MISSING_PLANS = [
    # =========================================================================
    # 1. Dynamic Programming (dp) — 28 problems
    #    NOTE: A "dynamic_programming" plan already exists in the original seed.
    #    This plan covers the *topic tag* "dp" which is the slug used in the
    #    problems collection, so we seed it under slug="dp" as an alias.
    # =========================================================================
    {
        "slug": "dp",
        "title": "Dynamic Programming",
        "type": "dsa",
        "topic": "Dynamic Programming",
        "introduction": (
            "Dynamic programming (DP) solves problems by breaking them into overlapping "
            "subproblems and caching results to avoid redundant work. The core recipe is: "
            "(1) define what state uniquely identifies a subproblem, (2) write the recurrence "
            "relating the current state to smaller states, and (3) identify base cases. Master "
            "the five DP families — linear, knapsack, interval, grid, and string matching — "
            "and you can pattern-match nearly any DP problem in interviews."
        ),
        "key_ideas": [
            "State definition is the hardest step: dp[i] means 'the answer considering elements 0..i'",
            "Top-down (memoization) = natural recursion + cache; bottom-up (tabulation) = iterative table filling",
            "Space optimization: if dp[i] depends only on dp[i-1], roll to O(1) space",
            "Knapsack family: 0/1 knapsack (pick or skip each item) vs unbounded (reuse items)",
            "Two-string DP: dp[i][j] aligns prefixes of two strings — used in LCS, edit distance, regex matching",
            "Interval DP: dp[i][j] = best answer for subarray i..j — used in burst balloons, palindrome partitioning",
        ],
        "canonical_problems": [
            {
                "name": "Climbing Stairs",
                "slug": "climbing-stairs",
                "difficulty": "easy",
                "why": "The simplest DP problem: dp[i] = dp[i-1] + dp[i-2], literally Fibonacci with a story",
            },
            {
                "name": "House Robber",
                "slug": "house-robber",
                "difficulty": "medium",
                "why": "1D DP with a take/skip decision — dp[i] = max(dp[i-1], dp[i-2] + nums[i])",
            },
            {
                "name": "Coin Change",
                "slug": "coin-change",
                "difficulty": "medium",
                "why": "Unbounded knapsack: try every coin denomination, dp[amount] = min over coins",
            },
            {
                "name": "Longest Common Subsequence",
                "slug": "longest-common-subsequence",
                "difficulty": "medium",
                "why": "Classic 2D DP on two strings — the template for edit distance, interleaving, regex",
            },
            {
                "name": "Burst Balloons",
                "slug": "burst-balloons",
                "difficulty": "hard",
                "why": "Interval DP: dp[i][j] = max coins from popping balloons i..j — teaches reverse thinking",
            },
        ],
        "common_mistakes": [
            "Defining the wrong state: too few dimensions miss information, too many cause TLE",
            "Off-by-one in base cases: dp[0] vs dp[1] confusion causes cascading errors",
            "Filling the table in wrong order — bottom-up needs dependencies computed first",
            "Forgetting to handle impossible states (return infinity or -1 appropriately)",
            "Premature space optimization before correctness is verified",
        ],
        "visual_examples": [
            {"description": "1D DP table for Climbing Stairs filling left-to-right, each cell is sum of two previous", "ds_type": "array"},
            {"description": "2D DP grid for LCS: rows = chars of s1, cols = chars of s2, arrows show match/skip", "ds_type": "grid"},
            {"description": "Recursion tree for Fibonacci: show exponential calls collapsing to O(n) with memoization", "ds_type": "tree"},
        ],
    },

    # =========================================================================
    # 2. String — 25 problems
    # =========================================================================
    {
        "slug": "string",
        "title": "Strings",
        "type": "dsa",
        "topic": "Strings",
        "introduction": (
            "String problems combine array techniques with character-specific tricks. "
            "Strings are immutable in most languages, so modification requires O(n) rebuilding. "
            "The key patterns are: frequency counting (anagrams, permutations), two-pointer / "
            "sliding window on characters, palindrome expansion from center, and prefix-based "
            "structures (tries). Many string problems are really array problems in disguise — "
            "the twist is the alphabet constraint (26 lowercase letters = constant-size map)."
        ),
        "key_ideas": [
            "Character frequency arrays: int[26] replaces a hash map for lowercase-letter problems, giving O(1) space",
            "Sliding window on strings: expand right to include, shrink left to satisfy constraint — tracks char counts",
            "Palindrome expansion: for each center (2n-1 centers), expand outward while characters match",
            "String building: use a list/StringBuilder, join at the end — avoid O(n^2) concatenation",
            "KMP / Rabin-Karp for substring search: rarely coded in interviews but understanding the idea helps",
            "Trie for prefix problems: when you need to check 'does any word start with X?' efficiently",
        ],
        "canonical_problems": [
            {
                "name": "Valid Palindrome",
                "slug": "valid-palindrome",
                "difficulty": "easy",
                "why": "Two-pointer squeeze on a string: skip non-alphanumeric, compare from both ends",
            },
            {
                "name": "Longest Substring Without Repeating Characters",
                "slug": "longest-substring-without-repeating-characters",
                "difficulty": "medium",
                "why": "Sliding window + hash set — the canonical window-on-string problem",
            },
            {
                "name": "Longest Palindromic Substring",
                "slug": "longest-palindromic-substring",
                "difficulty": "medium",
                "why": "Expand-from-center technique: try each of 2n-1 centers, O(n^2) total",
            },
            {
                "name": "Minimum Window Substring",
                "slug": "minimum-window-substring",
                "difficulty": "hard",
                "why": "Advanced sliding window: maintain a frequency deficit, shrink when all chars satisfied",
            },
            {
                "name": "Edit Distance",
                "slug": "edit-distance",
                "difficulty": "medium",
                "why": "2D DP on two strings: insert/delete/replace transitions — a string DP classic",
            },
        ],
        "common_mistakes": [
            "O(n^2) string concatenation in a loop instead of using a list and joining",
            "Forgetting strings are immutable: s[i] = 'x' doesn't work in Python/Java",
            "Not handling case sensitivity and non-alphanumeric characters",
            "Off-by-one when converting between 0-indexed positions and lengths",
            "Using == for string comparison in Java instead of .equals()",
        ],
        "visual_examples": [
            {"description": "Sliding window on 'abcabcbb': show left/right pointers and a set of chars in the window", "ds_type": "array"},
            {"description": "Palindrome expansion from center of 'babad': arrows expanding outward from each center", "ds_type": "array"},
            {"description": "Character frequency histogram comparing two strings for anagram check", "ds_type": "hash_map"},
        ],
    },

    # =========================================================================
    # 3. DFS (Depth-First Search) — 24 problems
    # =========================================================================
    {
        "slug": "dfs",
        "title": "Depth-First Search",
        "type": "dsa",
        "topic": "Depth-First Search",
        "introduction": (
            "Depth-First Search (DFS) explores as far as possible along each branch before "
            "backtracking. It's implemented with recursion (implicit stack) or an explicit stack. "
            "DFS is the workhorse for tree traversals (preorder, inorder, postorder), graph "
            "exploration (connected components, cycle detection), and backtracking (subsets, "
            "permutations). The key insight: DFS naturally encodes 'do something, recurse, undo' "
            "which maps perfectly to decision trees."
        ),
        "key_ideas": [
            "Tree DFS: preorder (root-left-right), inorder (left-root-right), postorder (left-right-root) — each has specific use cases",
            "Graph DFS needs a visited set to avoid cycles; tree DFS doesn't because trees are acyclic",
            "DFS for connected components: start from each unvisited node, mark all reachable nodes",
            "DFS + memoization = top-down DP (e.g., longest increasing path in a matrix)",
            "DFS on a grid: treat each cell as a graph node with 4 neighbors (up/down/left/right)",
            "Post-order DFS computes bottom-up: diameter, height, path sum all use this pattern",
        ],
        "canonical_problems": [
            {
                "name": "Maximum Depth of Binary Tree",
                "slug": "maximum-depth-of-binary-tree",
                "difficulty": "easy",
                "why": "Simplest DFS on a tree: return 1 + max(left_depth, right_depth), base case = 0",
            },
            {
                "name": "Number of Islands",
                "slug": "number-of-islands",
                "difficulty": "medium",
                "why": "DFS on a grid: flood-fill each '1' island, mark visited, count connected components",
            },
            {
                "name": "Pacific Atlantic Water Flow",
                "slug": "pacific-atlantic-water-flow",
                "difficulty": "medium",
                "why": "Reverse DFS from ocean edges — teaches the 'start from the answer' trick",
            },
            {
                "name": "Binary Tree Maximum Path Sum",
                "slug": "binary-tree-maximum-path-sum",
                "difficulty": "hard",
                "why": "Post-order DFS: at each node, compute max single-path and update global max-path-through-node",
            },
            {
                "name": "Longest Increasing Path in a Matrix",
                "slug": "longest-increasing-path-in-a-matrix",
                "difficulty": "hard",
                "why": "DFS + memoization on a grid — the bridge between DFS and dynamic programming",
            },
        ],
        "common_mistakes": [
            "Forgetting the visited set in graph DFS — causes infinite loops in cyclic graphs",
            "Not returning values from recursive calls — DFS returns info bottom-up, don't discard it",
            "Stack overflow on very deep recursion — convert to iterative with explicit stack if needed",
            "Modifying the grid in-place without restoring it (matters in backtracking, not in flood-fill)",
            "Confusing preorder vs postorder: some problems need the answer computed after children are processed",
        ],
        "visual_examples": [
            {"description": "DFS traversal of a binary tree: show the recursive call stack and node visit order", "ds_type": "tree"},
            {"description": "Grid DFS for Number of Islands: color cells as they're visited, show the flood-fill spreading", "ds_type": "grid"},
            {"description": "DFS on a directed graph: show discovery/finish times and back edges for cycle detection", "ds_type": "graph"},
        ],
    },

    # =========================================================================
    # 4. Hash Map — 22 problems
    # =========================================================================
    {
        "slug": "hash_map",
        "title": "Hash Maps",
        "type": "dsa",
        "topic": "Hash Maps",
        "introduction": (
            "Hash maps (dictionaries) provide O(1) average-case lookup, insertion, and deletion "
            "by mapping keys to array indices via a hash function. They're the single most "
            "useful data structure in coding interviews — whenever you see 'find if X exists' "
            "or 'count occurrences,' a hash map is likely involved. The three core patterns are: "
            "complement lookup (Two Sum), frequency counting (anagrams), and grouping by key "
            "(group anagrams)."
        ),
        "key_ideas": [
            "Complement lookup: store value -> index, check if target - current exists — eliminates nested loops",
            "Frequency counting: Counter/dict to tally occurrences, then compare or threshold",
            "Grouping: defaultdict(list) to bucket items by a computed key (sorted string, modulo, etc.)",
            "Two-pass vs one-pass: sometimes you need all data before querying; other times one scan suffices",
            "Hash set for existence checks: when you only need 'have I seen this?' without associated values",
            "Collision handling: chaining vs open addressing — interview knowledge, rarely coded",
        ],
        "canonical_problems": [
            {
                "name": "Two Sum",
                "slug": "two-sum",
                "difficulty": "easy",
                "why": "The foundational complement-lookup pattern: O(n) with a map vs O(n^2) brute force",
            },
            {
                "name": "Group Anagrams",
                "slug": "group-anagrams",
                "difficulty": "medium",
                "why": "Grouping by computed key: sorted(word) or char-count tuple as the dict key",
            },
            {
                "name": "Top K Frequent Elements",
                "slug": "top-k-frequent-elements",
                "difficulty": "medium",
                "why": "Frequency count + bucket sort or heap — bridges hash maps with other data structures",
            },
            {
                "name": "LRU Cache",
                "slug": "lru-cache",
                "difficulty": "medium",
                "why": "Hash map + doubly-linked list for O(1) get/put — a design + data structure hybrid",
            },
            {
                "name": "Longest Consecutive Sequence",
                "slug": "longest-consecutive-sequence",
                "difficulty": "medium",
                "why": "Hash set for O(1) lookups + clever start-of-sequence detection gives O(n) without sorting",
            },
        ],
        "common_mistakes": [
            "Using a list for lookups instead of a set/dict — accidentally O(n) per check",
            "Forgetting to handle duplicate keys: later inserts overwrite earlier values",
            "Not considering hash collisions in complexity analysis (worst case is O(n) per operation)",
            "Mutating dict keys (e.g., using a list as a key) — keys must be hashable/immutable",
            "Iterating and modifying a dict simultaneously — causes RuntimeError in Python",
        ],
        "visual_examples": [
            {"description": "Hash map for Two Sum: show array scan, each element checked against map then inserted", "ds_type": "hash_map"},
            {"description": "Frequency count: bar chart of character counts for 'anagram' vs 'nagaram'", "ds_type": "hash_map"},
            {"description": "LRU Cache: hash map pointing into a doubly-linked list, show get/put operations", "ds_type": "hash_map"},
        ],
    },

    # =========================================================================
    # 5. Matrix — 13 problems
    # =========================================================================
    {
        "slug": "matrix",
        "title": "Matrix Problems",
        "type": "dsa",
        "topic": "Matrix Problems",
        "introduction": (
            "Matrix problems treat a 2D grid as a graph where each cell connects to its "
            "4 (or 8) neighbors. The key techniques are: DFS/BFS flood-fill for connected "
            "components (islands), layer-by-layer traversal (spiral), in-place rotation using "
            "transpose + reverse, and binary search on sorted matrices. Many matrix problems "
            "are graph problems in disguise — the grid is just a compact adjacency representation."
        ),
        "key_ideas": [
            "Grid as graph: each cell (r,c) has neighbors (r+/-1, c) and (r, c+/-1) — use DFS or BFS",
            "Boundary checks: 0 <= r < rows and 0 <= c < cols — the most common source of bugs",
            "In-place rotation: 90-degree clockwise = transpose + reverse each row",
            "Spiral traversal: maintain four boundaries (top, bottom, left, right), shrink after each pass",
            "Search in sorted matrix: row-sorted + col-sorted allows O(m+n) staircase search from top-right",
            "Direction arrays: dr = [-1,1,0,0], dc = [0,0,-1,1] to iterate over 4 neighbors cleanly",
        ],
        "canonical_problems": [
            {
                "name": "Set Matrix Zeroes",
                "slug": "set-matrix-zeroes",
                "difficulty": "medium",
                "why": "In-place marking: use first row/col as flags to avoid O(mn) extra space",
            },
            {
                "name": "Spiral Matrix",
                "slug": "spiral-matrix",
                "difficulty": "medium",
                "why": "Layer-by-layer traversal with four boundary pointers — pure simulation problem",
            },
            {
                "name": "Rotate Image",
                "slug": "rotate-image",
                "difficulty": "medium",
                "why": "Transpose + reverse trick for 90-degree rotation — elegant O(1) space",
            },
            {
                "name": "Search a 2D Matrix",
                "slug": "search-a-2d-matrix",
                "difficulty": "medium",
                "why": "Treat the matrix as a flat sorted array — binary search with row/col conversion",
            },
            {
                "name": "Word Search",
                "slug": "word-search",
                "difficulty": "medium",
                "why": "DFS backtracking on a grid: explore all 4 directions, mark visited, unmark on backtrack",
            },
        ],
        "common_mistakes": [
            "Index out of bounds: not checking row/col boundaries before accessing neighbors",
            "Confusing rows and columns: matrix[row][col] where row is the y-axis and col is x-axis",
            "Forgetting to mark/unmark visited cells in DFS — causes infinite loops or missed paths",
            "Off-by-one in spiral traversal boundary shrinking — skipping the last row or column",
            "Modifying the matrix during iteration without a copy when needed",
        ],
        "visual_examples": [
            {"description": "Grid with DFS flood-fill: color cells as visited, show island detection", "ds_type": "grid"},
            {"description": "Spiral traversal: arrows showing the path through the matrix layer by layer", "ds_type": "grid"},
            {"description": "Matrix rotation: show transpose step then reverse-rows step side by side", "ds_type": "grid"},
        ],
    },

    # =========================================================================
    # 6. Sorting — 13 problems
    # =========================================================================
    {
        "slug": "sorting",
        "title": "Sorting",
        "type": "dsa",
        "topic": "Sorting",
        "introduction": (
            "Sorting is a preprocessing step that unlocks simpler algorithms: binary search "
            "needs sorted data, two-pointer squeeze needs sorted data, and many greedy "
            "algorithms process elements in sorted order. Beyond using built-in sort, you "
            "should understand merge sort (stable, O(n log n), basis for external sort), "
            "quicksort (in-place, cache-friendly), and counting/bucket sort (O(n) for "
            "bounded integer ranges). The key interview insight: sorting costs O(n log n) — "
            "if your brute force is O(n^2), sorting + linear scan may be optimal."
        ),
        "key_ideas": [
            "Comparison sorts have an O(n log n) lower bound — merge sort and heap sort achieve this",
            "Quicksort: pick pivot, partition into <pivot and >pivot, recurse — O(n log n) average, O(n^2) worst",
            "Merge sort: divide in half, sort each half, merge — always O(n log n), stable, but O(n) extra space",
            "Bucket sort / counting sort: O(n) when the range of values is bounded (e.g., frequency of characters)",
            "Custom comparators: sort by multiple keys, sort by a computed value — Python: key=lambda x: ...",
            "Sorting as a preprocessing step: enables two-pointer, binary search, greedy, and deduplication",
        ],
        "canonical_problems": [
            {
                "name": "Valid Anagram",
                "slug": "valid-anagram",
                "difficulty": "easy",
                "why": "Sort both strings and compare — the simplest 'sorting as normalization' pattern",
            },
            {
                "name": "Merge Intervals",
                "slug": "merge-intervals",
                "difficulty": "medium",
                "why": "Sort by start time, then merge overlapping — sorting enables a single linear pass",
            },
            {
                "name": "3Sum",
                "slug": "3sum",
                "difficulty": "medium",
                "why": "Sort first, then fix one element and two-pointer the rest — O(n^2) from O(n^3)",
            },
            {
                "name": "Kth Largest Element in an Array",
                "slug": "kth-largest-element-in-an-array",
                "difficulty": "medium",
                "why": "Quickselect (partition-based): O(n) average vs O(n log n) full sort — partial sorting",
            },
            {
                "name": "Car Fleet",
                "slug": "car-fleet",
                "difficulty": "medium",
                "why": "Sort by position descending, then stack-based simulation — sorting defines processing order",
            },
        ],
        "common_mistakes": [
            "Assuming sort is always O(n log n) — Timsort in Python is O(n) on nearly-sorted data",
            "Not using a stable sort when order of equal elements matters",
            "Custom comparator returning wrong sign — causes subtle ordering bugs",
            "Sorting when you only need the kth element — use quickselect or a heap instead",
            "Forgetting that sorted() returns a new list while .sort() modifies in-place (Python)",
        ],
        "visual_examples": [
            {"description": "Merge sort: show the divide and conquer tree, then the merge step combining sorted halves", "ds_type": "tree"},
            {"description": "Quicksort partition: pivot element, elements moving left/right of pivot", "ds_type": "array"},
            {"description": "Bucket sort: elements distributed into buckets by range, then each bucket sorted", "ds_type": "array"},
        ],
    },

    # =========================================================================
    # 7. BFS (Breadth-First Search) — 12 problems
    # =========================================================================
    {
        "slug": "bfs",
        "title": "Breadth-First Search",
        "type": "dsa",
        "topic": "Breadth-First Search",
        "introduction": (
            "Breadth-First Search (BFS) explores nodes level by level using a queue. It "
            "guarantees the shortest path in unweighted graphs, which is why it's the go-to "
            "for 'minimum steps/moves' problems. BFS is also the standard for level-order tree "
            "traversal. The pattern is: enqueue the start, dequeue, process, enqueue all "
            "unvisited neighbors, repeat. Multi-source BFS starts with multiple nodes in the "
            "queue simultaneously — used for problems like 'rotting oranges' and 'walls and gates.'"
        ),
        "key_ideas": [
            "BFS = shortest path in unweighted graphs: each level is one step further from the source",
            "Level-order traversal: process all nodes at depth d before moving to depth d+1 — use queue size trick",
            "Multi-source BFS: enqueue all sources at once, propagate outward simultaneously",
            "BFS on a grid: same as graph BFS but neighbors are 4-directional cells",
            "0-1 BFS: if edge weights are 0 or 1, use a deque — add 0-weight edges to front, 1-weight to back",
            "BFS vs DFS: BFS finds shortest path and uses more memory; DFS uses less memory but no shortest-path guarantee",
        ],
        "canonical_problems": [
            {
                "name": "Binary Tree Level Order Traversal",
                "slug": "binary-tree-level-order-traversal",
                "difficulty": "medium",
                "why": "The canonical BFS on a tree: queue + level-size trick to group nodes by depth",
            },
            {
                "name": "Rotting Oranges",
                "slug": "rotting-oranges",
                "difficulty": "medium",
                "why": "Multi-source BFS: all rotten oranges enqueued at time 0, spread outward level by level",
            },
            {
                "name": "Walls and Gates",
                "slug": "walls-and-gates",
                "difficulty": "medium",
                "why": "Multi-source BFS from all gates: each cell gets the minimum distance to any gate",
            },
            {
                "name": "Word Ladder",
                "slug": "word-ladder",
                "difficulty": "hard",
                "why": "BFS on an implicit graph: nodes are words, edges connect words differing by one letter",
            },
            {
                "name": "Binary Tree Right Side View",
                "slug": "binary-tree-right-side-view",
                "difficulty": "medium",
                "why": "Level-order BFS: the last node at each level is visible from the right side",
            },
        ],
        "common_mistakes": [
            "Forgetting to mark nodes as visited BEFORE enqueueing — causes duplicate processing and TLE",
            "Not using the level-size trick when level boundaries matter — mixing levels in the same loop",
            "Using DFS when shortest path is required — DFS does not guarantee shortest path",
            "BFS on weighted graphs without modification — need Dijkstra or 0-1 BFS instead",
            "Queue growing too large on dense graphs — consider bidirectional BFS for optimization",
        ],
        "visual_examples": [
            {"description": "BFS on a tree: show queue contents at each step, nodes processed level by level", "ds_type": "tree"},
            {"description": "Multi-source BFS on a grid: rotten oranges spreading outward, distance labels on cells", "ds_type": "grid"},
            {"description": "Word Ladder BFS: graph of words connected by single-letter changes, shortest path highlighted", "ds_type": "graph"},
        ],
    },

    # =========================================================================
    # 8. Math — 12 problems
    # =========================================================================
    {
        "slug": "math",
        "title": "Math & Geometry",
        "type": "dsa",
        "topic": "Math & Geometry",
        "introduction": (
            "Math problems in coding interviews test your ability to spot numerical patterns "
            "and mathematical properties. You won't need advanced math — the key areas are: "
            "modular arithmetic (avoid overflow, check divisibility), digit manipulation "
            "(reverse integer, palindrome number), fast exponentiation (binary method), and "
            "geometry basics (area, distance, rotation). The common thread: replace brute-force "
            "simulation with a mathematical formula or property."
        ),
        "key_ideas": [
            "Modular arithmetic: (a * b) % m = ((a % m) * (b % m)) % m — prevents overflow in large computations",
            "Fast exponentiation: compute x^n in O(log n) by squaring — if n is even, x^n = (x^(n/2))^2",
            "Digit manipulation: extract digits with % 10 and // 10 — rebuild reversed/modified numbers",
            "Matrix rotation: 90-degree clockwise = transpose + reverse rows — no extra space needed",
            "Combinatorics: unique paths = C(m+n-2, m-1) — sometimes a formula replaces DP entirely",
            "Cycle detection (Floyd's): slow/fast pointers meet in a cycle — applies to happy number, linked list cycle",
        ],
        "canonical_problems": [
            {
                "name": "Happy Number",
                "slug": "happy-number",
                "difficulty": "easy",
                "why": "Cycle detection with a hash set or Floyd's algorithm — math meets graph theory",
            },
            {
                "name": "Plus One",
                "slug": "plus-one",
                "difficulty": "easy",
                "why": "Carry propagation from least significant digit — simulates addition without BigInteger",
            },
            {
                "name": "Pow(x, n)",
                "slug": "powx-n",
                "difficulty": "medium",
                "why": "Fast exponentiation by squaring: O(log n) instead of O(n) — handle negative exponents",
            },
            {
                "name": "Multiply Strings",
                "slug": "multiply-strings",
                "difficulty": "medium",
                "why": "Grade-school multiplication digit by digit — teaches positional arithmetic",
            },
            {
                "name": "Rotate Image",
                "slug": "rotate-image",
                "difficulty": "medium",
                "why": "Matrix rotation in-place: transpose then reverse rows — a geometric transformation",
            },
        ],
        "common_mistakes": [
            "Integer overflow: not using long/BigInteger when intermediate products exceed 32-bit range",
            "Negative number edge cases: -1 % 10 behaves differently in Python vs Java/C++",
            "Forgetting n=0 and n=negative in exponentiation — x^0 = 1, x^(-n) = 1/x^n",
            "Off-by-one in combinatorics: C(n,k) vs C(n-1,k-1) — carefully define what you're counting",
            "Floating-point comparison: use abs(a-b) < epsilon instead of a == b for floats",
        ],
        "visual_examples": [
            {"description": "Fast exponentiation tree: show x^10 computed as (x^5)^2, x^5 as x*(x^2)^2", "ds_type": "tree"},
            {"description": "Digit extraction: show 12345 being broken into [1,2,3,4,5] with repeated %10 and //10", "ds_type": "array"},
            {"description": "Matrix rotation: original grid -> transposed grid -> row-reversed grid", "ds_type": "grid"},
        ],
    },

    # =========================================================================
    # 9. Bit Manipulation — 7 problems
    # =========================================================================
    {
        "slug": "bit_manipulation",
        "title": "Bit Manipulation",
        "type": "dsa",
        "topic": "Bit Manipulation",
        "introduction": (
            "Bit manipulation uses bitwise operators (&, |, ^, ~, <<, >>) to solve problems "
            "at the binary level. The most important trick is XOR: a ^ a = 0 and a ^ 0 = a, "
            "which lets you find the single unique element in O(1) space. Other key operations: "
            "check if the ith bit is set (n & (1 << i)), set a bit (n | (1 << i)), clear a "
            "bit (n & ~(1 << i)). Bit manipulation gives O(1) space solutions that replace "
            "hash maps for certain counting and pairing problems."
        ),
        "key_ideas": [
            "XOR properties: a ^ a = 0, a ^ 0 = a, XOR is commutative and associative — find the unique element",
            "Check bit: (n >> i) & 1 gives the ith bit — used in counting bits, checking parity",
            "Brian Kernighan's trick: n & (n-1) clears the lowest set bit — count set bits in O(number of 1-bits)",
            "Two's complement: -n = ~n + 1 — negative numbers have leading 1s in binary",
            "Bit shifting for multiplication/division: n << 1 = n*2, n >> 1 = n//2 — faster than arithmetic",
            "Add without +: use XOR for sum-without-carry, AND + left-shift for carry, repeat until carry is 0",
        ],
        "canonical_problems": [
            {
                "name": "Single Number",
                "slug": "single-number",
                "difficulty": "easy",
                "why": "XOR all elements: duplicates cancel out, leaving the unique number — O(1) space",
            },
            {
                "name": "Number of 1 Bits",
                "slug": "number-of-1-bits",
                "difficulty": "easy",
                "why": "Count set bits: either check each of 32 bits, or use n & (n-1) to clear lowest set bit",
            },
            {
                "name": "Counting Bits",
                "slug": "counting-bits",
                "difficulty": "easy",
                "why": "DP + bit trick: dp[i] = dp[i >> 1] + (i & 1) — number of 1-bits builds on smaller values",
            },
            {
                "name": "Reverse Bits",
                "slug": "reverse-bits",
                "difficulty": "easy",
                "why": "Extract bits from right, build result from left — 32 iterations with shift operations",
            },
            {
                "name": "Sum of Two Integers",
                "slug": "sum-of-two-integers",
                "difficulty": "medium",
                "why": "Add without arithmetic operators: XOR for bit sum, AND+shift for carry, loop until no carry",
            },
        ],
        "common_mistakes": [
            "Confusing signed vs unsigned: right shift (>>) is arithmetic (preserves sign) vs logical (>>>)",
            "Forgetting Python integers have arbitrary precision — no 32-bit overflow, need to mask with & 0xFFFFFFFF",
            "Not handling negative numbers in bit reversal or counting — two's complement representation",
            "Using ^ (XOR) when you meant ** (exponentiation) in Python — subtle syntax error",
            "Off-by-one in bit positions: bit 0 is the rightmost (least significant), not the leftmost",
        ],
        "visual_examples": [
            {"description": "XOR cancellation: show [4,1,2,1,2] being XORed step by step, pairs canceling to 0", "ds_type": "array"},
            {"description": "Brian Kernighan's trick: show n=1011 -> 1010 -> 1000 -> 0000, counting 3 steps", "ds_type": "array"},
            {"description": "Bit addition: XOR for sum bits, AND+shift for carry bits, iterate until carry=0", "ds_type": "array"},
        ],
    },

    # =========================================================================
    # 10. Intervals — 6 problems
    # =========================================================================
    {
        "slug": "intervals",
        "title": "Intervals",
        "type": "dsa",
        "topic": "Intervals",
        "introduction": (
            "Interval problems involve ranges [start, end] and require detecting overlaps, "
            "merging, or scheduling. The universal first step is: sort by start time (or end "
            "time for scheduling). Once sorted, you can process intervals left to right with "
            "a greedy or sweep-line approach. The three main patterns are: merge overlapping "
            "intervals, interval scheduling (maximize non-overlapping), and sweep line with "
            "a heap for concurrent intervals (meeting rooms)."
        ),
        "key_ideas": [
            "Sort by start time first — this is almost always the first step for interval problems",
            "Overlap detection: intervals [a,b] and [c,d] overlap iff a < d and c < b (assuming sorted)",
            "Merge pattern: sort, then extend current interval if overlap, else start new interval",
            "Interval scheduling: sort by end time, greedily pick non-overlapping — maximum number of meetings",
            "Sweep line with heap: track 'active' intervals, heap gives the earliest ending — count max concurrent",
            "Insert interval: binary search or linear scan to find insertion point, then merge affected intervals",
        ],
        "canonical_problems": [
            {
                "name": "Meeting Rooms",
                "slug": "meeting-rooms",
                "difficulty": "easy",
                "why": "Sort + check consecutive pairs for overlap — the simplest interval problem",
            },
            {
                "name": "Merge Intervals",
                "slug": "merge-intervals",
                "difficulty": "medium",
                "why": "Sort by start, extend or emit — the canonical merge pattern used in many problems",
            },
            {
                "name": "Insert Interval",
                "slug": "insert-interval",
                "difficulty": "medium",
                "why": "Three phases: intervals before, overlapping with, and after the new interval",
            },
            {
                "name": "Meeting Rooms II",
                "slug": "meeting-rooms-ii",
                "difficulty": "medium",
                "why": "Min-heap of end times to track active meetings — count the peak concurrent count",
            },
            {
                "name": "Non-overlapping Intervals",
                "slug": "non-overlapping-intervals",
                "difficulty": "medium",
                "why": "Greedy: sort by end time, keep intervals that don't overlap — min removals = total - max non-overlapping",
            },
        ],
        "common_mistakes": [
            "Not sorting first — interval algorithms assume sorted input",
            "Confusing inclusive vs exclusive endpoints: [1,3] and [3,5] — do they overlap?",
            "Sorting by start time when the algorithm needs sort by end time (interval scheduling)",
            "Using O(n^2) pairwise comparison instead of sort + linear scan",
            "Off-by-one when intervals touch at endpoints — clarify with the problem statement",
        ],
        "visual_examples": [
            {"description": "Intervals on a number line: show overlapping and non-overlapping pairs before and after merge", "ds_type": "array"},
            {"description": "Meeting Rooms II: timeline with overlapping meetings, heap tracking end times, max concurrent highlighted", "ds_type": "array"},
            {"description": "Insert Interval: new interval splitting the timeline into before/overlap/after segments", "ds_type": "array"},
        ],
    },

    # =========================================================================
    # 11. Trie — 3 problems
    # =========================================================================
    {
        "slug": "trie",
        "title": "Trie (Prefix Tree)",
        "type": "dsa",
        "topic": "Trie (Prefix Tree)",
        "introduction": (
            "A trie (prefix tree) stores strings character by character in a tree structure "
            "where each node represents a character and paths from root to leaves form words. "
            "Tries enable O(L) lookup, insertion, and prefix search where L is the word length — "
            "independent of the number of stored words. They're the go-to data structure when "
            "you need prefix-based operations: autocomplete, spell checking, word search on a "
            "board, and IP routing (longest prefix match)."
        ),
        "key_ideas": [
            "Each node has up to 26 children (for lowercase English) — a dict or array of child pointers",
            "is_end flag marks complete words vs prefixes — 'app' is a prefix of 'apple'",
            "Insert: walk down creating nodes as needed, mark the last node as is_end",
            "Search: walk down following characters, return True only if is_end is set at the end",
            "startsWith: same as search but don't check is_end — any path match means a prefix exists",
            "Trie + DFS backtracking: Word Search II uses a trie to prune the search space on a grid",
        ],
        "canonical_problems": [
            {
                "name": "Implement Trie (Prefix Tree)",
                "slug": "implement-trie-prefix-tree",
                "difficulty": "medium",
                "why": "Build the trie from scratch: insert, search, startsWith — the foundation for all trie problems",
            },
            {
                "name": "Design Add and Search Words Data Structure",
                "slug": "design-add-and-search-words-data-structure",
                "difficulty": "medium",
                "why": "Trie + DFS: the '.' wildcard forces branching at each wildcard position",
            },
            {
                "name": "Word Search II",
                "slug": "word-search-ii",
                "difficulty": "hard",
                "why": "Trie + backtracking on a grid: build trie from word list, DFS on the board pruning with trie nodes",
            },
        ],
        "common_mistakes": [
            "Using a hash map of full strings instead of a trie — loses the prefix-sharing advantage",
            "Forgetting the is_end flag — 'app' shouldn't match as a word if only 'apple' was inserted",
            "Not pruning trie nodes in Word Search II — removing found words improves from TLE to accepted",
            "Memory overhead: 26 pointers per node adds up — use dict-based children for sparse tries",
            "Confusing trie depth with string length — off-by-one if root represents empty string",
        ],
        "visual_examples": [
            {"description": "Trie storing ['apple', 'app', 'apt', 'bat']: tree with shared prefixes, is_end markers highlighted", "ds_type": "tree"},
            {"description": "Trie search for 'a.p': DFS branching at the wildcard '.', checking all children", "ds_type": "tree"},
            {"description": "Word Search II: trie overlaid on a grid, DFS paths following trie branches", "ds_type": "grid"},
        ],
    },

    # =========================================================================
    # 12. Union Find — 3 problems
    # =========================================================================
    {
        "slug": "union_find",
        "title": "Union Find (Disjoint Set)",
        "type": "dsa",
        "topic": "Union Find (Disjoint Set)",
        "introduction": (
            "Union-Find (Disjoint Set Union, DSU) tracks a collection of non-overlapping sets "
            "and supports two operations: find(x) returns the representative of x's set, and "
            "union(x,y) merges the sets containing x and y. With path compression and union by "
            "rank, both operations run in nearly O(1) amortized time (inverse Ackermann). "
            "Union-Find is the optimal choice for dynamic connectivity: 'are these two nodes "
            "connected?' and 'merge these two groups.'"
        ),
        "key_ideas": [
            "parent[] array: parent[x] = x means x is a root; otherwise follow parent pointers to find root",
            "Path compression: in find(), set each node's parent directly to the root — flattens the tree",
            "Union by rank: attach the shorter tree under the taller one — keeps tree height logarithmic",
            "Connected components: count roots (nodes where parent[x] == x) — decreases with each union",
            "Cycle detection in undirected graphs: if find(u) == find(v) before union, edge (u,v) creates a cycle",
            "Kruskal's MST: sort edges by weight, union endpoints, skip edges that would create a cycle",
        ],
        "canonical_problems": [
            {
                "name": "Number of Connected Components in an Undirected Graph",
                "slug": "number-of-connected-components-in-an-undirected-graph",
                "difficulty": "medium",
                "why": "Classic union-find: start with n components, each union decreases count by 1",
            },
            {
                "name": "Redundant Connection",
                "slug": "redundant-connection",
                "difficulty": "medium",
                "why": "Cycle detection: the first edge where find(u) == find(v) is the redundant edge",
            },
            {
                "name": "Graph Valid Tree",
                "slug": "graph-valid-tree",
                "difficulty": "medium",
                "why": "A tree has n-1 edges and is connected: union-find checks both conditions simultaneously",
            },
        ],
        "common_mistakes": [
            "Forgetting path compression: without it, find() is O(n) worst case instead of O(alpha(n))",
            "Not initializing parent[x] = x for all nodes — uninitialized values cause incorrect roots",
            "Using union-find on directed graphs — it only works for undirected connectivity",
            "Comparing parent[x] instead of find(x) — parent may not be the root after unions",
            "Off-by-one in component counting: initial count is n, decrease by 1 per successful union",
        ],
        "visual_examples": [
            {"description": "Union-Find forest: show trees with parent pointers, path compression flattening after find()", "ds_type": "tree"},
            {"description": "Union by rank: two trees of different heights, shorter tree attached under taller root", "ds_type": "tree"},
            {"description": "Redundant connection: edges added one by one, the edge forming a cycle is highlighted", "ds_type": "graph"},
        ],
    },

    # =========================================================================
    # 13. Topological Sort — 3 problems
    # =========================================================================
    {
        "slug": "topological_sort",
        "title": "Topological Sort",
        "type": "dsa",
        "topic": "Topological Sort",
        "introduction": (
            "Topological sort produces a linear ordering of vertices in a directed acyclic graph "
            "(DAG) such that for every edge u->v, u appears before v. It's essential for "
            "dependency resolution: course prerequisites, build systems, task scheduling. There "
            "are two approaches: Kahn's algorithm (BFS with in-degree tracking) and DFS-based "
            "(reverse postorder). Topological sort also detects cycles — if you can't process "
            "all nodes, there's a cycle."
        ),
        "key_ideas": [
            "Kahn's algorithm (BFS): compute in-degrees, enqueue all nodes with in-degree 0, process and decrement neighbors",
            "DFS-based: run DFS, append node to result after all descendants are processed (reverse postorder)",
            "Cycle detection: if Kahn's processes fewer than n nodes, there's a cycle (some nodes never reach in-degree 0)",
            "Multiple valid orderings: topological sort is not unique — the queue/stack order can vary",
            "Prerequisites pattern: if course B requires course A, edge A->B means A must come first",
            "DAG shortest/longest path: process nodes in topological order, relax edges — O(V+E)",
        ],
        "canonical_problems": [
            {
                "name": "Course Schedule",
                "slug": "course-schedule",
                "difficulty": "medium",
                "why": "Cycle detection in a directed graph: if a valid topological order exists, all courses can be taken",
            },
            {
                "name": "Course Schedule II",
                "slug": "course-schedule-ii",
                "difficulty": "medium",
                "why": "Actually produce the topological ordering: Kahn's BFS gives the order directly",
            },
            {
                "name": "Alien Dictionary",
                "slug": "alien-dictionary",
                "difficulty": "hard",
                "why": "Build a graph from sorted word pairs, then topological sort — combines string processing with graph algorithms",
            },
        ],
        "common_mistakes": [
            "Applying topological sort to graphs with cycles — it only works on DAGs, detect cycles first",
            "Building the graph incorrectly: edge direction matters — prerequisite POINTS TO dependent",
            "Not handling disconnected components: nodes with no edges still need to appear in the output",
            "Forgetting that multiple valid topological orders exist — don't assume uniqueness",
            "In Alien Dictionary: only adjacent words in the sorted list give ordering constraints, not all pairs",
        ],
        "visual_examples": [
            {"description": "DAG with courses and prerequisites: arrows showing dependencies, topological order numbered", "ds_type": "graph"},
            {"description": "Kahn's algorithm step by step: in-degree table, queue contents, processing order", "ds_type": "graph"},
            {"description": "Alien Dictionary: words -> character graph -> topological order of the alien alphabet", "ds_type": "graph"},
        ],
    },
]

# ---------------------------------------------------------------------------
# MISSING SD CONCEPT PLANS
# ---------------------------------------------------------------------------

SD_CONCEPT_PLANS = [
    # =========================================================================
    # 1. Data Modeling
    # =========================================================================
    {
        "slug": "data-modeling",
        "title": "Data Modeling",
        "type": "sd",
        "topic": "Data Modeling",
        "introduction": (
            "Data modeling is the foundation of every system design: choosing the right schema, "
            "relationships, and storage engine determines your system's performance, scalability, "
            "and evolution path. The core trade-off is normalization (reduce redundancy, maintain "
            "consistency) vs denormalization (reduce joins, improve read performance). In "
            "interviews, you must justify your schema choices by reasoning about access patterns."
        ),
        "key_ideas": [
            "Normalization (3NF): eliminate redundancy, enforce consistency — but expensive joins at scale",
            "Denormalization: pre-join data for read performance — accept write complexity and potential staleness",
            "Entity-Relationship modeling: entities (nouns), relationships (verbs), cardinality (1:1, 1:N, M:N)",
            "Schema-on-read (NoSQL) vs schema-on-write (SQL): flexibility vs safety trade-off",
        ],
        "canonical_problems": [
            {"name": "Design Instagram / Photo Sharing", "slug": "design-instagram-photo-sharing", "difficulty": "medium", "why": "Models users, posts, followers, likes — classic 1:N and M:N relationships with denormalized feed"},
            {"name": "Design Chat System / WhatsApp", "slug": "design-chat-system-whatsapp", "difficulty": "medium", "why": "Message storage schema: partition by conversation, sort by timestamp — time-series data modeling"},
            {"name": "Design Twitter / News Feed", "slug": "design-twitter-news-feed", "difficulty": "hard", "why": "Social graph modeling + fan-out storage: normalized user data vs denormalized timeline"},
        ],
        "common_mistakes": [
            "Over-normalizing for a read-heavy system — joins become the bottleneck at scale",
            "Choosing a schema without considering the primary access patterns",
            "Using auto-increment IDs in distributed systems — they don't scale across shards",
        ],
        "visual_examples": [
            {"description": "ER diagram: Users -> Posts (1:N), Users <-> Users (M:N followers), Posts -> Comments (1:N)", "ds_type": "mermaid"},
            {"description": "Normalized vs denormalized: separate tables with joins vs single document with embedded data", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 2. Numbers to Know
    # =========================================================================
    {
        "slug": "numbers-to-know",
        "title": "Numbers Every Engineer Should Know",
        "type": "sd",
        "topic": "Numbers to Know",
        "introduction": (
            "Back-of-the-envelope estimation is a core system design skill. You need to know "
            "latency numbers (L1 cache: 0.5ns, RAM: 100ns, SSD: 100us, HDD: 10ms, same-DC "
            "round trip: 0.5ms, cross-continent: 150ms), throughput numbers (SSD: 1GB/s, HDD: "
            "100MB/s, 1Gbps network: 100MB/s), and storage numbers (1M users * 1KB = 1GB). "
            "These let you quickly assess if a design is feasible and where bottlenecks will be."
        ),
        "key_ideas": [
            "Latency hierarchy: L1 cache (0.5ns) < L2 (7ns) < RAM (100ns) < SSD (100us) < HDD (10ms) < network (ms)",
            "Throughput: QPS estimation — 1M DAU with 10 requests each = ~100 RPS average, ~1000 RPS peak (10x)",
            "Storage estimation: users * data-per-user * retention period — convert to GB/TB/PB",
            "Bandwidth: 100MB/s per 1Gbps link — calculate if your design can serve N requests of size S",
        ],
        "canonical_problems": [
            {"name": "URL Shortener", "slug": "url-shortener", "difficulty": "medium", "why": "Classic estimation: 100M URLs/day, read:write 100:1, storage for 5 years = how many TB?"},
            {"name": "Design YouTube / Video Streaming", "slug": "design-youtube-video-streaming", "difficulty": "hard", "why": "Bandwidth-heavy: 1M concurrent streams * 5Mbps = 5Tbps — drives CDN and encoding decisions"},
            {"name": "Design Key-Value Store", "slug": "design-key-value-store", "difficulty": "medium", "why": "Memory vs disk: 1B keys * 1KB = 1TB — fits in memory across 100 servers with 10GB each?"},
        ],
        "common_mistakes": [
            "Confusing latency (time for one operation) with throughput (operations per second)",
            "Forgetting the 10x peak-to-average ratio when sizing for peak traffic",
            "Not accounting for replication factor in storage estimates (3x for most systems)",
        ],
        "visual_examples": [
            {"description": "Latency comparison: logarithmic scale from nanoseconds to seconds, color-coded by storage tier", "ds_type": "mermaid"},
            {"description": "Back-of-envelope calculation: DAU -> RPS -> storage -> bandwidth, step by step", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 3. Realtime Updates
    # =========================================================================
    {
        "slug": "realtime-updates",
        "title": "Realtime Updates",
        "type": "sd",
        "topic": "Realtime Updates",
        "introduction": (
            "Realtime updates push data from server to client without the client polling. The "
            "three main approaches are: WebSockets (full-duplex, persistent connection — best "
            "for chat, gaming), Server-Sent Events (SSE, server-to-client only, simpler, auto-"
            "reconnect), and long polling (client opens request, server holds until data is "
            "available — simplest to implement, worst at scale). Choosing the right mechanism "
            "depends on bidirectionality, connection count, and infrastructure support."
        ),
        "key_ideas": [
            "WebSockets: full-duplex over a single TCP connection — ideal for chat, collaborative editing, gaming",
            "Server-Sent Events (SSE): one-way server-to-client over HTTP — simpler than WS, built-in reconnect, works through proxies",
            "Long polling: client sends request, server holds until data or timeout — fallback for environments blocking WS/SSE",
            "Connection management at scale: 1M concurrent WS connections need ~40GB RAM — use sticky sessions + connection servers",
        ],
        "canonical_problems": [
            {"name": "Design Chat System / WhatsApp", "slug": "design-chat-system-whatsapp", "difficulty": "medium", "why": "WebSocket-based: bidirectional messaging, presence indicators, typing status — the canonical realtime system"},
            {"name": "Design Uber / Ride Sharing", "slug": "design-uber-ride-sharing", "difficulty": "hard", "why": "Location updates via WebSocket: driver positions streamed to riders every few seconds"},
            {"name": "Design Twitter / News Feed", "slug": "design-twitter-news-feed", "difficulty": "hard", "why": "SSE or long polling for feed updates: new tweets pushed to timeline without full refresh"},
        ],
        "common_mistakes": [
            "Using WebSockets when SSE suffices — WS adds complexity (connection management, ping/pong, reconnection logic)",
            "Not planning for reconnection: clients disconnect frequently on mobile — need message buffering and replay",
            "Ignoring load balancer configuration: WebSockets need sticky sessions or a dedicated connection layer",
        ],
        "visual_examples": [
            {"description": "Comparison: polling vs long-polling vs SSE vs WebSocket — timeline showing request/response patterns", "ds_type": "mermaid"},
            {"description": "WebSocket architecture: client <-> LB (sticky) <-> connection server <-> message broker <-> connection server <-> client", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 4. Contention
    # =========================================================================
    {
        "slug": "contention",
        "title": "Contention & Concurrency Control",
        "type": "sd",
        "topic": "Contention",
        "introduction": (
            "Contention arises when multiple actors try to read-modify-write the same resource "
            "simultaneously. The three main strategies are: pessimistic locking (acquire lock "
            "before access — simple but reduces throughput), optimistic concurrency control "
            "(proceed without locks, detect conflicts at commit time — better for low-contention "
            "workloads), and queue-based serialization (funnel all writes through a single-writer "
            "queue — eliminates contention by design)."
        ),
        "key_ideas": [
            "Pessimistic locking: SELECT FOR UPDATE or distributed lock (Redis/Zookeeper) — blocks other writers",
            "Optimistic concurrency (CAS): read version, write with WHERE version=X, retry on conflict — no blocking",
            "Queue-based serialization: route all writes for a key to the same queue/worker — eliminates races by design",
            "Distributed locks: Redlock, Zookeeper ephemeral nodes, DynamoDB conditional writes — all have trade-offs",
        ],
        "canonical_problems": [
            {"name": "Design Ticketmaster / Booking System", "slug": "design-ticketmaster-booking-system", "difficulty": "hard", "why": "Seat reservation: pessimistic lock on the seat row, or optimistic with version + retry on conflict"},
            {"name": "Design Payment System", "slug": "design-payment-system", "difficulty": "hard", "why": "Account balance updates: must be atomic — distributed transactions or saga with idempotency keys"},
            {"name": "Design Rate Limiter", "slug": "design-rate-limiter", "difficulty": "easy", "why": "Counter increment: Redis INCR is atomic, but distributed rate limiting needs coordination"},
        ],
        "common_mistakes": [
            "Using pessimistic locks with long hold times — blocks all other requests, destroys throughput",
            "Optimistic retry without backoff — thundering herd on high-contention resources",
            "Not making operations idempotent — retries after timeout can cause double-processing",
        ],
        "visual_examples": [
            {"description": "Pessimistic vs optimistic locking timeline: two concurrent requests, lock/wait vs attempt/conflict/retry", "ds_type": "mermaid"},
            {"description": "Queue-based serialization: multiple writers -> single queue -> serial processor -> database", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 5. Sagas
    # =========================================================================
    {
        "slug": "sagas",
        "title": "Sagas & Distributed Transactions",
        "type": "sd",
        "topic": "Sagas",
        "introduction": (
            "Sagas handle multi-step business processes across microservices where a traditional "
            "ACID transaction isn't possible. Each step has a compensating action that undoes its "
            "effect. If step 3 fails, you run compensations for steps 2 and 1 in reverse order. "
            "There are two coordination styles: choreography (each service listens to events and "
            "acts independently) and orchestration (a central coordinator directs the sequence). "
            "Sagas trade atomicity for availability — you get eventual consistency, not strong consistency."
        ),
        "key_ideas": [
            "Compensating transactions: each forward step has a reverse step — e.g., 'charge card' compensated by 'refund card'",
            "Choreography: services emit events, other services react — decentralized, but hard to track overall progress",
            "Orchestration: a central saga coordinator calls each service in sequence — easier to reason about, single point of failure",
            "Idempotency is critical: steps and compensations may execute multiple times due to retries",
        ],
        "canonical_problems": [
            {"name": "Design Payment System", "slug": "design-payment-system", "difficulty": "hard", "why": "Payment flow: reserve funds -> create order -> charge card -> notify. Failure at any step triggers compensations"},
            {"name": "Design Uber / Ride Sharing", "slug": "design-uber-ride-sharing", "difficulty": "hard", "why": "Ride booking: match driver -> reserve driver -> charge rider -> start trip. Driver cancellation triggers compensation"},
            {"name": "Design Ticketmaster / Booking System", "slug": "design-ticketmaster-booking-system", "difficulty": "hard", "why": "Seat booking: hold seat -> process payment -> confirm booking. Payment failure releases the held seat"},
        ],
        "common_mistakes": [
            "Not defining compensating actions for every step — leaves the system in an inconsistent state on failure",
            "Assuming saga = ACID transaction — sagas provide eventual consistency, not isolation",
            "Not handling the case where a compensation itself fails — need retry logic and dead-letter queues",
        ],
        "visual_examples": [
            {"description": "Saga sequence: Step 1 -> Step 2 -> Step 3 (FAIL) -> Compensate 2 -> Compensate 1, arrows and status", "ds_type": "mermaid"},
            {"description": "Choreography vs orchestration: event-driven fan-out vs central coordinator calling services", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 6. Scaling Reads
    # =========================================================================
    {
        "slug": "scaling-reads",
        "title": "Scaling Reads",
        "type": "sd",
        "topic": "Scaling Reads",
        "introduction": (
            "Most systems are read-heavy (90%+ reads). Scaling reads involves three layers: "
            "caching (reduce database hits), read replicas (spread load across multiple DB copies), "
            "and CDN/edge caching (serve static content close to users). The key trade-off is "
            "consistency — cached/replicated data may be stale. Understanding cache invalidation "
            "strategies and replication lag is essential for designing read-scalable systems."
        ),
        "key_ideas": [
            "Caching layer (Redis/Memcached): cache-aside, read-through, write-through, write-behind — each has different staleness/complexity",
            "Read replicas: async replication from primary — reads can go to any replica, but may see stale data",
            "CDN for static assets: images, CSS, JS served from edge locations — reduces origin load by 90%+",
            "Denormalization: pre-compute and store query results — trades write complexity for read speed",
        ],
        "canonical_problems": [
            {"name": "Design Instagram / Photo Sharing", "slug": "design-instagram-photo-sharing", "difficulty": "medium", "why": "Read-heavy feed: CDN for images, Redis for timeline cache, read replicas for user profiles"},
            {"name": "Design YouTube / Video Streaming", "slug": "design-youtube-video-streaming", "difficulty": "hard", "why": "Video serving: multi-tier CDN, adaptive bitrate, hot video caching at edge — extreme read scaling"},
            {"name": "Design Distributed Cache", "slug": "design-distributed-cache", "difficulty": "medium", "why": "The caching layer itself: consistent hashing, eviction policies, replication within the cache cluster"},
        ],
        "common_mistakes": [
            "Cache-aside without TTL: stale data lives forever — always set a TTL even if it's long",
            "Not considering cache stampede: when a hot key expires, hundreds of requests hit the DB simultaneously",
            "Assuming read replicas are strongly consistent — they lag by milliseconds to seconds",
        ],
        "visual_examples": [
            {"description": "Read path: client -> CDN -> cache -> read replica -> primary DB, with cache hit/miss paths", "ds_type": "mermaid"},
            {"description": "Cache-aside pattern: check cache -> miss -> query DB -> populate cache -> return", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 7. Scaling Writes
    # =========================================================================
    {
        "slug": "scaling-writes",
        "title": "Scaling Writes",
        "type": "sd",
        "topic": "Scaling Writes",
        "introduction": (
            "Scaling writes is harder than scaling reads because writes must be durable and "
            "consistent. The main strategies are: sharding (partition data across multiple "
            "databases by a shard key), write-ahead logging + batching (amortize disk I/O), "
            "message queues (buffer writes and process asynchronously), and CQRS (separate "
            "read and write models). The critical decision is choosing a shard key that "
            "distributes writes evenly without creating hot partitions."
        ),
        "key_ideas": [
            "Sharding: partition data by user_id, region, or hash — each shard handles a fraction of writes",
            "Write-behind (async writes): accept write, put in queue, batch-write to DB — improves throughput but risks data loss",
            "CQRS: separate write model (optimized for consistency) from read model (optimized for queries) — sync via events",
            "Append-only logs: Kafka, WAL — sequential writes are 100x faster than random writes on disk",
        ],
        "canonical_problems": [
            {"name": "Design Twitter / News Feed", "slug": "design-twitter-news-feed", "difficulty": "hard", "why": "Write amplification: one tweet by a celebrity fans out to millions of timelines — async via message queue"},
            {"name": "Design Chat System / WhatsApp", "slug": "design-chat-system-whatsapp", "difficulty": "medium", "why": "Message writes: partition by conversation_id, Cassandra for write-optimized storage, async delivery"},
            {"name": "Design Payment System", "slug": "design-payment-system", "difficulty": "hard", "why": "Write consistency: exactly-once processing with idempotency keys, WAL for durability before ACK"},
        ],
        "common_mistakes": [
            "Choosing a shard key that creates hot partitions (e.g., timestamp-based sharding for time-series data)",
            "Not using idempotency keys: retries after timeout cause duplicate writes",
            "Ignoring rebalancing: adding shards requires data migration — plan for it from the start",
        ],
        "visual_examples": [
            {"description": "Write path: client -> API -> message queue -> write workers -> sharded DB, with async acknowledgment", "ds_type": "mermaid"},
            {"description": "Sharding by user_id: hash(user_id) % N determines which shard receives the write", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 8. Large Blobs
    # =========================================================================
    {
        "slug": "large-blobs",
        "title": "Large Blob Storage",
        "type": "sd",
        "topic": "Large Blobs",
        "introduction": (
            "Large blobs (images, videos, files) require different handling than structured "
            "data. Never store blobs in your primary database — use object storage (S3, GCS, "
            "Azure Blob) for storage and a CDN for delivery. The upload path typically uses "
            "pre-signed URLs (client uploads directly to S3, bypassing your servers). For "
            "very large files, use multipart upload with resumability. Processing (thumbnails, "
            "transcoding) happens asynchronously via a worker pipeline."
        ),
        "key_ideas": [
            "Pre-signed URLs: server generates a signed S3 URL, client uploads directly — your servers never touch the blob",
            "Multipart upload: split large files into chunks, upload in parallel, reassemble — enables resume on failure",
            "CDN delivery: serve blobs from edge locations, not origin — reduces latency and origin load",
            "Async processing pipeline: upload triggers a job (Lambda, worker) for thumbnailing, transcoding, virus scan",
        ],
        "canonical_problems": [
            {"name": "Design Dropbox / File Storage", "slug": "design-dropbox-file-storage", "difficulty": "hard", "why": "File sync: chunked upload, deduplication via content-hash, delta sync for modified files"},
            {"name": "Design YouTube / Video Streaming", "slug": "design-youtube-video-streaming", "difficulty": "hard", "why": "Video upload: multipart to S3, transcoding pipeline (multiple resolutions), adaptive bitrate streaming"},
            {"name": "Design Instagram / Photo Sharing", "slug": "design-instagram-photo-sharing", "difficulty": "medium", "why": "Image upload: pre-signed URL, async thumbnail generation (multiple sizes), CDN for serving"},
        ],
        "common_mistakes": [
            "Storing blobs in the database — bloats DB size, kills backup/restore performance",
            "Routing blob uploads through application servers — wastes compute and bandwidth, use pre-signed URLs",
            "Not using content-addressable storage (hash-based keys) — misses deduplication opportunity",
        ],
        "visual_examples": [
            {"description": "Upload flow: client -> API (get signed URL) -> client -> S3 (direct upload) -> S3 event -> processing worker", "ds_type": "mermaid"},
            {"description": "CDN delivery: client -> edge (cache hit) or edge -> origin (cache miss), with TTL and invalidation", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 9. Long Tasks
    # =========================================================================
    {
        "slug": "long-tasks",
        "title": "Long-Running Tasks",
        "type": "sd",
        "topic": "Long-Running Tasks",
        "introduction": (
            "Long-running tasks (video transcoding, report generation, ML inference) can't be "
            "handled synchronously in a request-response cycle. The pattern is: accept the "
            "request, return a job ID immediately (202 Accepted), process asynchronously via "
            "a task queue, and let the client poll for status or receive a webhook/push "
            "notification on completion. Key concerns are: idempotency (tasks may restart), "
            "progress tracking, timeout handling, and dead-letter queues for failures."
        ),
        "key_ideas": [
            "Async job pattern: API returns job_id immediately, worker processes in background, client polls GET /jobs/{id}",
            "Task queues: Celery, SQS, Bull — enqueue jobs, workers dequeue and process, ack on completion",
            "Idempotency: tasks may restart after crash — use idempotency keys to prevent double-processing",
            "Dead-letter queues (DLQ): after N retries, move failed jobs to DLQ for manual investigation",
        ],
        "canonical_problems": [
            {"name": "Design YouTube / Video Streaming", "slug": "design-youtube-video-streaming", "difficulty": "hard", "why": "Video transcoding: upload triggers async job, multiple resolutions generated, progress tracked via job status"},
            {"name": "Design Web Crawler", "slug": "design-web-crawler", "difficulty": "medium", "why": "URL crawling: each URL is a task in a distributed queue, workers fetch/parse/enqueue new URLs"},
            {"name": "Design Notification System", "slug": "design-notification-system", "difficulty": "medium", "why": "Batch notifications: scheduled job processes millions of push/email/SMS notifications asynchronously"},
        ],
        "common_mistakes": [
            "Processing long tasks synchronously — request times out, user gets an error, server wastes resources",
            "Not implementing retry with exponential backoff — immediate retries cause thundering herd",
            "Forgetting to track task progress — users have no visibility into when their task will complete",
        ],
        "visual_examples": [
            {"description": "Async job flow: POST /transcode -> 202 {job_id} -> worker processes -> GET /jobs/{id} -> {status: 'complete'}", "ds_type": "mermaid"},
            {"description": "Task queue: producers enqueue, workers dequeue, ack/nack, DLQ for persistent failures", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 10. Replication
    # =========================================================================
    {
        "slug": "replication",
        "title": "Replication",
        "type": "sd",
        "topic": "Replication",
        "introduction": (
            "Replication copies data across multiple servers for durability (survive disk "
            "failures), availability (serve reads if one server is down), and performance "
            "(spread read load). The three models are: single-leader (one writer, many readers — "
            "simplest), multi-leader (multiple writers — for multi-datacenter), and leaderless "
            "(any node can write — Dynamo-style quorum reads/writes). The fundamental trade-off "
            "is consistency vs availability (CAP theorem): synchronous replication is consistent "
            "but slower; asynchronous is faster but risks stale reads."
        ),
        "key_ideas": [
            "Single-leader: one primary handles writes, replicas receive async updates — simple but primary is a bottleneck",
            "Multi-leader: each datacenter has a primary — handles geographic distribution but conflict resolution is complex",
            "Leaderless (quorum): write to W nodes, read from R nodes, W+R > N ensures consistency — Cassandra, DynamoDB",
            "Replication lag: async replicas may be seconds behind — read-after-write consistency needs routing to primary",
        ],
        "canonical_problems": [
            {"name": "Design Key-Value Store", "slug": "design-key-value-store", "difficulty": "medium", "why": "Quorum replication: W+R > N for consistency, tunable consistency levels per operation"},
            {"name": "Design Chat System / WhatsApp", "slug": "design-chat-system-whatsapp", "difficulty": "medium", "why": "Multi-datacenter replication: users in different regions need low-latency access to messages"},
            {"name": "Design Distributed Cache", "slug": "design-distributed-cache", "difficulty": "medium", "why": "Cache replication: primary-replica for read scaling, invalidation propagation across replicas"},
        ],
        "common_mistakes": [
            "Assuming replicas are always consistent — async replication means stale reads are possible",
            "Not handling split-brain: two nodes both think they're primary — use fencing tokens or consensus",
            "Ignoring replication lag in application logic — reading your own writes may fail without routing to primary",
        ],
        "visual_examples": [
            {"description": "Single-leader replication: primary receives writes, streams WAL to two replicas, reads go to any node", "ds_type": "mermaid"},
            {"description": "Quorum: N=3, W=2, R=2 — write goes to 2 nodes, read from 2 nodes, overlap guarantees seeing latest write", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 11. Load Balancing
    # =========================================================================
    {
        "slug": "load-balancing",
        "title": "Load Balancing",
        "type": "sd",
        "topic": "Load Balancing",
        "introduction": (
            "Load balancers distribute incoming requests across multiple servers to improve "
            "throughput, reduce latency, and provide fault tolerance. Layer 4 (transport) LBs "
            "route based on IP/port — fast but no content awareness. Layer 7 (application) LBs "
            "inspect HTTP headers, URLs, cookies — enable path-based routing, sticky sessions, "
            "and SSL termination. The key algorithms are round-robin (simple, even distribution), "
            "least connections (best for varying request durations), and consistent hashing "
            "(preserves cache locality when servers are added/removed)."
        ),
        "key_ideas": [
            "L4 vs L7: L4 is faster (no content parsing), L7 is smarter (URL routing, header inspection, SSL termination)",
            "Algorithms: round-robin (simplest), weighted round-robin, least connections, IP hash, consistent hashing",
            "Health checks: active (LB pings servers) vs passive (LB monitors response errors) — remove unhealthy servers",
            "Sticky sessions: route same client to same server (cookie or IP hash) — needed for WebSocket, stateful apps",
        ],
        "canonical_problems": [
            {"name": "Design URL Shortener", "slug": "url-shortener", "difficulty": "medium", "why": "L7 LB routes /api/* to backend, /* to CDN — path-based routing is the simplest L7 use case"},
            {"name": "Design Uber / Ride Sharing", "slug": "design-uber-ride-sharing", "difficulty": "hard", "why": "Geographic load balancing: route requests to nearest datacenter, consistent hashing for driver assignment"},
            {"name": "Design Chat System / WhatsApp", "slug": "design-chat-system-whatsapp", "difficulty": "medium", "why": "Sticky sessions for WebSocket: same client must reconnect to same server, or use a connection registry"},
        ],
        "common_mistakes": [
            "Single load balancer as SPOF — use active-passive LB pair with health monitoring",
            "Using round-robin when request durations vary widely — some servers get overloaded",
            "Not configuring health checks — dead servers continue receiving traffic",
        ],
        "visual_examples": [
            {"description": "L7 load balancer: routes /api to backend pool, /static to CDN, /ws to WebSocket servers", "ds_type": "mermaid"},
            {"description": "Least-connections algorithm: show connection counts on 3 servers, new request goes to lowest", "ds_type": "mermaid"},
        ],
    },
]

# ---------------------------------------------------------------------------
# MISSING SD TECHNOLOGY PLANS
# ---------------------------------------------------------------------------

SD_TECH_PLANS = [
    # =========================================================================
    # 1. Redis
    # =========================================================================
    {
        "slug": "redis",
        "title": "Redis",
        "type": "sd",
        "topic": "Redis",
        "introduction": (
            "Redis is an in-memory data structure server that provides sub-millisecond latency "
            "for reads and writes. It's far more than a cache — Redis supports strings, hashes, "
            "lists, sets, sorted sets, streams, and pub/sub. In system design, Redis appears as: "
            "a caching layer (most common), a session store, a rate limiter (INCR + EXPIRE), "
            "a distributed lock (SETNX), a leaderboard (sorted sets), and a message broker "
            "(Streams/Pub-Sub). The main limitation: data must fit in memory."
        ),
        "key_ideas": [
            "Data structures: Strings (cache), Hashes (objects), Lists (queues), Sets (unique items), Sorted Sets (leaderboards)",
            "Persistence: RDB (snapshots) vs AOF (append-only log) — trade recovery time vs data safety",
            "Replication: primary-replica async replication — read scaling but not write scaling",
            "Redis Cluster: hash slots (16384) distributed across nodes — horizontal scaling with auto-sharding",
        ],
        "canonical_problems": [
            {"name": "Design Rate Limiter", "slug": "design-rate-limiter", "difficulty": "easy", "why": "Redis INCR + EXPIRE implements sliding window counter in one atomic operation"},
            {"name": "Design Distributed Cache", "slug": "design-distributed-cache", "difficulty": "medium", "why": "Redis as the caching layer: eviction policies (LRU, LFU), TTL, cache-aside pattern"},
            {"name": "Design Chat System / WhatsApp", "slug": "design-chat-system-whatsapp", "difficulty": "medium", "why": "Redis Pub/Sub for real-time message delivery, Sorted Sets for recent messages"},
            {"name": "Design Twitter / News Feed", "slug": "design-twitter-news-feed", "difficulty": "hard", "why": "Redis Lists for cached timelines: LPUSH new tweets, LTRIM to keep N most recent"},
        ],
        "common_mistakes": [
            "Using Redis as primary storage — it's in-memory, data loss on crash without proper persistence config",
            "Not setting TTL on cache keys — memory fills up, eviction kicks in unpredictably",
            "Using KEYS command in production — blocks the single-threaded event loop, use SCAN instead",
        ],
        "visual_examples": [
            {"description": "Redis as cache: application checks Redis first, falls back to DB on miss, populates cache", "ds_type": "mermaid"},
            {"description": "Redis Cluster: 16384 hash slots distributed across 3 masters, each with a replica", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 2. Elasticsearch
    # =========================================================================
    {
        "slug": "elasticsearch",
        "title": "Elasticsearch",
        "type": "sd",
        "topic": "Elasticsearch",
        "introduction": (
            "Elasticsearch is a distributed search and analytics engine built on Apache Lucene. "
            "It provides full-text search, structured search, analytics, and log aggregation with "
            "near-real-time indexing. In system design, Elasticsearch is used when you need: "
            "full-text search (e-commerce product search), log analysis (ELK stack), autocomplete "
            "(completion suggester), and faceted filtering. It's not a primary database — use it "
            "as a secondary index synced from your source of truth."
        ),
        "key_ideas": [
            "Inverted index: maps each term to the list of documents containing it — O(1) lookup for any word",
            "Sharding: index split across N shards for horizontal scaling — each shard is a Lucene index",
            "Relevance scoring: TF-IDF / BM25 ranks results by relevance — tunable with boosting and custom analyzers",
            "Near-real-time: documents are searchable ~1 second after indexing — not instant, not batch",
        ],
        "canonical_problems": [
            {"name": "Design Google Search", "slug": "design-google-search", "difficulty": "hard", "why": "Full-text search at scale: inverted index, distributed crawling, ranking with PageRank + relevance"},
            {"name": "Design Twitter / News Feed", "slug": "design-twitter-news-feed", "difficulty": "hard", "why": "Tweet search: index tweets in Elasticsearch, support full-text + hashtag + user mention queries"},
            {"name": "Design Notification System", "slug": "design-notification-system", "difficulty": "medium", "why": "Searchable notification history: index notifications for filtering by type, date, read status"},
        ],
        "common_mistakes": [
            "Using Elasticsearch as the primary database — it's eventually consistent, not ACID compliant",
            "Not planning the index mapping upfront — changing mappings requires reindexing all documents",
            "Over-sharding: too many shards per index wastes resources — start with 1 shard per 50GB",
        ],
        "visual_examples": [
            {"description": "Inverted index: terms -> document IDs, showing how 'design' maps to docs [1, 3, 7, 12]", "ds_type": "mermaid"},
            {"description": "Elasticsearch cluster: index with 3 primary shards, each replicated, distributed across nodes", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 3. Kafka
    # =========================================================================
    {
        "slug": "kafka",
        "title": "Apache Kafka",
        "type": "sd",
        "topic": "Kafka",
        "introduction": (
            "Apache Kafka is a distributed event streaming platform designed for high-throughput, "
            "fault-tolerant, real-time data pipelines. Unlike traditional message queues (RabbitMQ), "
            "Kafka retains messages for a configurable period, allowing consumers to replay events. "
            "In system design, Kafka appears as: an event bus between microservices, a write-ahead "
            "log for databases, a stream processing platform (Kafka Streams), and a data pipeline "
            "feeding data warehouses. The key abstraction is the partitioned, replicated commit log."
        ),
        "key_ideas": [
            "Topics and partitions: a topic is split into partitions for parallelism — each partition is an ordered, immutable log",
            "Consumer groups: each partition is consumed by exactly one consumer in a group — horizontal scaling of consumers",
            "Retention: messages persist for days/weeks — consumers can replay from any offset, enabling reprocessing",
            "Exactly-once semantics: idempotent producers + transactional consumers — achievable but adds latency",
        ],
        "canonical_problems": [
            {"name": "Design Twitter / News Feed", "slug": "design-twitter-news-feed", "difficulty": "hard", "why": "Kafka as the fan-out bus: tweet published -> Kafka topic -> timeline workers consume and update caches"},
            {"name": "Design Uber / Ride Sharing", "slug": "design-uber-ride-sharing", "difficulty": "hard", "why": "Location stream: driver GPS events -> Kafka -> geospatial indexer + analytics + trip tracker"},
            {"name": "Design Payment System", "slug": "design-payment-system", "difficulty": "hard", "why": "Event sourcing: every payment state change is a Kafka event — enables audit trail and replay"},
            {"name": "Design Notification System", "slug": "design-notification-system", "difficulty": "medium", "why": "Notification pipeline: events -> Kafka -> notification workers (push, email, SMS) — decouple producers from delivery"},
        ],
        "common_mistakes": [
            "Choosing partition key poorly — all messages for one key go to one partition, creating a hot partition",
            "Not configuring consumer group offsets — auto-commit can lose messages on crash",
            "Using Kafka for request-response — it's for async event streaming, not synchronous RPC",
        ],
        "visual_examples": [
            {"description": "Kafka topic with 3 partitions: producers write to partitions by key hash, consumer group reads in parallel", "ds_type": "mermaid"},
            {"description": "Event pipeline: services -> Kafka topics -> stream processors -> downstream consumers + data warehouse", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 4. API Gateway
    # =========================================================================
    {
        "slug": "api-gateway",
        "title": "API Gateway",
        "type": "sd",
        "topic": "API Gateway",
        "introduction": (
            "An API Gateway is a reverse proxy that sits between clients and backend services, "
            "providing a single entry point for all API requests. It handles cross-cutting "
            "concerns: authentication, rate limiting, request routing, SSL termination, "
            "request/response transformation, and observability (logging, metrics, tracing). "
            "In microservices architectures, the gateway prevents clients from needing to know "
            "about individual services. Common implementations: AWS API Gateway, Kong, Nginx, "
            "Envoy, and custom gateways."
        ),
        "key_ideas": [
            "Single entry point: clients hit one URL, gateway routes to the right microservice based on path/headers",
            "Cross-cutting concerns: auth, rate limiting, CORS, logging, circuit breaking — handled once at the gateway",
            "Backend for Frontend (BFF): separate gateways for web, mobile, third-party — each aggregates differently",
            "Service discovery: gateway resolves service names to addresses via Consul, Kubernetes DNS, or config",
        ],
        "canonical_problems": [
            {"name": "Design Rate Limiter", "slug": "design-rate-limiter", "difficulty": "easy", "why": "Rate limiting at the gateway layer: centralized enforcement before requests reach backends"},
            {"name": "Design URL Shortener", "slug": "url-shortener", "difficulty": "medium", "why": "Gateway routes redirect requests to the shortener service, API requests to the CRUD service"},
            {"name": "Design Uber / Ride Sharing", "slug": "design-uber-ride-sharing", "difficulty": "hard", "why": "Mobile BFF: gateway aggregates driver, ride, payment, and map services into mobile-friendly responses"},
        ],
        "common_mistakes": [
            "Gateway as a single point of failure — deploy multiple instances behind a load balancer",
            "Putting business logic in the gateway — it should only handle cross-cutting concerns",
            "Not implementing circuit breaking — one slow backend causes cascading failures through the gateway",
        ],
        "visual_examples": [
            {"description": "API Gateway: client -> gateway (auth, rate limit, route) -> service A, B, C based on path", "ds_type": "mermaid"},
            {"description": "BFF pattern: web client -> web gateway, mobile client -> mobile gateway, both talking to same microservices", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 5. Cassandra
    # =========================================================================
    {
        "slug": "cassandra",
        "title": "Apache Cassandra",
        "type": "sd",
        "topic": "Cassandra",
        "introduction": (
            "Apache Cassandra is a distributed wide-column NoSQL database designed for massive "
            "write throughput, linear horizontal scaling, and high availability with no single "
            "point of failure. It uses a ring-based architecture with consistent hashing for "
            "data distribution. Cassandra excels at write-heavy workloads with known access "
            "patterns (time-series, messaging, IoT). The trade-off: you must model data around "
            "your queries (denormalize aggressively), and you get eventual consistency by default."
        ),
        "key_ideas": [
            "Partition key + clustering key: partition key determines which node stores the data, clustering key sorts within the partition",
            "Write path: write -> commit log (durability) -> memtable (memory) -> SSTable flush (disk) — writes are always fast",
            "Tunable consistency: ONE, QUORUM, ALL — trade consistency for latency per operation",
            "No joins, no subqueries: model your data to match your query patterns — one table per query is the norm",
        ],
        "canonical_problems": [
            {"name": "Design Chat System / WhatsApp", "slug": "design-chat-system-whatsapp", "difficulty": "medium", "why": "Message storage: partition by (chat_id), cluster by (timestamp) — fast writes, range reads by time"},
            {"name": "Design Twitter / News Feed", "slug": "design-twitter-news-feed", "difficulty": "hard", "why": "Timeline storage: partition by (user_id), cluster by (tweet_time DESC) — each user's feed is one partition"},
            {"name": "Design Uber / Ride Sharing", "slug": "design-uber-ride-sharing", "difficulty": "hard", "why": "Trip history: partition by (driver_id or rider_id), cluster by (trip_time) — write-heavy location tracking"},
        ],
        "common_mistakes": [
            "Using Cassandra for ad-hoc queries — it's optimized for known access patterns, not flexible querying",
            "Large partitions: too much data under one partition key causes performance issues — keep under 100MB",
            "Not understanding tombstones: deletes create tombstones that slow reads until compaction clears them",
        ],
        "visual_examples": [
            {"description": "Cassandra ring: 6 nodes, data distributed by consistent hashing of partition key, RF=3", "ds_type": "mermaid"},
            {"description": "Data model for chat: partition key = chat_id, clustering key = timestamp, columns = sender, message", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 6. DynamoDB
    # =========================================================================
    {
        "slug": "dynamodb",
        "title": "Amazon DynamoDB",
        "type": "sd",
        "topic": "DynamoDB",
        "introduction": (
            "DynamoDB is a fully managed key-value and document database by AWS that provides "
            "single-digit millisecond latency at any scale. It's serverless — no capacity "
            "planning, no servers to manage, automatic scaling. Data is organized by partition "
            "key (required) and optional sort key. DynamoDB is ideal when you need: predictable "
            "performance at scale, serverless operation, and simple key-value or key-range access "
            "patterns. Global Secondary Indexes (GSIs) enable alternative query patterns."
        ),
        "key_ideas": [
            "Partition key + sort key: partition key distributes data, sort key enables range queries within a partition",
            "Provisioned vs on-demand capacity: provisioned is cheaper for steady traffic, on-demand handles spiky workloads",
            "Global Secondary Indexes (GSI): project data into a new table with a different partition/sort key — enables alternative queries",
            "Conditional writes: PutItem with ConditionExpression for optimistic concurrency — CAS without distributed locks",
        ],
        "canonical_problems": [
            {"name": "Design URL Shortener", "slug": "url-shortener", "difficulty": "medium", "why": "Simple key-value: partition key = short_code, attributes = long_url, created_at, TTL"},
            {"name": "Design Key-Value Store", "slug": "design-key-value-store", "difficulty": "medium", "why": "DynamoDB IS a key-value store: understand partitioning, replication, and consistency model"},
            {"name": "Design Ticketmaster / Booking System", "slug": "design-ticketmaster-booking-system", "difficulty": "hard", "why": "Conditional writes for seat reservation: PutItem IF seat_status = 'available' — atomic CAS"},
        ],
        "common_mistakes": [
            "Hot partition: one partition key gets disproportionate traffic — distribute writes with write sharding",
            "Scan operations: DynamoDB Scan reads every item — always use Query with partition key for production",
            "GSI eventual consistency: GSI updates are async — reading from GSI immediately after write may miss the update",
        ],
        "visual_examples": [
            {"description": "DynamoDB table: partition key (user_id) + sort key (order_time), items sorted within partition", "ds_type": "mermaid"},
            {"description": "GSI projection: base table keyed by user_id, GSI keyed by email for login lookup", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 7. PostgreSQL
    # =========================================================================
    {
        "slug": "postgresql",
        "title": "PostgreSQL",
        "type": "sd",
        "topic": "PostgreSQL",
        "introduction": (
            "PostgreSQL is the most advanced open-source relational database, supporting ACID "
            "transactions, complex queries with joins, full-text search, JSONB for semi-structured "
            "data, and extensions like PostGIS (geospatial) and pg_vector (AI embeddings). In "
            "system design, PostgreSQL is often the default 'primary database' choice for data "
            "that needs strong consistency, complex relationships, and flexible querying. It "
            "scales vertically well (128+ cores, TB of RAM) and horizontally via Citus for "
            "sharding or read replicas for read scaling."
        ),
        "key_ideas": [
            "ACID transactions: strong consistency guarantee — essential for financial data, user accounts, inventory",
            "Indexes: B-tree (default, range queries), GIN (full-text, JSONB), BRIN (sorted data, time series), partial indexes",
            "MVCC: Multi-Version Concurrency Control — readers don't block writers, writers don't block readers",
            "Scaling: vertical (bigger machine), read replicas (async replication), Citus extension (distributed sharding)",
        ],
        "canonical_problems": [
            {"name": "Design Payment System", "slug": "design-payment-system", "difficulty": "hard", "why": "ACID transactions for balance updates: BEGIN -> debit + credit -> COMMIT — no partial transfers"},
            {"name": "Design Ticketmaster / Booking System", "slug": "design-ticketmaster-booking-system", "difficulty": "hard", "why": "SELECT FOR UPDATE on seat rows: pessimistic locking prevents double-booking"},
            {"name": "Design Instagram / Photo Sharing", "slug": "design-instagram-photo-sharing", "difficulty": "medium", "why": "User profiles, social graph, post metadata — relational data with complex queries + JSONB for flexibility"},
        ],
        "common_mistakes": [
            "Not adding indexes for common queries — sequential scans on large tables destroy performance",
            "Long-running transactions holding locks — blocks other writers, causes contention",
            "Using SELECT * instead of selecting specific columns — wastes I/O and network bandwidth",
        ],
        "visual_examples": [
            {"description": "PostgreSQL MVCC: two concurrent transactions reading different versions of the same row", "ds_type": "mermaid"},
            {"description": "Index types: B-tree for range, GIN for full-text, GiST for geospatial — choose by query pattern", "ds_type": "mermaid"},
        ],
    },

    # =========================================================================
    # 8. Zookeeper
    # =========================================================================
    {
        "slug": "zookeeper",
        "title": "Apache ZooKeeper",
        "type": "sd",
        "topic": "ZooKeeper",
        "introduction": (
            "ZooKeeper is a distributed coordination service that provides: configuration "
            "management (centralized config), naming/service discovery, distributed locks, "
            "leader election, and group membership. It maintains a tree of znodes (like a "
            "filesystem) with strong consistency guarantees via the ZAB consensus protocol. "
            "In system design, ZooKeeper is the 'brain' that coordinates distributed systems — "
            "Kafka uses it for broker coordination, HBase for master election, and many systems "
            "for distributed locking."
        ),
        "key_ideas": [
            "Znodes: hierarchical namespace (like a filesystem) — ephemeral znodes auto-delete when the session ends",
            "Watches: clients register watches on znodes, get notified on changes — event-driven coordination",
            "Leader election: each node creates an ephemeral sequential znode, the lowest sequence number is the leader",
            "Distributed locks: create ephemeral sequential znode, watch the previous one — queue-based fair locking",
        ],
        "canonical_problems": [
            {"name": "Design Key-Value Store", "slug": "design-key-value-store", "difficulty": "medium", "why": "ZooKeeper for leader election: one node is primary (handles writes), replicas follow"},
            {"name": "Design Uber / Ride Sharing", "slug": "design-uber-ride-sharing", "difficulty": "hard", "why": "Service discovery: ride-matching service registers in ZooKeeper, gateway discovers available instances"},
            {"name": "Design Distributed Cache", "slug": "design-distributed-cache", "difficulty": "medium", "why": "Cluster membership: ZooKeeper tracks which cache nodes are alive, triggers rebalancing on failure"},
        ],
        "common_mistakes": [
            "Using ZooKeeper for high-throughput data storage — it's designed for coordination, not data serving",
            "Not handling session expiry: ephemeral nodes disappear, locks are released — application must re-acquire",
            "ZooKeeper as a single point of failure — deploy an ensemble (3 or 5 nodes) for fault tolerance",
        ],
        "visual_examples": [
            {"description": "ZooKeeper znode tree: /services/payment/instance-001, /locks/resource-x/lock-0001, showing ephemeral nodes", "ds_type": "mermaid"},
            {"description": "Leader election: 3 nodes create sequential znodes, lowest number becomes leader, others watch", "ds_type": "mermaid"},
        ],
    },
]


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Seed missing teaching plans into MongoDB")
    parser.add_argument("--dry-run", action="store_true", help="Print plans without writing to DB")
    args = parser.parse_args()

    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        print("ERROR: MONGODB_URI not set. Load backend/.env or set the env var.")
        sys.exit(1)

    all_plans = DSA_MISSING_PLANS + SD_CONCEPT_PLANS + SD_TECH_PLANS
    print(f"Total plans to upsert: {len(all_plans)}")
    print(f"  DSA topics:       {len(DSA_MISSING_PLANS)}")
    print(f"  SD concepts:      {len(SD_CONCEPT_PLANS)}")
    print(f"  SD technologies:  {len(SD_TECH_PLANS)}")
    print()

    if args.dry_run:
        for plan in all_plans:
            print(f"  [DRY RUN] {plan['type']:4s}  {plan['slug']:<45s}  {plan['title']}")
        print("\nDry run complete — no data written.")
        return

    import certifi
    from pymongo import MongoClient

    client = MongoClient(uri, tlsCAFile=certifi.where())
    db = client["tutor_v2"]
    collection = db["teaching_plans"]

    upserted = 0
    updated = 0
    skipped = 0

    for plan in all_plans:
        slug = plan["slug"]
        result = collection.update_one(
            {"slug": slug},
            {"$set": plan},
            upsert=True,
        )
        if result.upserted_id:
            upserted += 1
            print(f"  [INSERT] {plan['type']:4s}  {slug:<45s}  {plan['title']}")
        elif result.modified_count > 0:
            updated += 1
            print(f"  [UPDATE] {plan['type']:4s}  {slug:<45s}  {plan['title']}")
        else:
            skipped += 1
            print(f"  [SKIP]   {plan['type']:4s}  {slug:<45s}  (already up to date)")

    # Ensure indexes exist
    collection.create_index("slug", unique=True)
    collection.create_index("type")

    print()
    print(f"Done!  Inserted: {upserted}  |  Updated: {updated}  |  Skipped: {skipped}")
    print(f"Total documents in teaching_plans: {collection.count_documents({})}")


if __name__ == "__main__":
    main()
