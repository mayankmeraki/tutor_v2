"""
Structured teaching plans for DSA topics and System Design concepts.

These plans are loaded into the AI tutor's context when a student selects a
topic.  Each plan gives the tutor a script: what to introduce, which visuals
to draw, which problems to walk through (easy -> hard), common pitfalls, and
how the pattern connects to other patterns.

Usage:
    from byo.scripts.teaching_plans import DSA_TEACHING_PLANS, SD_TEACHING_PLANS
"""

# ---------------------------------------------------------------------------
# DSA TEACHING PLANS
# ---------------------------------------------------------------------------

DSA_TEACHING_PLANS = {
    # -----------------------------------------------------------------------
    # 1. Arrays & Hashing
    # -----------------------------------------------------------------------
    "arrays_hashing": {
        "title": "Arrays & Hashing",
        "introduction": (
            "Arrays are the most fundamental data structure — contiguous memory, "
            "O(1) random access.  Hash maps let us trade space for time by giving "
            "O(1) average lookup.  Almost every coding interview starts here.  "
            "The core idea: when brute force is O(n^2) because of a nested search, "
            "a hash map can eliminate the inner loop."
        ),
        "key_ideas": [
            "Hash maps convert O(n) search into O(1) lookup — the 'complement trick'",
            "Frequency counting: use a dict/Counter to tally occurrences, then reason about counts",
            "Index mapping: store value -> index so you can answer 'have I seen X?' in O(1)",
            "Sorting as a preprocessing step: anagrams share sorted keys, duplicates cluster together",
            "In-place array tricks: swapping, partitioning, using the array itself as a hash map (e.g., index marking)",
        ],
        "visual_examples": [
            {
                "description": "Show array + hash map side by side; as we scan left to right, each element is checked against the map, then inserted",
                "ds_type": "array",
            },
            {
                "description": "Frequency histogram — bar chart of character counts for an anagram check",
                "ds_type": "hash_map",
            },
            {
                "description": "Group Anagrams: sorted-key buckets visualised as a dict of lists",
                "ds_type": "hash_map",
            },
        ],
        "canonical_problems": [
            {
                "name": "Two Sum",
                "slug": "two-sum",
                "difficulty": "easy",
                "why": "The foundational complement-lookup pattern — O(n) with a hash map instead of O(n^2) brute force",
            },
            {
                "name": "Valid Anagram",
                "slug": "valid-anagram",
                "difficulty": "easy",
                "why": "Introduces frequency counting; compare two Counter dicts or sort both strings",
            },
            {
                "name": "Group Anagrams",
                "slug": "group-anagrams",
                "difficulty": "medium",
                "why": "Combines hashing with a clever key choice (sorted string or char-count tuple)",
            },
            {
                "name": "Top K Frequent Elements",
                "slug": "top-k-frequent-elements",
                "difficulty": "medium",
                "why": "Frequency count + bucket sort or heap — bridges hashing and heap patterns",
            },
            {
                "name": "Longest Consecutive Sequence",
                "slug": "longest-consecutive-sequence",
                "difficulty": "medium",
                "why": "Set membership + clever start-of-sequence detection gives O(n) without sorting",
            },
        ],
        "common_mistakes": [
            "Forgetting to handle duplicate values (e.g., Two Sum with two identical numbers)",
            "Using a list search instead of a set/dict — accidentally O(n^2)",
            "Off-by-one when converting between 0-indexed and 1-indexed",
            "Not considering empty input or single-element arrays",
            "Mutating the array while iterating over it",
        ],
        "complexity_pattern": "Most hash-map problems run in O(n) time and O(n) space.  Sorting-based alternatives are O(n log n) time, O(1) extra space.",
        "related_patterns": ["two_pointers", "sliding_window", "heap"],
    },

    # -----------------------------------------------------------------------
    # 2. Two Pointers
    # -----------------------------------------------------------------------
    "two_pointers": {
        "title": "Two Pointers",
        "introduction": (
            "Two pointers is a technique where you maintain two indices that move "
            "through a data structure — usually an array or string — according to "
            "some rule.  The three main flavours are: (1) opposite-end squeeze "
            "(converging from both ends), (2) same-direction slow/fast (partitioning "
            "or cycle detection), and (3) two separate arrays (merge-style).  "
            "The key insight: by moving pointers intelligently, you prune the search "
            "space from O(n^2) to O(n)."
        ),
        "key_ideas": [
            "Opposite-end squeeze: left and right converge — works on sorted arrays or palindrome checks",
            "Slow/fast pointers: one moves 1 step, the other 2 — detects cycles (Floyd's algorithm)",
            "Partition pointers: one tracks the 'write' position while the other scans — in-place removal/dedup",
            "Sort first, then two-pointer: transforms unsorted problems into linear scans (e.g., 3Sum)",
            "Greedy pointer movement: always move the pointer that gives a better chance of improving the answer",
        ],
        "visual_examples": [
            {
                "description": "Show a sorted array with L at index 0, R at the end; arrows converging toward middle as sum is checked",
                "ds_type": "array",
            },
            {
                "description": "Container With Most Water: two vertical bars with water between them; move the shorter bar inward",
                "ds_type": "array",
            },
            {
                "description": "Slow/fast on a linked list: slow moves 1 node, fast moves 2 — show them meeting inside a cycle",
                "ds_type": "linked_list",
            },
        ],
        "canonical_problems": [
            {
                "name": "Valid Palindrome",
                "slug": "valid-palindrome",
                "difficulty": "easy",
                "why": "Simplest two-pointer squeeze: compare chars from both ends, skip non-alphanumeric",
            },
            {
                "name": "Two Sum II – Input Array Is Sorted",
                "slug": "two-sum-ii-input-array-is-sorted",
                "difficulty": "medium",
                "why": "Classic squeeze on sorted data — move left up if sum is too small, right down if too big",
            },
            {
                "name": "Container With Most Water",
                "slug": "container-with-most-water",
                "difficulty": "medium",
                "why": "Two pointers with a greedy decision — always move the shorter side inward",
            },
            {
                "name": "3Sum",
                "slug": "3sum",
                "difficulty": "medium",
                "why": "Fix one element, run two-pointer on the rest; the real challenge is deduplication",
            },
            {
                "name": "Trapping Rain Water",
                "slug": "trapping-rain-water",
                "difficulty": "hard",
                "why": "Two pointers with running max from each side — elegant O(1) space solution",
            },
        ],
        "common_mistakes": [
            "Forgetting to skip duplicates in 3Sum (causes duplicate triplets)",
            "Moving the wrong pointer — always move the one that can improve the answer",
            "Not sorting the array first when the technique requires sorted input",
            "Infinite loop: forgetting to advance at least one pointer each iteration",
            "Using two pointers on unsorted data where order matters",
        ],
        "complexity_pattern": "O(n) for a single pass with two pointers; O(n log n) if sorting is needed first.  Space is usually O(1).",
        "related_patterns": ["sliding_window", "binary_search", "linked_list"],
    },

    # -----------------------------------------------------------------------
    # 3. Sliding Window
    # -----------------------------------------------------------------------
    "sliding_window": {
        "title": "Sliding Window",
        "introduction": (
            "Sliding window maintains a contiguous subarray/substring bounded by "
            "two pointers (left and right).  The right pointer expands the window "
            "to include more elements; the left pointer contracts it to restore a "
            "constraint.  There are two flavours: fixed-size windows (move both "
            "pointers in lockstep) and variable-size windows (expand right, shrink "
            "left only when a condition is violated).  This turns O(n*k) or O(n^2) "
            "brute force into O(n)."
        ),
        "key_ideas": [
            "Fixed window: size is given; slide by adding the new right element and removing the old left element",
            "Variable window: expand right to explore, contract left to satisfy the constraint, track the best answer",
            "Use a hash map or Counter inside the window to track frequencies",
            "The window invariant: define exactly what makes the current window 'valid' — shrink only when invalid",
            "Deque for sliding window maximum: maintain a monotonically decreasing deque of indices",
        ],
        "visual_examples": [
            {
                "description": "Highlight a subarray with a bracket; slide it right one step — show element entering on the right and leaving on the left",
                "ds_type": "array",
            },
            {
                "description": "Variable window on a string: right expands to include new chars, left shrinks when a duplicate is found (frequency map shown beside)",
                "ds_type": "string",
            },
            {
                "description": "Sliding window maximum: array with a deque overlay showing how elements are popped from the back when a larger element enters",
                "ds_type": "array",
            },
        ],
        "canonical_problems": [
            {
                "name": "Best Time to Buy and Sell Stock",
                "slug": "best-time-to-buy-and-sell-stock",
                "difficulty": "easy",
                "why": "Track running minimum (left) while scanning prices (right) — a natural sliding window / kadane variant",
            },
            {
                "name": "Longest Substring Without Repeating Characters",
                "slug": "longest-substring-without-repeating-characters",
                "difficulty": "medium",
                "why": "Variable window with a set/map; shrink left when a duplicate enters",
            },
            {
                "name": "Permutation in String",
                "slug": "permutation-in-string",
                "difficulty": "medium",
                "why": "Fixed window of size len(s1); compare frequency counts — teaches the 'matches' counter trick",
            },
            {
                "name": "Minimum Window Substring",
                "slug": "minimum-window-substring",
                "difficulty": "hard",
                "why": "Variable window with a 'have vs need' counter — the classic hard sliding window problem",
            },
            {
                "name": "Sliding Window Maximum",
                "slug": "sliding-window-maximum",
                "difficulty": "hard",
                "why": "Fixed window + monotonic deque — combines sliding window with deque data structure",
            },
        ],
        "common_mistakes": [
            "Forgetting to shrink the window — only expanding leads to wrong answers",
            "Off-by-one on window size: the window [l, r] has size r - l + 1, not r - l",
            "Updating the answer at the wrong time — update after the window is valid, not before",
            "Not correctly removing the leftmost element's contribution when the window slides",
            "Confusing fixed and variable window templates — they have different loop structures",
        ],
        "complexity_pattern": "O(n) time — each element enters and leaves the window at most once.  Space depends on the alphabet/constraint, often O(k) or O(26).",
        "related_patterns": ["two_pointers", "arrays_hashing", "heap"],
    },

    # -----------------------------------------------------------------------
    # 4. Stack
    # -----------------------------------------------------------------------
    "stack": {
        "title": "Stack",
        "introduction": (
            "A stack is LIFO (last-in, first-out).  In interview problems it appears "
            "in three main roles: (1) matching — parentheses, tags, nested structures; "
            "(2) monotonic stack — finding the next greater/smaller element; (3) expression "
            "evaluation — converting infix to postfix and computing results.  The key "
            "intuition: whenever you need to 'remember something and come back to it later,' "
            "a stack is the right tool."
        ),
        "key_ideas": [
            "Matching/nesting: push openers, pop on closer; if stack is empty at the end, everything matched",
            "Monotonic stack: maintain a stack where elements are in increasing (or decreasing) order — pop violators to answer queries",
            "Next Greater Element pattern: iterate right-to-left, pop smaller elements, top of stack is the answer",
            "Expression evaluation: two stacks (operands + operators) or convert to Reverse Polish Notation first",
            "Stack as recursion replacement: any recursive DFS can be rewritten with an explicit stack",
        ],
        "visual_examples": [
            {
                "description": "Stack of parentheses: push '(', '[', '{' — animate popping when matching closer arrives; show mismatch case",
                "ds_type": "stack",
            },
            {
                "description": "Monotonic decreasing stack for Next Greater Element: show bars of varying height, stack state after each step",
                "ds_type": "stack",
            },
            {
                "description": "Daily Temperatures: array of temps with stack of indices; pop when a warmer day is found, record the gap",
                "ds_type": "stack",
            },
        ],
        "canonical_problems": [
            {
                "name": "Valid Parentheses",
                "slug": "valid-parentheses",
                "difficulty": "easy",
                "why": "The quintessential stack problem — push openers, pop and check on closers",
            },
            {
                "name": "Min Stack",
                "slug": "min-stack",
                "difficulty": "medium",
                "why": "Design problem: maintain a parallel stack (or tuple) to track the running minimum",
            },
            {
                "name": "Daily Temperatures",
                "slug": "daily-temperatures",
                "difficulty": "medium",
                "why": "Monotonic decreasing stack — find the next warmer day for each position",
            },
            {
                "name": "Evaluate Reverse Polish Notation",
                "slug": "evaluate-reverse-polish-notation",
                "difficulty": "medium",
                "why": "Stack-based expression evaluation — push operands, pop two on operator",
            },
            {
                "name": "Largest Rectangle in Histogram",
                "slug": "largest-rectangle-in-histogram",
                "difficulty": "hard",
                "why": "Monotonic increasing stack — find the maximum rectangle by tracking left/right boundaries",
            },
        ],
        "common_mistakes": [
            "Popping from an empty stack — always check before popping",
            "Forgetting to process remaining elements on the stack after the main loop",
            "Storing values instead of indices on the monotonic stack (you usually need indices for distance calculations)",
            "Using a stack when a simple counter would suffice (e.g., single-type parentheses only needs a count)",
            "Not handling edge cases: empty string, single element, all same values",
        ],
        "complexity_pattern": "O(n) time — each element is pushed and popped at most once.  O(n) space for the stack.",
        "related_patterns": ["arrays_hashing", "dynamic_programming", "trees"],
    },

    # -----------------------------------------------------------------------
    # 5. Binary Search
    # -----------------------------------------------------------------------
    "binary_search": {
        "title": "Binary Search",
        "introduction": (
            "Binary search is search-space reduction: at each step you eliminate half "
            "the remaining candidates.  The classic version searches a sorted array, "
            "but the deeper idea applies whenever you can define a monotonic predicate — "
            "a condition that is False for all values below some threshold and True above "
            "(or vice versa).  You are searching for the boundary.  This generalisation "
            "opens up problems on rotated arrays, matrix search, and 'search on the answer' "
            "problems where you binary search the result itself."
        ),
        "key_ideas": [
            "Invariant-based reasoning: define what lo and hi represent at all times; the answer is where they converge",
            "Three templates: (1) exact match, (2) leftmost/rightmost (bisect_left/right), (3) search on the answer",
            "Rotated array: one half is always sorted — check which half, then decide which way to go",
            "Search on the answer: binary search the result value, use a feasibility check as the predicate",
            "Avoid infinite loops: always ensure the search space shrinks — be careful with lo = mid vs lo = mid + 1",
        ],
        "visual_examples": [
            {
                "description": "Sorted array with lo/hi/mid pointers; show the half being eliminated at each step with a strikethrough",
                "ds_type": "array",
            },
            {
                "description": "Rotated sorted array: show the 'break point' and how one half is always sorted",
                "ds_type": "array",
            },
            {
                "description": "Search on the answer: a number line of candidate answers; the feasibility boundary divides feasible from infeasible",
                "ds_type": "number_line",
            },
        ],
        "canonical_problems": [
            {
                "name": "Binary Search",
                "slug": "binary-search",
                "difficulty": "easy",
                "why": "The template itself — get the lo/hi/mid mechanics right and handle the 'not found' case",
            },
            {
                "name": "Search a 2D Matrix",
                "slug": "search-a-2d-matrix",
                "difficulty": "medium",
                "why": "Treat a row-sorted, column-increasing matrix as a flat sorted array — single binary search",
            },
            {
                "name": "Koko Eating Bananas",
                "slug": "koko-eating-bananas",
                "difficulty": "medium",
                "why": "Search on the answer: binary search the eating speed, feasibility check is O(n)",
            },
            {
                "name": "Find Minimum in Rotated Sorted Array",
                "slug": "find-minimum-in-rotated-sorted-array",
                "difficulty": "medium",
                "why": "Binary search on a rotated array — compare mid to right to decide which half to keep",
            },
            {
                "name": "Median of Two Sorted Arrays",
                "slug": "median-of-two-sorted-arrays",
                "difficulty": "hard",
                "why": "Binary search on the partition point of the shorter array — the hardest binary search problem",
            },
        ],
        "common_mistakes": [
            "Infinite loop from lo = mid instead of lo = mid + 1 (or equivalent off-by-one)",
            "Wrong comparison: using < when you need <= or vice versa, changing the boundary semantics",
            "Forgetting that the search space must be monotonic for binary search to work",
            "Integer overflow in mid calculation — use lo + (hi - lo) // 2 instead of (lo + hi) // 2",
            "Not handling empty input or single-element arrays",
        ],
        "complexity_pattern": "O(log n) time for the search itself.  If there is a feasibility check, total is O(n log n) or O(n log(max_val)).",
        "related_patterns": ["two_pointers", "arrays_hashing", "heap"],
    },

    # -----------------------------------------------------------------------
    # 6. Linked List
    # -----------------------------------------------------------------------
    "linked_list": {
        "title": "Linked List",
        "introduction": (
            "Linked lists are sequences of nodes connected by pointers.  Unlike arrays, "
            "they have O(1) insertion/deletion at a known position but O(n) access.  "
            "Interview problems focus on pointer manipulation: reversal, cycle detection "
            "(Floyd's tortoise and hare), merging sorted lists, and reordering.  The main "
            "skill is drawing pictures and tracking which pointers change at each step.  "
            "A dummy/sentinel head simplifies edge cases enormously."
        ),
        "key_ideas": [
            "Dummy head: create a sentinel node to avoid special-casing insertions at the head",
            "Reversal: three pointers (prev, curr, next) — the fundamental in-place reversal pattern",
            "Fast/slow (Floyd's): slow moves 1 step, fast moves 2 — they meet inside a cycle; used for cycle detection and finding the middle",
            "Merge two sorted lists: compare heads, attach the smaller, advance that pointer — the merge step of merge sort",
            "Runner technique: use two pointers at different speeds or starting positions to solve reorder/palindrome problems",
        ],
        "visual_examples": [
            {
                "description": "Reversal animation: show prev/curr/next pointers; at each step, curr.next = prev, then all three advance",
                "ds_type": "linked_list",
            },
            {
                "description": "Cycle detection: slow (green) and fast (red) pointers moving through a linked list with a loop; they eventually collide",
                "ds_type": "linked_list",
            },
            {
                "description": "Merge two sorted lists: two linked lists with a dummy head and a tail pointer attaching nodes",
                "ds_type": "linked_list",
            },
        ],
        "canonical_problems": [
            {
                "name": "Reverse Linked List",
                "slug": "reverse-linked-list",
                "difficulty": "easy",
                "why": "The fundamental pointer-manipulation pattern — iterative (3 pointers) and recursive versions",
            },
            {
                "name": "Merge Two Sorted Lists",
                "slug": "merge-two-sorted-lists",
                "difficulty": "easy",
                "why": "Merge with a dummy head — builds intuition for merge sort and merge K lists",
            },
            {
                "name": "Linked List Cycle",
                "slug": "linked-list-cycle",
                "difficulty": "easy",
                "why": "Floyd's tortoise and hare — the foundation for all fast/slow pointer problems",
            },
            {
                "name": "Remove Nth Node From End of List",
                "slug": "remove-nth-node-from-end-of-list",
                "difficulty": "medium",
                "why": "Two-pointer gap technique: advance one pointer n steps, then move both until the first hits the end",
            },
            {
                "name": "Reorder List",
                "slug": "reorder-list",
                "difficulty": "medium",
                "why": "Combines three patterns: find middle (slow/fast), reverse second half, interleave",
            },
        ],
        "common_mistakes": [
            "Losing a reference: not saving curr.next before overwriting it during reversal",
            "Forgetting the dummy head — leads to ugly special-case code for head insertion",
            "Not handling None/null properly — dereferencing fast.next when fast is None",
            "Assuming linked lists have a length attribute (they usually do not in interview settings)",
            "Modifying the list while also trying to traverse it without saving pointers",
        ],
        "complexity_pattern": "Most problems are O(n) time, O(1) space (in-place pointer manipulation).  Recursive solutions use O(n) stack space.",
        "related_patterns": ["two_pointers", "stack", "trees"],
    },

    # -----------------------------------------------------------------------
    # 7. Trees
    # -----------------------------------------------------------------------
    "trees": {
        "title": "Trees",
        "introduction": (
            "Trees are hierarchical structures with a root node and children.  Binary "
            "trees are the most common in interviews.  The three core traversals — "
            "inorder, preorder, postorder — are the backbone.  BST (binary search tree) "
            "problems exploit the sorted property (left < root < right).  Many tree "
            "problems have elegant recursive solutions where you solve for left and right "
            "subtrees, then combine.  The key mental model: think of each node as a "
            "subproblem, and define what information flows up (return value) vs down "
            "(parameters)."
        ),
        "key_ideas": [
            "Recursive structure: solve(root) = combine(solve(root.left), solve(root.right)) — most tree problems follow this template",
            "Traversals: inorder (left-root-right → sorted for BST), preorder (root-left-right → serialization), postorder (left-right-root → bottom-up aggregation)",
            "Level-order (BFS): use a queue; process one level at a time — useful for level averages, zigzag, right side view",
            "BST property: everything left < root < everything right — enables O(log n) search, insert, delete",
            "LCA (Lowest Common Ancestor): in a BST, split point where p and q diverge; in a general tree, recursive 'found left/found right' logic",
        ],
        "visual_examples": [
            {
                "description": "Binary tree with inorder traversal path highlighted — show node visit order and resulting sorted array for BST",
                "ds_type": "tree",
            },
            {
                "description": "BFS level-order: show a queue beside the tree; nodes enter and leave the queue level by level",
                "ds_type": "tree",
            },
            {
                "description": "LCA visualization: highlight the paths from root to p and root to q; the last shared node is the LCA",
                "ds_type": "tree",
            },
        ],
        "canonical_problems": [
            {
                "name": "Invert Binary Tree",
                "slug": "invert-binary-tree",
                "difficulty": "easy",
                "why": "Simplest recursive tree problem — swap left and right children at every node",
            },
            {
                "name": "Maximum Depth of Binary Tree",
                "slug": "maximum-depth-of-binary-tree",
                "difficulty": "easy",
                "why": "Base recursion: 1 + max(depth(left), depth(right)) — teaches the bottom-up return pattern",
            },
            {
                "name": "Binary Tree Level Order Traversal",
                "slug": "binary-tree-level-order-traversal",
                "difficulty": "medium",
                "why": "BFS with a queue — the template for all level-based tree problems",
            },
            {
                "name": "Validate Binary Search Tree",
                "slug": "validate-binary-search-tree",
                "difficulty": "medium",
                "why": "Pass min/max bounds down recursively — teaches the top-down parameter pattern",
            },
            {
                "name": "Binary Tree Maximum Path Sum",
                "slug": "binary-tree-maximum-path-sum",
                "difficulty": "hard",
                "why": "At each node, consider using it as a 'turn' — global max updated at every node, but return single-path sum upward",
            },
        ],
        "common_mistakes": [
            "Confusing the return value (what goes up) with the global answer (updated via nonlocal/class variable)",
            "Not handling None/null base case — always check if root is None first",
            "Assuming a binary tree is a BST (using BST logic on a general tree)",
            "BFS: forgetting to process all nodes at the current level before moving to the next (use len(queue) at the start of each iteration)",
            "Recursive stack overflow on extremely deep trees — iterative solutions with an explicit stack are safer",
        ],
        "complexity_pattern": "O(n) time to visit every node.  O(h) space for recursion stack (h = height, worst case O(n) for skewed trees, O(log n) for balanced).",
        "related_patterns": ["graphs", "dynamic_programming", "stack"],
    },

    # -----------------------------------------------------------------------
    # 8. Graphs
    # -----------------------------------------------------------------------
    "graphs": {
        "title": "Graphs",
        "introduction": (
            "Graphs generalise trees: nodes connected by edges, possibly with cycles, "
            "direction, and weights.  The two fundamental traversals are BFS (level-by-level, "
            "shortest path in unweighted graphs) and DFS (go deep, backtrack).  Key "
            "representations: adjacency list (most common) and adjacency matrix.  "
            "Topological sort handles DAGs (directed acyclic graphs) and models dependency "
            "ordering.  Graph problems are pattern-heavy — once you recognise the pattern, "
            "the code is mostly template."
        ),
        "key_ideas": [
            "BFS for shortest path in unweighted graphs: queue + visited set; distance is the level number",
            "DFS for connectivity, cycle detection, and backtracking: recursion or explicit stack + visited set",
            "Topological sort: Kahn's algorithm (BFS with in-degree) or DFS post-order reversal — only works on DAGs",
            "Cycle detection: in undirected graphs, DFS + parent tracking; in directed graphs, track 'in current path' state (3-color: white/gray/black)",
            "Grid problems ARE graph problems: each cell is a node, 4 (or 8) neighbours are edges; BFS/DFS on grids uses the same templates",
        ],
        "visual_examples": [
            {
                "description": "BFS on a grid: show wavefront expanding from source, coloring cells level by level",
                "ds_type": "grid",
            },
            {
                "description": "DFS on a graph: show the call stack growing as we go deeper, then backtracking when hitting a visited node",
                "ds_type": "graph",
            },
            {
                "description": "Topological sort: show a DAG with in-degrees; remove nodes with in-degree 0 one by one, appending to result",
                "ds_type": "graph",
            },
        ],
        "canonical_problems": [
            {
                "name": "Number of Islands",
                "slug": "number-of-islands",
                "difficulty": "medium",
                "why": "The gateway graph problem — BFS or DFS flood fill on a grid; count connected components",
            },
            {
                "name": "Clone Graph",
                "slug": "clone-graph",
                "difficulty": "medium",
                "why": "BFS/DFS with a hash map of old -> new nodes — teaches graph traversal + reconstruction",
            },
            {
                "name": "Course Schedule",
                "slug": "course-schedule",
                "difficulty": "medium",
                "why": "Topological sort / cycle detection on a directed graph — models prerequisite dependencies",
            },
            {
                "name": "Pacific Atlantic Water Flow",
                "slug": "pacific-atlantic-water-flow",
                "difficulty": "medium",
                "why": "Reverse BFS/DFS from both oceans — teaches the 'search from the destination' trick",
            },
            {
                "name": "Word Ladder",
                "slug": "word-ladder",
                "difficulty": "hard",
                "why": "BFS shortest path in an implicit graph — nodes are words, edges connect words differing by one letter",
            },
        ],
        "common_mistakes": [
            "Forgetting the visited set — causes infinite loops in cyclic graphs",
            "Using DFS for shortest path (DFS does not guarantee shortest path in unweighted graphs)",
            "Building the adjacency list incorrectly (forgetting to add both directions for undirected graphs)",
            "Not handling disconnected components — always consider iterating over all nodes, not just starting from node 0",
            "Topological sort on a graph with cycles — must detect the cycle and report impossibility",
        ],
        "complexity_pattern": "O(V + E) for BFS and DFS.  Grid problems: V = rows * cols, E = 4V.  Space O(V) for visited set + queue/stack.",
        "related_patterns": ["trees", "dynamic_programming", "backtracking"],
    },

    # -----------------------------------------------------------------------
    # 9. Dynamic Programming
    # -----------------------------------------------------------------------
    "dynamic_programming": {
        "title": "Dynamic Programming",
        "introduction": (
            "Dynamic programming (DP) solves problems with overlapping subproblems and "
            "optimal substructure.  The recipe: (1) define the state — what information "
            "uniquely identifies a subproblem; (2) write the recurrence — how to compute "
            "the current state from smaller states; (3) identify the base cases; (4) decide "
            "the computation order (bottom-up tabulation or top-down memoization).  The "
            "hardest part is step 1 — defining the right state.  Once you have that, the "
            "rest is mechanical."
        ),
        "key_ideas": [
            "State definition: dp[i] = the answer for the subproblem ending at / considering the first i elements",
            "Recurrence: express dp[i] in terms of dp[j] for j < i — this is the transition",
            "Memoization (top-down): write the recursive solution first, then cache results with @lru_cache or a dict",
            "Tabulation (bottom-up): fill a table iteratively in the right order — often more space-efficient and faster",
            "Space optimization: if dp[i] only depends on dp[i-1] (or a few previous), you can reduce from O(n) to O(1) space",
            "2D DP: dp[i][j] for two-constraint problems (e.g., knapsack: items x capacity, LCS: two strings)",
        ],
        "visual_examples": [
            {
                "description": "1D DP table for Climbing Stairs: show the table filling left to right, each cell summing the previous two",
                "ds_type": "array",
            },
            {
                "description": "2D DP grid for Longest Common Subsequence: rows = string1 chars, cols = string2 chars; arrows show the recurrence direction",
                "ds_type": "grid",
            },
            {
                "description": "Recursion tree for Fibonacci (without memo) vs memoized: show the exponential tree collapsing to linear with caching",
                "ds_type": "tree",
            },
        ],
        "canonical_problems": [
            {
                "name": "Climbing Stairs",
                "slug": "climbing-stairs",
                "difficulty": "easy",
                "why": "The simplest DP: dp[i] = dp[i-1] + dp[i-2] — literally Fibonacci with a story",
            },
            {
                "name": "House Robber",
                "slug": "house-robber",
                "difficulty": "medium",
                "why": "1D DP with a skip/take decision: dp[i] = max(dp[i-1], dp[i-2] + nums[i])",
            },
            {
                "name": "Coin Change",
                "slug": "coin-change",
                "difficulty": "medium",
                "why": "Unbounded knapsack variant — dp on the amount, try each coin denomination",
            },
            {
                "name": "Longest Increasing Subsequence",
                "slug": "longest-increasing-subsequence",
                "difficulty": "medium",
                "why": "O(n^2) DP is intuitive; O(n log n) with binary search + patience sorting is the follow-up",
            },
            {
                "name": "Edit Distance",
                "slug": "edit-distance",
                "difficulty": "medium",
                "why": "Classic 2D DP on two strings — insert, delete, replace operations map to three transitions",
            },
        ],
        "common_mistakes": [
            "Not identifying the correct state — too many dimensions or missing a necessary dimension",
            "Wrong base case — dp[0] is often a source of off-by-one errors",
            "Filling the table in the wrong order (e.g., left-to-right when the recurrence needs right-to-left)",
            "Forgetting to handle impossible/invalid states (e.g., returning infinity instead of -1)",
            "Trying to optimize space before getting the correct O(n) or O(n*m) solution working first",
        ],
        "complexity_pattern": "Time = O(number of states * transitions per state).  1D: O(n) or O(n*k).  2D: O(n*m).  Space matches the table size, often reducible.",
        "related_patterns": ["greedy", "backtracking", "graphs"],
    },

    # -----------------------------------------------------------------------
    # 10. Backtracking
    # -----------------------------------------------------------------------
    "backtracking": {
        "title": "Backtracking",
        "introduction": (
            "Backtracking is systematic trial-and-error: build a solution incrementally, "
            "and abandon (backtrack) as soon as you know the current path cannot lead to a "
            "valid solution.  It is DFS on the decision tree.  The template: (1) choose — pick "
            "the next element to add; (2) explore — recurse with the updated state; (3) unchoose — "
            "remove the element and try the next option.  The key optimisation is pruning: the "
            "earlier you detect an invalid path, the more branches you skip."
        ),
        "key_ideas": [
            "Decision tree: each level of recursion represents one decision; the leaves are complete solutions or dead ends",
            "Template: backtrack(state, choices) — for each choice, make it, recurse, undo it",
            "Subsets vs permutations: subsets use a start index (avoid re-picking earlier elements); permutations use a used/visited set",
            "Pruning: add conditions before recursing to skip branches that cannot possibly lead to a valid solution",
            "Constraint satisfaction: Sudoku, N-Queens — place an element, check constraints, recurse or backtrack",
        ],
        "visual_examples": [
            {
                "description": "Decision tree for subsets of [1,2,3]: at each node, choose to include or exclude the current element; leaves are all subsets",
                "ds_type": "tree",
            },
            {
                "description": "N-Queens board: place queens row by row, show conflict detection (column, diagonal) and backtracking when stuck",
                "ds_type": "grid",
            },
            {
                "description": "Permutation tree: at each level, pick from remaining elements; show the 'used' set shrinking available choices",
                "ds_type": "tree",
            },
        ],
        "canonical_problems": [
            {
                "name": "Subsets",
                "slug": "subsets",
                "difficulty": "medium",
                "why": "The purest backtracking template — include or exclude each element, collect all leaves",
            },
            {
                "name": "Combination Sum",
                "slug": "combination-sum",
                "difficulty": "medium",
                "why": "Backtracking with reuse allowed — start index stays the same (unbounded) or advances (bounded)",
            },
            {
                "name": "Permutations",
                "slug": "permutations",
                "difficulty": "medium",
                "why": "Backtracking with a used set instead of a start index — every remaining element is a valid choice",
            },
            {
                "name": "Word Search",
                "slug": "word-search",
                "difficulty": "medium",
                "why": "Backtracking on a grid — DFS in 4 directions with visited marking and unmarking",
            },
            {
                "name": "N-Queens",
                "slug": "n-queens",
                "difficulty": "hard",
                "why": "Constraint satisfaction: place one queen per row, track columns and diagonals, prune aggressively",
            },
        ],
        "common_mistakes": [
            "Forgetting to undo the choice (unchoose step) — leads to corrupted state in later branches",
            "Not using a start index for combinations/subsets — generates duplicate subsets",
            "Passing mutable state (like a list) without copying — all branches share the same object",
            "Not pruning early enough — the solution works but TLEs on large inputs",
            "Confusing subsets and permutations templates — they have different loop structures",
        ],
        "complexity_pattern": "Subsets: O(2^n).  Permutations: O(n!).  With pruning, often much better in practice but worst case remains exponential.",
        "related_patterns": ["dynamic_programming", "graphs", "trees"],
    },

    # -----------------------------------------------------------------------
    # 11. Heap / Priority Queue
    # -----------------------------------------------------------------------
    "heap": {
        "title": "Heap / Priority Queue",
        "introduction": (
            "A heap (usually a min-heap) is a complete binary tree where every parent is "
            "smaller than its children.  It supports O(log n) insert and O(log n) extract-min, "
            "plus O(1) peek-min.  In Python, use heapq (min-heap by default; negate values for "
            "max-heap).  The three classic interview patterns are: (1) Top-K elements, (2) merge "
            "K sorted things, and (3) running median with two heaps."
        ),
        "key_ideas": [
            "Top-K pattern: maintain a min-heap of size K; if a new element is larger than the heap's min, pop and push",
            "Merge K sorted lists/arrays: push the first element of each list; pop the smallest, push the next element from that list",
            "Two-heap median: max-heap for the lower half, min-heap for the upper half; balance sizes to get median in O(1)",
            "Lazy deletion: mark elements as deleted but don't remove them; skip them when they reach the top",
            "Heap as a greedy scheduler: always process the most/least urgent task first",
        ],
        "visual_examples": [
            {
                "description": "Min-heap as a binary tree: show insert (bubble up) and extract-min (swap root with last, bubble down)",
                "ds_type": "tree",
            },
            {
                "description": "Merge K sorted lists: K pointers plus a min-heap; the smallest pointer is popped, its next element is pushed",
                "ds_type": "heap",
            },
            {
                "description": "Two-heap median: left max-heap and right min-heap side by side; show rebalancing when sizes differ by more than 1",
                "ds_type": "heap",
            },
        ],
        "canonical_problems": [
            {
                "name": "Kth Largest Element in an Array",
                "slug": "kth-largest-element-in-an-array",
                "difficulty": "medium",
                "why": "Top-K with a min-heap of size K, or quickselect for O(n) average — the foundational heap problem",
            },
            {
                "name": "Top K Frequent Elements",
                "slug": "top-k-frequent-elements",
                "difficulty": "medium",
                "why": "Count frequencies with a hash map, then use a heap of size K to extract the top K — bridges hashing and heap",
            },
            {
                "name": "Merge K Sorted Lists",
                "slug": "merge-k-sorted-lists",
                "difficulty": "hard",
                "why": "Push list heads into a min-heap; pop the smallest, push its successor — O(n log k)",
            },
            {
                "name": "Find Median from Data Stream",
                "slug": "find-median-from-data-stream",
                "difficulty": "hard",
                "why": "Two-heap approach: max-heap for lower half, min-heap for upper half — O(log n) add, O(1) median",
            },
            {
                "name": "Task Scheduler",
                "slug": "task-scheduler",
                "difficulty": "medium",
                "why": "Greedy with a max-heap: always schedule the most frequent task; use a cooldown queue for waiting tasks",
            },
        ],
        "common_mistakes": [
            "Using a max-heap when you need a min-heap (or vice versa) — in Python, negate values for max-heap",
            "Forgetting that Python's heapq is a min-heap — kth largest needs a min-heap of size K, not a max-heap",
            "Not maintaining heap size at K for top-K problems (pushing everything then popping defeats the purpose)",
            "Comparing unhashable or incomparable objects in the heap — use (priority, tie-breaker, object) tuples",
            "Assuming heap gives sorted order — heap only guarantees the top element is the min/max",
        ],
        "complexity_pattern": "Insert/extract: O(log n).  Building a heap from n elements: O(n).  Top-K: O(n log K).  Merge K sorted: O(n log K).",
        "related_patterns": ["arrays_hashing", "binary_search", "greedy"],
    },

    # -----------------------------------------------------------------------
    # 12. Greedy
    # -----------------------------------------------------------------------
    "greedy": {
        "title": "Greedy",
        "introduction": (
            "Greedy algorithms make the locally optimal choice at each step, hoping it "
            "leads to the globally optimal solution.  Unlike DP, greedy never reconsiders "
            "past decisions.  The challenge is proving the greedy choice property: that a "
            "locally optimal choice is always part of some globally optimal solution.  "
            "Classic domains: interval scheduling, activity selection, Huffman coding, "
            "and jump/gas problems.  When greedy works, it is usually simpler and faster "
            "than DP."
        ),
        "key_ideas": [
            "Greedy choice property: a locally optimal choice is safe — it does not rule out the global optimum",
            "Interval scheduling: sort by end time, greedily pick the earliest-ending non-overlapping interval",
            "Interval merging: sort by start time, merge overlapping intervals by extending the end time",
            "Jump game: track the farthest reachable index; if current index exceeds it, you are stuck",
            "Exchange argument: the standard proof technique — show swapping any other choice for the greedy choice does not make things worse",
        ],
        "visual_examples": [
            {
                "description": "Interval scheduling: timeline with overlapping intervals; highlight the greedy selection (earliest end) and the intervals it eliminates",
                "ds_type": "intervals",
            },
            {
                "description": "Jump Game: array of jump lengths with arcs showing reachable positions; track the farthest reachable index",
                "ds_type": "array",
            },
            {
                "description": "Merge Intervals: timeline showing overlapping intervals being merged into larger ones",
                "ds_type": "intervals",
            },
        ],
        "canonical_problems": [
            {
                "name": "Maximum Subarray",
                "slug": "maximum-subarray",
                "difficulty": "medium",
                "why": "Kadane's algorithm: greedily extend the current subarray or start fresh — O(n) and elegant",
            },
            {
                "name": "Jump Game",
                "slug": "jump-game",
                "difficulty": "medium",
                "why": "Track farthest reachable index; if you can reach the end, return true — pure greedy",
            },
            {
                "name": "Merge Intervals",
                "slug": "merge-intervals",
                "difficulty": "medium",
                "why": "Sort by start, greedily merge overlapping intervals — the template for interval problems",
            },
            {
                "name": "Non-overlapping Intervals",
                "slug": "non-overlapping-intervals",
                "difficulty": "medium",
                "why": "Interval scheduling: sort by end time, count conflicts — equivalent to finding the maximum non-overlapping set",
            },
            {
                "name": "Jump Game II",
                "slug": "jump-game-ii",
                "difficulty": "medium",
                "why": "BFS-flavoured greedy: treat each reachable range as a level, count levels to reach the end",
            },
        ],
        "common_mistakes": [
            "Applying greedy when it does not work — not every optimisation problem has the greedy choice property (e.g., 0/1 knapsack requires DP)",
            "Sorting by the wrong criterion (e.g., sorting intervals by start time when you should sort by end time for scheduling)",
            "Not considering edge cases: empty intervals, single interval, fully overlapping intervals",
            "Confusing 'can I reach the end?' (Jump Game) with 'minimum jumps to reach the end' (Jump Game II) — different greedy strategies",
            "Forgetting to prove or at least convince yourself that greedy is correct before coding",
        ],
        "complexity_pattern": "Usually O(n log n) if sorting is needed, O(n) for the greedy pass.  Space is usually O(1) or O(n) for output.",
        "related_patterns": ["dynamic_programming", "heap", "arrays_hashing"],
    },
}



# ---------------------------------------------------------------------------
# SYSTEM DESIGN TEACHING PLANS
# ---------------------------------------------------------------------------

SD_TEACHING_PLANS = {
    "networking": {
        "title": "Networking Essentials",
        "introduction": (
            "Imagine a user in Tokyo taps 'Buy Now' on their phone. Within 200 milliseconds, "
            "a DNS lookup resolves the hostname, a TCP connection is established through a TLS "
            "handshake, an HTTP request traverses a CDN edge node, passes through a load balancer "
            "in us-east-1, hits an application server, writes to a database, and a response "
            "travels the reverse path — all before the user notices any delay. Every layer of "
            "that journey is a networking decision you will be asked about in system design "
            "interviews.\n\n"
            "Networking is not a standalone interview topic — it is the substrate under every "
            "design. When you say 'the client calls the API,' the interviewer expects you to "
            "reason about DNS resolution time (~10-100ms), TCP handshake cost (~1 RTT, say 50ms "
            "cross-continent), TLS negotiation (~2 RTT for TLS 1.2, ~1 RTT for TLS 1.3), and "
            "HTTP overhead (headers, serialization, keep-alive reuse). These numbers change your "
            "design: a mobile client with 200ms RTT to your data center needs a CDN and edge "
            "caching far more urgently than a server-to-server call at 0.5ms RTT within the "
            "same availability zone.\n\n"
            "In this topic you will learn the OSI layers that matter for system design (L3, L4, "
            "L7), the mechanical differences between TCP, UDP, and QUIC, how HTTP has evolved "
            "across three major versions, the real-time communication patterns (WebSocket, SSE, "
            "long polling) and when each is appropriate, how DNS resolution actually works as a "
            "recursive chain, how CDNs reduce latency by bringing content closer to users, and "
            "what happens during a TLS handshake. The goal is not to memorize RFCs — it is to "
            "build intuition so you can say, in an interview, 'this adds 100ms of latency and "
            "here is how I would eliminate it.'"
        ),
        "key_concepts": [
            {
                "name": "OSI Layers That Matter: L3, L4, L7",
                "explanation": (
                    "The OSI model has 7 layers, but system design interviews care about three. "
                    "Layer 3 (Network) handles IP addressing and routing — every packet has a source "
                    "and destination IP. This is where routers operate, where BGP determines internet-scale "
                    "routes, and where Anycast works (multiple servers share one IP, and routers send traffic "
                    "to the nearest one — this is how Cloudflare's 1.1.1.1 DNS works). Layer 4 (Transport) "
                    "is TCP and UDP — the choice between reliable-ordered delivery and fast-lossy delivery. "
                    "L4 load balancers (AWS NLB, Google Maglev) route based on IP and port without inspecting "
                    "the payload — they are fast (~microsecond overhead) but cannot make routing decisions "
                    "based on URL path, cookies, or headers. Layer 7 (Application) is HTTP, gRPC, WebSocket — "
                    "the protocols your application actually speaks. L7 load balancers (AWS ALB, Nginx, Envoy) "
                    "terminate the connection, inspect the request, and can route /api/* to backend servers "
                    "and /static/* to a CDN origin, do header-based canary deployments, or inject authentication.\n\n"
                    "In interviews, the distinction matters when discussing load balancers: 'I would use an L7 "
                    "load balancer here because I need path-based routing and sticky sessions' shows deeper "
                    "understanding than just saying 'add a load balancer.' When you mention a CDN, note that "
                    "it operates at L7 (it caches HTTP responses) but is deployed using L3 Anycast (so DNS "
                    "resolves to the nearest edge POP). The practical numbers: L4 balancing adds ~0.1ms, L7 "
                    "adds ~1-5ms because it must parse the HTTP request. For internal service-to-service calls "
                    "within a data center, L4 is usually sufficient. For user-facing traffic that needs "
                    "path routing, TLS termination, or WAF protection, L7 is required."
                ),
            },
            {
                "name": "TCP vs UDP vs QUIC",
                "explanation": (
                    "TCP is connection-oriented: the 3-way handshake (SYN, SYN-ACK, ACK) costs 1 RTT before "
                    "any data flows. TCP guarantees in-order delivery, retransmits lost packets, and performs "
                    "flow control (receiver advertises window size) and congestion control (sender probes "
                    "available bandwidth). This reliability comes at a cost: head-of-line blocking, where a "
                    "single lost packet stalls all subsequent data until retransmitted. For a 50ms RTT, the "
                    "handshake alone adds 50ms, and TLS 1.2 adds another 100ms (2 RTT) — so the first byte "
                    "takes 150ms before any application data is exchanged.\n\n"
                    "UDP sends datagrams with no connection setup, no ordering, no retransmission. A DNS query "
                    "is a single UDP packet out and one back — about 10-50ms total. Video streaming (Netflix, "
                    "YouTube) and real-time voice/video (Zoom, Discord) use UDP because a dropped video frame "
                    "is better than a frozen screen waiting for retransmission. Gaming uses UDP because 16ms "
                    "frame updates cannot tolerate TCP's retransmit delays.\n\n"
                    "QUIC, designed by Google and now standardized as the transport for HTTP/3, is built on UDP "
                    "but adds connection-oriented features: reliable delivery, multiplexed streams, and built-in "
                    "TLS 1.3. The critical improvement: QUIC combines the transport handshake and TLS handshake "
                    "into a single RTT (0-RTT for resumption). And because streams are independent, a lost "
                    "packet on stream A does not block stream B — eliminating TCP's head-of-line blocking. "
                    "In interviews, mention QUIC when discussing mobile clients (handles network switching "
                    "via connection IDs rather than IP tuples) or when latency budgets are tight. The trade-off: "
                    "QUIC is newer, harder to debug with standard tools (tcpdump sees opaque UDP), and some "
                    "corporate firewalls block UDP traffic."
                ),
            },
            {
                "name": "HTTP/1.1 vs HTTP/2 vs HTTP/3",
                "explanation": (
                    "HTTP/1.1 uses one request-response pair per TCP connection (or pipelined, which nobody "
                    "actually uses due to head-of-line blocking). Browsers open 6 parallel TCP connections per "
                    "domain to work around this — each with its own handshake cost. Large pages with 50+ "
                    "resources suffer badly. HTTP/2, deployed by most major sites since 2015, multiplexes "
                    "multiple streams (requests and responses) over a single TCP connection. It adds HPACK "
                    "header compression (headers like Cookie and User-Agent are sent once, then referenced by "
                    "index) and server push (the server can proactively send resources the client will need). "
                    "The result: a single connection handles all requests, reducing handshake overhead and "
                    "improving performance by 20-50% on typical web pages.\n\n"
                    "However, HTTP/2 still runs over TCP, so a single lost packet blocks ALL streams on that "
                    "connection (TCP-level head-of-line blocking). HTTP/3 fixes this by running over QUIC "
                    "instead of TCP. Each stream is independently reliable — a lost packet only blocks its own "
                    "stream. Connection setup is 1 RTT (0-RTT for resumption). Google reports 8% reduction in "
                    "search latency and 3% reduction in YouTube rebuffering with QUIC/HTTP/3.\n\n"
                    "In interviews, know which version to recommend: HTTP/1.1 is legacy but still common for "
                    "simple REST APIs; HTTP/2 is the default for any modern web service (use it unless you have "
                    "a reason not to); HTTP/3 is ideal for mobile-heavy or latency-sensitive applications. When "
                    "discussing gRPC, note that it requires HTTP/2 for its bidirectional streaming. When discussing "
                    "CDNs, note that Cloudflare and Google Cloud CDN already serve HTTP/3 at the edge."
                ),
            },
            {
                "name": "WebSocket vs SSE vs Long Polling",
                "explanation": (
                    "These are the three patterns for server-to-client real-time communication, and choosing "
                    "the right one is a frequent interview question. Long polling is the simplest: the client "
                    "sends an HTTP request, the server holds it open until there is new data (or a timeout, "
                    "typically 30-60 seconds), then responds. The client immediately sends another request. "
                    "It works everywhere (firewalls, proxies) but wastes resources holding connections open and "
                    "has ~1 HTTP request overhead per message. Good for low-frequency updates (email notifications).\n\n"
                    "Server-Sent Events (SSE) is a one-way channel: the server pushes events to the client over "
                    "a long-lived HTTP connection using the text/event-stream content type. It supports automatic "
                    "reconnection and event IDs for resuming where you left off. SSE is simpler than WebSocket "
                    "(it is just HTTP, works through proxies, no special server support needed) but is "
                    "unidirectional — the client cannot send data back on the same connection. Ideal for live "
                    "feeds, stock tickers, or streaming AI responses (ChatGPT uses SSE).\n\n"
                    "WebSocket upgrades an HTTP connection to a full-duplex, bidirectional channel. After the "
                    "handshake (HTTP 101 Upgrade), both client and server can send frames at any time with ~2 "
                    "bytes of framing overhead (vs ~100+ bytes for HTTP headers). Use WebSocket when you need "
                    "bidirectional communication: chat applications, collaborative editing, multiplayer games, "
                    "live trading platforms. The trade-offs: WebSocket connections are stateful (sticky sessions "
                    "or a message broker are needed for scale), harder to load-balance (L7 balancers must "
                    "support the Upgrade header), and do not work through some corporate proxies. In interviews, "
                    "say SSE unless you need bidirectional — it is simpler and sufficient for most notification "
                    "and streaming use cases."
                ),
            },
            {
                "name": "DNS Resolution Chain",
                "explanation": (
                    "When your browser needs to resolve api.example.com, it follows a recursive chain. First, "
                    "the browser's local cache (Chrome caches DNS for up to 60 seconds). Then the OS resolver "
                    "cache. Then the configured recursive resolver (your ISP's, or a public one like 8.8.8.8 or "
                    "1.1.1.1). If the recursive resolver does not have a cached answer, it starts the iterative "
                    "lookup: query a root nameserver (there are 13 logical root servers, replicated via Anycast "
                    "to 1000+ physical servers), which returns the TLD nameserver for .com. Query the .com TLD "
                    "server, which returns the authoritative nameserver for example.com. Query the authoritative "
                    "nameserver, which returns the A/AAAA record (IP address) for api.example.com. The whole "
                    "chain is typically 10-100ms uncached, <1ms cached.\n\n"
                    "TTL (Time To Live) is the critical knob: a 300-second TTL means resolvers cache the answer "
                    "for 5 minutes. Short TTLs (30-60s) enable fast failover — if your server goes down, update "
                    "DNS and clients pick up the new IP within a minute. Long TTLs (3600s+) reduce DNS traffic "
                    "and lookup latency but make failover slow. In practice, services like AWS Route 53 use "
                    "health checks with 60s TTL and weighted/latency-based routing to direct users to the "
                    "nearest healthy endpoint.\n\n"
                    "In interviews, DNS comes up in two contexts: (1) the 'what happens when you type a URL' "
                    "question — walk through the full chain, and (2) DNS as a load balancing mechanism. "
                    "GeoDNS (Route 53 latency-based routing) returns different IPs based on the client's "
                    "location. This is the first layer of global load balancing, before CDN, before L4/L7 "
                    "balancers. Mention that DNS is a single point of failure — DDoS attacks on DNS providers "
                    "(like the 2016 Dyn attack) can take down major sites."
                ),
            },
            {
                "name": "CDNs and TLS Handshake",
                "explanation": (
                    "A CDN (Content Delivery Network) caches content at edge locations (PoPs — Points of "
                    "Presence) geographically close to users. When a user in Mumbai requests an image, instead "
                    "of traveling 150ms RTT to a server in Virginia, the CDN edge in Mumbai serves it in ~5ms. "
                    "CDNs cache static assets (images, CSS, JS) and increasingly dynamic content (API responses "
                    "with short TTLs, personalized at the edge via edge compute like Cloudflare Workers). "
                    "Cloudflare has 300+ PoPs, AWS CloudFront has 450+. The cache HIT ratio is the key metric — "
                    "a well-configured CDN hits 95%+ for static content.\n\n"
                    "CDN placement in your architecture: DNS resolves to the CDN edge (via CNAME to cdn.example.com "
                    "which resolves via Anycast). The edge checks its cache. On a miss, it fetches from your "
                    "origin server (the 'origin pull' model) and caches the response. You control caching via "
                    "Cache-Control headers (max-age, s-maxage, stale-while-revalidate). In interviews, always "
                    "place the CDN between the client and your load balancer, and mention it early — it is the "
                    "single biggest latency win for read-heavy, globally distributed applications.\n\n"
                    "TLS (Transport Layer Security) encrypts the connection. The TLS 1.2 handshake adds 2 RTT: "
                    "one for TCP, one for the TLS exchange (ClientHello, ServerHello, certificate, key exchange). "
                    "TLS 1.3 reduces this to 1 RTT by combining steps, and supports 0-RTT resumption for "
                    "returning clients (at the cost of replay attack vulnerability for the 0-RTT data). QUIC "
                    "integrates TLS 1.3 into the transport handshake, achieving 1 RTT for new connections and "
                    "0 RTT for resumption. In practice, the CDN terminates TLS at the edge (so the expensive "
                    "handshake happens over 5ms RTT instead of 150ms), then uses a persistent, keep-alive "
                    "connection to your origin — another reason to use a CDN even for dynamic content."
                ),
            },
        ],
        "real_world_examples": [
            "Google's QUIC protocol handles 35%+ of Chrome's traffic — 8% faster search, 3% less YouTube rebuffering. Connection migration lets mobile clients switch from WiFi to cellular without re-handshaking.",
            "Cloudflare's Anycast network routes DNS queries (1.1.1.1) to the nearest of 300+ PoPs, achieving <10ms response time globally. Their CDN terminates TLS at the edge, saving 100-200ms of latency for distant users.",
            "Netflix uses its own CDN (Open Connect) with dedicated appliances in ISP data centers. Cache hit ratios exceed 95%. Video chunks are served over HTTP/2 with QUIC fallback, using adaptive bitrate streaming over TCP/UDP.",
            "Discord uses WebSocket for real-time chat delivery and UDP via a custom protocol for voice/video. Their gateway servers maintain millions of concurrent WebSocket connections, load-balanced with consistent hashing.",
            "AWS Route 53 provides DNS with latency-based routing and health checks (60s TTL). It answered 1 trillion+ queries/day as of 2022, using Anycast across 30+ edge locations for sub-millisecond resolution.",
        ],
        "common_interview_questions": [
            "What happens when you type google.com in the browser? — Walk through DNS resolution (browser cache, OS cache, recursive resolver, root/TLD/authoritative), TCP 3-way handshake (~1 RTT), TLS negotiation (~1-2 RTT), HTTP GET request, server processing, response, browser rendering. Mention CDN intercept if applicable.",
            "When would you choose WebSocket vs SSE vs long polling? — WebSocket for bidirectional (chat, gaming); SSE for server-push only (live feeds, AI streaming); long polling as a fallback when SSE is not supported or for very low frequency updates.",
            "How does a CDN reduce latency, and where do you place it? — CDN caches at edge PoPs close to users, reducing RTT from ~150ms (cross-continent) to ~5ms (same city). Place it between DNS and your load balancer. Configure Cache-Control headers. It also terminates TLS at the edge.",
            "Explain TCP head-of-line blocking and how HTTP/3 solves it. — In TCP, a lost packet blocks all subsequent data. HTTP/2 multiplexes streams over one TCP connection, so one lost packet blocks ALL streams. HTTP/3/QUIC gives each stream independent reliability, so loss on stream A does not stall stream B.",
            "How would you design a system for users in 50 countries with <100ms latency? — GeoDNS (Route 53 latency routing) to direct to nearest region. CDN for static/cacheable content. Multi-region deployment with regional databases. QUIC/HTTP/3 for reduced handshake. Edge compute for personalization.",
        ],
        "key_trade_offs": [
            "TCP reliability vs UDP speed — choose TCP when every byte must arrive correctly (financial transactions, file transfers); choose UDP when speed matters more than completeness (video streaming, gaming, DNS). QUIC bridges the gap with reliable-but-fast over UDP.",
            "L4 load balancing vs L7 load balancing — L4 is faster (~0.1ms overhead) and simpler, good for internal traffic or when content-based routing is unnecessary. L7 adds ~1-5ms but enables path-based routing, TLS termination, sticky sessions, WAF integration. Use L7 for user-facing traffic.",
            "Short DNS TTL vs long DNS TTL — Short TTL (30-60s) enables fast failover and traffic shifting but increases DNS query volume and adds lookup latency. Long TTL (3600s) reduces DNS load but makes failover slow. Production sweet spot is usually 60-300s with health checks.",
            "WebSocket vs SSE — WebSocket gives full duplex but requires sticky sessions, special load balancer support, and stateful connection management. SSE is simpler (just HTTP), works through all proxies, auto-reconnects, but is unidirectional. Default to SSE unless you genuinely need client-to-server streaming.",
            "CDN edge caching vs origin freshness — Aggressive caching (long max-age) gives best performance but risks serving stale content. Short TTLs or stale-while-revalidate patterns balance freshness and speed. Cache purge APIs (Cloudflare, CloudFront) enable instant invalidation when content changes.",
        ],
        "common_mistakes": [
            "Saying 'add a load balancer' without specifying L4 or L7, or explaining why. Interviewers want to know you understand the difference — L4 for raw TCP passthrough, L7 for HTTP-aware routing and TLS termination.",
            "Ignoring latency numbers entirely. Saying 'the client calls the API' without acknowledging that a cross-continent call is ~150ms RTT, or that DNS adds 10-100ms, makes your design feel hand-wavy. Anchor your design in concrete latency budgets.",
            "Choosing WebSocket when SSE would suffice. Many candidates default to WebSocket for any real-time feature, but for server-push scenarios (notifications, live feeds, streaming responses) SSE is simpler, works through proxies, and auto-reconnects. Reserve WebSocket for genuinely bidirectional needs.",
            "Forgetting that HTTP/2 is multiplexed. Candidates sometimes propose multiple connections or domain sharding (an HTTP/1.1 trick) when HTTP/2 already solves the problem with stream multiplexing over a single connection.",
            "Not mentioning TLS cost or CDN TLS termination. TLS adds 1-2 RTT to every new connection. A CDN terminating TLS at the edge (5ms RTT) instead of at the origin (150ms RTT) saves 150-300ms on the first request. This is a high-signal detail that shows depth.",
        ],
        "interview_tips": [
            "When asked 'what happens when you type a URL,' structure your answer in layers: DNS (application), TCP (transport), TLS (security), HTTP (application), server processing, response. Mention specific latency at each step — this demonstrates you think about performance, not just correctness.",
            "Anchor every networking claim in a concrete number. 'TCP handshake costs 1 RTT, which is ~50ms cross-continent or ~0.5ms within an AZ. TLS 1.3 adds another RTT. QUIC combines both into 1 RTT.' Interviewers remember candidates who reason quantitatively.",
            "When placing a CDN, always explain the cache key strategy and invalidation approach, not just 'put a CDN in front.' Say: 'CDN caches by URL with a 60s TTL. For user-specific content, we use Cache-Control: private or vary on the auth header to prevent cross-user leakage.'",
            "Use the phrase 'at this layer' to show OSI awareness. For example: 'At L4, the NLB routes to a healthy backend based on IP hash. At L7, Nginx routes /api to the app tier and /static to the CDN origin.' This shows you think in layers, which is the mark of a strong systems thinker.",
        ],
        "related_concepts": ["api_design", "caching", "consistent_hashing", "data_modeling"],
    },

    "api_design": {
        "title": "API Design",
        "introduction": (
            "Every system design interview involves designing an API — it is the contract between "
            "your client and your backend, and increasingly between your own microservices. Consider "
            "the Ticketmaster API: when a user searches for concerts, the client calls "
            "GET /v1/events?keyword=coldplay&city=austin&page=1. When they purchase a ticket, it is "
            "POST /v1/orders with a JSON body containing the event_id, seat_ids, and an idempotency "
            "key. That idempotency key prevents double-charging if the network glitches and the "
            "client retries — a detail that separates junior from senior API design.\n\n"
            "API design is not just REST endpoints. You need to reason about which paradigm to use "
            "(REST for external consumers, gRPC for internal service-to-service, GraphQL for "
            "client-driven data fetching), how to handle pagination at scale (why cursor-based "
            "beats offset-based when you have 100 million rows), how to protect your service with "
            "rate limiting (token bucket algorithms, distributed rate limiting with Redis), how to "
            "evolve your API without breaking existing clients (versioning strategies), and how to "
            "authenticate requests (OAuth2 flows, JWT structure, API keys).\n\n"
            "In interviews, API design often comes in Step 3 of the system design framework — after "
            "requirements and entities, before the high-level architecture. A strong candidate maps "
            "each functional requirement to a specific endpoint, chooses correct HTTP methods (and "
            "explains idempotency), defines the response shape including pagination metadata, and "
            "calls out rate limiting and auth. This section teaches you to design APIs that an "
            "interviewer would want to ship to production."
        ),
        "key_concepts": [
            {
                "name": "REST Deep Dive: Resources, Methods, Idempotency",
                "explanation": (
                    "REST models your domain as resources identified by URLs. The first design decision is "
                    "resource modeling: nouns, not verbs. /users, /events/{event_id}/tickets, /orders/{order_id}. "
                    "Nested resources express ownership — /users/{id}/playlists means playlists belong to a user. "
                    "But avoid deep nesting (more than 2 levels) — /users/{id}/playlists/{id}/songs/{id}/comments "
                    "becomes unmanageable; flatten to /comments?song_id=123.\n\n"
                    "HTTP methods map to operations with specific semantics. GET is safe (no side effects) and "
                    "idempotent (calling it 10 times gives the same result). POST creates a resource and is NOT "
                    "idempotent — two identical POSTs create two resources, which is why Stripe requires an "
                    "Idempotency-Key header on POST requests so retries are safe. PUT replaces the entire resource "
                    "and IS idempotent. PATCH partially updates and may or may not be idempotent. DELETE is "
                    "idempotent — deleting an already-deleted resource returns 204 or 404, not an error.\n\n"
                    "Status codes communicate outcome. The critical ones: 200 (OK, successful GET/PUT/PATCH), "
                    "201 (Created, successful POST — include Location header), 204 (No Content, successful DELETE), "
                    "400 (Bad Request — client sent malformed data), 401 (Unauthorized — not authenticated), "
                    "403 (Forbidden — authenticated but not authorized), 404 (Not Found), 409 (Conflict — e.g., "
                    "duplicate email), 429 (Too Many Requests — rate limited, include Retry-After header), "
                    "500 (Internal Server Error), 503 (Service Unavailable — overloaded, try later).\n\n"
                    "Parameters go in three places: path for resource identity (/events/{event_id}), query "
                    "string for filtering and pagination (?city=austin&limit=20&cursor=abc), and body for "
                    "creation/update payloads (JSON with the resource fields). Never put sensitive data in "
                    "query params — they appear in logs and browser history."
                ),
            },
            {
                "name": "GraphQL: When and Why",
                "explanation": (
                    "GraphQL lets the client specify exactly which fields it needs in a single request. "
                    "Instead of GET /users/123 returning 30 fields (over-fetching) or needing GET /users/123, "
                    "GET /users/123/posts, GET /users/123/followers as three separate calls (under-fetching), "
                    "the client sends: query { user(id: 123) { name, posts { title }, followerCount } }. "
                    "This is transformative for mobile clients on slow networks — fewer round trips, smaller "
                    "payloads.\n\n"
                    "The N+1 problem is GraphQL's biggest trap. If a query requests users { posts { comments } }, "
                    "a naive resolver fetches each user, then N queries for their posts, then N*M queries for "
                    "comments. The solution is DataLoader — a batching/caching layer that collects all IDs from "
                    "one level and issues a single WHERE id IN (...) query. Facebook (who created GraphQL) uses "
                    "DataLoader extensively. Without it, GraphQL performance is catastrophically worse than REST.\n\n"
                    "When to use GraphQL: when you have many clients with different data needs (mobile vs web vs "
                    "watch), when over-fetching is a real performance problem, when your data graph is complex "
                    "with many relationships. When NOT to use it: for simple CRUD APIs with predictable access "
                    "patterns (REST is simpler), for file uploads (GraphQL handles them poorly), for real-time "
                    "streaming (use gRPC or WebSocket instead), or when your team does not want to maintain a "
                    "schema and resolvers layer. In interviews, mention GraphQL when the problem involves diverse "
                    "clients or complex nested data, but do not default to it — REST is usually the right first "
                    "answer, and choosing GraphQL without justification can look like chasing trends."
                ),
            },
            {
                "name": "gRPC and Protocol Buffers",
                "explanation": (
                    "gRPC is a high-performance RPC framework that uses HTTP/2 for transport and Protocol "
                    "Buffers (protobuf) for serialization. Where REST sends human-readable JSON over HTTP/1.1, "
                    "gRPC sends compact binary data over multiplexed HTTP/2 streams. The performance difference "
                    "is significant: protobuf encoding is 3-10x smaller than JSON and 20-100x faster to "
                    "serialize/deserialize. For internal service-to-service communication handling millions of "
                    "RPCs per second, this matters enormously.\n\n"
                    "gRPC supports four communication patterns. Unary: one request, one response (like REST). "
                    "Server streaming: one request, stream of responses (client calls GetStockPrices, server "
                    "pushes updates). Client streaming: stream of requests, one response (client uploads chunks, "
                    "server responds with status). Bidirectional streaming: both sides stream simultaneously "
                    "(real-time collaboration, chat). This streaming capability is something REST fundamentally "
                    "cannot do — it is why gRPC is used for internal microservice communication at Google, "
                    "Netflix, and Square.\n\n"
                    "The contract is defined in .proto files: you declare messages (like JSON Schema but typed "
                    "and versioned) and services (like API endpoints), then code-generate client and server stubs "
                    "in any language. This means a Go service and a Python service can communicate with "
                    "compile-time type safety and zero manual serialization. The downside: gRPC is not "
                    "browser-friendly (browsers cannot make raw HTTP/2 calls — you need gRPC-Web, a proxy "
                    "layer), not human-readable (binary payloads require tooling to inspect), and harder to "
                    "debug with curl. In interviews, use gRPC for internal communication between services and "
                    "REST for external/public APIs. If asked about a system with 5+ microservices, mention that "
                    "internal traffic uses gRPC for performance and type safety."
                ),
            },
            {
                "name": "Pagination: Offset vs Cursor",
                "explanation": (
                    "Offset pagination uses ?page=5&size=20, which translates to SQL OFFSET 80 LIMIT 20. "
                    "It is simple to implement and gives clients random access to any page. But it has two "
                    "critical problems. First, performance: OFFSET 1000000 LIMIT 20 forces the database to scan "
                    "and discard 1 million rows before returning 20 — O(offset) cost. On a table with 100M rows, "
                    "deep pagination is cripplingly slow. Second, consistency: if a new item is inserted while "
                    "the client is paginating, items shift — the client may see duplicates or miss items entirely.\n\n"
                    "Cursor pagination uses ?cursor=eyJ0IjoiMjAyNC0wMS0xNVQxMjowMDowMFoiLCJpIjoiYWJjMTIzIn0=&limit=20. "
                    "The cursor encodes the last seen item's sort key (e.g., created_at + id). The query becomes "
                    "WHERE (created_at, id) < (:cursor_ts, :cursor_id) ORDER BY created_at DESC, id DESC LIMIT 20. "
                    "This uses an index seek — O(log n) regardless of how deep into the dataset you are. And "
                    "insertions/deletions do not cause duplicates or gaps because the cursor anchors to a specific "
                    "item, not a numeric offset.\n\n"
                    "Twitter's API v2 returns: { data: [...], meta: { next_token: 'abc123', result_count: 20 } }. "
                    "The client passes next_token as pagination_token on the next request. Ticketmaster's discovery "
                    "API similarly uses a page cursor. In interviews, always recommend cursor pagination for large "
                    "datasets (any table expected to exceed 100K rows). Use offset only when random page access is "
                    "required (admin dashboards with 'go to page 50') and the dataset is small. The response "
                    "should always include has_next (boolean) and next_cursor (the opaque cursor string)."
                ),
            },
            {
                "name": "Rate Limiting: Algorithms and Distribution",
                "explanation": (
                    "Rate limiting protects your service from abuse, DoS attacks, and misbehaving clients. The "
                    "three main algorithms are token bucket, sliding window log, and sliding window counter.\n\n"
                    "Token bucket: a bucket holds up to B tokens, refilled at rate R tokens per second. Each "
                    "request consumes one token. If the bucket is empty, the request is rejected (429). This "
                    "allows short bursts (up to B requests) while maintaining an average rate of R. It is the "
                    "most common algorithm — AWS API Gateway, Stripe, and most rate limiters use it. Implementation: "
                    "store (token_count, last_refill_timestamp) per user in Redis. On each request, calculate "
                    "tokens_to_add = (now - last_refill) * rate, clamp to max, decrement by 1.\n\n"
                    "Sliding window log: store the timestamp of every request in a sorted set. On each new "
                    "request, remove entries older than the window, count remaining entries, reject if over limit. "
                    "Precise but memory-heavy — storing every timestamp for a high-traffic API is expensive.\n\n"
                    "Sliding window counter: a hybrid. Divide time into fixed windows (e.g., 1-minute buckets). "
                    "Weight the previous window's count by the overlap. Example: at 1:00:45 with a 1-minute "
                    "window, the effective count is (prev_window_count * 0.25) + current_window_count. Less "
                    "precise but very memory-efficient — just two counters per user.\n\n"
                    "Distributed rate limiting is the hard part. With 10 API servers, each seeing a fraction of "
                    "traffic, per-server limits are inaccurate. Solution: centralize the counter in Redis with "
                    "atomic INCR + EXPIRE. Redis handles ~100K ops/sec per instance, which is sufficient for "
                    "most APIs. For extreme scale, use a local rate limiter with periodic sync to a central store "
                    "(eventual consistency, but prevents thundering herd on Redis). Return 429 with headers: "
                    "X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After."
                ),
            },
            {
                "name": "Authentication: API Keys, OAuth2, JWT",
                "explanation": (
                    "API keys are the simplest authentication method: a long random string passed in a header "
                    "(X-API-Key: abc123) or query parameter. Ticketmaster's API uses an apikey query parameter. "
                    "API keys identify the calling application (not the user), are easy to implement, and are "
                    "appropriate for server-to-server communication or public APIs with usage tracking. "
                    "Limitations: they do not expire by default (must be rotated manually), and they carry "
                    "full permissions (no scoping).\n\n"
                    "OAuth2 is the standard for delegated authorization — 'let this app access my data without "
                    "giving it my password.' The Authorization Code flow (used by Twitter, Google, GitHub): "
                    "the client redirects the user to the auth server, the user logs in and grants permission, "
                    "the auth server redirects back with a code, the client exchanges the code for an access "
                    "token (short-lived, ~1 hour) and a refresh token (long-lived, ~30 days). The access token "
                    "is sent as a Bearer token in the Authorization header. This is the gold standard for "
                    "user-facing APIs.\n\n"
                    "JWT (JSON Web Token) is a format for access tokens. It contains three Base64-encoded parts: "
                    "header (algorithm, type), payload (user_id, scopes, expiration), and signature (HMAC or RSA). "
                    "The key property: JWTs are self-contained — the server can validate them without a database "
                    "lookup by verifying the signature. This is crucial for stateless microservices. The trade-off: "
                    "JWTs cannot be revoked before expiration (unlike opaque tokens that can be deleted from a "
                    "store). Mitigation: use short expiration (15 minutes) with refresh tokens, or maintain a "
                    "revocation list (but this re-introduces statefulness). In interviews, use OAuth2 + JWT "
                    "for user-facing APIs and API keys for service-to-service. Always mention that tokens go in "
                    "the Authorization header, never in URL params (they appear in logs)."
                ),
            },
        ],
        "real_world_examples": [
            "Stripe's REST API is the gold standard: clean resource naming (/v1/charges, /v1/customers/{id}), idempotency keys on all POST requests (Idempotency-Key header), cursor pagination, versioning via Stripe-Version header, and detailed error responses with machine-readable error codes.",
            "Twitter API v2 uses OAuth2 with PKCE for user authentication, bearer tokens for app-only access, cursor-based pagination (next_token in response meta), rate limiting at 300 requests per 15-minute window per user (returned in X-Rate-Limit headers), and field selection via tweet.fields parameter (GraphQL-like).",
            "Google's internal services communicate via gRPC with Protocol Buffers. The public API (Maps, YouTube) uses REST with API keys, but the backend has 10 billion+ gRPC calls per second across their microservice mesh, all type-safe via .proto contract files.",
            "GitHub's REST API (v3) and GraphQL API (v4) run side by side. The GraphQL API was introduced because mobile clients needed to fetch repository, issues, and pull requests in a single request instead of 3 REST calls. Rate limits are 5000 requests/hour for authenticated users.",
            "Ticketmaster Discovery API: GET /v2/events.json?apikey=KEY&keyword=coldplay&city=austin&page=0&size=20. Uses offset pagination (acceptable because most users never go past page 5), API key authentication, and 5000 requests/day rate limit per API key.",
        ],
        "common_interview_questions": [
            "Design the API for a Twitter-like feed. — GET /v1/feed?cursor=abc&limit=20 (cursor pagination, returns tweets from followed users). POST /v1/tweets (body: {text, media_ids}, requires auth token, returns 201 with tweet object). DELETE /v1/tweets/{id} (204, idempotent). Mention rate limiting: 300 tweets/3hrs, 180 feed requests/15min.",
            "How do you handle idempotency in payment APIs? — Client generates a unique Idempotency-Key UUID and sends it with every POST /orders request. Server stores the key with the result. On retry, server returns the stored result instead of processing again. Without this, a network timeout after payment processing could cause double-charging.",
            "When would you choose GraphQL over REST? — When multiple clients (mobile, web, watch) need different subsets of the same data and over-fetching wastes bandwidth. When the data model is a deep graph with many relationships. NOT for simple CRUD, file uploads, or when the team lacks GraphQL expertise.",
            "How do you implement distributed rate limiting? — Use Redis with atomic INCR on a key like rate:{user_id}:{minute_bucket}, set EXPIRE to the window duration. Token bucket: store {count, last_refill_ts} in a Redis hash, atomically calculate and decrement via Lua script to avoid race conditions.",
            "REST vs gRPC — when would you choose each? — REST for external/public APIs (human-readable, browser-friendly, universal tooling). gRPC for internal service-to-service (binary efficiency, streaming, type safety, code generation). In a microservice architecture, the API gateway exposes REST to clients and translates to gRPC for internal calls.",
        ],
        "key_trade_offs": [
            "REST (universal, human-readable, browser-native, massive tooling) vs gRPC (3-10x faster serialization, streaming, type-safe contracts) — use REST for external APIs, gRPC for internal service mesh. Many systems use both: REST at the edge, gRPC inside.",
            "Offset pagination (simple, random page access) vs cursor pagination (O(log n) at any depth, stable under writes) — use offset for small datasets or admin UIs; cursor for anything user-facing with >100K rows. The performance difference at 1M+ rows is dramatic.",
            "Strict rate limiting (protects backend, prevents abuse) vs generous limits (better developer experience, fewer support tickets) — start generous, tighten based on observed abuse. Always return rate limit headers so clients can self-throttle. Consider tiered limits: free tier at 100 req/min, paid at 10K req/min.",
            "JWT tokens (stateless validation, no DB lookup) vs opaque tokens (revocable, server-side session) — JWTs scale better for microservices but cannot be instantly revoked. Use short-lived JWTs (15min) with refresh tokens as a compromise.",
            "URL versioning (/v1/users — explicit, easy to route, easy to test with curl) vs header versioning (Accept: application/vnd.api+json;v=2 — cleaner URLs, harder to discover) — most production APIs use URL versioning for its simplicity. Use header versioning only if URL aesthetics matter to your team.",
        ],
        "common_mistakes": [
            "Using verbs instead of nouns in REST endpoints. POST /createUser should be POST /users. GET /getEventsByCity should be GET /events?city=austin. The HTTP method already specifies the action — the URL should identify the resource.",
            "Not handling idempotency on POST/PATCH. Every create or update endpoint that touches money, inventory, or state must support idempotency keys. Without them, network retries cause double-charging, double-booking, or duplicate records. This is the single most common production API bug.",
            "Using offset pagination on large tables without understanding the performance cost. OFFSET 5000000 on a PostgreSQL table with 10M rows takes seconds because the DB scans and discards 5M rows. Cursor pagination with a composite index makes this O(log n).",
            "Defaulting to GraphQL without justification. If the problem has predictable, fixed query patterns (like a URL shortener or a chat app), REST is simpler and more performant. GraphQL adds a resolver layer, N+1 risk, and caching complexity that is unjustified for simple APIs.",
            "Putting authentication tokens in URL query parameters. GET /users?token=secret123 exposes the token in server logs, browser history, referrer headers, and proxy logs. Always use the Authorization: Bearer header.",
        ],
        "interview_tips": [
            "Start API design by mapping functional requirements to endpoints. 'The first requirement is users can post tweets. That is POST /v1/tweets with a JSON body. Second requirement is viewing a feed — GET /v1/feed with cursor pagination.' This shows structure and traceability.",
            "Always mention idempotency when designing a POST endpoint that mutates state. Say: 'POST /v1/orders accepts an Idempotency-Key header. The server stores the key in Redis with a 24-hour TTL. On duplicate keys, it returns the cached result. This prevents double-charging on retries.' This single detail signals production experience.",
            "When asked about rate limiting, name the algorithm: 'I would use a token bucket algorithm with Redis. Each user gets a bucket of 100 tokens, refilling at 10 per second. The check is an atomic Lua script: calculate tokens since last refill, decrement, return allow/deny.' Being specific about the mechanism is far stronger than saying 'add rate limiting.'",
            "Frame gRPC as a deliberate choice: 'External clients hit our REST API through the API gateway. Internally, the order service and payment service communicate via gRPC — the protobuf encoding is 5x smaller than JSON, and we get compile-time type safety from the .proto contracts.' This shows you understand where each paradigm fits.",
        ],
        "related_concepts": ["networking", "caching", "message_queues", "data_modeling"],
    },

    "data_modeling": {
        "title": "Data Modeling",
        "introduction": (
            "When you say 'I would use a database' in a system design interview, the follow-up is always: "
            "'Which database? What does the schema look like? How do you index it?' Data modeling is the "
            "art of structuring your data so that your most common queries are fast, your writes are "
            "efficient, and your system can scale. Get it wrong and no amount of caching or sharding will "
            "save you — you will be fighting your data model forever.\n\n"
            "The landscape has five major database families, each optimized for different access patterns. "
            "Relational databases (PostgreSQL, MySQL) excel at structured data with complex relationships and "
            "transactions. Document stores (MongoDB, DynamoDB) store denormalized JSON-like documents for "
            "flexible schemas. Key-value stores (Redis, Memcached) are the fastest for simple lookups. "
            "Wide-column stores (Cassandra, HBase) handle massive write throughput across distributed clusters. "
            "Graph databases (Neo4j, Amazon Neptune) traverse relationships efficiently when the query is "
            "'find all friends-of-friends' rather than 'find a user by ID.'\n\n"
            "In this topic you will learn when to use each database type with concrete decision criteria, "
            "how to design schemas for both relational (normalization vs denormalization) and NoSQL (embedding "
            "vs referencing) models, when and how to create indexes, the ACID vs BASE consistency spectrum, "
            "and how to optimize for read-heavy vs write-heavy workloads. The default recommendation for "
            "most system design interviews is PostgreSQL — and you will learn exactly when to deviate from "
            "that default and why."
        ),
        "key_concepts": [
            {
                "name": "Five Database Types Compared",
                "explanation": (
                    "Relational (PostgreSQL, MySQL): rows and columns, enforced schema, SQL, ACID transactions, "
                    "JOINs. Use when: you have structured data with relationships (users, orders, products), "
                    "need transactions (banking, inventory), or need ad-hoc queries. PostgreSQL handles 10K+ "
                    "transactions/sec on a single node and supports JSONB for semi-structured data. It is the "
                    "right default for 80% of system design problems.\n\n"
                    "Document (MongoDB, DynamoDB, Firestore): stores JSON/BSON documents in collections. Schema "
                    "is flexible — each document can have different fields. Use when: your data is naturally "
                    "hierarchical (a product with nested variants and reviews), your schema evolves rapidly "
                    "(early-stage startup), or you need horizontal scaling with simple partition keys. DynamoDB "
                    "handles millions of requests/sec with single-digit ms latency. Trade-off: no JOINs, so "
                    "related data must be denormalized into a single document or fetched with multiple queries.\n\n"
                    "Key-Value (Redis, Memcached, DynamoDB in KV mode): simple get(key)/set(key, value). "
                    "Redis does 100K+ ops/sec with sub-millisecond latency. Use for: caching, session storage, "
                    "rate limiting counters, leaderboards (sorted sets). Not suitable for queries beyond exact "
                    "key lookup — you cannot say 'find all keys where value.age > 25.'\n\n"
                    "Wide-Column (Cassandra, HBase, ScyllaDB): data is organized by row key, with columns "
                    "grouped into column families. Designed for massive write throughput across distributed "
                    "clusters — Cassandra handles 1M+ writes/sec across a 100-node cluster. Use for: time-series "
                    "data (IoT sensors, metrics), activity feeds, messaging systems. The partition key determines "
                    "data distribution; the clustering key determines sort order within a partition. Trade-off: "
                    "queries are efficient only when they follow the partition/clustering key structure.\n\n"
                    "Graph (Neo4j, Amazon Neptune, Dgraph): nodes and edges with properties. Traversal queries "
                    "(shortest path, friends-of-friends, recommendation engines) that would require expensive "
                    "recursive JOINs in SQL are O(1) per hop in a graph DB. Use for: social networks, fraud "
                    "detection, knowledge graphs. Trade-off: not suitable for general-purpose CRUD, poor at "
                    "aggregations and analytics, smaller ecosystem than relational databases."
                ),
            },
            {
                "name": "Schema Design: Normalization vs Denormalization",
                "explanation": (
                    "Normalization eliminates data redundancy by splitting data into multiple tables connected "
                    "by foreign keys. Third Normal Form (3NF) means: every non-key column depends on the key, "
                    "the whole key, and nothing but the key. Example: instead of storing the city name on every "
                    "order row, you store a city_id that references a cities table. Benefits: single source of "
                    "truth (update the city name once), smaller storage, consistent data. Cost: queries require "
                    "JOINs, which are expensive at scale.\n\n"
                    "Denormalization intentionally duplicates data to avoid JOINs. Example: an e-commerce "
                    "product listing page needs product name, price, seller name, average rating, and review "
                    "count. Normalized, that is 4 JOINs (products, sellers, ratings, reviews). Denormalized, "
                    "you store seller_name, avg_rating, and review_count directly on the product row. The "
                    "read is a single indexed lookup — 10x faster. Cost: writes must update data in multiple "
                    "places (if the seller changes their name, you must update every product row). Eventual "
                    "consistency between copies is acceptable in most cases.\n\n"
                    "The decision framework: normalize by default (it is safer and prevents anomalies). "
                    "Denormalize specific query paths that are performance-critical. A Twitter feed that is "
                    "read 1000x more than it is written should be denormalized. An accounting ledger where "
                    "correctness matters more than read speed should be normalized. In practice, production "
                    "systems are a hybrid — normalized core tables with denormalized materialized views or "
                    "cache layers for hot read paths. In interviews, start normalized and say: 'For the feed "
                    "query, I would denormalize by pre-computing the feed into a separate table, trading write "
                    "complexity for O(1) reads.' This shows you understand both sides."
                ),
            },
            {
                "name": "Indexing Strategy Basics",
                "explanation": (
                    "Without an index, every query does a sequential scan — reading every row in the table. "
                    "On a table with 10 million rows, that is ~10 seconds. A B-tree index reduces this to "
                    "~3-4 disk seeks, or ~10-40ms. The index is a sorted data structure (B-tree in PostgreSQL "
                    "and MySQL) that maps column values to row locations. You pay for this on writes: every "
                    "INSERT, UPDATE, and DELETE must also update every index on that table.\n\n"
                    "Which columns to index: (1) primary keys (automatically indexed), (2) foreign keys used "
                    "in JOINs (PostgreSQL does NOT auto-index FKs — a common performance trap), (3) columns "
                    "in WHERE clauses on frequent queries, (4) columns in ORDER BY clauses (the index is "
                    "pre-sorted, so ORDER BY becomes free). Which columns NOT to index: low-cardinality columns "
                    "(a boolean is_active column has only 2 values — the index does not help), columns on "
                    "write-heavy tables with few reads, and tables with fewer than ~10K rows (sequential scan "
                    "is fast enough).\n\n"
                    "Composite indexes on (col_a, col_b) support queries filtering on (a) or (a, b) but NOT "
                    "(b) alone — the leftmost prefix rule. Column order matters: put the column with higher "
                    "selectivity (more distinct values) or the one used in equality conditions first, followed "
                    "by range conditions. For example, on a query WHERE user_id = 123 AND created_at > '2024-01-01', "
                    "index on (user_id, created_at) — user_id is the equality condition and should come first.\n\n"
                    "In interviews, when designing a schema, always call out your index strategy: 'I would add "
                    "a composite index on (user_id, created_at DESC) for the feed query, and a unique index on "
                    "email for the users table.' This shows you think about query performance, not just "
                    "correctness. If the interviewer asks about a slow query, your first move is EXPLAIN ANALYZE "
                    "to check for sequential scans."
                ),
            },
            {
                "name": "Foreign Keys vs Embedding (SQL vs NoSQL Modeling)",
                "explanation": (
                    "In relational databases, relationships are modeled with foreign keys. An order has a "
                    "user_id that references users(id). This is a pointer — to get the user's name for an "
                    "order, you JOIN orders and users. Benefits: no data duplication, referential integrity "
                    "enforced by the database (you cannot create an order for a non-existent user), and any "
                    "query pattern is possible with JOINs.\n\n"
                    "In document databases, the equivalent choice is embedding vs referencing. Embedding: store "
                    "the related data inside the parent document. An order document contains { user: { name: 'Alice', "
                    "email: 'alice@...' }, items: [...] }. Reads are a single document fetch — extremely fast. "
                    "But if Alice changes her email, you must update every order document that embedded her info. "
                    "Referencing: store just the user_id in the order document and do a separate lookup. This "
                    "avoids duplication but requires two queries (no JOINs in most document DBs).\n\n"
                    "The decision rule: embed when the data is read together, rarely changes independently, "
                    "and has a bounded size. A blog post with comments (if comments are bounded and always "
                    "displayed with the post) is a good embedding candidate. Reference when the related entity "
                    "has its own lifecycle, changes independently, or is shared across many parents. A user "
                    "who appears in orders, reviews, and messages should be referenced, not embedded in all "
                    "three.\n\n"
                    "MongoDB's 16MB document size limit is a practical constraint — if a document can grow "
                    "unboundedly (a user's order history), you must reference. DynamoDB's item limit is 400KB. "
                    "In interviews, if you choose a document database, always explain your embedding vs "
                    "referencing decision and justify it with the access pattern."
                ),
            },
            {
                "name": "ACID vs BASE",
                "explanation": (
                    "ACID (Atomicity, Consistency, Isolation, Durability) is the guarantee provided by "
                    "relational databases. Atomicity: a transaction is all-or-nothing — if any step fails, "
                    "everything rolls back. Consistency: transactions move the database from one valid state "
                    "to another (constraints are enforced). Isolation: concurrent transactions do not see each "
                    "other's intermediate states (implemented via locking or MVCC). Durability: once committed, "
                    "data survives crashes (written to disk/WAL). PostgreSQL provides full ACID — this is why "
                    "it is the default for financial systems, e-commerce, and any system where correctness is "
                    "paramount.\n\n"
                    "BASE (Basically Available, Soft state, Eventually consistent) is the philosophy of most "
                    "distributed NoSQL systems. Basically Available: the system always responds, even if some "
                    "nodes are down (possibly with stale data). Soft state: data may change over time without "
                    "input (as replicas converge). Eventually consistent: given enough time without new writes, "
                    "all replicas will converge to the same value. DynamoDB, Cassandra, and Couchbase default "
                    "to BASE semantics. DynamoDB offers optional strongly consistent reads at the cost of "
                    "higher latency and lower availability.\n\n"
                    "The decision framework: ACID when correctness trumps availability — bank account transfers "
                    "(money cannot appear or disappear), inventory decrements (cannot oversell), user "
                    "registration (cannot create duplicate accounts). BASE when availability and partition "
                    "tolerance trump strict consistency — social media feeds (seeing a post 2 seconds late is "
                    "fine), analytics counters (approximate counts are acceptable), shopping carts (merge "
                    "conflicts can be resolved). Many systems use both: ACID for the payment service "
                    "(PostgreSQL) and BASE for the recommendation engine (Cassandra). In interviews, say: "
                    "'The order service needs ACID transactions, so I use PostgreSQL. The activity feed "
                    "tolerates eventual consistency, so I use DynamoDB for its write throughput.'"
                ),
            },
            {
                "name": "Read-Heavy vs Write-Heavy Optimization and PostgreSQL as Default",
                "explanation": (
                    "Read-heavy systems (100:1 read/write ratio — social feeds, product catalogs, content "
                    "platforms): optimize with read replicas (PostgreSQL streaming replication can support 5-10 "
                    "replicas, each handling read traffic), caching layers (Redis cache-aside reduces DB load "
                    "by 90%+), denormalized views (materialized views in PostgreSQL auto-refresh on a schedule), "
                    "CDN caching for content that can tolerate staleness, and aggressive indexing (the write "
                    "penalty of indexes is negligible when writes are rare). The read path: CDN -> cache -> "
                    "read replica -> primary DB (only on cache miss).\n\n"
                    "Write-heavy systems (1:100 or higher — IoT telemetry, logging, metrics, financial "
                    "transactions): optimize with write-optimized storage engines (LSM-tree based databases "
                    "like Cassandra, RocksDB batch writes in memory and flush to disk periodically — much "
                    "faster than B-tree for sequential writes), append-only patterns (event sourcing, WAL-style "
                    "writes), batching (buffer writes in memory and flush periodically), partitioning/sharding "
                    "(spread writes across multiple nodes), and minimal indexing (each index adds a write). "
                    "The write path: load balancer -> partition router -> shard (append to WAL -> memtable -> "
                    "periodic flush to SSTables).\n\n"
                    "PostgreSQL as the default: in 80% of system design interviews, PostgreSQL is the right "
                    "starting answer. It supports relational data with ACID, JSONB for semi-structured data "
                    "(reducing the need for MongoDB), full-text search (reducing the need for Elasticsearch "
                    "for simple cases), pub/sub via LISTEN/NOTIFY, and scales to 10K+ TPS on a single "
                    "machine. Deviate from PostgreSQL when: you need >50K writes/sec sustained (use Cassandra "
                    "or DynamoDB), your data is naturally a graph with multi-hop traversals (use Neo4j), you "
                    "need sub-millisecond key-value lookups at extreme scale (use Redis or DynamoDB), or you "
                    "need a globally distributed database with automatic sharding (use CockroachDB or Spanner). "
                    "In interviews, start with PostgreSQL and justify any deviation: 'I would use PostgreSQL "
                    "for the user and order tables. For the real-time analytics stream, I would use Cassandra "
                    "because we need 500K writes/sec across distributed nodes.'"
                ),
            },
        ],
        "real_world_examples": [
            "Instagram uses PostgreSQL sharded by user_id for core data (users, photos, likes, comments). They chose PostgreSQL over NoSQL because they need transactions for like counts and ACID guarantees for user data. At their scale (~2B users), they shard across thousands of PostgreSQL instances using Vitess-like routing.",
            "Netflix uses Cassandra for its viewing history and personalization data — write-heavy (hundreds of millions of plays/day), partition key is user_id, clustering key is timestamp. They chose Cassandra over PostgreSQL because they need massive write throughput across multiple regions with tunable consistency.",
            "Airbnb uses a denormalized search index (Elasticsearch) alongside a normalized PostgreSQL database. Listings are stored normalized in PostgreSQL (source of truth), then denormalized and indexed in Elasticsearch for search queries that need full-text search, geo-filtering, and faceted search across 50+ fields.",
            "Twitter uses a hybrid approach: PostgreSQL for user accounts and authentication (ACID), Redis for timeline caching (fan-out on write pushes tweet IDs into per-user Redis lists), and Manhattan (their custom KV store) for tweet storage. The data model choice is driven by access pattern: account data needs transactions, timelines need fast reads, tweet storage needs massive throughput.",
            "Uber uses Google's Spanner (NewSQL / globally distributed relational) for their core trip database because they need ACID transactions across multiple regions. A trip starts in San Francisco but the driver's payment may be processed in a different data center — Spanner's global consistency ensures the trip record is consistent everywhere.",
        ],
        "common_interview_questions": [
            "Which database would you use for a chat application? — PostgreSQL for user accounts and group membership (relational, ACID). Redis or DynamoDB for message storage (write-heavy, partition by conversation_id, sort by timestamp). Consider Cassandra if message volume exceeds what a single PostgreSQL instance handles. Do NOT use a graph database unless the question specifically involves complex relationship traversals.",
            "How would you model a social media feed? — Users table (normalized, PostgreSQL). Follows table (user_id, followed_id, created_at — indexed on both columns for 'who do I follow' and 'who follows me' queries). Tweets table (tweet_id, user_id, text, created_at). Feed: either fan-out on write (pre-compute feeds into a Redis list per user) or fan-out on read (query tweets from followed users at read time with a composite index on (user_id, created_at DESC)).",
            "When would you denormalize? — When a specific query path is read 100x+ more than it is written, and the JOIN version is too slow. Examples: embed seller_name on product rows for listing pages, pre-compute follower_count on user rows instead of COUNT(*) every time, store the most recent 3 comments directly on a post document.",
            "Explain the difference between ACID and BASE with a concrete example. — Bank transfer: ACID ensures that debiting account A and crediting account B happen atomically — if the credit fails, the debit rolls back. Social media like counter: BASE is acceptable because seeing 4,999 likes instead of 5,000 for a few seconds does not cause financial loss. The like will converge to 5,000 once replicas sync.",
            "Your query is slow. Walk me through your debugging process. — EXPLAIN ANALYZE the query to check for sequential scans. If a seq scan exists on a large table, add an index on the WHERE/JOIN columns. Check if the index exists but is not being used (wrong column order, type mismatch, or optimizer choosing seq scan for high-cardinality result). Check for N+1 queries in the application layer. If the table is >100M rows, consider partitioning or read replicas.",
        ],
        "key_trade_offs": [
            "Normalization (no data duplication, enforced consistency, flexible queries) vs denormalization (fast reads, no JOINs, but data duplication and update complexity) — normalize by default, denormalize specific hot read paths. A hybrid approach is almost always the right answer in interviews.",
            "SQL/relational (ACID transactions, JOINs, ad-hoc queries, mature tooling) vs NoSQL/document (flexible schema, horizontal scaling, high write throughput) — start with PostgreSQL and deviate only when you hit a specific limitation: schema rigidity, write volume beyond 10K TPS, or need for automatic global distribution.",
            "More indexes (faster reads) vs fewer indexes (faster writes, less storage) — index columns that appear in WHERE, JOIN, and ORDER BY clauses of frequent queries. Do not index low-cardinality columns, write-heavy tables with rare reads, or tiny tables. A good rule: 3-5 indexes per table is typical; more than 10 is a red flag.",
            "Embedding (single read, no JOINs, fast) vs referencing (no duplication, independent lifecycles, flexible) in document databases — embed bounded, co-accessed, rarely-updated subdocuments; reference entities with independent lifecycles or unbounded growth.",
            "PostgreSQL (safe default, rich features, ACID) vs specialized databases (Cassandra for write-heavy, Redis for cache/KV, Neo4j for graphs, Elasticsearch for search) — use PostgreSQL as the core and add specialized databases only for access patterns PostgreSQL cannot serve efficiently. Every additional database is operational complexity.",
        ],
        "common_mistakes": [
            "Saying 'I would use MongoDB' without justifying why a document model fits the problem. MongoDB is a valid choice for hierarchical, flexible-schema data — but for a system with users, orders, and payments that need transactions and JOINs, PostgreSQL is almost always better. Candidates who default to NoSQL without reasoning lose credibility.",
            "Forgetting to index foreign keys in PostgreSQL. PostgreSQL auto-indexes primary keys but NOT foreign keys. A JOIN on orders.user_id = users.id without an index on orders.user_id causes a sequential scan on the orders table. This is one of the most common performance bugs in production PostgreSQL applications.",
            "Over-normalizing to the point of unusable query performance. A product page that requires 6 JOINs to render (products JOIN sellers JOIN categories JOIN ratings JOIN shipping JOIN promotions) will be slow. Denormalize the hot path — store seller_name and avg_rating directly on the product row.",
            "Confusing ACID consistency with CAP consistency. ACID consistency means database constraints (foreign keys, unique constraints, check constraints) are enforced after every transaction. CAP consistency means every read returns the most recent write across distributed nodes. They are different properties that apply at different levels.",
            "Choosing a database based on hype rather than access patterns. Using Cassandra for a 10K-row lookup table, or Redis as a primary database, or a graph database for a simple friends list that a SQL JOIN handles fine. Always start from 'what are my query patterns and what volume do I expect' and let that drive the database choice.",
        ],
        "interview_tips": [
            "Default to PostgreSQL and explicitly justify any other choice. Say: 'I would start with PostgreSQL for users, orders, and payments because we need ACID transactions. For the activity feed, which is write-heavy at 100K events/sec, I would use Cassandra partitioned by user_id.' This shows you have a default and know when to deviate.",
            "Always pair a table schema with its indexes. When you write 'tweets: id, user_id, text, created_at,' immediately follow with: 'Indexes: primary key on id, composite index on (user_id, created_at DESC) for the feed query, index on created_at for the trending query.' Schema without indexes is an incomplete design.",
            "When asked 'SQL or NoSQL?', reframe it as an access pattern question: 'It depends on the access pattern. If we need JOINs across entities and transactions, relational. If we need flexible schemas and horizontal write scaling, document. If we need sub-ms key lookups, KV store. Let me look at our requirements.' This shows maturity over dogmatism.",
            "Use the phrase 'denormalize the read path' when justifying data duplication. Say: 'The product listing page is read 10,000x per second but products are updated once per day. I would denormalize seller_name and avg_rating onto the product row to serve the listing with a single indexed query instead of 3 JOINs. The write path updates the denormalized fields asynchronously via a Kafka consumer.' This shows you understand the trade-off and have a mechanism for keeping data consistent.",
        ],
        "related_concepts": ["caching", "sharding", "database_indexing", "cap_theorem", "api_design"],
    },
    "caching": {
    "title": "Caching",
    "introduction": (
        "Every millisecond of latency costs money. Amazon found that every 100ms of added latency cost them 1% in sales. "
        "Google discovered that an extra 500ms in search page generation dropped traffic by 20%. Caching is the single most "
        "impactful technique for reducing latency in distributed systems, and understanding it deeply is non-negotiable for "
        "system design interviews. Here is the memory hierarchy that drives every caching decision: CPU L1 cache access takes "
        "about 1 nanosecond, RAM access about 100 nanoseconds, SSD random read about 100 microseconds, a network round-trip "
        "within a data center about 500 microseconds to 1 millisecond, and a spinning disk seek about 10 milliseconds. That "
        "means RAM is roughly 1,000x faster than SSD and 100,000x faster than disk. Caching exploits this hierarchy by keeping "
        "frequently accessed data in faster storage tiers. But caching is not just 'put stuff in Redis.' You need to reason "
        "about where to cache (client, CDN, application, database), how to populate the cache (lazy vs eager), how to keep "
        "the cache consistent with the source of truth (invalidation strategies), what to evict when the cache is full "
        "(eviction policies), and how to handle failure modes like cache stampedes. In interviews, candidates who can articulate "
        "these trade-offs precisely — not just say 'add a cache' — stand out immediately. You will learn the four canonical "
        "cache locations and when each is appropriate, the major read/write caching strategies and their consistency guarantees, "
        "eviction policies and when each makes sense, distributed caching architectures with Redis Cluster and Memcached, "
        "and the subtle failure modes like thundering herds that separate senior engineers from junior ones."
    ),
    "key_concepts": [
        {
            "name": "Cache Locations (The Four Layers)",
            "explanation": (
                "There are four distinct locations where caching can occur, and a well-designed system often uses several "
                "simultaneously. First: client-side or browser caching. The browser stores responses locally using HTTP "
                "cache headers — Cache-Control, ETag, Last-Modified. When you set 'Cache-Control: max-age=86400', the "
                "browser will not even make a network request for 24 hours; it serves the resource from local disk or "
                "memory. This eliminates network latency entirely for repeat visits. ETags enable conditional requests: "
                "the browser sends 'If-None-Match: <etag>' and the server returns 304 Not Modified with no body if the "
                "content hasn't changed. Client caching is the cheapest cache layer because it offloads work completely "
                "from your infrastructure, but you have limited control — users can clear caches, and invalidation is slow "
                "(you must wait for TTLs to expire or use versioned URLs like 'app.v2.3.js'). "
                "Second: CDN and edge caching. Services like CloudFront, Akamai, or Cloudflare maintain servers in 200+ "
                "points of presence worldwide. Static assets (images, CSS, JS) are the obvious fit, but CDNs increasingly "
                "cache dynamic API responses too. A CDN hit means your origin server does zero work, and the user gets a "
                "response from a server that might be 5ms away instead of 150ms. The trade-off: CDN cache invalidation has "
                "propagation delay (typically 1-15 seconds globally), and you pay per request plus bandwidth. "
                "Third: application-level caching, typically using Redis or Memcached as an in-memory data store sitting "
                "between your application servers and database. This is the most common layer discussed in interviews. Redis "
                "gives you sub-millisecond reads (typically 0.1-0.5ms) compared to 5-50ms for a database query. It supports "
                "rich data structures (strings, hashes, sorted sets, HyperLogLog) and can handle 100,000+ operations per "
                "second on a single node. Memcached is simpler — pure key-value with no persistence — but is excellent for "
                "simple caching use cases and scales horizontally via client-side consistent hashing. "
                "Fourth: database query caching. MySQL has a built-in query cache (deprecated in 8.0 for good reason — it "
                "is invalidated on any write to the table), but more useful are materialized views in PostgreSQL or "
                "application-managed result caching. In interviews, mention all four layers and explain why you would choose "
                "specific layers for the problem at hand. A read-heavy social media feed might use CDN caching for media, "
                "Redis for the computed feed, and database-level indexes — but not database query caching because writes "
                "are too frequent."
            ),
        },
        {
            "name": "Caching Strategies (Read and Write Patterns)",
            "explanation": (
                "Cache-aside (also called lazy loading) is the most common pattern. The application checks the cache first. "
                "On a cache hit, it returns the cached value. On a cache miss, it reads from the database, writes the result "
                "into the cache, and then returns it. The application is responsible for all cache management. Advantages: "
                "only requested data is cached (no wasted memory), and the system is resilient to cache failures (it falls "
                "back to the database). Disadvantages: the first request for any piece of data always has a cache miss, "
                "causing higher latency; and the cache can become stale because there is no automatic update when the "
                "database changes. Cache-aside works best for read-heavy workloads where some staleness is acceptable. "
                "Write-through caching writes data to both the cache and the database synchronously on every write. The "
                "application writes to the cache, and the cache writes to the database (or vice versa — the key point is "
                "both are updated in the same operation). Advantage: the cache is always consistent with the database, so "
                "reads never see stale data. Disadvantage: write latency increases because every write must go to two places, "
                "and the cache fills with data that may never be read. Write-through is ideal when you cannot tolerate stale "
                "reads — financial data, user session state, inventory counts. "
                "Write-behind (write-back) caching writes data to the cache immediately and then asynchronously flushes "
                "changes to the database in batches. This dramatically improves write performance because the application "
                "only waits for the cache write (sub-millisecond) instead of the database write (5-50ms). The batching also "
                "reduces database load — if the same key is updated 10 times in a second, only the final value is written "
                "to the database. The critical risk: if the cache node fails before flushing, data is lost. This is why "
                "Redis with AOF persistence or replication is often used. Write-behind works well for high-throughput write "
                "workloads like analytics event counters, leaderboard scores, or rate limit counters. "
                "Refresh-ahead proactively reloads cache entries before they expire, based on predicted access patterns. "
                "If a cache entry has a 60-second TTL, and the system predicts (based on recent access frequency) that it "
                "will be requested again, it automatically refreshes the entry at, say, 50 seconds — before expiration. "
                "The user never experiences a cache miss. This requires good access pattern prediction and adds complexity, "
                "but it eliminates the latency spike that cache-aside causes on expiration. It is used in high-traffic "
                "systems where even occasional cache misses cause noticeable user impact."
            ),
        },
        {
            "name": "Cache Invalidation and Eviction",
            "explanation": (
                "Phil Karlton famously said there are only two hard problems in computer science: cache invalidation and "
                "naming things. Cache invalidation is the process of removing or updating stale data in the cache. TTL-based "
                "invalidation is the simplest approach: every cache entry gets a time-to-live, and the cache automatically "
                "deletes it after that duration. Short TTLs (5-30 seconds) keep data fresh but increase cache miss rate and "
                "database load. Long TTLs (minutes to hours) reduce load but serve staler data. The right TTL depends on "
                "how frequently the underlying data changes and how much staleness your application tolerates. "
                "Event-driven invalidation is more precise: when the source data changes, an event (database trigger, "
                "application event, message queue notification) explicitly invalidates or updates the cache entry. This "
                "gives you strong consistency without sacrificing cache hit rates. The complexity cost is maintaining the "
                "event pipeline reliably. If the invalidation message is lost or delayed, the cache serves stale data. "
                "Versioned keys sidestep invalidation entirely. Instead of caching under 'user:123:profile', you cache "
                "under 'user:123:profile:v7'. When the profile changes, increment the version to v8. Old entries simply "
                "expire via TTL. This is particularly useful for immutable data or when you need atomic switches between "
                "old and new data. "
                "Eviction policies determine what to remove when the cache reaches its memory limit. LRU (Least Recently "
                "Used) evicts the entry that has not been accessed for the longest time. It is the default in Redis and "
                "works well for most workloads because it approximates the principle that recently accessed data is likely "
                "to be accessed again. LFU (Least Frequently Used) evicts the entry with the fewest accesses, which is "
                "better when some data is consistently popular (a trending tweet, a popular product). Redis 4.0+ supports "
                "an approximated LFU. FIFO (First In, First Out) evicts the oldest entry regardless of access pattern — "
                "simple but usually suboptimal. Random eviction is surprisingly effective for uniform access patterns and "
                "is nearly as good as LRU for many real workloads while being much simpler to implement. In interviews, "
                "always state which eviction policy you would use and why — it demonstrates understanding of access patterns."
            ),
        },
        {
            "name": "Cache Stampede and Thundering Herd",
            "explanation": (
                "A cache stampede (also called thundering herd) occurs when a popular cache entry expires and many concurrent "
                "requests simultaneously find a cache miss, all hitting the database at once to regenerate the value. If a "
                "celebrity's profile is cached with a 60-second TTL and receives 10,000 requests per second, when that entry "
                "expires, 10,000 requests simultaneously query the database. This can overload the database and cause "
                "cascading failures. "
                "Solution one: cache locking (also called request coalescing). When a cache miss occurs, the first request "
                "acquires a distributed lock (e.g., using Redis SETNX), fetches from the database, and populates the cache. "
                "All other concurrent requests wait for the lock to be released or serve a slightly stale value. This "
                "reduces database load from N concurrent requests to exactly 1. The risk is that if the lock holder crashes, "
                "other requests may be blocked; mitigate this with lock TTLs. "
                "Solution two: probabilistic early expiration (also called early recomputation). Instead of all entries "
                "expiring at exactly the TTL, each request checks if it should proactively refresh the cache before expiration. "
                "The probability of refreshing increases as the TTL approaches — the formula is typically: "
                "should_refresh = (current_time - (expiry_time - TTL * beta * ln(random()))) > 0, where beta controls the "
                "early refresh window. This statistically ensures that exactly one request refreshes the cache before the "
                "actual expiration, and it does so without any distributed coordination or locking. "
                "Solution three: never expire. Set no TTL and instead use event-driven invalidation to update the cache "
                "whenever the underlying data changes. This eliminates stampedes entirely but requires reliable change "
                "detection. In interviews, always mention the stampede problem when discussing TTL-based caching — it "
                "shows you think about failure modes, not just the happy path. A strong answer combines locking for "
                "correctness with probabilistic early expiration for performance."
            ),
        },
        {
            "name": "Distributed Caching and Multi-Region Consistency",
            "explanation": (
                "A single Redis node can handle about 100,000 operations per second, but large-scale systems need more "
                "throughput and more memory than one node provides. Redis Cluster partitions data across multiple nodes "
                "using hash slots — there are 16,384 hash slots, and each node owns a range of slots. The key is hashed "
                "using CRC16, and the result modulo 16,384 determines the slot. Clients are 'cluster-aware' — they know "
                "which node owns which slots and route requests directly, avoiding extra hops. When you add a node, Redis "
                "Cluster migrates a subset of hash slots to the new node. This is online — the cluster continues serving "
                "requests during migration. Redis Cluster also provides replication: each primary node has one or more "
                "replicas that take over automatically on failure. "
                "Memcached takes a different approach: it provides no built-in clustering. Instead, clients implement "
                "consistent hashing to distribute keys across multiple Memcached servers. This makes Memcached simpler "
                "to operate but means the client library is responsible for distribution, failover, and rebalancing. "
                "Facebook famously ran the largest Memcached deployment in the world — thousands of servers caching "
                "billions of items — and published a detailed paper on their architecture. "
                "Multi-region caching adds another dimension of complexity. If you have Redis clusters in US-East and "
                "EU-West, a user in Europe writes data that updates the US-East database and US-East cache, but the "
                "EU-West cache still has the old value. Solutions include: cross-region cache invalidation via a message "
                "bus (write to the database, publish an invalidation event, all regions consume it and invalidate their "
                "local cache), global Redis with CRDTs (Conflict-free Replicated Data Types, available in Redis Enterprise), "
                "or simply accepting staleness with short TTLs and designing the application to tolerate it. "
                "In interviews, specify whether your cache is a single node, a cluster, or multi-region. Each has different "
                "latency, consistency, and operational characteristics. Saying 'add Redis' without specifying the topology "
                "is incomplete."
            ),
        },
    ],
    "real_world_examples": [
        "Facebook/Meta TAO: a distributed, highly-available cache for the social graph, sitting in front of MySQL. TAO handles billions of reads per second, using a write-through cache with cross-region invalidation via a leader-follower model. Each region has a full cache; writes go to the leader region, which invalidates follower caches asynchronously.",
        "Netflix EVCache: a distributed caching solution built on top of Memcached, handling 30+ million requests per second across thousands of nodes. Netflix uses it for everything from subscriber data to video metadata. EVCache adds cross-region replication, automatic warm-up of new nodes, and circuit breakers around cache failures.",
        "Twitter Timeline Cache: Twitter caches each user's home timeline (the list of tweet IDs) in Redis. When a user opens Twitter, the timeline is served from cache in under 5ms. The fanout-on-write model pushes new tweets into follower timelines in Redis, effectively using write-behind caching for timeline updates.",
        "Cloudflare CDN Edge Cache: Cloudflare caches HTTP responses at 310+ points of presence globally. Their Tiered Cache architecture routes cache misses to a regional 'upper-tier' cache before going to the origin, reducing origin load by up to 90%. They use custom TTL logic and support cache tags for granular invalidation.",
        "Amazon DynamoDB DAX: DynamoDB Accelerator is a write-through, in-memory cache purpose-built for DynamoDB. It provides microsecond read latency (vs single-digit millisecond for standard DynamoDB reads) and is fully managed. DAX uses a cluster architecture with a primary node for writes and read replicas.",
    ],
    "common_interview_questions": [
        "How would you design a caching layer for a social media feed? — Hint: cache-aside with Redis for the computed feed; fanout-on-write for celebrity posts; TTL of 30-60 seconds; handle cache stampedes on popular feeds with locking.",
        "What happens when your cache goes down? — Hint: distinguish between cache-aside (degrades to database-only, latency increases) and write-through (may lose writes if cache is in the write path). Discuss circuit breakers, fallback strategies, and cache warming.",
        "How do you keep cache consistent with the database? — Hint: discuss the spectrum from eventual consistency (TTL-based) to strong consistency (write-through + synchronous invalidation). Mention the double-write problem: if you update the database and then update the cache, a failure between the two leaves them inconsistent.",
        "When would you choose Memcached over Redis? — Hint: Memcached is simpler, multi-threaded (better CPU utilization on a single node), and uses memory more efficiently for simple key-value pairs. Redis wins when you need data structures (sorted sets, lists), persistence, pub/sub, or Lua scripting.",
        "How would you handle caching for a multi-region application? — Hint: local Redis cluster per region for low latency reads; cross-region invalidation via Kafka or similar message bus; accept eventual consistency (typically < 1 second stale); for critical data, read-from-leader pattern.",
    ],
    "key_trade_offs": [
        "Consistency vs Latency — write-through cache gives strong consistency but adds write latency (every write hits both cache and DB); cache-aside with TTL gives lower write latency but allows stale reads up to the TTL duration.",
        "Memory cost vs Hit rate — caching more data improves hit rates but costs more RAM ($3-6/GB/month for Redis Cloud). Profile your access patterns: often 10% of keys serve 90% of traffic (Zipf distribution), so a small cache can achieve a high hit rate.",
        "Short TTL vs Long TTL — short TTLs (seconds) keep data fresh but increase database load and cache miss rate; long TTLs (minutes/hours) reduce load but risk serving outdated data. Choose based on how stale your application can tolerate.",
        "Single cache node vs Distributed cluster — a single Redis node is simpler (no partition logic, no cross-node coordination) and can handle 100K ops/sec. A cluster provides higher throughput and more memory but adds complexity: hash slots, cluster-aware clients, rebalancing during scaling.",
        "Cache-aside vs Read-through — cache-aside keeps cache logic in the application (flexible but duplicated across services); read-through abstracts it into the cache layer (cleaner application code but tighter coupling to the cache provider).",
    ],
    "common_mistakes": [
        "Saying 'add a cache' without specifying what is cached, where the cache sits, what strategy is used, or how invalidation works. Interviewers want to see you reason about these decisions, not just name-drop Redis.",
        "Ignoring the cold start problem. When a new cache node starts or after a cache flush, the cache is empty and all requests hit the database. Discuss cache warming: pre-loading hot keys from the database or replaying recent access logs.",
        "Forgetting about cache consistency during writes. If you update the database and then delete the cache key, a concurrent read between those two operations will re-populate the cache with the old value. The standard solution is to delete the cache key (not update it) and use a short TTL as a safety net.",
        "Not considering what happens when the cache is unavailable. If your system treats cache as required infrastructure (no fallback), a Redis outage becomes a full system outage. Design for graceful degradation: serve from the database with higher latency rather than returning errors.",
        "Caching data that changes frequently or is rarely re-read. Caching a value that changes every second with a 60-second TTL means 59 out of 60 seconds serve stale data. Caching data that is only read once wastes memory. Cache data that is read-heavy and tolerates some staleness.",
    ],
    "interview_tips": [
        "Start with the access pattern: 'This is read-heavy at 10:1 read-to-write ratio, so caching will have high impact. I would use cache-aside with Redis because...' — always justify cache decisions with workload characteristics.",
        "Quantify the improvement: 'Without caching, each request queries the database at ~20ms. With a Redis cache (0.5ms latency) and a 95% hit rate, average latency drops to 0.5*0.95 + 20*0.05 = 1.475ms — a 13x improvement.'",
        "Address failure modes proactively: 'For cache stampede protection, I would implement request coalescing with a distributed lock using Redis SETNX with a 5-second TTL, so only one request regenerates the cache entry.'",
        "Name the invalidation strategy explicitly: 'I would use event-driven invalidation via a CDC (Change Data Capture) stream from the database, so cache entries are invalidated within seconds of the underlying data changing, without relying on TTL expiration.'",
    ],
    "related_concepts": ["consistent_hashing", "sharding", "load_balancing", "cdn_design"],
},
"sharding": {
    "title": "Sharding",
    "introduction": (
        "A single database server has hard physical limits. A powerful PostgreSQL instance might handle 10,000-50,000 "
        "queries per second, store a few terabytes of data, and support a few hundred concurrent connections before "
        "performance degrades. When your application grows beyond these limits — whether due to data volume, query "
        "throughput, or connection count — vertical scaling (bigger hardware) hits a ceiling and becomes prohibitively "
        "expensive. Sharding is horizontal partitioning of data across multiple database instances (shards), where "
        "each shard holds a subset of the data and handles a subset of the traffic. It is one of the most important "
        "and most complex techniques in distributed systems, because it fundamentally changes how you store, query, "
        "and reason about data. Instagram sharded their PostgreSQL database when they had roughly 25 million users "
        "and were hitting connection and I/O limits on a single instance. Slack shards their message database by "
        "workspace, allowing each shard to handle the message volume of the workspaces assigned to it. Understanding "
        "sharding deeply means understanding shard key selection (the most critical decision), distribution strategies "
        "(range, hash, directory), the operational complexity of resharding, and the query limitations that come with "
        "splitting your data across machines. In interviews, sharding questions test whether you can make principled "
        "trade-offs between query flexibility, data distribution, and operational complexity. The goal here is to "
        "give you the depth to reason through these trade-offs confidently, covering why sharding is necessary, "
        "how to choose a shard key, the three main distribution strategies, how to handle the pain points "
        "(cross-shard queries, hot spots, resharding), and real production examples of sharding done well and poorly."
    ),
    "key_concepts": [
        {
            "name": "Partitioning vs Sharding and Why Shard",
            "explanation": (
                "Partitioning and sharding are related but distinct. Partitioning is splitting a table's data into "
                "smaller pieces based on a column value — PostgreSQL supports range partitioning (e.g., orders by month) "
                "and list partitioning (e.g., orders by region) natively. All partitions live on the same database server. "
                "Partitioning improves query performance (the optimizer can skip irrelevant partitions) and simplifies "
                "data lifecycle management (drop an old month's partition instead of deleting millions of rows), but it "
                "does not solve throughput or capacity limits because everything is still on one machine. "
                "Sharding (sometimes called horizontal scaling or horizontal partitioning across nodes) distributes "
                "partitions across multiple independent database servers. Each shard is a fully functional database "
                "instance — it has its own CPU, memory, disk, and connection pool. This means total throughput scales "
                "linearly: 4 shards give you roughly 4x the query capacity and 4x the storage. "
                "You need sharding when: (1) your data exceeds what one server can store — a single PostgreSQL instance "
                "practically tops out at a few terabytes before backup and recovery times become unmanageable; (2) your "
                "read/write throughput exceeds one server's capacity — even with read replicas for reads, writes are "
                "still bottlenecked on the primary; (3) your connection count exceeds server limits — each application "
                "server needs database connections, and at hundreds of app servers, you exhaust the database's connection "
                "pool. Sharding addresses all three by distributing load across independent machines. "
                "The cost of sharding is significant: cross-shard queries become expensive (distributed joins), "
                "transactions across shards require two-phase commit or are avoided entirely, application complexity "
                "increases (routing logic, shard-aware queries), and operational overhead grows (managing N databases "
                "instead of 1). This is why the standard advice is: do not shard until you must. Exhaust vertical "
                "scaling, read replicas, caching, and query optimization first."
            ),
        },
        {
            "name": "Shard Key Selection",
            "explanation": (
                "The shard key (also called partition key or distribution key) is the column whose value determines "
                "which shard a row lives on. This is the single most important decision in sharding because it is "
                "extremely difficult to change later — it requires migrating all data. A good shard key has four "
                "properties. "
                "First, high cardinality: the key must have many distinct values so data can be distributed across "
                "many shards. A boolean column (true/false) is terrible — you can only have 2 shards. A user_id "
                "(millions of distinct values) is excellent. "
                "Second, uniform distribution: values should spread data evenly across shards. If you shard by "
                "country_code and 60% of your users are in the US, the US shard holds 60% of the data — a severe "
                "imbalance. User_id (assuming sequential or random IDs) distributes evenly. "
                "Third, query alignment: the shard key should be present in your most frequent queries so the "
                "routing layer can direct each query to a single shard. If 90% of queries filter by user_id, "
                "shard by user_id — each query hits exactly one shard. If you shard by user_id but frequently "
                "query by email, every email lookup must scatter to all shards (a full scatter-gather), which is "
                "N times slower where N is the number of shards. "
                "Fourth, avoid hot spots: even with high cardinality and uniform distribution, some keys may receive "
                "disproportionate traffic. A celebrity user_id on a social platform might get 1000x more reads than "
                "average, making that shard a hot spot. Solutions include splitting hot keys across sub-shards or "
                "adding caching in front of the hot shard. "
                "Practical example: for a messaging app, shard by conversation_id (not user_id). Most queries are "
                "'get messages in this conversation', which hits one shard. If you shard by user_id, displaying a "
                "group conversation requires querying the shard of every participant. For an e-commerce platform, "
                "shard by seller_id if queries are seller-centric (inventory management), or by order_id if queries "
                "are order-centric (order tracking). The shard key must match the primary access pattern."
            ),
        },
        {
            "name": "Distribution Strategies (Range, Hash, Directory)",
            "explanation": (
                "Range-based sharding assigns contiguous ranges of the shard key to each shard. For example, "
                "user_ids 1-1,000,000 go to shard 1, 1,000,001-2,000,000 to shard 2, and so on. Alternatively, "
                "you might range-shard by date: January data on shard 1, February on shard 2. The advantage is "
                "that range queries are efficient — 'find all users with IDs between 500,000 and 600,000' hits "
                "exactly one shard. The disadvantage is that new data often clusters at the end of the range "
                "(the newest users, the current month), creating a hot shard that absorbs all writes while older "
                "shards sit idle. Range sharding works well for time-series data where you need time-range queries "
                "and can tolerate uneven write distribution across shards. HBase uses range-based sharding natively. "
                "Hash-based sharding applies a hash function to the shard key and uses the result to determine "
                "the shard: shard_number = hash(key) mod N. This distributes data uniformly regardless of the "
                "key distribution — even if 60% of your users are in the US, hash(user_id) spreads them evenly "
                "across shards. The critical disadvantage: range queries become impossible. 'Find all users with "
                "IDs between 500K and 600K' must scatter to every shard because hash(500000) and hash(500001) "
                "likely map to different shards. The hash function should be deterministic, fast, and produce "
                "uniform output — MurmurHash, xxHash, and CityHash are common choices in production systems. "
                "Avoid cryptographic hashes (SHA-256, MD5) because they are slower than necessary for this purpose. "
                "The other critical problem with hash-based sharding: when you change N (the number of shards), "
                "hash(key) mod N changes for almost every key, requiring massive data migration. This is exactly "
                "the problem that consistent hashing solves. "
                "Directory-based sharding (lookup table) maintains an explicit mapping from shard key values (or "
                "ranges) to shard identifiers. A central service or database stores entries like 'user 12345 -> "
                "shard 7'. This is the most flexible approach — you can move individual users between shards without "
                "changing any hash function, balance shards by reassigning entries, and handle special cases (pin "
                "a VIP customer to a dedicated shard). The cost: every data access requires a lookup to the directory "
                "service first, adding latency and creating a potential single point of failure. The directory itself "
                "must be highly available and fast — typically cached in memory. Slack uses a directory approach to "
                "assign workspaces to database shards."
            ),
        },
        {
            "name": "Resharding and Rebalancing",
            "explanation": (
                "Resharding — changing the number of shards or redistributing data across shards — is one of the most "
                "operationally painful activities in distributed systems. With simple hash-based sharding (hash mod N), "
                "changing N from 4 to 5 remaps roughly 80% of keys to different shards. Even with consistent hashing, "
                "adding a node requires migrating roughly 1/N of the total data. "
                "The standard approach for online resharding is double-write with backfill. Step 1: set up the new shard "
                "topology (new shards running but empty). Step 2: enable double-writing — all new writes go to both the "
                "old and new shard topologies. Step 3: run a background migration job that copies existing data from old "
                "shards to their new locations in the new topology. Step 4: verify data consistency between old and new. "
                "Step 5: switch reads to the new topology. Step 6: stop double-writing and decommission old shards. "
                "This process can take days or weeks for large datasets. "
                "An alternative is the split-and-merge approach: instead of rehashing everything, split an overloaded "
                "shard into two by dividing its key range. This moves only the data from the overloaded shard, not all "
                "shards. MongoDB's auto-sharding uses chunk splitting — when a chunk exceeds a size threshold (default "
                "128 MB), the balancer splits it and migrates the new chunk to a less-loaded shard. "
                "To minimize resharding frequency, over-provision the shard key space from the start. Instead of 4 hash "
                "shards, create 256 virtual shards (hash slots) and map groups of virtual shards to physical nodes. "
                "When you add a physical node, just reassign some virtual shards to it — the mapping changes, not the "
                "hash function. This is exactly the approach Redis Cluster uses with its 16,384 hash slots. "
                "In interviews, always acknowledge that resharding is complex and discuss how your design minimizes its "
                "frequency and impact. Saying 'we can just add more shards later' without addressing the migration "
                "mechanics is a red flag."
            ),
        },
        {
            "name": "Cross-Shard Queries and Distributed Joins",
            "explanation": (
                "Once data is distributed across shards, any query that does not include the shard key must fan out "
                "to all shards — this is the scatter-gather pattern. If you have 100 shards and run 'SELECT * FROM "
                "users WHERE email = ?' and email is not the shard key, the query goes to all 100 shards, each "
                "executes it locally, and the results are merged. The latency is determined by the slowest shard "
                "(tail latency), and the total work is 100x a single-shard query. "
                "Distributed joins are even worse. If users are sharded by user_id and orders are sharded by "
                "order_id, joining users with orders requires pulling data from multiple user shards and multiple "
                "order shards, then combining them in the application layer. This is so expensive that most sharded "
                "systems simply prohibit distributed joins and denormalize the data instead — store the user's name "
                "and email directly in the orders table so you never need to join. "
                "Global secondary indexes help with non-shard-key queries. There are two approaches: local secondary "
                "indexes (each shard maintains an index of its own data — a query by that index must still scatter "
                "to all shards, but each shard can use its local index for efficiency) and global secondary indexes "
                "(a separate sharded index keyed by the secondary attribute, pointing to the primary shard — a query "
                "hits the global index first to find the shard, then queries that shard directly). Global secondary "
                "indexes make reads fast but writes slow (every write must update the primary shard plus the global "
                "index). DynamoDB supports both local and global secondary indexes. "
                "The shared-nothing architecture principle states that each shard operates independently — no shared "
                "disk, no shared memory, no shared state. This maximizes scalability because shards do not contend "
                "for resources, but it means all coordination (distributed transactions, cross-shard queries) must "
                "happen through explicit network communication, which is slow and complex. In interviews, when you "
                "choose a shard key, immediately identify which queries become cross-shard and how you will handle "
                "them — denormalization, global secondary indexes, or accepting scatter-gather overhead."
            ),
        },
        {
            "name": "Practical Example: Sharding a User Table",
            "explanation": (
                "Consider a social platform with 500 million users, 50 TB of user data, and 100,000 queries per "
                "second. A single PostgreSQL instance cannot handle this. You decide to shard. "
                "Option A: shard by user_id using hash-based distribution. Hash(user_id) mod 64 gives you 64 shards, "
                "each holding roughly 8 million users and 800 GB of data, handling roughly 1,500 queries per second. "
                "This is well within a single PostgreSQL instance's capacity. User profile lookups (by user_id) hit "
                "one shard. The user's posts, followers, and settings (all keyed by user_id) can live on the same "
                "shard, enabling local joins. The downside: finding a user by username or email requires a scatter "
                "to all 64 shards unless you build a global secondary index mapping username -> user_id. "
                "Option B: shard by geography (US, EU, APAC). This keeps a user's data close to them physically, "
                "reducing latency. EU users query EU shards in EU data centers. But the distribution is severely "
                "uneven — the US shard might hold 40% of users. You also cannot do cross-region social features "
                "easily: if a US user follows an EU user, displaying the EU user's profile requires a cross-shard "
                "(and cross-region) query. "
                "The recommended approach for most interview scenarios: shard by user_id with hash distribution. "
                "Build a lean global secondary index (in Redis or a separate small database) for username -> user_id "
                "and email -> user_id lookups. Accept that analytics queries ('count all users in France') require "
                "scatter-gather and run them asynchronously against read replicas or a separate analytics pipeline. "
                "Start with a high number of virtual shards (e.g., 1024 hash slots mapped to 16 physical nodes). "
                "When you need to scale, remap hash slots to new nodes — the application sees the same 1024 slots, "
                "only the physical mapping changes. In the interview, walk through this reasoning step by step: "
                "identify the bottleneck, choose the shard key with justification, pick the distribution strategy, "
                "address the secondary access patterns, and explain how you would scale over time."
            ),
        },
    ],
    "real_world_examples": [
        "Instagram PostgreSQL Sharding: Instagram shards user data across thousands of PostgreSQL instances by user_id using hash-based distribution. They pre-shard into several thousand logical shards mapped to fewer physical machines, making it straightforward to add physical capacity by remapping logical shards. Each shard contains all data for its assigned users: photos, likes, follows.",
        "Slack Workspace-Based Sharding: Slack shards MySQL databases by workspace (team). Each workspace's messages, channels, and files live on a single shard. This aligns perfectly with their query pattern (most queries are within a workspace) and provides natural data isolation. They use a directory service to map workspace IDs to database shards.",
        "MongoDB Auto-Sharding: MongoDB shards collections automatically using either range-based or hash-based distribution on a chosen shard key. The mongos router directs queries to the appropriate shard. The balancer automatically migrates chunks between shards to maintain even distribution. MongoDB supports zone-based sharding for data locality requirements.",
        "Vitess (YouTube/PlanetScale): Vitess is a sharding middleware for MySQL, originally built at YouTube. It sits between the application and MySQL, routing queries to the correct shard based on a VIndex (virtual index). Vitess handles resharding online by splitting and merging shards while serving traffic. PlanetScale offers Vitess as a managed service.",
        "CockroachDB Automatic Range Sharding: CockroachDB automatically splits data into 512 MB ranges and distributes them across nodes. Ranges split automatically when they grow too large and merge when they shrink. Rebalancing happens continuously in the background. The application sees a single SQL interface with no manual shard management.",
    ],
    "common_interview_questions": [
        "How would you shard a database for a chat application? — Hint: shard by conversation_id (not user_id). Most queries fetch messages within a conversation, so single-shard queries dominate. For 'list my conversations', maintain a per-user conversation index on the user's shard or in a separate lookup table.",
        "What happens when one shard becomes a hot spot? — Hint: identify why (popular user, viral content, time-based clustering). Solutions: further split the hot shard, add read replicas to the hot shard, cache hot data in Redis, or use application-level routing to distribute hot-key requests.",
        "How do you handle cross-shard transactions? — Hint: avoid them if possible by co-locating related data on the same shard (shard by the same key). When unavoidable, use two-phase commit (2PC) for strong consistency or saga pattern for eventual consistency. Both add latency and complexity.",
        "When would you choose range sharding over hash sharding? — Hint: range sharding when you need range queries (time-series data, log analytics, sequential ID lookups). Hash sharding when you need uniform distribution and your queries are point lookups by key. Many systems use compound approaches: hash on tenant_id, then range on timestamp within each tenant's shard.",
        "How would you migrate from a single database to a sharded architecture? — Hint: double-write approach — write to both old and new, backfill historical data, verify consistency, switch reads, then decommission. Use a feature flag to control the cutover. The entire process should be reversible at every step.",
    ],
    "key_trade_offs": [
        "Hash sharding vs Range sharding — hash distributes data uniformly but destroys range query ability; range preserves range queries but creates hot spots for sequential writes. Choose hash for point-lookup workloads (user profiles), range for time-series or sequential-scan workloads (log analytics).",
        "More shards vs Fewer shards — more shards give higher throughput and smaller per-shard data size, but increase operational complexity, cross-shard query cost, and connection overhead. Start with fewer shards (but more virtual shards) and split when needed.",
        "Shard key aligned with reads vs Writes — optimizing the shard key for read patterns (e.g., query by user) may create write hot spots (e.g., all new user registrations hit the latest range shard). There is rarely a perfect key; choose the one that optimizes your dominant access pattern.",
        "Co-located data vs Independent sharding — storing related entities on the same shard (user + user's orders) enables local joins but couples their scaling. Sharding them independently (users by user_id, orders by order_id) allows each to scale separately but makes joins cross-shard.",
        "Application-level sharding vs Middleware — application-level sharding (each service knows the shard routing) is transparent and flexible but duplicates logic. Middleware (Vitess, ProxySQL) centralizes routing but adds a network hop and is a potential bottleneck.",
    ],
    "common_mistakes": [
        "Choosing a shard key with low cardinality. Sharding by country (200 values) limits you to 200 shards maximum and guarantees uneven distribution. Always verify that your shard key has cardinality at least 10x your target shard count.",
        "Forgetting to address secondary access patterns. Candidates shard by user_id and then handwave when asked 'how do you look up a user by email?' Have a concrete answer: global secondary index, separate lookup table, or denormalized data.",
        "Assuming sharding is free. Every cross-shard query pays a latency tax. If 30% of your queries require scatter-gather across 64 shards, you have effectively made 30% of your queries 10-50x slower. Quantify the percentage of queries that will be cross-shard before choosing a shard key.",
        "Not discussing resharding. Interviewers specifically listen for whether you acknowledge that the number of shards will need to change over time. Always mention virtual shards or consistent hashing as a mechanism to make resharding less painful.",
        "Sharding too early. If your database handles the load with proper indexing, query optimization, connection pooling, and read replicas, sharding adds unnecessary complexity. Always mention that sharding is a last resort after exhausting simpler scaling techniques.",
    ],
    "interview_tips": [
        "Frame sharding as a last resort: 'Before sharding, I would verify we have exhausted vertical scaling, read replicas, connection pooling, query optimization, and caching. If we are still bottlenecked on write throughput or data volume, then sharding is the right next step.'",
        "Always justify your shard key with data: 'I would shard by user_id because: it has high cardinality (500M+ distinct values), hash distribution is uniform, and 85% of our queries include user_id in the WHERE clause, so 85% of queries hit a single shard.'",
        "Address the hard parts upfront: 'The main challenge with this shard key is that searching by email requires a scatter-gather query. I would mitigate this with a lightweight global index — a Redis hash mapping email to user_id — which adds less than 1ms of lookup overhead.'",
        "Mention virtual shards for future-proofing: 'I would create 1024 logical shards mapped to 16 physical nodes. When we need to scale to 32 nodes, we reassign logical shards — no data rehashing, just remapping the directory. This is the approach Redis Cluster and Vitess use.'",
    ],
    "related_concepts": ["consistent_hashing", "replication", "caching", "database_indexing"],
},
"consistent_hashing": {
    "title": "Consistent Hashing",
    "introduction": (
        "Imagine you have 4 cache servers and you distribute keys using hash(key) mod 4. Server 0 gets keys "
        "whose hash ends in 0, server 1 gets those ending in 1, and so on. This works until you need to add a "
        "5th server. Now the formula is hash(key) mod 5, and roughly 80% of all keys map to a different server "
        "than before. Those keys are effectively 'lost' — the cache must be repopulated from the database, causing "
        "a massive spike in database load that can take down your entire system. Similarly, if one of your 4 servers "
        "fails, hash(key) mod 3 remaps about 75% of keys. This is the fundamental problem with naive modulo hashing: "
        "any change in the number of nodes causes near-total redistribution. Consistent hashing, introduced by "
        "Karger et al. in 1997, solves this elegantly. When a node is added or removed, only K/N keys need to move "
        "on average, where K is the total number of keys and N is the number of nodes. This is the theoretical "
        "minimum — you cannot do better. Consistent hashing is foundational infrastructure in production systems: "
        "Amazon DynamoDB uses it for partition assignment, Apache Cassandra uses it for its token ring, Akamai "
        "uses it for CDN request routing, and Discord uses it for routing messages to the correct server. In "
        "interviews, consistent hashing appears both as a standalone question and as a building block for designing "
        "distributed caches, distributed databases, and load balancers. You need to understand the hash ring "
        "concept, how nodes and keys are placed on the ring, what happens during node addition and removal, why "
        "virtual nodes are essential in practice, and how consistent hashing compares to alternatives like "
        "rendezvous hashing."
    ),
    "key_concepts": [
        {
            "name": "The Hash Ring",
            "explanation": (
                "Consistent hashing maps both nodes and keys onto the same circular hash space — the hash ring. "
                "The ring represents the output range of a hash function, typically 0 to 2^32 - 1 (about 4.3 billion "
                "positions). The ring wraps around: position 2^32 is the same as position 0. To place a node on the "
                "ring, hash the node's identifier (IP address, hostname, or name): position = hash('node-A'). Each "
                "node occupies one position on the ring. To assign a key to a node, hash the key to get its position "
                "on the ring, then walk clockwise until you encounter a node. That node is responsible for the key. "
                "Formally, a key is assigned to the first node whose position is greater than or equal to the key's "
                "hash position (wrapping around if necessary). "
                "For example, if nodes A, B, and C are at positions 1000, 5000, and 9000 on a ring of size 10000, "
                "a key that hashes to position 3500 walks clockwise and hits node B at position 5000. A key at "
                "position 9500 walks clockwise, wraps past position 10000 (which equals 0), and hits node A at "
                "position 1000. "
                "Each node is responsible for all keys between its position and the previous node's position "
                "(going clockwise). Node A owns keys from 9001 to 1000, node B owns 1001 to 5000, and node C "
                "owns 5001 to 9000. This means each node 'owns' a contiguous arc of the ring. The hash function "
                "must be deterministic and produce a uniform distribution — MD5, SHA-1, or MurmurHash are typical "
                "choices. In production, MurmurHash is preferred for its speed (10x faster than MD5) with excellent "
                "distribution properties."
            ),
        },
        {
            "name": "Node Addition and Removal",
            "explanation": (
                "The power of consistent hashing is what happens when nodes change. When a new node D is added at "
                "position 7000, it takes over responsibility for keys from 5001 to 7000 — keys that previously "
                "belonged to node C (which was at 9000). Nodes A and B are completely unaffected. Only the keys "
                "in the arc between the new node and its predecessor need to move. "
                "Mathematically, when adding a node to a ring with N existing nodes, the expected number of keys "
                "that move is K/N, where K is the total number of keys. With 1 million keys and 10 nodes, adding "
                "an 11th node moves roughly 100,000 keys (10%) — compared to modulo hashing, which would move "
                "about 900,000 keys (90%). This is the theoretical minimum: if you are distributing K keys across "
                "N+1 nodes, each node should hold K/(N+1) keys, so the new node must receive at least K/(N+1) keys, "
                "which is approximately K/N for large N. "
                "When a node fails or is removed, the process reverses. If node B (at position 5000) goes down, "
                "its keys (1001 to 5000) are absorbed by the next node clockwise — node C at 9000. Again, only "
                "one segment of the ring is affected. Nodes A and the other remaining nodes are unaffected. This "
                "property is critical for fault tolerance: a node failure causes a graceful redistribution to one "
                "neighbor, not a catastrophic rehashing of the entire keyspace. "
                "In practice, the receiving node must be able to handle the sudden increase in load (its key space "
                "roughly doubles). This is why replication is important: if each key is replicated to the next 2 "
                "nodes clockwise, then when a node fails, the load increase is distributed across 2 nodes instead "
                "of concentrated on 1. DynamoDB and Cassandra both use this replication strategy."
            ),
        },
        {
            "name": "Virtual Nodes (Vnodes)",
            "explanation": (
                "With only physical nodes on the ring, the distribution is often uneven. If you have 3 nodes and "
                "they happen to hash to positions 1000, 1500, and 9000, node C (at 9000) owns the arc from 1501 "
                "to 9000 — a massive 75% of the ring — while node B (at 1500) owns only 500 positions (5%). This "
                "unevenness worsens with fewer nodes and is essentially random, depending on where the hash function "
                "places each node. "
                "Virtual nodes solve this by giving each physical node multiple positions on the ring. Instead of "
                "hashing 'node-A' once, you hash 'node-A-0', 'node-A-1', 'node-A-2', ..., 'node-A-149', placing "
                "150 virtual nodes for each physical node. With 3 physical nodes and 150 vnodes each, you have 450 "
                "points on the ring, distributed much more uniformly. Each physical node owns many small arcs instead "
                "of one large arc, and the law of large numbers ensures the total key ownership converges toward an "
                "even 33% split. "
                "The number of vnodes per physical node is typically 100 to 200 in production. Cassandra defaults to "
                "256 tokens per node. More vnodes means better distribution but more metadata to maintain (the ring "
                "table that maps virtual positions to physical nodes). The memory overhead is minimal — a ring table "
                "for 10 physical nodes with 200 vnodes each is just 2,000 entries (position, node_id), a few KB. "
                "Virtual nodes also improve rebalancing when a physical node is added. Without vnodes, adding a node "
                "takes keys from only one neighbor. With vnodes, the new node's 150 virtual positions are scattered "
                "across the ring, taking small amounts of keys from many different nodes. This distributes the "
                "migration load evenly and the receiving nodes barely notice the reduction. "
                "Weighted consistent hashing extends this further: a more powerful physical node gets more vnodes "
                "(e.g., 300 instead of 150), so it owns a proportionally larger share of the keyspace. This lets "
                "you run heterogeneous hardware in the same cluster — a machine with 2x the RAM gets 2x the vnodes "
                "and stores 2x the data."
            ),
        },
        {
            "name": "Production Implementations",
            "explanation": (
                "Amazon DynamoDB uses consistent hashing for partition assignment. Each table's data is split into "
                "partitions, and each partition is assigned to a position on a hash ring. When a table grows and "
                "needs more partitions, DynamoDB splits an existing partition and places the new half at a new ring "
                "position. Storage nodes that own adjacent ring positions replicate data for fault tolerance. The "
                "partition key (specified by the developer) is hashed to determine which partition handles a request. "
                "Apache Cassandra uses a token ring: each node is assigned a set of tokens (virtual node positions) "
                "in the hash ring. The default partitioner is Murmur3Partitioner, which hashes partition keys using "
                "MurmurHash3 into a 64-bit range. Each node owns the token ranges assigned to it. Cassandra "
                "replicates each key to N nodes (configurable replication factor, typically 3), choosing the next "
                "N-1 nodes clockwise on the ring. When a node joins the cluster, it receives token ranges from "
                "existing nodes and streams data in the background while the cluster continues serving traffic. "
                "Akamai CDN (one of the co-inventors of consistent hashing) uses it to determine which edge server "
                "should cache a given URL. When a user requests content, the CDN hashes the URL to find the "
                "responsible edge server. Consistent hashing ensures that the same URL is consistently served by "
                "the same server (maximizing cache hit rate) while gracefully redistributing URLs when servers are "
                "added or removed. "
                "Discord uses consistent hashing to route messages to the correct guild (server) handler process. "
                "Each guild is assigned to a node via consistent hashing on the guild ID, ensuring that all messages "
                "for a guild are processed by the same node (preserving ordering). When a node fails, only its "
                "guilds are redistributed to other nodes. "
                "Memcached client libraries (like libmemcached and the Java SpyMemcached client) implement consistent "
                "hashing on the client side. The client maintains the hash ring, hashes each cache key, and sends the "
                "request directly to the responsible Memcached server. When a server is added or removed, the client "
                "updates its ring, and only a fraction of keys miss."
            ),
        },
        {
            "name": "Rendezvous Hashing (Highest Random Weight)",
            "explanation": (
                "Rendezvous hashing is an alternative to consistent hashing that solves the same problem — minimal "
                "key redistribution when nodes change — with a different mechanism. For each key, compute a score "
                "for every node: score = hash(key, node_id). Assign the key to the node with the highest score. "
                "This is why it is also called Highest Random Weight (HRW) hashing. "
                "When a node is removed, only the keys that were assigned to that node need to move — they are "
                "reassigned to whichever remaining node now has the highest score. Keys assigned to other nodes "
                "are unaffected because the removal of a node cannot increase any other node's score. When a node "
                "is added, some keys will have a higher score with the new node than with their current node, and "
                "only those keys move. The fraction of keys that move is approximately 1/(N+1), the same optimal "
                "proportion as consistent hashing. "
                "The advantage of rendezvous hashing over consistent hashing: there is no ring structure to maintain, "
                "no virtual nodes to configure, and the algorithm is simpler to implement — just a loop over all nodes "
                "for each key lookup. Distribution is naturally uniform without virtual nodes. "
                "The disadvantage: lookup time is O(N) because you must compute the hash for every node to find the "
                "maximum. With consistent hashing and a sorted ring, lookup is O(log N) via binary search. For small "
                "clusters (dozens to a few hundred nodes), O(N) is negligible. For very large clusters (thousands of "
                "nodes), consistent hashing with virtual nodes is more efficient. "
                "Rendezvous hashing is used in Microsoft's Azure for partition assignment, in GitHub's load balancer "
                "for routing to backend servers, and in various distributed caching systems. In interviews, mentioning "
                "rendezvous hashing as an alternative to consistent hashing — and being able to articulate the "
                "trade-off between O(N) lookup simplicity and O(log N) ring-based lookup — demonstrates depth. "
                "Most interviewers will be impressed because rendezvous hashing is less commonly discussed despite "
                "being equally elegant."
            ),
        },
    ],
    "real_world_examples": [
        "Amazon DynamoDB: uses consistent hashing with virtual nodes for partition assignment across storage nodes. Each partition key is hashed via MD5, and the hash determines which partition (and thus which storage node) handles the request. Adding storage capacity means placing new virtual nodes on the ring and migrating only the affected key ranges.",
        "Apache Cassandra Token Ring: each Cassandra node owns a set of token ranges on a hash ring (MurmurHash3, 64-bit space). With a replication factor of 3, each key is stored on 3 consecutive nodes clockwise. When a node joins or leaves, Cassandra streams only the affected token ranges, with the cluster remaining available throughout.",
        "Akamai CDN Request Routing: co-invented consistent hashing in 1997. Each URL is hashed to a position on the ring, and the responsible edge server is found by clockwise traversal. This ensures the same URL is consistently served by the same edge server (cache affinity) while gracefully handling server additions and failures.",
        "Discord Guild Routing: Discord hashes guild (server) IDs using consistent hashing to assign each guild to a gateway node. All events for a guild are processed by the same node, maintaining ordering guarantees. When a node goes down, only its guilds are redistributed, typically within seconds.",
        "Memcached Client-Side Routing: Memcached itself has no clustering — consistent hashing is implemented in client libraries. The ketama algorithm (by Last.fm engineers) places each Memcached server at 100-200 virtual positions on a ring, and keys are routed client-side. Adding a server redistributes only 1/N of keys instead of nearly all.",
    ],
    "common_interview_questions": [
        "What is the problem with simple modulo hashing, and how does consistent hashing solve it? — Hint: modulo hashing redistributes ~(N-1)/N of all keys when a node is added (going from N to N+1 nodes). Consistent hashing redistributes only ~K/N keys (approximately 1/N fraction) because each key's assignment depends only on its nearest clockwise node, not on the total count.",
        "How do virtual nodes improve load balancing? — Hint: with few physical nodes, hash positions may be unevenly spaced, causing one node to own a disproportionate share of the ring. Virtual nodes (100-200 per physical node) scatter each node's positions across the ring, averaging out the arc sizes. The standard deviation of load drops from O(1/sqrt(N)) to O(1/sqrt(V*N)) where V is virtual nodes per physical node.",
        "What happens when a node goes down in a consistent hashing ring? — Hint: only the keys on the failed node's arc are affected. They are absorbed by the next clockwise node. With replication (keys stored on the next R clockwise nodes), reads can be served immediately from replicas, and only the replication factor needs to be restored by re-replicating to a new node.",
        "How would you implement consistent hashing for a distributed cache? — Hint: maintain a sorted array of (hash_position, node_id) entries for all virtual nodes. To find the node for a key: hash the key, binary search the sorted array for the first position >= key_hash (with wraparound). This gives O(log V*N) lookup time. The ring metadata is small (a few KB) and can be stored on every client.",
        "How does consistent hashing compare to rendezvous hashing? — Hint: both achieve minimal key redistribution (K/N keys move when adding a node). Consistent hashing uses a ring with O(log N) lookup but requires virtual nodes for good distribution. Rendezvous hashing has O(N) lookup but natural uniform distribution without any tuning. Prefer consistent hashing for large clusters (N > 100), rendezvous for small ones.",
    ],
    "key_trade_offs": [
        "Consistent hashing vs Modulo hashing — consistent hashing moves only K/N keys when the node count changes vs K*(N-1)/N for modulo. Choose modulo only when the node count is guaranteed fixed; choose consistent hashing for any dynamic cluster.",
        "More virtual nodes vs Fewer virtual nodes — more vnodes (200+) give near-perfect distribution but increase ring metadata size and rebalancing time. Fewer vnodes (10-50) have faster lookups but worse distribution. The sweet spot is 100-200 vnodes per physical node for most production systems.",
        "Consistent hashing vs Rendezvous hashing — consistent hashing has O(log N) lookup but requires virtual nodes and ring maintenance. Rendezvous hashing has O(N) lookup but is simpler with naturally uniform distribution. Choose consistent hashing for large clusters, rendezvous for small clusters or when implementation simplicity matters.",
        "Replication on the ring vs External replication — ring-based replication (store on next R clockwise nodes) is elegant and automatic but means a node failure increases load on its neighbors. External replication (separate replication layer) is more flexible but adds architectural complexity.",
    ],
    "common_mistakes": [
        "Forgetting virtual nodes. Describing consistent hashing without virtual nodes is incomplete — in practice, 3-5 physical nodes on a ring will have severely unbalanced distribution. Always mention virtual nodes as essential for production use.",
        "Confusing the hash function for nodes and keys. Both nodes and keys must use the same hash function mapping to the same ring space. If you hash nodes with SHA-1 (160-bit) and keys with MurmurHash (32-bit), they are on different rings and the system is broken.",
        "Not quantifying the improvement. Instead of just saying 'consistent hashing moves fewer keys,' state the numbers: 'With modulo hashing, adding a 5th node to 4 moves ~80% of keys. With consistent hashing, it moves ~20% (K/5). That is a 4x reduction in cache misses during scaling.'",
        "Ignoring the replication strategy. In a real distributed system, assigning a key to one node is not enough — you need redundancy. Explain how consistent hashing naturally supports replication by assigning each key to the next R nodes clockwise, and how this interacts with node failures.",
        "Treating consistent hashing as only for caching. Candidates often associate it exclusively with Memcached/Redis. In reality, it is used for database partition assignment (DynamoDB, Cassandra), CDN routing (Akamai), message routing (Discord), and any system that needs to distribute work across a dynamic set of nodes.",
    ],
    "interview_tips": [
        "Draw the ring: 'Let me draw a hash ring from 0 to 2^32. I will place 3 nodes: A at position 1 billion, B at 2.5 billion, C at 3.8 billion. A key that hashes to 2 billion walks clockwise and lands on B.' Visualization makes the concept instantly clear to the interviewer.",
        "Derive the math: 'When we add a 4th node D at position 3 billion, it takes over keys from 2.5 billion to 3 billion — keys that previously belonged to C. That is roughly 1/8 of the ring, or about K/4 keys for 4 nodes. Nodes A and B are completely unaffected.'",
        "Connect to real systems: 'This is exactly how DynamoDB assigns partitions to storage nodes. Each partition key is hashed onto the ring, and the clockwise node stores it. With virtual nodes, DynamoDB achieves even distribution across heterogeneous hardware.'",
        "Address the follow-up about hot keys: 'Consistent hashing distributes keys uniformly, but it does not prevent hot keys. If one key receives 1000x more traffic, its assigned node becomes a hot spot. The solution is application-level: cache the hot key in every application server's local memory, or split it into sub-keys (e.g., hot_key_0 through hot_key_9) that map to different ring positions.'",
    ],
    "related_concepts": ["sharding", "caching", "load_balancing", "replication"],
},
    "cap_theorem": {
    "title": "CAP Theorem & Consistency Models",
    "introduction": (
        "Imagine you are building a banking application that serves customers across "
        "three data centers in New York, London, and Tokyo. A customer in New York "
        "transfers $500 to their savings account. At the exact same moment, the London "
        "data center receives a read request for that customer's balance. Should the "
        "London server show the old balance (fast, available) or wait until it confirms "
        "the New York write has propagated (correct, consistent)? Now imagine the network "
        "link between New York and London goes down. Do you refuse to serve the London "
        "customer entirely, or do you show them a potentially stale balance? This is the "
        "heart of the CAP theorem, and it is the single most important theoretical "
        "framework for understanding distributed systems trade-offs. The CAP theorem, "
        "proven by Eric Brewer in 2000 and formalized by Gilbert and Lynch in 2002, "
        "states that a distributed data store can provide at most two of three guarantees: "
        "Consistency (every read receives the most recent write or an error), Availability "
        "(every request receives a non-error response, without guaranteeing it contains "
        "the most recent write), and Partition Tolerance (the system continues to operate "
        "despite arbitrary message loss or failure between nodes). In practice, network "
        "partitions are not optional in distributed systems. Switches fail, cables get "
        "cut, cloud availability zones lose connectivity. This means partition tolerance "
        "is mandatory, and the real engineering choice is between consistency and "
        "availability: CP or AP. But the story does not end there. Real systems do not "
        "make a single binary choice. They operate on a rich spectrum of consistency "
        "models, from strong linearizability all the way down to eventual consistency. "
        "Understanding this spectrum, knowing which model each major database offers, "
        "and being able to justify your choice for a given use case is what separates "
        "a strong system design interview from a mediocre one. In this topic, you will "
        "learn the three CAP properties in depth, why the choice is really C vs A, "
        "the full consistency spectrum with concrete database examples for each level, "
        "the PACELC extension that covers the no-partition case, and how to map "
        "technologies to consistency guarantees in an interview setting."
    ),
    "key_concepts": [
        {
            "name": "The Three CAP Properties",
            "explanation": (
                "Consistency in CAP means linearizability: if client A writes a value and "
                "gets an acknowledgment, then any subsequent read by any client (B, C, or A "
                "itself) must return that value or a newer one. This is a specific, strong "
                "guarantee, not the same as ACID consistency (which means the database "
                "transitions between valid states respecting constraints). Interviewers "
                "frequently test whether you know this distinction. Availability in CAP "
                "means every request received by a non-failing node must result in a "
                "response. Note the precision: it does not mean 99.99% uptime. It means "
                "literally every request to a healthy node gets an answer, even if another "
                "node is unreachable. A system that returns errors during a partition is "
                "not CAP-available, even if its uptime SLA is high. Partition Tolerance "
                "means the system continues to function when network messages between "
                "nodes are lost or delayed indefinitely. In any real distributed system, "
                "partitions are inevitable. Google reports that their internal network "
                "experiences dozens of partitions per year across their data centers. "
                "Amazon has documented similar findings. A single top-of-rack switch "
                "failure can partition servers within the same data center. The critical "
                "insight is that partition tolerance is not a choice; it is a requirement. "
                "If you build a distributed system that does not tolerate partitions, the "
                "first network hiccup will cause data loss or total unavailability. "
                "Therefore, the real decision is: when a partition occurs, do you sacrifice "
                "consistency (serve potentially stale data, AP) or availability (refuse "
                "requests until the partition heals, CP)? In an interview, frame it this "
                "way: 'Since partitions are inevitable in distributed systems, CAP really "
                "asks us to choose between consistency and availability during a partition. "
                "The right choice depends on the business requirement.' This shows you "
                "understand the theorem deeply, not just the surface-level 'pick 2 of 3' "
                "oversimplification."
            ),
        },
        {
            "name": "CP Systems: Consistency Over Availability",
            "explanation": (
                "A CP system, when faced with a network partition, will refuse to serve "
                "requests (or return errors) rather than risk returning stale or incorrect "
                "data. The canonical example is a banking system. If the network between "
                "two replicas partitions, a CP system will stop accepting writes (or reads, "
                "depending on the design) to the partitioned nodes. The customer sees an "
                "error or timeout, but they never see an incorrect balance. Concrete "
                "examples: ZooKeeper is CP. It is used for distributed coordination "
                "(leader election, configuration management, distributed locks). During "
                "a partition, if a ZooKeeper node cannot reach a quorum (majority of nodes), "
                "it stops serving reads and writes entirely. This is the right trade-off "
                "because serving stale configuration data could cause cascading failures "
                "across the entire distributed system. HBase is CP. It relies on ZooKeeper "
                "for coordination and will become unavailable for a region if the region "
                "server cannot communicate with the master. Google Spanner is CP with "
                "remarkable availability. It uses TrueTime (GPS and atomic clocks in every "
                "data center) to achieve external consistency (stronger than linearizability) "
                "with availability that approaches AP systems. Spanner achieves this by "
                "making partitions extremely rare through redundant network paths, not by "
                "relaxing consistency. Spanner's reported availability is 99.9999% (five "
                "nines), which shows that CP does not automatically mean 'frequently "
                "unavailable.' MongoDB in its default configuration with replica sets is "
                "CP: if the primary is unreachable, writes fail until a new primary is "
                "elected (which takes 10-30 seconds). When to choose CP in an interview: "
                "any system where incorrect data causes real harm. Financial transactions, "
                "inventory management (overselling), seat reservations (double booking), "
                "distributed locks, leader election. The interview framing: 'For this use "
                "case, showing an error is better than showing wrong data, so I would "
                "choose a CP approach with strong consistency.'"
            ),
        },
        {
            "name": "AP Systems: Availability Over Consistency",
            "explanation": (
                "An AP system, during a network partition, continues to serve all requests "
                "even though different nodes may have divergent data. The system remains "
                "responsive, but reads may return stale values, and concurrent writes to "
                "partitioned nodes may create conflicts that need resolution later. The "
                "canonical example is a social media feed. If the network partitions, it "
                "is far better to show a user their feed (even if it is missing the last "
                "few posts from a friend) than to show them an error page. The user "
                "experience of 'slightly stale' is vastly better than 'totally broken.' "
                "Concrete examples: Cassandra is AP with tunable consistency. By default "
                "(consistency level ONE), Cassandra writes to a single replica and returns "
                "success. The write propagates to other replicas asynchronously. If you "
                "need stronger guarantees, you can use QUORUM (majority of replicas must "
                "acknowledge), which moves Cassandra toward CP behavior for that specific "
                "operation. This per-query tunability is a powerful interview talking point. "
                "DynamoDB is AP by default: writes go to a single node and propagate "
                "asynchronously, reads are eventually consistent. DynamoDB offers a "
                "'strongly consistent read' option that reads from the leader node, which "
                "costs 2x the read capacity units and adds latency. CouchDB is AP and "
                "uses multi-version concurrency control (MVCC) with conflict resolution. "
                "When partitioned nodes reconnect, CouchDB detects conflicting document "
                "versions and lets the application resolve them. DNS is perhaps the most "
                "famous AP system: DNS caches serve stale records during outages, and TTL "
                "controls how stale records can get. When to choose AP in an interview: "
                "any system where availability and user experience matter more than perfect "
                "correctness. Social media feeds, product catalogs (a price being a few "
                "seconds stale is fine), content delivery, shopping carts (Amazon's Dynamo "
                "paper explicitly chose AP for the shopping cart because a lost add-to-cart "
                "is worse than a duplicate item). The interview framing: 'Users would "
                "rather see slightly stale data than get an error, so I would choose AP "
                "with eventual consistency and design idempotent conflict resolution.'"
            ),
        },
        {
            "name": "The Consistency Spectrum",
            "explanation": (
                "The CAP theorem presents a binary C-vs-A choice, but real systems operate "
                "on a rich spectrum of consistency models. From strongest to weakest: "
                "Linearizability (also called strong consistency or external consistency) "
                "is the strongest model. Operations appear to execute atomically at some "
                "point between invocation and completion, and the order respects real-time "
                "ordering. If write W completes before read R begins, R must see W. Google "
                "Spanner provides this. It costs network round-trips to coordinate (typically "
                "10-100ms for cross-region). Sequential Consistency is slightly weaker: all "
                "operations appear to execute in some sequential order, and each client's "
                "operations appear in the order they were issued. But there is no real-time "
                "ordering guarantee. Two clients may disagree about which write happened "
                "first, as long as they both see the same total order. Causal Consistency "
                "guarantees that causally related operations are seen in order. If A writes "
                "X, then reads X, then writes Y, every node will see X before Y. But "
                "concurrent, unrelated writes may be seen in different orders by different "
                "nodes. This is much cheaper than linearizability because only causally "
                "related operations need coordination. Read-Your-Writes Consistency "
                "guarantees that after a client writes a value, that same client will always "
                "read back the value it wrote (or a newer one). Other clients may still see "
                "stale data. This is the minimum consistency most users expect. If you post "
                "a tweet and immediately refresh, you need to see your own tweet. Monotonic "
                "Reads guarantees that if a client reads a value, subsequent reads by that "
                "client will never return an older value. Without this, a user could see a "
                "comment, refresh, and the comment disappears, then refresh again and it "
                "reappears. Eventual Consistency is the weakest useful model: if no new "
                "writes are made, all replicas will eventually converge to the same value. "
                "There is no guarantee about how long 'eventually' takes (though in practice "
                "it is typically milliseconds to seconds). DynamoDB default reads, Cassandra "
                "with consistency level ONE, and DNS all provide eventual consistency. In "
                "interviews, show you understand this spectrum by saying: 'Strong consistency "
                "is not always necessary. For the user profile service, read-your-writes is "
                "sufficient. For the payment service, I need linearizability.'"
            ),
        },
        {
            "name": "PACELC Theorem",
            "explanation": (
                "The CAP theorem only describes what happens during a partition. But most of "
                "the time, your system is running without any partition at all. Daniel Abadi "
                "proposed the PACELC theorem in 2010 to address this gap. PACELC states: "
                "if there is a Partition, the system must choose between Availability and "
                "Consistency (the CAP part); Else (when the system is running normally), "
                "the system must choose between Latency and Consistency. This is important "
                "because even without partitions, strong consistency has a cost: coordinating "
                "across replicas adds latency. A system that requires acknowledgment from "
                "a quorum of replicas before confirming a write will always be slower than "
                "one that writes to a single node and returns immediately. Concrete technology "
                "mapping: DynamoDB is PA/EL. During a partition, it chooses availability "
                "(serves stale data). When there is no partition, it chooses low latency "
                "(single-node reads by default). This is why DynamoDB has single-digit "
                "millisecond latency for reads. Spanner is PC/EC. During a partition, it "
                "chooses consistency (rejects requests to partitioned nodes). When there is "
                "no partition, it still chooses consistency over latency (cross-region writes "
                "take 10-100ms because of TrueTime coordination). Cassandra is PA/EL by "
                "default but is PA/EC at QUORUM consistency level. The per-query tunability "
                "of Cassandra means its PACELC classification changes based on configuration. "
                "MongoDB is PC/EC: consistent during partitions (primary election) and "
                "consistent during normal operation (reads from primary). In an interview, "
                "PACELC is an excellent way to demonstrate depth: 'CAP tells us what happens "
                "during a partition, but PACELC captures the everyday trade-off too. Even "
                "without partitions, I am choosing between latency and consistency. For this "
                "read-heavy feed service, I would choose PA/EL because sub-10ms reads "
                "matter more than perfect consistency.'"
            ),
        },
        {
            "name": "Technology Mapping and Interview Application",
            "explanation": (
                "In a system design interview, you need to quickly map your consistency "
                "requirements to a concrete technology choice. Here is the essential mapping: "
                "Strong consistency (linearizability): Google Spanner (NewSQL, globally "
                "distributed, uses TrueTime), CockroachDB (open-source Spanner-inspired, "
                "uses hybrid logical clocks), PostgreSQL with synchronous replication "
                "(single-region, primary-replica). These are right for financial systems, "
                "inventory, booking systems. Tunable consistency: Apache Cassandra (choose "
                "per query: ONE, QUORUM, ALL), DynamoDB (default eventual, optional strong "
                "reads), Azure Cosmos DB (five consistency levels: strong, bounded staleness, "
                "session, consistent prefix, eventual). These are right when different "
                "operations in the same system need different guarantees. Eventual "
                "consistency: DynamoDB default, Cassandra at ONE, DNS, CDN caches, "
                "ElasticSearch. These are right for search indexes, analytics, caching, "
                "content feeds. The key interview pattern is to identify which parts of "
                "your system need strong consistency and which can tolerate eventual. Almost "
                "no system needs the same consistency level everywhere. A common winning "
                "answer structure: 'For the payment processing path, I need strong consistency "
                "so I would use PostgreSQL with synchronous replication or Spanner. For the "
                "user activity feed, eventual consistency is fine, so I would use DynamoDB "
                "or Cassandra with consistency level ONE for fast reads. For the search "
                "index, I would use Elasticsearch which is inherently eventually consistent.' "
                "This shows the interviewer you can match consistency requirements to specific "
                "system components rather than applying a blanket policy. Also worth noting: "
                "CAP consistency is different from ACID consistency. ACID consistency means "
                "a transaction takes the database from one valid state to another (respecting "
                "constraints, triggers, cascades). CAP consistency means all nodes see the "
                "same data at the same time. These are orthogonal concepts that share an "
                "unfortunately overloaded name."
            ),
        },
    ],
    "real_world_examples": [
        "Google Spanner: CP/EC — uses TrueTime (GPS + atomic clocks) for global linearizability. Achieves 99.9999% availability not by relaxing consistency but by making partitions nearly impossible through redundant networking. Cross-region writes take ~10-100ms due to Paxos consensus rounds.",
        "Amazon DynamoDB: AP/EL — the original Dynamo paper (2007) explicitly chose availability over consistency for Amazon's shopping cart. A lost 'add to cart' event costs a sale, but a duplicate item is easily removed. Default reads are eventually consistent (single-digit ms latency), strongly consistent reads cost 2x capacity units.",
        "Apache Cassandra: AP with tunable consistency — consistency level ONE gives fastest reads/writes (AP). QUORUM reads require floor(N/2)+1 replicas to agree, giving stronger consistency at higher latency. ALL requires every replica, which is effectively CP. Facebook created Cassandra for inbox search — availability matters more than perfect ordering.",
        "Apache ZooKeeper: CP — used for distributed coordination (leader election, config management, distributed locks). During a partition, nodes that cannot reach a quorum stop serving entirely. Correctness of coordination is more important than availability because serving stale leader information could cause split-brain.",
    ],
    "common_interview_questions": [
        "Explain the CAP theorem. Why can you only pick two of three properties, and why is partition tolerance mandatory?",
        "Your system needs to handle bank transfers between accounts. Would you choose CP or AP? What database would you use?",
        "What is eventual consistency? Give an example where it is acceptable and one where it is not.",
        "Explain the difference between strong consistency, causal consistency, and eventual consistency. When would you choose each?",
        "What is the PACELC theorem and how does it extend CAP? Classify DynamoDB and Spanner under PACELC.",
    ],
    "key_trade_offs": [
        "Strong consistency guarantees correctness but costs latency (cross-replica coordination adds 10-100ms for cross-region systems) and reduces availability during partitions. Eventual consistency is fast and available but requires application-level conflict resolution and tolerating stale reads.",
        "Per-operation consistency tuning (like Cassandra QUORUM vs ONE) gives flexibility but increases system complexity. Engineers must understand which operations need which consistency level, and mixing levels can create subtle bugs.",
        "The cost of coordination grows with geographic distance. A system with replicas in US-East and EU-West pays ~80ms per round-trip for consensus. This is why many systems use eventual consistency for cross-region replication and strong consistency only within a single region.",
        "CP systems are not necessarily 'frequently unavailable.' Spanner achieves 99.9999% availability while being CP by investing heavily in redundant networking to make partitions nearly impossible. The trade-off becomes cost and infrastructure complexity.",
    ],
    "common_mistakes": [
        "Saying 'CAP means pick 2 of 3' without explaining that partition tolerance is mandatory, so the real choice is C vs A during a partition.",
        "Confusing CAP consistency (all nodes see the same data) with ACID consistency (database transitions between valid states). They are completely different concepts with an unfortunate naming collision.",
        "Treating consistency as binary (strong vs eventual) when there is a rich spectrum (linearizability, sequential, causal, read-your-writes, monotonic reads, eventual) and the right choice depends on the specific operation.",
        "Defaulting to strong consistency everywhere without considering the latency and availability cost. Most systems need strong consistency for only a small subset of operations (payments, inventory) and can use eventual consistency for the rest.",
    ],
    "interview_tips": [
        "When asked about CAP, immediately reframe: 'Since partitions are inevitable, the real question is whether we sacrifice consistency or availability during a partition. For this system, I would choose...' This shows you understand the theorem beyond the textbook definition.",
        "Use PACELC to demonstrate depth. After discussing the partition scenario, add: 'Even without partitions, there is a latency-consistency trade-off. DynamoDB is PA/EL, which is why it has single-digit ms reads. Spanner is PC/EC, which is why writes cost 10-100ms.'",
        "Map different consistency needs to different components of the same system: 'The payment path needs linearizability (Spanner or Postgres with sync replication), the feed uses eventual consistency (DynamoDB), and the search index is inherently eventually consistent (Elasticsearch).' This shows architectural maturity.",
    ],
    "related_concepts": ["sharding", "message_queues", "consistent_hashing"],
},

"database_indexing": {
    "title": "Database Indexing",
    "introduction": (
        "Consider a users table with 50 million rows. A query like SELECT * FROM users "
        "WHERE email = 'alice@example.com' without an index must examine every single row "
        "sequentially. That is a full table scan: the database reads 50 million rows from "
        "disk, checking each one. On a typical SSD, this takes multiple seconds. With a "
        "B-tree index on the email column, the same query traverses a balanced tree of "
        "height 4-5 (since each B-tree node holds hundreds of keys), following 4-5 pointer "
        "lookups to find the exact row. That is under a millisecond. The difference between "
        "O(n) and O(log n) at scale is the difference between a usable application and one "
        "that times out. But indexing is not free. Every index consumes disk space (typically "
        "1-3% of the table size per index), and every write (INSERT, UPDATE, DELETE) must "
        "update every index on that table. A table with 10 indexes means every single INSERT "
        "triggers 10 additional B-tree update operations. This is why indexing is fundamentally "
        "about trade-offs: you are trading write performance and storage for read performance. "
        "The art is knowing exactly which indexes your query patterns need, no more and no "
        "less. In system design interviews, indexing comes up constantly. When you propose "
        "a database schema, the interviewer expects you to identify which columns need indexes, "
        "what type of index to use, and how your indexing strategy interacts with your "
        "read/write ratio. A candidate who says 'I would add an index on user_id' shows "
        "basic competence. A candidate who says 'I would create a composite index on "
        "(user_id, created_at) to support the feed query, and since it covers all the "
        "SELECT columns, the database can do an index-only scan without touching the heap' "
        "demonstrates deep understanding. In this topic, you will learn how B-tree and hash "
        "indexes work at the mechanical level, composite index design and the leftmost prefix "
        "rule, covering indexes and index-only scans, when not to index, how to read EXPLAIN "
        "plans, and specialized index types for full-text search and spatial data."
    ),
    "key_concepts": [
        {
            "name": "B-Tree Indexes: Mechanics and Performance",
            "explanation": (
                "A B-tree (technically B+ tree in most databases) is a self-balancing tree "
                "structure where each internal node contains multiple keys and child pointers, "
                "and all leaf nodes are at the same depth. In PostgreSQL, a typical B-tree node "
                "(page) is 8 KB and can hold roughly 200-500 keys depending on key size. This "
                "means a B-tree with 100 million entries has a height of only 3-4 levels "
                "(since 500^4 = 62.5 billion). Each level requires one disk page read, so a "
                "point lookup costs 3-4 random reads. Since the upper levels of the tree are "
                "almost always cached in memory (the root and first level fit in a few MB), "
                "the actual I/O is often just 1-2 page reads from disk. The leaf nodes of a "
                "B+ tree are linked together in a doubly-linked list. This is what makes range "
                "queries efficient: to answer SELECT * FROM orders WHERE created_at BETWEEN "
                "'2024-01-01' AND '2024-01-31', the database finds the first matching leaf "
                "using the tree traversal (O(log n)), then follows the leaf links sequentially "
                "to find all matching entries. This sequential access pattern is extremely "
                "cache-friendly and fast on SSDs. B-trees support: equality lookups (=), range "
                "queries (<, >, BETWEEN), prefix matching (LIKE 'foo%'), and ORDER BY on the "
                "indexed column (the index is already sorted, so no additional sort is needed). "
                "They do NOT efficiently support: non-prefix LIKE queries (LIKE '%foo%'), "
                "function-based lookups (WHERE UPPER(name) = 'ALICE' unless you create a "
                "functional index), or inequality on non-leading columns in a composite index. "
                "Write cost: every INSERT requires O(log n) to find the correct leaf, then "
                "potentially splits the leaf if it is full (splits cascade up the tree but are "
                "rare). Updates to an indexed column require removing the old entry and inserting "
                "the new one. In interview framing: 'B-tree is the default choice. It handles "
                "both point lookups and range queries. For a table with 100M rows, a lookup "
                "costs about 3-4 page reads, which is under 1ms on SSD. The trade-off is "
                "that every write must also update the index.'"
            ),
        },
        {
            "name": "Hash Indexes",
            "explanation": (
                "A hash index computes a hash of the key and maps it directly to the row "
                "location. This gives O(1) average-case point lookups, which is faster than "
                "B-tree's O(log n) for exact equality queries. However, hash indexes have "
                "severe limitations: they do not support range queries (WHERE price > 100), "
                "sorting (ORDER BY), or prefix matching (LIKE 'foo%'). The hash function "
                "destroys ordering, so sequential access is impossible. In PostgreSQL, hash "
                "indexes exist but were not crash-safe until version 10, and they still do "
                "not support unique constraints. In practice, PostgreSQL hash indexes are "
                "rarely used because B-tree performance is close enough for point lookups "
                "and far more versatile. Where hash indexes truly shine is in-memory: Redis "
                "uses hash tables as its primary data structure, giving O(1) lookups for "
                "GET commands. Memory-mapped hash indexes in databases like Oracle can be "
                "very fast for high-throughput OLTP workloads with only equality queries. "
                "MySQL InnoDB uses an adaptive hash index: it automatically detects frequently "
                "accessed B-tree pages and builds an in-memory hash table for them, combining "
                "B-tree versatility with hash-speed for hot data. The key interview point: "
                "hash indexes are O(1) for equality but useless for ranges. In practice, "
                "B-trees are almost always the better choice for on-disk databases because "
                "the versatility of range queries and sorting far outweighs the marginal "
                "speed advantage of hash for equality-only. The exception is when you have "
                "a known workload that is exclusively point lookups on a high-cardinality "
                "column with massive throughput requirements, and you are using an in-memory "
                "store. Even then, profile first."
            ),
        },
        {
            "name": "Composite Indexes and the Leftmost Prefix Rule",
            "explanation": (
                "A composite index (also called a multi-column index) is a single B-tree "
                "built on the concatenation of multiple columns. For an index on (country, "
                "city, zipcode), the B-tree sorts first by country, then by city within each "
                "country, then by zipcode within each city. This creates the leftmost prefix "
                "rule: the index can be used for queries that filter on (country), (country, "
                "city), or (country, city, zipcode), but NOT for queries that filter on only "
                "(city) or only (zipcode) or (city, zipcode). The reason is mechanical: the "
                "B-tree is sorted by country first, so without specifying country, the database "
                "cannot use the tree structure to narrow down the search. This has critical "
                "implications for index design. Consider an e-commerce order table with queries: "
                "(1) orders by user: WHERE user_id = ?, (2) recent orders by user: WHERE "
                "user_id = ? ORDER BY created_at DESC, (3) orders by user in date range: WHERE "
                "user_id = ? AND created_at BETWEEN ? AND ?. A single composite index on "
                "(user_id, created_at) serves all three queries. Query 1 uses the leftmost "
                "prefix. Query 2 uses both columns, and since the index is sorted by created_at "
                "within each user_id, the ORDER BY is free (no filesort needed). Query 3 uses "
                "the full composite key for an efficient range scan within a user's orders. "
                "Without this composite index, you might create two separate indexes, wasting "
                "space and write overhead. Column ordering matters enormously. A rule of thumb: "
                "put the equality-filtered column first, then the range-filtered or ORDER BY "
                "column second. WHERE user_id = ? AND created_at > ? benefits from (user_id, "
                "created_at) but not from (created_at, user_id), because the B-tree needs to "
                "narrow to a specific user first, then scan dates sequentially. In interviews, "
                "designing one good composite index that serves multiple query patterns is a "
                "strong signal. Say: 'Instead of three separate indexes, I would create a "
                "single composite index on (user_id, created_at) that serves all three query "
                "patterns while minimizing write overhead.'"
            ),
        },
        {
            "name": "Covering Indexes and Index-Only Scans",
            "explanation": (
                "Normally, when a query uses an index, the database does two steps: (1) "
                "traverse the index to find matching row pointers (TIDs in PostgreSQL), then "
                "(2) follow those pointers to the heap (main table) to fetch the full row. "
                "Step 2 involves random I/O to the heap, which can be expensive if the query "
                "matches many rows spread across different pages. A covering index eliminates "
                "step 2 entirely. If the index contains all columns that the query needs "
                "(both the WHERE clause columns and the SELECT columns), the database can "
                "answer the query from the index alone. PostgreSQL calls this an 'index-only "
                "scan.' For example, if your query is SELECT user_id, created_at FROM orders "
                "WHERE user_id = 123 ORDER BY created_at DESC LIMIT 20, and you have an index "
                "on (user_id, created_at), this is a covering index because the SELECT clause "
                "only asks for user_id and created_at, both of which are in the index. No "
                "heap access needed. PostgreSQL 11 introduced the INCLUDE clause to make "
                "covering indexes more practical: CREATE INDEX idx ON orders (user_id, "
                "created_at) INCLUDE (status, total). The INCLUDE columns are stored in the "
                "leaf nodes but are NOT part of the search key. They do not affect the "
                "B-tree sort order, and they cannot be used for filtering or sorting. They "
                "exist solely to make the index 'cover' more queries. The trade-off: covering "
                "indexes are larger because they duplicate column data. An index that includes "
                "a VARCHAR(255) column in every leaf node will be significantly larger than "
                "one that does not. The storage cost must be weighed against the I/O savings. "
                "In PostgreSQL specifically, there is an additional complication: the visibility "
                "map. PostgreSQL's MVCC means that an index-only scan can only skip the heap "
                "access for pages that are known to be all-visible (no recently deleted or "
                "updated rows). On a freshly vacuumed table, index-only scans are very "
                "effective. On a table with heavy updates, they may still need to check the "
                "heap for visibility, reducing the benefit. In interviews, mentioning covering "
                "indexes signals you have real-world query optimization experience. Say: 'I "
                "would make this a covering index by including the status column, so the "
                "dashboard query can be answered entirely from the index without heap access.'"
            ),
        },
        {
            "name": "Clustered vs Non-Clustered Indexes",
            "explanation": (
                "A clustered index determines the physical order of data on disk. The table's "
                "rows are stored in the order of the clustered index's key. A table can have "
                "only one clustered index because the data can only be physically ordered one "
                "way. In MySQL InnoDB, the primary key is always the clustered index. This "
                "means rows are physically stored on disk in primary key order. When you do "
                "a range query on the primary key (SELECT * FROM users WHERE id BETWEEN 1000 "
                "AND 2000), InnoDB reads contiguous disk pages. This sequential I/O is "
                "extremely fast. A non-clustered index (called a secondary index) is a "
                "separate data structure that contains a copy of the indexed columns plus "
                "a pointer back to the main data. In InnoDB, secondary indexes store the "
                "primary key value as the pointer (not a physical row address). This means "
                "a secondary index lookup requires two tree traversals: one to the secondary "
                "index, then another to the primary key (clustered) index to find the actual "
                "row. This is called a 'bookmark lookup' or 'double lookup.' PostgreSQL works "
                "differently: there is no clustered index by default. All indexes are "
                "secondary, and they store a physical tuple ID (TID) pointing to the heap. "
                "You can physically reorder a PostgreSQL table using CLUSTER, but this is a "
                "one-time operation that locks the table and is not maintained as new rows "
                "are inserted. The practical implications for system design: in InnoDB, "
                "choose a good primary key because it determines physical data layout. "
                "Auto-increment integers are ideal: sequential writes append to the end of "
                "the clustered index, avoiding page splits. UUIDs as primary keys are "
                "problematic in InnoDB: random values cause constant page splits and "
                "fragmentation because new rows are inserted at random positions in the "
                "tree. If you must use UUIDs, consider UUIDv7 (time-sorted) or ULID. "
                "In interviews: 'InnoDB's clustered index means I would use an auto-increment "
                "primary key for write-heavy tables. UUIDs cause random inserts and page "
                "splits in the clustered index, which kills write throughput.' This shows "
                "you understand the physical implications of index choice."
            ),
        },
        {
            "name": "When NOT to Index and Specialized Index Types",
            "explanation": (
                "Not every column should be indexed. The four main cases where indexing hurts "
                "more than it helps: (1) Write-heavy tables with few reads: every index adds "
                "write overhead. A logging table that is INSERT-only and rarely queried should "
                "have minimal indexes. (2) Low-cardinality columns: an index on a boolean "
                "column (active = true/false) or a status column with 3 values is almost "
                "useless because the index is not selective. If 50% of rows match, the database "
                "will prefer a sequential scan over the index because the random I/O of "
                "following index pointers to widely scattered heap pages is more expensive "
                "than just reading all pages sequentially. The selectivity threshold is roughly: "
                "if more than 10-15% of rows match, the database will likely ignore the index. "
                "(3) Tiny tables: a table with 100 rows fits in a single disk page. A "
                "sequential scan of one page is faster than traversing an index tree. "
                "(4) Frequently updated columns: if the indexed column changes constantly "
                "(e.g., a 'last_seen' timestamp updated on every request), the index "
                "maintenance cost is very high. Consider whether the column needs to be "
                "indexed or if the query can be restructured. Index bloat is a real operational "
                "concern. In PostgreSQL, when rows are updated, the old index entries are not "
                "immediately removed (due to MVCC). Dead index entries accumulate until "
                "VACUUM removes them. On tables with heavy UPDATE workloads, indexes can "
                "bloat to 2-5x their ideal size, wasting space and slowing scans. Regular "
                "REINDEX or pg_repack can address this. Specialized index types worth "
                "mentioning in interviews: PostgreSQL GIN (Generalized Inverted Index) is "
                "used for full-text search (tsvector columns), JSONB containment queries, "
                "and array element lookups. GiST (Generalized Search Tree) handles spatial "
                "data (PostGIS geometry columns), range types, and nearest-neighbor searches. "
                "BRIN (Block Range Index) is extremely compact and works for naturally ordered "
                "data like timestamps in append-only tables. Partial indexes (WHERE clause on "
                "the index) index only a subset of rows: CREATE INDEX idx ON orders (user_id) "
                "WHERE status = 'pending' creates a tiny, fast index for just the pending "
                "orders. In interviews: 'I would not index the is_active boolean because it "
                "has only two values and poor selectivity. Instead, I would create a partial "
                "index on the active orders only, which is smaller, faster, and cheaper to "
                "maintain.'"
            ),
        },
    ],
    "real_world_examples": [
        "PostgreSQL B-tree is the default index type. A B-tree on 100M rows has height 3-4 and serves point lookups in under 1ms. Leaf nodes are linked for efficient range scans. GIN indexes power full-text search on tsvector columns, and GiST indexes power PostGIS spatial queries (find restaurants within 5km).",
        "MySQL InnoDB clustered index: the primary key determines physical row order. Auto-increment PKs give sequential writes (fast). UUID PKs cause random page splits (slow, up to 3x worse insert throughput). Secondary index lookups require a double traversal (secondary tree then primary key tree).",
        "MongoDB compound indexes follow the ESR rule (Equality, Sort, Range): put equality-match fields first, then sort fields, then range fields. MongoDB's explain() output shows queryPlanner.winningPlan.stage: IXSCAN vs COLLSCAN (index scan vs collection scan).",
        "DynamoDB: the primary key (partition key + optional sort key) is the only 'index' on the base table. Global Secondary Indexes (GSIs) project attributes to a separate table with a different partition/sort key, enabling alternative query patterns. Each GSI consumes its own read/write capacity.",
    ],
    "common_interview_questions": [
        "You have a slow query on a 50M row table. Walk me through your investigation process from EXPLAIN ANALYZE to index creation.",
        "What is the difference between a clustered and non-clustered index? Why does InnoDB's clustered index make UUID primary keys problematic?",
        "You have an index on (a, b, c). Which of these queries can use it: WHERE b = 1? WHERE a = 1 AND c = 3? WHERE a = 1 ORDER BY b?",
        "When would you NOT add an index? Give specific scenarios.",
        "Explain covering indexes. When would you use PostgreSQL's INCLUDE clause, and what is the trade-off?",
    ],
    "key_trade_offs": [
        "Read speed vs write speed: each additional index improves query performance but adds overhead to every INSERT, UPDATE, and DELETE. The right number of indexes depends on your read/write ratio. A read-heavy analytics workload can tolerate many indexes; a write-heavy logging workload should minimize them.",
        "B-tree (versatile: ranges, sorting, equality, prefix) vs hash index (O(1) equality only). B-tree is almost always the right default for on-disk databases. Hash wins only for in-memory stores with exclusively point-lookup workloads.",
        "Covering index (eliminates heap access, fastest possible reads) vs storage bloat (duplicates column data in the index). Worth it for high-frequency queries on hot paths; not worth it for rarely-run reports.",
        "Composite index (serves multiple query patterns with one index) vs multiple single-column indexes (simpler to understand but use more space, more write overhead, and the database must merge results via bitmap scans). Prefer composite indexes for known query patterns.",
    ],
    "common_mistakes": [
        "Creating individual indexes on every column instead of designing composite indexes that serve multiple query patterns. Five single-column indexes are worse than one well-designed composite index in almost every case.",
        "Ignoring the leftmost prefix rule: creating an index on (a, b, c) and expecting it to speed up WHERE b = 1 queries. It will not. The query must filter on the leading column(s).",
        "Using UUID primary keys in InnoDB without understanding the clustered index implications. Random UUIDs cause random writes into the middle of the B-tree, leading to constant page splits and fragmentation. Use UUIDv7 or auto-increment instead.",
        "Indexing low-cardinality columns (booleans, enums with 3 values) where the index has poor selectivity. The database will ignore the index and do a sequential scan anyway. Use partial indexes instead.",
    ],
    "interview_tips": [
        "When proposing a schema, immediately follow up with your indexing strategy. Say: 'For this orders table, I would create a composite index on (user_id, created_at) to support the user's order history query, with an INCLUDE on status for the dashboard view.' This shows you think about query access patterns, not just schema design.",
        "If asked about a slow query, start with EXPLAIN ANALYZE (PostgreSQL) or EXPLAIN (MySQL) and narrate what you see: 'I would look for Seq Scan on a large table, which means no index is being used. Then I would check if there is an index the planner is ignoring due to low selectivity or stale statistics.'",
        "Know the clustered index story cold. It comes up frequently: 'InnoDB stores rows in primary key order. This means range queries on the PK are sequential I/O (fast), but random PK values like UUIDs cause fragmentation. PostgreSQL does not have a clustered index by default; all indexes are secondary with TID pointers to the heap.'",
    ],
    "related_concepts": ["sharding", "caching", "cap_theorem"],
},

"message_queues": {
    "title": "Message Queues & Event-Driven Architecture",
    "introduction": (
        "Picture this scenario: a user places an order on an e-commerce site. The system "
        "needs to charge their credit card, update inventory, send a confirmation email, "
        "notify the warehouse, update the analytics dashboard, and trigger a recommendation "
        "engine update. If the order service calls each of these downstream services "
        "synchronously, one at a time, the user waits for all six operations to complete "
        "before seeing 'Order Confirmed.' If the email service is slow (2 seconds) or "
        "the analytics service is down, the entire order fails or hangs. This is tight "
        "coupling, and it is the number one architectural problem that message queues solve. "
        "With a message queue, the order service publishes an 'OrderPlaced' event and "
        "immediately returns success to the user. The payment service, inventory service, "
        "email service, and analytics service each consume the event independently, at "
        "their own pace. If the email service is down, the message sits in the queue "
        "until the service recovers. If a traffic spike sends 10x normal orders, the "
        "queue absorbs the burst and consumers process messages as fast as they can. "
        "This is the essence of event-driven architecture: decouple producers from "
        "consumers, absorb traffic spikes gracefully, enable independent scaling and "
        "deployment of services, and provide built-in retry semantics for failure recovery. "
        "The two fundamental paradigms are message queues (point-to-point: each message "
        "processed by exactly one consumer, used for work distribution) and event streams "
        "(pub/sub: each event delivered to all interested subscribers, used for event "
        "broadcasting and real-time data pipelines). The major technologies, Kafka, "
        "RabbitMQ, and SQS, represent fundamentally different architectures with different "
        "strengths. Kafka is a distributed commit log optimized for high-throughput event "
        "streaming. RabbitMQ is a traditional message broker with rich routing. SQS is a "
        "fully managed queue service with zero operational overhead. In this topic, you "
        "will learn the mechanical differences between queues and streams, deep dives into "
        "Kafka, RabbitMQ, and SQS, delivery guarantees and idempotency, backpressure "
        "handling, and the event sourcing and CQRS patterns."
    ),
    "key_concepts": [
        {
            "name": "Message Queue vs Event Stream: Fundamental Architecture Difference",
            "explanation": (
                "A message queue (RabbitMQ, SQS) follows the traditional broker model: "
                "producers send messages to the broker, the broker routes them to queues, "
                "and consumers pull messages from queues. Once a consumer acknowledges a "
                "message, it is deleted from the queue. The broker is responsible for "
                "routing, delivery guarantees, and message lifecycle. An event stream "
                "(Kafka, Amazon Kinesis, Apache Pulsar) follows the distributed log model: "
                "producers append events to an ordered, immutable log (topic). Consumers "
                "read from the log at their own offset (position). Critically, consuming "
                "a message does NOT delete it. Messages are retained for a configurable "
                "duration (hours, days, or forever with log compaction). This means multiple "
                "consumer groups can read the same data independently, and a new consumer "
                "can replay the entire history from the beginning. The practical implications "
                "are significant. With a message queue: once consumed, the message is gone. "
                "You cannot replay. If you add a new service that needs historical data, "
                "you need a separate mechanism. Routing is flexible (topic exchanges, header "
                "matching). Latency is typically lower for individual messages. With an event "
                "stream: messages persist. New consumers can start from any point in history. "
                "This enables event sourcing, change data capture, and stream processing. "
                "But routing is simpler (partition by key). The key interview distinction: "
                "'I would use a message queue like RabbitMQ or SQS when I need work "
                "distribution with flexible routing, like task processing or sending "
                "notifications. I would use an event stream like Kafka when I need a durable "
                "log that multiple services can independently consume, like an event bus "
                "for microservices or a real-time data pipeline.'"
            ),
        },
        {
            "name": "Kafka Deep Dive: Topics, Partitions, Consumer Groups, and Offsets",
            "explanation": (
                "Kafka organizes data into topics (logical categories like 'orders' or "
                "'user-clicks'). Each topic is divided into partitions, which are the unit "
                "of parallelism. A partition is an ordered, immutable sequence of records, "
                "each assigned a sequential offset number (0, 1, 2, ...). Producers write "
                "to partitions. By default, messages are round-robin across partitions. If "
                "you specify a partition key (e.g., user_id), all messages with the same key "
                "go to the same partition (via hash). This guarantees ordering per key: all "
                "events for user 123 arrive in order. Within a partition, order is strict. "
                "Across partitions, there is no ordering guarantee. Consumer groups enable "
                "parallel consumption. Each partition is assigned to exactly one consumer "
                "within a group. If a topic has 6 partitions and a consumer group has 3 "
                "consumers, each consumer reads 2 partitions. If you add a 4th consumer, "
                "Kafka rebalances: some consumers get 2 partitions, some get 1. If you have "
                "more consumers than partitions, the extras sit idle. This means the number "
                "of partitions sets the maximum parallelism for a consumer group. Multiple "
                "consumer groups can read the same topic independently: group 'analytics' "
                "and group 'notifications' each get all messages, tracking their own offsets. "
                "This is how Kafka achieves both point-to-point (one consumer group) and "
                "pub/sub (multiple consumer groups). Offsets are the consumer's position in "
                "a partition. Kafka stores committed offsets in an internal topic "
                "(__consumer_offsets). If a consumer crashes and restarts, it resumes from "
                "its last committed offset. Log compaction is an alternative retention policy: "
                "instead of deleting old messages by time, Kafka keeps only the latest "
                "message for each key. This is useful for maintaining a snapshot of current "
                "state (like the latest address for each customer). Throughput: a single "
                "Kafka broker can handle 100K-200K messages per second for small messages. "
                "A typical production cluster with 3-5 brokers handles 500K-1M messages/s. "
                "LinkedIn processes over 7 trillion messages per day through Kafka."
            ),
        },
        {
            "name": "RabbitMQ and SQS: Traditional Queuing",
            "explanation": (
                "RabbitMQ implements AMQP (Advanced Message Queuing Protocol) and offers "
                "rich routing through exchanges. Producers publish to an exchange (not "
                "directly to a queue). The exchange routes messages to queues based on "
                "bindings. Exchange types: Direct exchange routes by exact routing key match. "
                "A message with key 'order.created' goes to queues bound with that exact key. "
                "Topic exchange routes by pattern matching. A queue bound with 'order.*' "
                "receives 'order.created' and 'order.shipped.' Fanout exchange broadcasts to "
                "all bound queues regardless of routing key. Headers exchange routes based on "
                "message headers instead of routing key. Dead Letter Queues (DLQ) are "
                "critical for production reliability. When a message fails processing "
                "repeatedly (exceeds retry count) or expires (TTL), RabbitMQ moves it to "
                "a configured DLQ instead of discarding it. Operations engineers can inspect "
                "DLQ messages, debug the failure, fix the consumer, and replay the messages. "
                "Without DLQs, failed messages are silently lost. RabbitMQ throughput: "
                "typically 10K-50K messages/second per node, much lower than Kafka, but with "
                "richer per-message routing and lower latency for individual messages. "
                "Amazon SQS is a fully managed queue service. Standard SQS offers at-least-once "
                "delivery with best-effort ordering (messages may arrive out of order or be "
                "delivered twice). Throughput is virtually unlimited because AWS scales "
                "transparently. SQS FIFO guarantees exactly-once processing and strict "
                "ordering within a message group (identified by a MessageGroupId). FIFO "
                "throughput is limited to 300 messages/second per group (3000 with batching). "
                "Visibility timeout is the key SQS mechanism: when a consumer receives a "
                "message, it becomes invisible to other consumers for a configurable duration "
                "(default 30 seconds). If the consumer processes it and deletes it within "
                "that window, done. If the consumer crashes, the visibility timeout expires, "
                "and the message becomes visible again for another consumer to pick up. "
                "This provides automatic retry without any additional infrastructure. In "
                "interviews: 'SQS if I want zero ops overhead and my use case fits "
                "standard queuing. RabbitMQ if I need complex routing patterns. Kafka if "
                "I need a durable event log with replay capability.'"
            ),
        },
        {
            "name": "Delivery Guarantees and Idempotency",
            "explanation": (
                "There are three delivery guarantee levels, and understanding them is "
                "essential for system design interviews. At-most-once: the producer sends "
                "the message and does not retry on failure. The message may be lost (network "
                "error, broker crash) but will never be duplicated. Use case: metrics and "
                "logging where occasional data loss is acceptable. At-least-once: the "
                "producer retries until the broker acknowledges. If the acknowledgment is "
                "lost (broker received and stored the message but the ACK did not reach the "
                "producer), the producer retries, creating a duplicate. The consumer may "
                "see the same message more than once. This is the default in most systems "
                "(Kafka, RabbitMQ, SQS) because it is relatively simple to implement. "
                "Exactly-once: each message is processed exactly one time. This is the "
                "hardest guarantee and requires coordination between producer, broker, and "
                "consumer. Kafka achieves exactly-once semantics (EOS) through idempotent "
                "producers (each producer gets a unique ID, the broker deduplicates by "
                "sequence number) combined with transactional writes (produce to multiple "
                "partitions and commit offsets atomically). However, this only covers "
                "Kafka-to-Kafka processing. If the consumer has side effects outside Kafka "
                "(writing to a database, calling an API), exactly-once requires the consumer "
                "to be idempotent. Idempotency is the practical solution for at-least-once "
                "systems. An idempotent operation produces the same result whether applied "
                "once or multiple times. Techniques: (1) Idempotency keys: attach a unique "
                "ID to each message. Before processing, check if this ID has already been "
                "processed (using a database table or Redis set). If yes, skip. Stripe "
                "uses this for payment API calls. (2) Database upserts: INSERT ON CONFLICT "
                "UPDATE ensures the same record is not created twice. (3) Natural "
                "idempotency: some operations are inherently idempotent (SET balance = 500 "
                "is idempotent; ADD 500 TO balance is not). In interviews: 'I would use "
                "at-least-once delivery with idempotent consumers. Each message carries a "
                "unique event_id. The consumer checks a processed_events table before acting. "
                "This gives us effectively exactly-once semantics without the complexity and "
                "performance cost of true exactly-once protocols.'"
            ),
        },
        {
            "name": "Backpressure and Ordering Guarantees",
            "explanation": (
                "Backpressure occurs when producers generate messages faster than consumers "
                "can process them. Without handling backpressure, the queue grows unboundedly "
                "until it exhausts memory or disk, causing cascading failures. Strategies: "
                "(1) Buffer and absorb: the queue itself is the buffer. Kafka's on-disk log "
                "can hold terabytes of data, absorbing hours-long traffic spikes. SQS can "
                "hold up to 120,000 in-flight messages per standard queue. This works when "
                "spikes are temporary. (2) Scale consumers: add more consumer instances to "
                "increase throughput. In Kafka, add consumers up to the number of partitions. "
                "In SQS, add Lambda functions or EC2 instances. Auto-scaling policies can "
                "trigger based on queue depth (SQS ApproximateNumberOfMessagesVisible "
                "CloudWatch metric). (3) Rate limiting at the producer: if the queue is "
                "persistently full, the problem is a producer sending too fast. Apply rate "
                "limits or sampling at the source. (4) Shed load: drop low-priority messages "
                "when the queue exceeds a threshold. Use message priority queues (RabbitMQ "
                "supports priority) to ensure critical messages are processed first. "
                "Ordering guarantees vary by technology. Kafka guarantees strict ordering "
                "within a single partition but no ordering across partitions. To maintain "
                "ordering for a specific entity (all events for user 123), use the entity "
                "ID as the partition key. This pins all events for that entity to one "
                "partition, preserving order. SQS Standard offers best-effort ordering "
                "(frequently but not always in order). SQS FIFO guarantees strict ordering "
                "within a MessageGroupId. If you need strict global ordering across all "
                "messages, use a single partition (Kafka) or single message group (SQS FIFO), "
                "but this limits throughput to one consumer. The trade-off: ordering vs "
                "parallelism. In interviews: 'I would partition Kafka by user_id so all "
                "events for a user are strictly ordered. Cross-user ordering is not "
                "required for this use case, so I get both ordering and parallelism.'"
            ),
        },
        {
            "name": "Event Sourcing and CQRS",
            "explanation": (
                "Event Sourcing is an architectural pattern where state changes are stored "
                "as an immutable sequence of events rather than as mutable current state. "
                "Instead of storing 'account balance = $500' (current state), you store the "
                "events: 'deposited $1000', 'withdrew $300', 'deposited $200', 'withdrew $400.' "
                "The current balance is derived by replaying all events. This gives you a "
                "complete audit trail (every state change is recorded), the ability to "
                "reconstruct state at any point in time (replay events up to that timestamp), "
                "and the ability to add new projections (views) that process historical events "
                "retroactively. Kafka is a natural event store because its immutable log "
                "retains events and supports replay from any offset. The downside: reading "
                "current state requires replaying all events (slow for long histories). This "
                "is solved with snapshots: periodically save the current state, then replay "
                "only events after the snapshot. CQRS (Command Query Responsibility "
                "Segregation) separates the write model from the read model. Commands "
                "(writes) go to one data store optimized for writes. Queries (reads) go to "
                "a different data store optimized for reads. The read model is updated "
                "asynchronously from the write model, usually via events. For example, in "
                "an e-commerce system: the write model uses a normalized relational database "
                "(PostgreSQL) for orders with full ACID transactions. The read model uses "
                "a denormalized store (Elasticsearch for search, Redis for dashboards, "
                "DynamoDB for user-facing queries). When an order is placed, an 'OrderCreated' "
                "event is published. Multiple read-side projections consume this event and "
                "update their respective stores. The trade-off: CQRS introduces eventual "
                "consistency between write and read models (the read model lags behind the "
                "write model by the event propagation delay, typically milliseconds to "
                "seconds). It also adds architectural complexity: you have multiple data "
                "stores to maintain, event handlers that can fail, and eventual consistency "
                "semantics to communicate to users. In interviews, mention event sourcing "
                "and CQRS when the interviewer asks about audit trails, temporal queries, "
                "or systems with very different read and write patterns. Say: 'Since this "
                "system needs a complete audit trail and the read/write patterns are very "
                "different (simple writes, complex queries), I would use CQRS with event "
                "sourcing. Writes go to a normalized event store, and read-optimized "
                "projections are updated asynchronously via Kafka.'"
            ),
        },
    ],
    "real_world_examples": [
        "LinkedIn uses Kafka as its central nervous system, processing over 7 trillion messages per day across 100+ Kafka clusters. Every user action (profile view, message sent, connection request) is a Kafka event consumed by dozens of services: recommendations, notifications, analytics, search indexing, and ad targeting.",
        "Uber uses Kafka for real-time trip events. When a rider requests a ride, the event flows through Kafka to the matching service, pricing service, ETA service, and driver notification service. Kafka's partition-by-key (rider_id) ensures all events for a trip are ordered.",
        "Shopify uses RabbitMQ for background job processing: sending order confirmation emails, generating invoices, updating inventory counts, and notifying third-party fulfillment services. RabbitMQ's routing exchanges let Shopify route different order events to different processing queues.",
        "AWS Lambda with SQS: a common serverless pattern where SQS triggers Lambda functions automatically. Lambda scales to match queue depth (up to 1000 concurrent executions by default). Failed messages go to a DLQ. Zero server management, pay-per-message pricing.",
    ],
    "common_interview_questions": [
        "Why use a message queue instead of direct synchronous API calls between services? What problems does async processing introduce?",
        "Compare Kafka and RabbitMQ. When would you choose each? Be specific about the architectural differences, not just throughput numbers.",
        "How would you ensure exactly-once processing in a system that writes to both Kafka and a PostgreSQL database? Explain the idempotency pattern.",
        "A consumer is falling behind and the queue depth is growing. Walk me through your investigation and remediation steps.",
        "Design a notification system that sends emails, push notifications, and SMS for an e-commerce order. Which messaging technology and patterns would you use?",
    ],
    "key_trade_offs": [
        "Kafka (distributed log, high throughput, message retention, replay capability, partition-based parallelism) vs RabbitMQ (traditional broker, rich routing with exchanges, lower latency per message, simpler for task queues, messages deleted after consumption). Choose based on whether you need a durable event log or flexible task routing.",
        "At-least-once delivery with idempotent consumers (simple, practical, the industry standard) vs exactly-once semantics (theoretically correct but complex, performance overhead, Kafka EOS only covers Kafka-to-Kafka). Almost every production system uses at-least-once with idempotency keys.",
        "More Kafka partitions enable more parallel consumers and higher throughput, but increase rebalancing time when consumers join/leave, complicate ordering guarantees (ordering only within a partition), and use more file handles and memory on brokers. Start with enough partitions for near-term needs and scale up (you can add partitions but not remove them).",
        "Synchronous processing (simple, easy to debug, immediate feedback to user) vs asynchronous event-driven processing (decoupled, resilient, scalable, but introduces eventual consistency, harder to debug, requires idempotency). Use sync for the critical path (charge credit card) and async for everything else (send email, update analytics).",
    ],
    "common_mistakes": [
        "Treating Kafka like a message queue (expecting message deletion after consumption) or treating RabbitMQ like an event stream (expecting message replay). They are fundamentally different architectures solving different problems.",
        "Ignoring idempotency: assuming at-least-once delivery means messages will only be delivered once. Network issues, consumer crashes, and rebalances all cause redelivery. Every consumer must handle duplicate messages safely.",
        "Setting the number of Kafka partitions equal to the current number of consumers. Partitions cannot be decreased later, so set them higher than current needs. A good starting point is 3x your expected consumer count.",
        "Using a single message queue for both critical and non-critical work without priority. A flood of analytics events should not block payment confirmation emails. Use separate queues or priority queuing.",
    ],
    "interview_tips": [
        "When designing any system with multiple services, proactively introduce a message queue: 'The order service should not directly call the email, inventory, and analytics services. I would publish an OrderPlaced event to Kafka. Each downstream service consumes independently. This decouples them and provides natural retry semantics.' Interviewers look for this architectural instinct.",
        "Know the partition key selection reasoning: 'I would partition by user_id so all events for a user are ordered. This means I can have 12 partitions and 12 consumers for parallel processing while maintaining per-user event ordering.' This shows you understand the ordering-vs-parallelism trade-off.",
        "When asked about exactly-once, give the practical answer: 'True exactly-once is expensive and complex. In practice, I use at-least-once delivery with an idempotency key. Each event has a unique UUID. The consumer checks a processed_events table before processing. This gives effectively exactly-once behavior with much simpler implementation.'",
    ],
    "related_concepts": ["api_design", "cap_theorem", "sharding"],
},

"numbers_to_know": {
    "title": "Numbers Every Engineer Should Know",
    "introduction": (
        "In a system design interview, the interviewer says: 'Design a photo-sharing "
        "service like Instagram with 500 million daily active users.' You need to quickly "
        "estimate: how many photos are uploaded per day, how much storage that requires "
        "per year, what the peak QPS looks like, and whether a single database server "
        "can handle it. If you cannot do these calculations quickly and roughly correctly, "
        "your design will be either wildly over-engineered or hopelessly under-provisioned. "
        "Back-of-envelope estimation is a core system design skill. Interviewers use it "
        "to test whether you have practical intuition about system scale. A candidate who "
        "says 'I would use a single PostgreSQL server' for a system with 100K QPS has no "
        "sense of scale. A candidate who says 'I need 1000 servers' for a system with 100 "
        "QPS is over-engineering. The numbers in this topic are the building blocks of "
        "capacity estimation. You need to know three categories: latency numbers (how long "
        "operations take at different levels of the storage hierarchy and network), "
        "throughput numbers (how many operations per second various components can handle), "
        "and storage numbers (how large common data types are). With these building blocks, "
        "you can estimate any system's capacity requirements in 2-3 minutes. The technique "
        "is not about precision. Getting within 2-5x of the correct answer is sufficient. "
        "The goal is to identify which components are bottlenecks and need special attention "
        "in your design. If your estimate shows 50K QPS and a single database handles 5K "
        "QPS, you know you need sharding or caching. If your estimate shows 10 TB of "
        "storage per year and each server has 1 TB, you know you need distributed storage. "
        "These numbers also help you call out unrealistic assumptions: if someone says "
        "'just put it all in Redis' for 50 TB of data, you know that is not feasible "
        "(Redis is in-memory and 50 TB of RAM would cost millions). In this topic, you "
        "will memorize the essential latency hierarchy, throughput baselines, storage "
        "estimates for common data types, the power-of-2 table, and learn a systematic "
        "technique for back-of-envelope calculations with worked examples."
    ),
    "key_concepts": [
        {
            "name": "Latency Numbers: The Memory and Storage Hierarchy",
            "explanation": (
                "Every engineer should have the following latency numbers memorized, because "
                "they determine which storage layer is appropriate for each part of your "
                "system. L1 cache reference: approximately 1 nanosecond. This is the fastest "
                "storage available, located on the CPU die itself. L1 cache is typically "
                "32-64 KB per core. You cannot control what goes here (the CPU manages it), "
                "but it explains why hot loops on small data are incredibly fast. L2 cache "
                "reference: approximately 4 nanoseconds. Larger than L1 (256 KB - 1 MB per "
                "core), still on-chip but further from the execution units. L3 cache "
                "reference: approximately 10-20 nanoseconds. Shared across all cores, "
                "typically 8-64 MB. This is the last level of CPU cache before main memory. "
                "Main memory (RAM) reference: approximately 100 nanoseconds. This is where "
                "Redis, Memcached, and in-memory database data lives. 100ns is roughly 100x "
                "slower than L1 cache but still extremely fast compared to any disk I/O. "
                "A server with 256 GB of RAM can serve reads in ~100ns, which translates to "
                "millions of operations per second. SSD random read: approximately 100 "
                "microseconds (100,000 ns). This is 1000x slower than RAM. SSDs have no "
                "seek time (unlike HDDs) but still require I/O bus traversal. A good NVMe "
                "SSD handles 100K-500K random read IOPS. SSD sequential read 1 MB: "
                "approximately 1 millisecond. Sequential reads on SSD are much faster than "
                "random because they avoid the per-I/O overhead. A modern NVMe SSD reads "
                "sequentially at 2-7 GB/s. This is why B-tree range scans (sequential leaf "
                "traversal) are so much faster than random lookups. HDD seek: approximately "
                "10 milliseconds. HDDs must physically move a read/write head to the correct "
                "track, making random access extremely expensive. HDDs are still used for "
                "cold storage and archival because they cost roughly $20/TB vs $100/TB for "
                "SSD. Network round-trip within same datacenter: approximately 0.5 "
                "milliseconds. This is the cost of one hop between services in the same "
                "availability zone. Cross-region network round-trip: approximately 50-150 "
                "milliseconds. US East to US West is roughly 60-80ms. US to Europe is "
                "roughly 80-120ms. US to Asia is roughly 150-250ms. This number dominates "
                "the design of globally distributed systems and is why CDNs exist. The key "
                "insight: there are roughly 10x jumps between each layer. L1 (1ns) -> RAM "
                "(100ns, 100x) -> SSD random (100us, 1000x) -> HDD seek (10ms, 100x) -> "
                "cross-region network (100ms, 10x). Memorize these orders of magnitude and "
                "you can estimate any system's latency profile."
            ),
        },
        {
            "name": "Throughput Numbers: What Can a Single Machine Handle?",
            "explanation": (
                "Knowing what a single server can handle tells you when you need to scale "
                "horizontally. These are approximate baselines that vary with hardware, "
                "workload, and configuration, but they are good starting points for "
                "estimation. Web server (simple request handling): a single server running "
                "Nginx or a lightweight application server can handle 10K-50K simple HTTP "
                "requests per second (returning a cached response, serving a static file, "
                "or doing minimal computation). If the request requires database access, "
                "the bottleneck shifts to the database. Application server (with business "
                "logic): a single instance of a typical web framework (Django, Rails, "
                "Spring Boot) handles 500-5,000 requests per second depending on complexity. "
                "Compute-heavy operations (image processing, ML inference) drop this to "
                "tens or hundreds per second. Relational database (PostgreSQL, MySQL): "
                "5K-20K simple queries per second per server. Simple means index lookups "
                "and single-row inserts. Complex analytical queries can drop throughput to "
                "tens per second. Read-heavy workloads with good indexing and caching are "
                "at the higher end. Write-heavy workloads are at the lower end because "
                "writes require WAL logging, index updates, and fsync. Redis (in-memory): "
                "100K-300K operations per second per instance for simple GET/SET commands. "
                "This is why Redis is used for caching, session stores, and rate limiting. "
                "Complex Redis operations (sorted set range queries, Lua scripts) reduce "
                "this. Kafka (single broker): 100K-200K messages per second for small "
                "messages (1 KB). A cluster of 5 brokers handles 500K-1M messages/second. "
                "For interview estimation: if your system needs X QPS, and a single database "
                "handles 10K QPS, you need at least ceil(X / 10K) database instances "
                "(ignoring replication). If X = 100K, you need 10 database shards. A common "
                "pattern: Redis cache in front of the database absorbs 80-95% of reads. "
                "If your read QPS is 100K but 90% hits the cache (Redis: 200K ops/s), "
                "only 10K reads hit the database (within a single instance's capacity). "
                "This cache-in-front arithmetic is a critical interview skill."
            ),
        },
        {
            "name": "Storage Numbers: How Big Is Common Data?",
            "explanation": (
                "Accurate storage estimation requires knowing the size of common data types. "
                "These are the essential numbers. Text data: a single character in UTF-8 is "
                "1 byte (ASCII) or 1-4 bytes (international characters). A tweet (280 "
                "characters) is roughly 280-400 bytes including metadata (user_id, timestamp, "
                "tweet_id). A typical JSON API response is 1-10 KB. An average email is "
                "roughly 50-100 KB including headers. Image data: a smartphone photo (JPEG, "
                "12MP) is roughly 2-5 MB. A compressed thumbnail (200x200) is roughly 10-30 "
                "KB. A profile picture (500x500, JPEG, optimized) is roughly 50-200 KB. "
                "A high-resolution photo for a photo-sharing service, stored at multiple "
                "sizes (thumbnail + medium + original), averages roughly 2-3 MB total across "
                "all sizes. Video data: a minute of compressed video at 720p is roughly "
                "50-100 MB (depending on codec and bitrate). At 1080p, roughly 100-200 MB. "
                "At 4K, roughly 300-500 MB per minute. A 10-second short-form video (TikTok "
                "style) at 1080p is roughly 15-30 MB. Streaming services encode multiple "
                "quality levels, roughly 3-5x the single-stream size for all bitrate "
                "versions. Database row sizes: a typical user profile row (id, name, email, "
                "created_at, a few fields) is roughly 200-500 bytes. An order row with "
                "typical fields is roughly 200-1000 bytes. A database with 100M users at "
                "500 bytes per row uses roughly 50 GB of raw data, plus 50-100% overhead "
                "for indexes, MVCC versioning, and free space. Log data: a single structured "
                "log line (JSON format) is roughly 200-500 bytes. A server generating 1000 "
                "log lines per second produces 200-500 KB/s, which is roughly 20-40 GB per "
                "day per server. These numbers are the building blocks. When an interviewer "
                "says 'design Instagram,' you immediately think: 500M DAU, maybe 10% upload "
                "daily, 1 photo each, 3 MB average = 50M * 3 MB = 150 TB per day. That is "
                "the storage growth rate, and it tells you immediately that you need "
                "distributed object storage (S3), not a database."
            ),
        },
        {
            "name": "Powers of 2 and Quick Conversion Table",
            "explanation": (
                "The powers of 2 are the fundamental unit conversions for computer science. "
                "Memorize these: 2^10 = 1,024, approximately 1 Thousand (1 KB). 2^20 = "
                "1,048,576, approximately 1 Million (1 MB). 2^30 = 1,073,741,824, "
                "approximately 1 Billion (1 GB). 2^40 = approximately 1 Trillion (1 TB). "
                "2^50 = approximately 1 Quadrillion (1 PB). For estimation purposes, treat "
                "2^10 as exactly 1000. This gives you fast conversions: 1 GB = 10^9 bytes. "
                "1 TB = 10^12 bytes. The error from this approximation is only 2.4% at "
                "each level, which is well within estimation accuracy. Time conversions "
                "you should memorize: 1 day = 86,400 seconds, approximately 10^5 seconds "
                "(use 86,400 or round to 100K for quick math). 1 month approximately 2.5 "
                "million seconds. 1 year approximately 31.5 million seconds, approximately "
                "3 * 10^7 seconds. The most common calculation in system design interviews "
                "is converting daily active users and actions to QPS (queries per second): "
                "QPS = (DAU * actions_per_user) / seconds_per_day. For 100M DAU with 10 "
                "actions each: 100M * 10 / 86,400 = 1B / 86,400 approximately 12K QPS "
                "average. Peak QPS is typically 2-3x average (during peak hours, traffic "
                "concentrates into a few hours rather than spreading across 24). So peak "
                "is roughly 24K-36K QPS. Another useful rule: 1 million requests per day "
                "is approximately 12 QPS. This is a quick conversion factor: just divide "
                "daily requests by 100K. 500M requests/day = 5K QPS average. These rules "
                "let you do capacity math in your head during an interview without pulling "
                "out a calculator. Practice until the conversions are instant: 'Our system "
                "has 200M DAU, each makes 5 requests. That is 1B requests per day, which "
                "is about 12K QPS average, 36K peak.'"
            ),
        },
        {
            "name": "Back-of-Envelope Estimation Technique",
            "explanation": (
                "The technique for back-of-envelope estimation follows a systematic four-step "
                "process. Step 1: Clarify the scope. What are we estimating? Storage, QPS, "
                "bandwidth, number of servers? What is the time horizon (per day, per year)? "
                "Step 2: State your assumptions explicitly. 'I will assume 500M DAU, 10% "
                "upload photos daily, average photo size 3 MB, 3x peak-to-average ratio.' "
                "Write these down. The interviewer can correct them if they are unreasonable, "
                "and it shows your methodology is sound. Step 3: Do the arithmetic. Use "
                "round numbers aggressively. 500M * 0.1 = 50M photos/day. 50M * 3 MB = "
                "150 TB/day. 150 TB * 365 = approximately 55 PB/year. For QPS: 50M uploads "
                "/ 86,400 seconds = approximately 600 uploads/second average, 1,800/second "
                "peak. For read QPS (users browsing): 500M * 20 views/day = 10B/day = "
                "approximately 120K QPS average, 360K peak. Step 4: Interpret the results "
                "and draw design conclusions. '55 PB per year means we need object storage "
                "(S3, GCS) not a database for photos. 120K read QPS means we need a CDN "
                "for serving images (a single server cannot handle this) and a caching layer "
                "in front of our metadata database. 600 upload QPS is manageable with a "
                "handful of upload servers, but we need to think about writing metadata "
                "to the database under this load.' The interpretation step is where you "
                "demonstrate engineering judgment. The raw numbers are just inputs to design "
                "decisions. Always sanity-check your results: does 55 PB/year sound "
                "reasonable for a service like Instagram? Instagram reportedly stores over "
                "100 PB as of recent years, so yes, this is in the right ballpark for a "
                "service that has been running for 10+ years with growing user base. If "
                "your estimate gave 55 EB (exabytes), you would know something is off by "
                "several orders of magnitude."
            ),
        },
        {
            "name": "Worked Example: Estimate Storage for a URL Shortener",
            "explanation": (
                "Let us work through a complete estimation to demonstrate the technique. "
                "Problem: estimate the storage requirements for a URL shortener service "
                "(like bit.ly) for 5 years. Step 1: Scope. We need to estimate: storage "
                "for URL mappings and QPS for reads and writes. Step 2: Assumptions. "
                "100M new URLs shortened per month (bit.ly reportedly handles about 600M "
                "clicks per month, with roughly 100M new links created). Each shortened URL "
                "record contains: short_code (7 characters = 7 bytes), original_url "
                "(average 100 characters = 100 bytes), user_id (8 bytes, bigint), "
                "created_at (8 bytes, timestamp), click_count (4 bytes, integer). Total "
                "per record approximately 130 bytes. Add 50% overhead for database internals "
                "(indexes, page headers, MVCC, free space) = approximately 200 bytes per "
                "record stored. Step 3: Arithmetic. Records per year: 100M/month * 12 = "
                "1.2B per year. Records over 5 years: 6B records. Storage: 6B * 200 bytes "
                "= 1.2 TB. That fits on a single modern server's SSD with room to spare. "
                "QPS for writes: 100M / month = 100M / (30 * 86400) = approximately 40 "
                "writes/second average. Peak: approximately 120/second. This is trivial "
                "for a single database. QPS for reads (redirects): assume 100:1 read:write "
                "ratio (most links are clicked many times). 40 * 100 = 4,000 reads/second "
                "average. Peak: approximately 12,000/second. This is within a single "
                "PostgreSQL server's capacity with proper indexing, but a Redis cache in "
                "front would reduce database load significantly. Step 4: Design conclusions. "
                "'1.2 TB of data fits on a single machine, so we do not need sharding for "
                "storage. 12K peak read QPS is handleable with a single database plus Redis "
                "cache (cache hit rate for popular links will be very high). The system is "
                "read-heavy (100:1), so I would optimize for reads with caching and a B-tree "
                "index on the short_code column. A Redis cache with LRU eviction for hot "
                "links would absorb 90%+ of reads.' This example shows how the numbers "
                "drive design decisions: we proved we do not need sharding, identified the "
                "need for caching, and quantified the read/write asymmetry."
            ),
        },
    ],
    "real_world_examples": [
        "Google serves approximately 8.5 billion search queries per day (2024), which is roughly 100K QPS average. Each query touches an inverted index spread across thousands of servers, with results returned in under 500ms. The search index alone is estimated at hundreds of petabytes.",
        "Netflix streams to roughly 230M subscribers. During peak evening hours in a region, a single popular show can generate millions of concurrent streams. Netflix uses a CDN (Open Connect) that caches content at ISP locations to serve video within ~1ms of the viewer, avoiding cross-network latency entirely.",
        "Twitter (X) handled approximately 500M tweets per day at peak, which is roughly 6K writes/second average. But the read amplification is massive: each tweet is delivered to potentially millions of followers' timelines. The fan-out on write approach means a single celebrity tweet (50M followers) generates 50M cache writes.",
        "Amazon processes roughly 66K orders per minute during peak Prime Day, which is approximately 1.1K orders/second. Each order triggers inventory updates, payment processing, warehouse routing, and notification events, creating 10-20x amplification in downstream service calls.",
    ],
    "common_interview_questions": [
        "Estimate the storage requirements for YouTube video uploads for one year. State your assumptions clearly.",
        "A system has 200M DAU with an average of 5 API calls per user per day. What is the average and peak QPS? Can a single server handle this?",
        "Estimate the bandwidth needed to serve 1 million concurrent video streams at 1080p.",
        "How many servers do you need if each handles 10K QPS and your peak load is 500K QPS? What about with a 90% cache hit rate?",
        "Walk me through an estimation for the total database storage needed for a messaging app like WhatsApp with 2 billion users.",
    ],
    "key_trade_offs": [
        "Precision vs speed: in an interview, getting within 2-5x of the real answer in 2 minutes is better than spending 10 minutes on exact calculations. Use round numbers aggressively (86,400 seconds/day rounds to 100K for quick mental math).",
        "Over-provisioning (more servers than needed, higher cost, simpler architecture) vs right-sizing (cheaper but requires careful capacity planning and risks under-provisioning during traffic spikes). Most systems over-provision by 2-3x for headroom.",
        "Horizontal scaling (add more machines, linear cost growth, requires distributed system complexity) vs vertical scaling (bigger machine, simpler architecture, hits hardware limits). The numbers tell you when you have crossed the vertical scaling threshold.",
        "Caching (reduces load on expensive components, but adds complexity and consistency challenges) vs raw compute scaling (simpler but more expensive). The numbers from this topic help you calculate whether caching is necessary or if the base system can handle the load directly.",
    ],
    "common_mistakes": [
        "Forgetting the peak-to-average ratio. Average QPS is not the number you design for. Peak is typically 2-3x average (concentrated during business hours or evenings). Design for peak or your system falls over during rush hour.",
        "Confusing storage with bandwidth. '10 TB of data' and '10 TB per day of transfer' are completely different engineering problems. Storage is a capacity question (how many disks). Bandwidth is a throughput question (how many network links).",
        "Using overly precise numbers that create a false sense of accuracy. Saying '11,574 QPS' implies precision that does not exist in an estimation. Say '12K QPS' or 'roughly 10K QPS.' The assumptions have far more error than the arithmetic.",
        "Not interpreting the numbers into design decisions. The estimation is not the end product; it is input to architectural choices. Always conclude with: 'This means we need X' or 'This is within a single server's capacity, so we do not need Y.'",
    ],
    "interview_tips": [
        "Memorize these anchor numbers cold: RAM access = 100ns, SSD random read = 100us, cross-region network = 100ms. Single database = 10K QPS for simple queries. Single Redis = 200K ops/s. 1M requests per day = 12 QPS. 1 day = 86,400 seconds. With these anchors you can estimate any system.",
        "Always state assumptions explicitly before calculating: 'I am assuming 500M DAU, 10% are active uploaders, average upload is 3 MB.' This shows methodology and lets the interviewer course-correct if your assumptions are off. It also buys you time to think while you write.",
        "End every estimation with a design implication: 'So peak QPS is 36K, which means a single PostgreSQL instance at 10K QPS is not enough. I would add a Redis cache layer, which handles 200K ops/s. With a 90% cache hit rate, only 3.6K QPS hits the database, which is well within capacity.' The interviewer is testing whether you can connect numbers to architecture, not whether you can multiply.",
    ],
    "related_concepts": ["caching", "sharding", "database_indexing", "cap_theorem"],
},
    "redis": {
    "title": "Redis Deep Dive",
    "introduction": (
        "Redis (Remote Dictionary Server) is an open-source, in-memory data structure store that serves as a "
        "database, cache, message broker, and streaming engine. The critical insight for interviews is that Redis "
        "is not just a cache — it is a full-featured data structure server that provides atomic operations on "
        "rich types like sorted sets, bitmaps, hyperloglogs, and streams. Redis stores all data in RAM, which "
        "gives it sub-millisecond latency and throughput exceeding 100,000 operations per second on a single "
        "instance. It achieves this with a single-threaded event loop (using I/O multiplexing via epoll/kqueue), "
        "which eliminates locking overhead entirely — every operation is atomic by definition. This single-threaded "
        "model is counterintuitive but extremely effective: the bottleneck is almost never CPU but rather memory "
        "bandwidth and network I/O. Redis 6+ introduced I/O threading for network read/write, but command "
        "execution remains single-threaded. You would reach for Redis when you need microsecond-level latency "
        "for read-heavy workloads, need atomic operations on complex data structures (leaderboards, rate limiters, "
        "session stores), or need a shared state layer between multiple application servers. Redis is not the "
        "right choice when your dataset exceeds available RAM, when you need complex query capabilities (joins, "
        "aggregations across keys), or when you require strong durability guarantees — a crash between persistence "
        "snapshots means data loss. In system design interviews, Redis appears in nearly every design as either "
        "a caching layer, a session store, a rate limiter, or a real-time component. Understanding its data "
        "structures and their time complexities is essential."
    ),
    "key_concepts": [
        {
            "name": "Core Data Structures and Their Use Cases",
            "explanation": (
                "Redis provides five fundamental data structures, each with specific use cases and performance "
                "characteristics. Strings are the simplest — binary-safe sequences up to 512MB. Use them for "
                "caching serialized objects, counters (INCR/DECR are atomic), and distributed locks (SET NX EX). "
                "Hashes map field-value pairs under a single key, perfect for representing objects: HSET user:1001 "
                "name 'Alice' email 'alice@example.com'. Hashes are memory-efficient for small objects because Redis "
                "uses a compact ziplist encoding when the hash has fewer than ~128 fields. Lists are doubly-linked "
                "lists supporting O(1) push/pop at both ends (LPUSH, RPUSH, LPOP, RPOP). Use them for message "
                "queues (LPUSH + BRPOP for blocking consumer), activity feeds (LPUSH new items, LTRIM to cap "
                "length), and recent-items lists. Sets are unordered collections of unique strings with O(1) "
                "add/remove/membership-check. Use them for tracking unique visitors (SADD, SCARD), tagging systems, "
                "and computing intersections/unions across sets (SINTER, SUNION) — for example, finding mutual "
                "friends. Sorted Sets (ZSETs) are the most powerful structure: each member has a score, and the "
                "set is ordered by score. ZADD is O(log N), ZRANGE and ZRANK are efficient. Use sorted sets for "
                "leaderboards (score = points, ZREVRANGE for top N), priority queues (score = timestamp), and "
                "sliding-window rate limiters (score = request timestamp, ZRANGEBYSCORE to count requests in window)."
            ),
        },
        {
            "name": "Advanced Data Structures: HyperLogLog, Bloom Filters, and Geo",
            "explanation": (
                "Redis includes probabilistic and specialized data structures that solve problems at scale with "
                "minimal memory. HyperLogLog (HLL) estimates the cardinality (count of distinct elements) of a "
                "set using only 12KB of memory regardless of the number of elements. PFADD adds an element, "
                "PFCOUNT returns the approximate count with a standard error of 0.81%. Use HLL for counting "
                "unique page views, unique IP addresses, or unique search queries — anywhere you need 'how many "
                "distinct X?' without storing every X. Bloom Filters (available via the RedisBloom module) answer "
                "'is X in the set?' with no false negatives and a configurable false positive rate. They use far "
                "less memory than storing the actual set. Use them to check if a username is taken before hitting "
                "the database, to filter out previously-seen items in a recommendation engine, or to avoid "
                "unnecessary disk lookups (LSM-tree databases like Cassandra use Bloom filters for exactly this). "
                "Geo Indexes (GEOADD, GEODIST, GEOSEARCH) store latitude/longitude pairs and support radius "
                "queries. Under the hood, Redis encodes coordinates into a sorted set using geohash, so geo "
                "queries are O(N+log(M)) where N is the number of results and M is total elements. Use them for "
                "'find restaurants within 5km' or 'show nearby drivers' features. The key interview insight is "
                "knowing when to reach for these specialized structures instead of building something from scratch."
            ),
        },
        {
            "name": "Persistence: RDB Snapshots vs AOF",
            "explanation": (
                "Redis is in-memory, but it provides two persistence mechanisms to survive restarts. RDB (Redis "
                "Database Backup) creates point-in-time snapshots at configured intervals (e.g., every 5 minutes "
                "if at least 100 keys changed). Redis forks the process and the child writes the snapshot to disk "
                "while the parent continues serving requests — this uses copy-on-write semantics from the OS. "
                "RDB files are compact and fast to load on restart, but you can lose the last few minutes of data "
                "since the last snapshot. AOF (Append Only File) logs every write command. You configure the fsync "
                "policy: 'always' (safest, slowest — fsync every command), 'everysec' (recommended — fsync once "
                "per second, lose at most 1 second of data), or 'no' (let the OS decide). AOF files grow over "
                "time, so Redis periodically rewrites them — compacting the log into the minimal set of commands "
                "to reproduce the current state. The best practice is to use both: AOF for durability with everysec "
                "fsync, and RDB for fast backup/restore. In interviews, the trade-off to articulate is: RDB is "
                "better for disaster recovery (compact, fast restore) while AOF is better for durability (minimal "
                "data loss). Neither provides the ACID guarantees of a traditional database — if you need true "
                "durability, Redis is the wrong tool for your source of truth."
            ),
        },
        {
            "name": "Redis Cluster: Horizontal Scaling",
            "explanation": (
                "A single Redis instance is limited by the memory of one machine. Redis Cluster provides automatic "
                "data sharding across multiple nodes. The key space is divided into 16,384 hash slots. Each key "
                "is assigned to a slot via CRC16(key) mod 16384, and each master node owns a subset of these "
                "slots. A typical production cluster has 3 masters and 3 replicas (one replica per master for "
                "failover). When you add or remove nodes, you reshard by moving hash slots between nodes — Redis "
                "Cluster handles the migration transparently, redirecting clients with MOVED and ASK responses. "
                "Multi-key operations (MGET, transactions) only work when all keys map to the same slot. You can "
                "force this by using hash tags: keys named {user:1001}.profile and {user:1001}.settings both hash "
                "on 'user:1001' and land on the same slot. The cluster uses a gossip protocol for node discovery "
                "and failure detection. If a master fails, its replica is promoted automatically (similar to "
                "Raft-style leader election). The trade-offs to know: cluster mode adds latency for cross-slot "
                "operations, requires more careful key design to co-locate related data, and some commands (like "
                "KEYS, which scans all keys) do not work across the cluster. Alternatives to Redis Cluster include "
                "client-side sharding (the application decides which instance to talk to) and proxy-based sharding "
                "(Twemproxy, Codis), each with their own trade-offs."
            ),
        },
        {
            "name": "Five Key Use Cases with Concrete Implementation",
            "explanation": (
                "First, caching with TTL: SET user:1001:profile '{json}' EX 3600 caches a user profile for one "
                "hour. On cache miss, read from PostgreSQL, write to Redis. Use cache-aside pattern. Thundering "
                "herd mitigation: use a short lock (SET lock:user:1001 NX EX 5) so only one request rebuilds the "
                "cache. Second, distributed locking with the Redlock algorithm: acquire locks on N/2+1 independent "
                "Redis instances with the same random token and a TTL. If the majority succeeds within the TTL, "
                "the lock is acquired. Release by checking the token and deleting (Lua script for atomicity). "
                "Redlock is controversial — Martin Kleppmann argued it is unsafe under clock skew and GC pauses — "
                "but it is widely used and expected knowledge in interviews. Third, leaderboards with sorted sets: "
                "ZADD leaderboard 1500 'player:42' updates a score. ZREVRANGE leaderboard 0 9 WITHSCORES returns "
                "the top 10. ZRANK leaderboard 'player:42' returns a player's rank. All operations are O(log N). "
                "Fourth, rate limiting with a sliding window: for each user, use a sorted set where each request "
                "adds ZADD rate:user:42 <timestamp> <unique_id>, then ZREMRANGEBYSCORE to remove entries outside "
                "the window, and ZCARD to count remaining entries. If count exceeds the limit, reject. This gives "
                "a precise sliding window. Fifth, Pub/Sub for real-time notifications: PUBLISH channel:chat:room1 "
                "'message' broadcasts to all subscribers. SUBSCRIBE channel:chat:room1 blocks and receives "
                "messages. Limitation: Pub/Sub has no persistence — if a subscriber is disconnected, messages are "
                "lost. For durable messaging, use Redis Streams (XADD/XREADGROUP) instead, which provides "
                "consumer groups, acknowledgment, and persistence."
            ),
        },
        {
            "name": "Performance Characteristics and Limitations",
            "explanation": (
                "Redis benchmarks show 100,000 to 200,000+ operations per second on a single instance for simple "
                "GET/SET operations with typical latency under 1 millisecond. Pipeline mode (batching multiple "
                "commands in a single round trip) can push throughput to 500,000+ ops/sec by amortizing network "
                "latency. Lua scripting executes atomically on the server, avoiding round trips for multi-step "
                "operations. The single-threaded model means a slow command (like KEYS * on a million keys, or "
                "SORT on a large list) blocks all other clients. Use SCAN instead of KEYS, and avoid O(N) commands "
                "on large collections in production. Memory management is critical: Redis uses jemalloc, and "
                "memory fragmentation can cause actual memory usage to exceed the dataset size. Set maxmemory and "
                "choose an eviction policy (allkeys-lru is the most common for caching). When NOT to use Redis: "
                "when your dataset is larger than available RAM (Redis stores everything in memory — unlike "
                "databases with disk-based storage), when you need complex querying capabilities (joins, "
                "aggregations, full-text search across fields), when you need strong durability guarantees for "
                "financial transactions, or when you need ACID transactions across multiple keys on different "
                "slots. Redis is a complement to your primary database, not a replacement for it."
            ),
        },
    ],
    "real_world_examples": [
        "Twitter uses Redis to store timeline caches — each user's home timeline is a Redis list of tweet IDs, with LPUSH for new tweets and LTRIM to cap at 800 entries",
        "GitHub uses Redis sorted sets for trending repository rankings, with scores based on stars/forks weighted by recency",
        "Snapchat uses Redis for rate limiting API requests per user, implementing a sliding window counter with sorted sets",
        "Instagram uses Redis to store 300 million user session mappings, using simple key-value pairs with TTL for automatic expiry",
        "Stripe uses Redis as a distributed lock coordinator (Redlock pattern) to prevent double-charging during payment processing",
    ],
    "common_interview_questions": [
        "How would you implement a rate limiter using Redis? (Sliding window with sorted sets vs token bucket with INCR + EXPIRE)",
        "Redis is single-threaded — how does it achieve such high throughput? (I/O multiplexing, no locking, in-memory, efficient data structures)",
        "How does Redis Cluster handle a node failure? (Replica promotion, gossip protocol, client redirection with MOVED)",
        "Compare cache-aside vs write-through when using Redis as a cache. When would you choose each?",
        "How would you implement a distributed lock with Redis? What are the failure modes? (Redlock algorithm, clock skew, GC pauses, fencing tokens)",
        "Your Redis instance is running out of memory. What are your options? (Eviction policy, cluster sharding, data model optimization, move cold data to disk-based store)",
    ],
    "key_trade_offs": [
        "Speed (in-memory, sub-ms latency) vs durability (crash = potential data loss between snapshots/AOF syncs)",
        "Simplicity of single-threaded model (no locks) vs limitation of not using multiple CPU cores for computation",
        "RDB snapshots (compact, fast restore) vs AOF (better durability, larger files, slower restore)",
        "Redis Cluster (horizontal scaling) vs single instance (simpler, supports all commands, no slot restrictions)",
        "Pub/Sub (fire-and-forget, no persistence) vs Streams (durable, consumer groups, acknowledgment, but more complex)",
    ],
    "common_mistakes": [
        "Using KEYS * in production — it blocks the single thread and scans every key. Use SCAN with a cursor instead",
        "Not setting maxmemory and eviction policy — Redis will consume all available RAM and get OOM-killed by the OS",
        "Using Redis as the sole source of truth for critical data — it is not a database replacement despite persistence options",
        "Ignoring key expiry and letting the dataset grow unbounded — always set TTL on cache entries",
        "Running O(N) commands (LRANGE 0 -1, SMEMBERS, HGETALL) on collections with millions of elements — use pagination variants (SSCAN, HSCAN)",
        "Assuming Pub/Sub is durable — subscribers that disconnect miss messages. Use Streams for durable messaging",
    ],
    "interview_tips": [
        "When a design calls for caching, do not just say 'add Redis' — specify the data structure (hash for objects, sorted set for ranked data, string for simple values), the caching pattern (cache-aside vs write-through), and the invalidation strategy (TTL vs event-driven)",
        "Know the time complexity of Redis operations: GET/SET are O(1), ZADD/ZRANK are O(log N), ZRANGE is O(log N + M) where M is the result size. Interviewers love hearing you reason about complexity",
        "Always mention the single-threaded model when explaining why Redis is fast — it shows you understand the architecture, not just the API",
    ],
    "related_concepts": ["caching", "consistent_hashing", "message_queues", "sharding"],
},

"kafka": {
    "title": "Apache Kafka Deep Dive",
    "introduction": (
        "Apache Kafka is a distributed event streaming platform designed for high-throughput, fault-tolerant, "
        "real-time data pipelines. The critical distinction for interviews is that Kafka is not a traditional "
        "message queue — it is a distributed commit log. Messages are not deleted after consumption; they are "
        "retained for a configurable period (or forever with log compaction), and multiple consumer groups can "
        "independently read from the same topic at different offsets. This makes Kafka suitable for event "
        "sourcing, stream processing, data integration, and replay scenarios that traditional queues like "
        "RabbitMQ or SQS cannot handle. LinkedIn originally built Kafka to handle their activity stream pipeline "
        "— tracking page views, clicks, and searches — and it now processes trillions of messages per day at "
        "companies like Netflix, Uber, and Airbnb. A production Kafka cluster can handle millions of messages "
        "per second with end-to-end latency in the low milliseconds. You would reach for Kafka when you need "
        "to decouple producers and consumers at high scale, when multiple downstream systems need to process "
        "the same events independently, when you need replay capability (reprocessing historical data), or when "
        "you are building event-driven architectures. You would not choose Kafka for simple task queues with "
        "low throughput (SQS is simpler), for request-reply patterns (use gRPC), or when you need message-level "
        "routing and filtering (RabbitMQ's exchange/binding model is more flexible for complex routing). In "
        "system design interviews, Kafka appears whenever you need asynchronous processing at scale — activity "
        "feeds, notification systems, log aggregation, real-time analytics, and change data capture."
    ),
    "key_concepts": [
        {
            "name": "Core Architecture: Brokers, Topics, Partitions",
            "explanation": (
                "A Kafka cluster consists of multiple brokers (servers), each storing a subset of the data. Data "
                "is organized into topics, and each topic is divided into partitions. A partition is an ordered, "
                "immutable sequence of messages (a commit log) stored on a single broker. Each message within a "
                "partition has a unique, monotonically increasing offset. Topics typically have multiple partitions "
                "(e.g., 12 or 64) distributed across brokers for parallelism and load balancing. Partitions are "
                "the unit of parallelism in Kafka: if a topic has 12 partitions, up to 12 consumers in a group "
                "can read simultaneously. They are also the unit of replication: each partition has one leader "
                "and N-1 follower replicas on different brokers. All reads and writes go to the leader; followers "
                "replicate asynchronously. The replication factor (typically 3) determines fault tolerance — with "
                "replication factor 3, you can lose 2 brokers and still have all data. The controller broker "
                "manages partition leadership and cluster metadata. In Kafka 3.3+, KRaft mode replaces ZooKeeper "
                "with a built-in Raft-based metadata quorum, simplifying operations. Understanding this hierarchy "
                "— cluster contains brokers, brokers contain partition replicas, partitions contain ordered messages "
                "— is foundational for every Kafka interview question."
            ),
        },
        {
            "name": "Producers: Partitioning, Batching, and Durability",
            "explanation": (
                "Producers send messages to topics. The critical decision is how messages are assigned to "
                "partitions. If a message has a key, Kafka uses hash(key) mod num_partitions — all messages "
                "with the same key go to the same partition, guaranteeing ordering for that key. If no key is "
                "provided, Kafka uses a sticky partitioner (round-robin across partitions in batches) for even "
                "distribution. You can also implement a custom partitioner. Producers batch messages before "
                "sending: the batch.size (default 16KB) and linger.ms (default 0, often set to 5-20ms) control "
                "the trade-off between latency and throughput. Larger batches mean fewer network round trips "
                "and better compression, but higher end-to-end latency. The acks configuration controls "
                "durability: acks=0 (fire and forget, fastest, possible data loss), acks=1 (leader acknowledges, "
                "data loss if leader crashes before replication), acks=all (all in-sync replicas acknowledge, "
                "strongest durability). For critical data, use acks=all combined with min.insync.replicas=2 — "
                "this means at least 2 replicas (leader + 1 follower) must confirm the write. If fewer than "
                "min.insync.replicas are available, the producer receives an error rather than silently losing "
                "data. Idempotent producers (enable.idempotence=true) assign a sequence number to each message, "
                "allowing brokers to deduplicate retries — this is a building block for exactly-once semantics."
            ),
        },
        {
            "name": "Consumer Groups, Rebalancing, and Offset Management",
            "explanation": (
                "Consumers read from topics by joining consumer groups. Within a group, each partition is assigned "
                "to exactly one consumer — this is how Kafka achieves parallel consumption. If you have 12 "
                "partitions and 12 consumers in a group, each consumer reads from one partition. If you add a "
                "13th consumer, it sits idle. If a consumer dies, its partitions are reassigned to surviving "
                "consumers — this is rebalancing. Rebalancing can cause a brief pause in consumption (stop-the-"
                "world rebalance) or be incremental (cooperative rebalancing in newer Kafka versions). Different "
                "consumer groups reading from the same topic are completely independent — each tracks its own "
                "offsets. This allows multiple downstream systems to process the same event stream independently. "
                "Offset management is crucial: Kafka stores committed offsets in a special __consumer_offsets "
                "topic. Auto-commit (enable.auto.commit=true) periodically commits the latest offset, but this "
                "can lead to duplicate processing (consumer crashes after processing but before commit) or data "
                "loss (commit happens before processing completes). Manual commit gives you control: process a "
                "batch, then commitSync(). For exactly-once, combine manual offset commit with transactional "
                "producers (read-process-write in a single atomic transaction). The key interview insight is "
                "understanding the relationship between partition count and consumer parallelism: partition count "
                "sets the upper bound on consumer parallelism within a group, and you cannot reduce partition "
                "count after creation without recreating the topic."
            ),
        },
        {
            "name": "Retention, Log Compaction, and Exactly-Once Semantics",
            "explanation": (
                "Kafka retains messages based on time (retention.ms, default 7 days) or size (retention.bytes). "
                "Unlike traditional queues, consumed messages are not deleted — they remain until the retention "
                "policy removes them. This enables replay: a consumer can seek to any offset and reprocess "
                "historical data. Log compaction is an alternative retention policy: instead of deleting old "
                "segments by time, Kafka keeps only the latest value for each key. This turns a topic into a "
                "key-value changelog — perfect for database change capture, configuration distribution, or "
                "materialized views. A compacted topic for user profiles would retain only the latest profile "
                "for each user_id, regardless of how many updates occurred. Exactly-once semantics (EOS) is "
                "Kafka's strongest delivery guarantee, built on two foundations: idempotent producers (each "
                "message gets a producer ID + sequence number for deduplication) and transactional API (atomically "
                "produce to multiple partitions and commit offsets). With EOS, a stream processing application "
                "can read from input topics, process, write to output topics, and commit input offsets all "
                "atomically — if any step fails, the entire transaction is rolled back. This is enabled by "
                "setting processing.guarantee=exactly_once_v2 in Kafka Streams. The trade-off: EOS adds latency "
                "(transaction coordination) and reduces throughput (smaller batches, more metadata). Most "
                "applications use at-least-once with idempotent consumers (designing consumers to handle "
                "duplicates safely), which is simpler and higher throughput."
            ),
        },
        {
            "name": "Kafka Connect and Kafka Streams",
            "explanation": (
                "Kafka Connect is a framework for streaming data between Kafka and external systems without "
                "writing code. Source connectors pull data into Kafka (e.g., Debezium CDC connector reads the "
                "PostgreSQL WAL and produces change events to Kafka topics — one topic per table). Sink "
                "connectors push data from Kafka to external systems (e.g., Elasticsearch sink connector indexes "
                "Kafka messages for search, S3 sink connector archives events for data lake). Connectors run "
                "as tasks distributed across Connect workers, providing parallelism and fault tolerance. This "
                "is the standard pattern for building data pipelines: source DB -> Debezium -> Kafka -> sink "
                "connectors -> search index, analytics warehouse, cache. Kafka Streams is a client library "
                "(not a separate cluster) for building stream processing applications. It supports stateless "
                "operations (filter, map, flatMap), stateful operations (aggregations, joins with local state "
                "stores backed by RocksDB), and windowed computations (tumbling, hopping, session windows). "
                "Unlike Apache Flink or Spark Streaming, Kafka Streams runs as a regular Java application — "
                "no separate cluster to manage. It rebalances processing across instances using the consumer "
                "group protocol. For complex event processing (CEP) or very large state, Apache Flink is more "
                "capable but adds operational complexity. For most stream processing embedded in microservices, "
                "Kafka Streams is the simpler choice."
            ),
        },
        {
            "name": "Kafka vs SQS vs RabbitMQ: When to Choose What",
            "explanation": (
                "This comparison comes up constantly in interviews. Kafka is a distributed commit log optimized "
                "for high-throughput ordered event streaming with replay capability. Choose Kafka when: multiple "
                "consumer groups need independent access to the same events, you need replay/reprocessing, you "
                "need strict ordering per key, or throughput requirements exceed 100K messages/sec. RabbitMQ is "
                "a traditional message broker implementing AMQP with rich routing (direct, fanout, topic, headers "
                "exchanges). Choose RabbitMQ when: you need complex routing logic (route messages to different "
                "queues based on headers or routing keys), you need per-message acknowledgment and redelivery, "
                "or your use case is classic task distribution (work queues). RabbitMQ deletes messages after "
                "consumption — no replay. SQS is AWS's fully managed message queue. Choose SQS when: you want "
                "zero operational overhead (no brokers to manage), you need simple point-to-point or fan-out "
                "(with SNS), or your volume is moderate and you are already on AWS. SQS guarantees at-least-once "
                "delivery with visibility timeout, supports FIFO queues for ordering, and auto-scales. The key "
                "differentiator: Kafka retains messages (consumers track their position), while RabbitMQ and SQS "
                "delete messages after acknowledgment. This makes Kafka suitable for event sourcing and audit "
                "logs where you need a permanent record of what happened, while RabbitMQ/SQS are better for "
                "task queues where you only care about processing each item once."
            ),
        },
    ],
    "real_world_examples": [
        "LinkedIn processes 7 trillion messages per day through Kafka for activity tracking, metrics, and data pipeline integration across all their services",
        "Uber uses Kafka as the backbone of their event-driven architecture — every ride request, driver location update, and trip event flows through Kafka topics, enabling real-time surge pricing and ETA calculation",
        "Netflix uses Kafka + Kafka Connect + Flink for real-time stream processing — tracking viewing events, A/B test impressions, and feeding their recommendation engine",
        "The New York Times uses Kafka with log compaction to store the entire published article corpus — new subscribers can consume the full archive, then receive real-time updates for new articles",
    ],
    "common_interview_questions": [
        "How does Kafka guarantee message ordering? (Per partition only. Same key = same partition = ordered. No global ordering across partitions)",
        "A consumer group has 6 consumers but the topic has 4 partitions. What happens? (2 consumers sit idle. You need at least as many partitions as consumers for full parallelism)",
        "How would you handle a scenario where one partition gets much more traffic than others? (Hot key problem — add salt/suffix to keys, use custom partitioner, or repartition to more partitions)",
        "Explain exactly-once semantics in Kafka. What is the performance cost? (Idempotent producer + transactional API. Cost: higher latency, lower throughput due to transaction coordination)",
        "How would you design a notification system using Kafka? (Producers publish events to topic, notification service consumes, partitioned by user_id for ordering per user)",
        "A Kafka broker goes down. What happens to the partitions it was leading? (Followers in ISR are eligible for leader election. Controller assigns new leaders. min.insync.replicas determines write availability)",
    ],
    "key_trade_offs": [
        "Throughput (larger batches, linger.ms, compression) vs latency (smaller batches, linger.ms=0, no compression)",
        "Durability (acks=all, replication factor 3, min.insync.replicas=2) vs performance (acks=1, lower replication)",
        "More partitions = more parallelism but more file handles, longer leader elections, and more end-to-end latency for producers using acks=all",
        "Log retention (time-based, simple, enables replay) vs log compaction (key-based, space-efficient, enables changelog semantics)",
        "Exactly-once (strongest guarantee, higher latency) vs at-least-once with idempotent consumers (simpler, faster, requires application-level deduplication)",
    ],
    "common_mistakes": [
        "Setting partition count too low initially — you cannot reduce partitions later. Start with enough partitions for your expected peak parallelism (e.g., 12-64 for most use cases)",
        "Using acks=0 or acks=1 for critical data and then being surprised by data loss during broker failures",
        "Assuming Kafka provides global ordering — ordering is per-partition only. If you need ordering across different keys, they must share a partition",
        "Not monitoring consumer lag — if consumers fall behind, you need to scale consumers or optimize processing. Use kafka-consumer-groups.sh or Burrow for monitoring",
        "Creating a topic per user or per entity instead of partitioning a single topic by entity key — this leads to millions of topics and operational nightmares",
        "Ignoring backpressure — if a consumer cannot keep up, messages accumulate. Design consumers to handle bursts and implement dead-letter topics for poison messages",
    ],
    "interview_tips": [
        "When designing a system with Kafka, always specify: the topic name, the partition key (and why), the number of partitions, the consumer group structure, and the delivery guarantee. This shows depth",
        "Draw the data flow: producer -> topic (N partitions, replication factor 3) -> consumer group A (service X) + consumer group B (service Y). Showing multiple consumer groups reading independently is a key Kafka differentiator",
        "If an interviewer asks about message ordering, immediately clarify: ordering is per partition, not per topic. Then explain how you would choose a partition key to get the ordering you need",
    ],
    "related_concepts": ["message_queues", "api_design", "sharding", "cap_theorem"],
},

"elasticsearch": {
    "title": "Elasticsearch Deep Dive",
    "introduction": (
        "Elasticsearch is a distributed, RESTful search and analytics engine built on top of Apache Lucene. "
        "It stores JSON documents, indexes them for fast retrieval, and provides a powerful query DSL for both "
        "full-text search and structured queries. The key insight for interviews is understanding what Elasticsearch "
        "does differently from a relational database: it builds an inverted index, which maps every unique term "
        "to the list of documents containing that term. This is why a full-text search across millions of documents "
        "can return results in milliseconds, while the same query against a SQL database would require a full table "
        "scan. Elasticsearch is part of the Elastic Stack (formerly ELK Stack): Elasticsearch for storage and "
        "search, Logstash and Beats for data ingestion, and Kibana for visualization. You would reach for "
        "Elasticsearch when you need full-text search with relevance ranking (product search, documentation "
        "search), log and event analytics (centralized logging with Kibana dashboards), autocomplete and "
        "typeahead functionality, geospatial search (find stores within 10km), or real-time aggregation "
        "dashboards. You would not use Elasticsearch as a primary database because it lacks ACID transactions, "
        "has eventual consistency (a document may not be searchable for up to 1 second after indexing by default), "
        "and is not optimized for frequent updates to the same document. In system design interviews, Elasticsearch "
        "appears whenever the design requires search functionality, log analytics, or real-time dashboards. The "
        "pattern is almost always: primary database (PostgreSQL, DynamoDB) as the source of truth, with "
        "Elasticsearch as a secondary index for search, kept in sync via change data capture or application-level "
        "dual writes."
    ),
    "key_concepts": [
        {
            "name": "The Inverted Index: How Text Search Actually Works",
            "explanation": (
                "The inverted index is the core data structure that makes Elasticsearch fast. For every indexed "
                "text field, Elasticsearch tokenizes the text into terms, applies analyzers (lowercase, stemming, "
                "stop word removal), and builds a mapping from each term to a posting list — the sorted list of "
                "document IDs containing that term. When you search for 'distributed systems', Elasticsearch looks "
                "up the posting lists for 'distributed' and 'systems' and computes their intersection. This is "
                "an O(N) operation where N is the length of the shorter posting list, not the total number of "
                "documents. Analyzers are pipelines of character filters, tokenizers, and token filters. The "
                "standard analyzer lowercases text and splits on whitespace and punctuation. Custom analyzers "
                "handle language-specific needs: English stemming ('running' -> 'run'), synonym expansion "
                "('NY' -> 'New York'), or n-gram tokenization for autocomplete. Relevance scoring uses BM25 "
                "(which replaced TF-IDF as the default in ES 5+). BM25 considers term frequency (how often the "
                "term appears in the document), inverse document frequency (how rare the term is across all "
                "documents), and field length (shorter fields with the term score higher). Understanding BM25 "
                "at a high level is important for interviews: a document that contains the search term many times, "
                "where the term is rare across the corpus, and the matching field is short, will rank highest."
            ),
        },
        {
            "name": "Documents, Indices, Mappings, and Field Types",
            "explanation": (
                "Elasticsearch stores data as JSON documents grouped into indices (analogous to tables in SQL). "
                "Each document has a unique _id and belongs to an index. A mapping defines the schema: which "
                "fields exist, their types, and how they are indexed. The two most important field types are "
                "'text' and 'keyword'. Text fields are analyzed (tokenized, lowercased, stemmed) and used for "
                "full-text search — searching for 'quick brown fox' will match a document containing 'The Quick "
                "Brown Foxes'. Keyword fields are not analyzed — they are stored as exact values and used for "
                "filtering, sorting, and aggregations. A common pattern is to map a field as both: 'title' as "
                "text for search and 'title.keyword' as keyword for exact matching and sorting. Other important "
                "types include: 'integer'/'long'/'float' for numeric range queries, 'date' for time-based "
                "filtering, 'geo_point' for latitude/longitude, 'nested' for arrays of objects that need "
                "independent querying (without nested, objects in an array are flattened and cross-matched), "
                "and 'completion' for the suggest API (autocomplete). Dynamic mapping auto-detects types from "
                "the first document, but in production you should always define explicit mappings to avoid "
                "surprises like a numeric ID being mapped as text. Mapping changes are limited after creation — "
                "you cannot change a field's type without reindexing. This makes upfront schema design important."
            ),
        },
        {
            "name": "Cluster Architecture: Nodes, Shards, and Replicas",
            "explanation": (
                "An Elasticsearch cluster consists of multiple nodes with different roles. Master-eligible nodes "
                "manage cluster state (index creation, shard allocation, node tracking). Data nodes store shards "
                "and execute queries. Coordinating nodes (or any node acting as coordinator) receive client "
                "requests, scatter them to relevant data nodes, and gather/merge results. In production, you "
                "typically have 3 dedicated master nodes (for quorum), N data nodes (scaled by data volume and "
                "query load), and optional coordinating-only nodes for heavy aggregation workloads. Each index "
                "is divided into primary shards (set at index creation, cannot be changed). Each primary shard "
                "has zero or more replica shards on different nodes. When a query arrives, the coordinating node "
                "sends it to one copy of each shard (primary or replica), collects results, merges and sorts "
                "them, and returns the top N. Replicas serve two purposes: fault tolerance (if a node dies, "
                "replicas on other nodes promote to primary) and read throughput (search requests are load-"
                "balanced across primary and replica shards). The number of primary shards determines the maximum "
                "parallelism for a single query and the maximum data capacity for that index. Oversharding (too "
                "many small shards) wastes memory and slows cluster state management. Undersharding (too few "
                "large shards) limits query parallelism. A common guideline is to keep shards between 10GB and "
                "50GB each."
            ),
        },
        {
            "name": "Search Queries vs Aggregations",
            "explanation": (
                "Elasticsearch queries fall into two categories. Search queries find and score documents: match "
                "(full-text search with relevance scoring), term (exact keyword match), bool (combine must, should, "
                "must_not, filter clauses), range (numeric or date ranges), and multi_match (search across multiple "
                "fields). The 'filter' context is important for performance — filter clauses do not calculate "
                "relevance scores and are cached, making them much faster for structured filtering (e.g., "
                "status=active, date > 2024-01-01). Aggregations compute analytics over the result set: terms "
                "aggregation (group by field, like SQL GROUP BY), date_histogram (group by time buckets), avg/sum/"
                "min/max (metrics), percentiles, and cardinality (approximate distinct count using HyperLogLog). "
                "Aggregations can be nested: group by category, then within each category compute average price "
                "and a date histogram of sales. This makes Elasticsearch powerful for real-time dashboards — "
                "Kibana dashboards are essentially aggregation queries rendered as charts. A common interview "
                "pattern is designing a log analytics system: logs are indexed with timestamp, service_name, "
                "log_level, and message. Queries filter by time range and service (filter context, cached), "
                "full-text search on message (query context, scored), and aggregations compute error rates per "
                "service over time (date_histogram + terms aggregation). Understanding when to use query context "
                "vs filter context is a practical performance optimization interviewers appreciate."
            ),
        },
        {
            "name": "Index Lifecycle Management and Scaling Patterns",
            "explanation": (
                "For time-series data (logs, metrics, events), the standard pattern is time-based indices: one "
                "index per day or week (e.g., logs-2024.01.15). Index Lifecycle Management (ILM) automates the "
                "lifecycle: hot phase (actively written and searched, stored on fast SSDs), warm phase (read-only, "
                "can be moved to cheaper storage, shards can be shrunk and force-merged for better compression), "
                "cold phase (infrequently accessed, can be stored on cheapest storage), and delete phase (indices "
                "older than N days are automatically deleted). Index aliases provide a stable endpoint: the alias "
                "'logs-current' always points to today's index, and 'logs-all' points to all log indices. Rollover "
                "API creates a new index when the current one hits a size or age threshold. For scaling write "
                "throughput, increase the number of primary shards (more parallelism for indexing). For scaling "
                "read throughput, add replicas (more copies to serve searches). For reducing storage, tune the "
                "refresh interval (default 1 second — increasing to 30 seconds reduces segment creation and "
                "merging overhead for heavy indexing workloads). The near-real-time nature of Elasticsearch comes "
                "from this refresh interval: a newly indexed document is not searchable until the next refresh. "
                "This is a critical interview point — Elasticsearch is eventually consistent with a ~1 second "
                "delay by default."
            ),
        },
        {
            "name": "When to Use and When Not to Use Elasticsearch",
            "explanation": (
                "Use Elasticsearch for: full-text search with relevance ranking (product search — 'comfortable "
                "running shoes' should rank differently from 'running shoe store' based on your product catalog), "
                "log analytics and observability (centralized logging across microservices with Kibana dashboards "
                "showing error rates, latency percentiles, request volumes), autocomplete and typeahead (using "
                "completion suggesters or edge n-gram tokenization), geospatial search (find restaurants within "
                "5km using geo_distance queries), and real-time analytics dashboards (aggregating millions of "
                "events into charts). Do NOT use Elasticsearch as: a primary database (no ACID transactions, "
                "eventual consistency, poor update performance due to immutable segments — updates are actually "
                "delete + reinsert), a replacement for relational queries requiring joins (Elasticsearch has no "
                "native join — you denormalize data or use nested/parent-child types, both with limitations), "
                "or a system requiring immediate read-after-write consistency (the refresh interval means a "
                "write may not be visible for up to 1 second). The standard architecture is: PostgreSQL or "
                "DynamoDB as the source of truth with ACID guarantees, and Elasticsearch as a secondary read "
                "model kept in sync via Kafka Connect (Debezium captures changes from the database WAL, publishes "
                "to Kafka, Elasticsearch sink connector indexes them). This gives you the best of both worlds: "
                "transactional writes to the primary database and fast, flexible search via Elasticsearch."
            ),
        },
    ],
    "real_world_examples": [
        "Wikipedia uses Elasticsearch to power its search across 60+ million articles in 300+ languages, with custom analyzers for each language's tokenization and stemming rules",
        "GitHub uses Elasticsearch for code search across 200+ million repositories — indexing source code with custom tokenizers that understand programming syntax and camelCase splitting",
        "Netflix uses Elasticsearch with Kibana for centralized logging across thousands of microservices, querying billions of log entries with sub-second response times using time-based indices and ILM",
        "Uber uses Elasticsearch for geospatial search — finding available drivers near a rider's location using geo_distance queries on driver coordinate documents updated in real-time",
    ],
    "common_interview_questions": [
        "How would you design a product search system? (PostgreSQL for product catalog, Elasticsearch for search. Sync via CDC/Kafka. Custom analyzers for product names, filters for price/category in filter context, BM25 for relevance)",
        "Explain how an inverted index works and why it makes full-text search fast. (Term -> posting list mapping. Search is posting list intersection, not full scan. O(posting list length) not O(total documents))",
        "How does Elasticsearch achieve horizontal scalability? (Index split into shards distributed across data nodes. Queries scatter to all shards, results gathered and merged by coordinating node)",
        "Your Elasticsearch cluster is slow. How do you diagnose and fix it? (Check shard count and sizes, review slow query log, use filter context for structured queries, increase refresh interval for write-heavy workloads, add data nodes for capacity)",
        "How would you keep Elasticsearch in sync with your primary database? (CDC with Debezium -> Kafka -> ES sink connector. Or application-level dual writes with eventual consistency. Never use ES as source of truth)",
        "Design a centralized logging system for 1000 microservices. (Beats/Fluentd on each host -> Kafka buffer -> Logstash/Flink for parsing -> Elasticsearch with daily indices and ILM -> Kibana dashboards)",
    ],
    "key_trade_offs": [
        "Relevance (text fields with analyzers, BM25 scoring) vs exact matching (keyword fields, filter context, no scoring overhead)",
        "Indexing throughput (larger refresh interval, fewer replicas) vs search freshness (smaller refresh interval, more replicas for read scaling)",
        "More shards (higher query parallelism, smaller shard size) vs fewer shards (lower overhead, simpler cluster management)",
        "Denormalization (fast queries, data duplication, complex updates) vs nested/parent-child documents (normalized, slower queries, simpler updates)",
        "Full Elastic Stack (powerful but operationally complex) vs managed service like AWS OpenSearch (simpler ops, but potentially behind on features and version)",
    ],
    "common_mistakes": [
        "Using Elasticsearch as the primary database — it lacks transactions, has eventual consistency, and updates are expensive (delete + reinsert internally)",
        "Not defining explicit mappings and relying on dynamic mapping — leads to fields being mapped as wrong types that cannot be changed without reindexing",
        "Using query context where filter context would suffice — filters are cached and skip scoring, making them significantly faster for structured predicates",
        "Creating too many small shards (oversharding) — each shard consumes memory for its Lucene segment metadata. Thousands of tiny shards degrade cluster performance",
        "Not setting up ILM for time-series data — indices grow unbounded, old data is never cleaned up, and the cluster eventually runs out of disk",
        "Expecting immediate read-after-write consistency — the default 1-second refresh interval means recently indexed documents may not appear in search results immediately",
    ],
    "interview_tips": [
        "When a design needs search, describe the full pipeline: source of truth database -> sync mechanism (CDC/Kafka preferred over dual writes) -> Elasticsearch with explicit mappings -> query with filter context for structured fields and query context for text",
        "Mention the inverted index by name and explain it in one sentence: 'it maps every term to the list of documents containing it, so search is a posting list lookup, not a full scan'. This shows you understand why ES is fast, not just that it is fast",
        "Always distinguish between text fields (analyzed, for full-text search) and keyword fields (exact match, for filtering and sorting) — this is the most fundamental mapping decision in ES and shows practical experience",
    ],
    "related_concepts": ["database_indexing", "sharding", "caching", "kafka"],
},

"sql_vs_nosql": {
    "title": "SQL vs NoSQL Decision Framework",
    "introduction": (
        "The choice between SQL and NoSQL databases is one of the most consequential decisions in system design, "
        "yet it is frequently oversimplified. The pragmatic starting point is: use PostgreSQL unless you have a "
        "specific, articulable reason not to. Relational databases have survived 40+ years because they are "
        "general-purpose: ACID transactions, a mature query language (SQL), strong consistency, flexible indexing, "
        "and rich tooling. NoSQL databases were born from the realization that certain workloads have specific "
        "access patterns, scale requirements, or data models that relational databases handle poorly. The four "
        "NoSQL families — document stores, key-value stores, wide-column stores, and graph databases — each "
        "solve a different problem. Document stores (MongoDB) handle semi-structured data with flexible schemas. "
        "Key-value stores (Redis, DynamoDB) provide ultra-low-latency lookups by primary key. Wide-column stores "
        "(Cassandra, HBase) handle massive write throughput with time-series and IoT data. Graph databases "
        "(Neo4j) efficiently traverse relationships that would require expensive recursive joins in SQL. In "
        "practice, most production systems use polyglot persistence — multiple databases for different parts "
        "of the system: PostgreSQL for transactional data, Redis for caching and sessions, Elasticsearch for "
        "search, Kafka for event streaming. The interview skill is not picking one database but articulating "
        "the trade-offs: what you gain, what you give up, and why the workload's specific access patterns "
        "make that trade-off worthwhile. Every choice has CAP theorem implications: SQL databases typically "
        "prioritize consistency (CP), while many NoSQL databases prioritize availability and partition tolerance "
        "(AP) with eventual consistency."
    ),
    "key_concepts": [
        {
            "name": "Relational Databases: ACID, Schemas, Joins, and Normalization",
            "explanation": (
                "Relational databases (PostgreSQL, MySQL, Oracle) store data in tables with predefined schemas. "
                "ACID properties — Atomicity (all-or-nothing transactions), Consistency (data always satisfies "
                "constraints), Isolation (concurrent transactions do not interfere), Durability (committed data "
                "survives crashes) — make them the gold standard for correctness. Normalization eliminates data "
                "duplication: a user's address is stored once in an addresses table, and an orders table references "
                "it via a foreign key. This means updates only happen in one place, but reads require joins. "
                "Joins are the superpower and the bottleneck of relational databases: they enable ad-hoc queries "
                "across related data (SELECT orders.*, users.name FROM orders JOIN users ON orders.user_id = "
                "users.id), but complex joins across large tables are expensive and difficult to scale horizontally. "
                "Relational databases scale vertically well (bigger machine) and can handle significant read scale "
                "with read replicas, but horizontal write scaling (sharding) is complex because joins and "
                "transactions across shards are painful. PostgreSQL specifically has become the modern default "
                "because it supports JSON columns (giving document-store flexibility within a relational model), "
                "full-text search, GIS extensions (PostGIS), and excellent indexing (B-tree, hash, GIN, GiST). "
                "The interview point is: PostgreSQL is almost always a safe starting choice. You move to NoSQL "
                "when you hit a specific limitation — not preemptively."
            ),
        },
        {
            "name": "Document Stores: MongoDB and Flexible Schemas",
            "explanation": (
                "Document databases store data as self-contained JSON-like documents (BSON in MongoDB). Each "
                "document can have a different structure — no fixed schema required. This is ideal for data with "
                "variable attributes: product catalogs (a laptop has different attributes than a shirt), content "
                "management systems (articles have different sections, metadata, and media types), and user "
                "profiles (different users have different fields populated). The data model encourages embedding "
                "related data within a single document rather than normalizing across tables. A blog post document "
                "might embed its comments array directly, rather than storing comments in a separate collection "
                "with a foreign key. This denormalization makes reads fast (one query retrieves everything) but "
                "makes updates harder (updating a user's name requires updating it in every document where it is "
                "embedded). MongoDB provides rich querying on nested fields, array elements, and supports "
                "aggregation pipelines for analytics. It scales horizontally with built-in sharding (shard key "
                "determines data distribution). MongoDB 4.0+ supports multi-document ACID transactions, reducing "
                "the gap with relational databases. When to choose MongoDB over PostgreSQL: when your schema is "
                "truly unpredictable and changes frequently, when your access pattern is primarily read-one-document "
                "(no joins needed), or when you need horizontal write scaling from day one. When NOT to choose "
                "MongoDB: when you need complex joins across entities, when data integrity via foreign keys and "
                "constraints is critical, or when your data is inherently relational (orders referencing products "
                "referencing suppliers)."
            ),
        },
        {
            "name": "Key-Value Stores: Redis and DynamoDB",
            "explanation": (
                "Key-value stores are the simplest NoSQL model: you store a value (string, JSON, binary) "
                "associated with a unique key, and retrieve it by key. This simplicity enables extreme performance. "
                "Redis (in-memory) delivers sub-millisecond latency for GET/SET operations. DynamoDB (AWS managed, "
                "disk-based with SSD) delivers single-digit millisecond latency at any scale with automatic "
                "horizontal scaling. DynamoDB's data model is richer than pure key-value: each item has a "
                "partition key (for distribution) and an optional sort key (for range queries within a partition). "
                "This enables access patterns like 'get all orders for user X sorted by date' with a single "
                "query — partition key = user_id, sort key = timestamp. Global Secondary Indexes (GSIs) support "
                "alternative access patterns on different attributes. DynamoDB pricing is based on read/write "
                "capacity units and storage, making costs predictable but requiring careful capacity planning "
                "(or on-demand mode for variable workloads). Common use cases for key-value stores: session "
                "management (session_id -> session_data with TTL), shopping carts (user_id -> cart items), "
                "feature flags (flag_name -> configuration), user preferences, and caching. When to choose "
                "key-value over relational: when your access pattern is exclusively by primary key (no ad-hoc "
                "queries), when you need predictable single-digit millisecond latency at any scale, or when "
                "you need automatic horizontal scaling without managing sharding. When NOT to choose: when you "
                "need to query by arbitrary fields, when you need joins or transactions across items, or when "
                "your access patterns are unpredictable and evolving."
            ),
        },
        {
            "name": "Wide-Column Stores: Cassandra and HBase",
            "explanation": (
                "Wide-column stores (Cassandra, HBase, ScyllaDB) organize data into rows and column families, "
                "where each row can have a different set of columns. They are optimized for massive write "
                "throughput and horizontal scaling with no single point of failure. Cassandra uses a masterless "
                "architecture (every node is equal) with consistent hashing for data distribution and tunable "
                "consistency (ONE, QUORUM, ALL per query). This means you choose the consistency-availability "
                "trade-off per operation: strong consistency for critical reads (QUORUM), eventual consistency "
                "for high-availability reads (ONE). The data model is query-driven: you design your tables "
                "around the queries you need to run, not around the entities in your domain. A time-series "
                "table for IoT sensor data might have partition key = sensor_id and clustering columns = "
                "timestamp, enabling efficient range scans (all readings for sensor X between time A and B). "
                "This is fundamentally different from relational design where you normalize first and query "
                "flexibly. Cassandra excels at write-heavy workloads because writes go to a commit log and "
                "memtable, then are flushed to SSTables on disk — writes are always sequential I/O, never "
                "requiring random seeks. Netflix uses Cassandra to store viewing history (hundreds of thousands "
                "of writes per second). Apple runs one of the largest Cassandra deployments with 150,000+ "
                "nodes. When to choose wide-column: time-series data (IoT, metrics, logs), high write throughput "
                "(10x-100x more writes than reads), multi-datacenter replication requirements, or when you need "
                "linear horizontal scaling. When NOT to choose: when you need ad-hoc queries (Cassandra requires "
                "you to know your queries upfront), when you need secondary indexes on many fields (Cassandra's "
                "secondary indexes are limited), or when you need strong ACID transactions."
            ),
        },
        {
            "name": "Graph Databases: Neo4j and Relationship-Heavy Data",
            "explanation": (
                "Graph databases store data as nodes (entities) and edges (relationships), with properties on "
                "both. They excel when the relationships between entities are as important as the entities "
                "themselves. The key advantage is index-free adjacency: each node directly references its "
                "neighbors, so traversing a relationship is a constant-time pointer hop, not a join. In a "
                "relational database, finding friends-of-friends requires a self-join on the friendships table; "
                "finding friends-of-friends-of-friends requires a 3-way self-join. Each additional degree of "
                "separation adds another expensive join. In Neo4j, traversing 3 hops is three pointer lookups "
                "regardless of the total database size — performance depends on the local neighborhood, not the "
                "global dataset. Neo4j's query language Cypher is purpose-built for graph patterns: "
                "MATCH (a:Person)-[:FRIENDS]->(b)-[:FRIENDS]->(c) WHERE a.name = 'Alice' RETURN c. Use cases: "
                "social networks (friend recommendations, mutual connections, influence analysis), fraud detection "
                "(finding suspicious transaction rings), knowledge graphs (connected entities with typed "
                "relationships), recommendation engines (users who liked X also liked Y, traversed through "
                "user-item-user paths), and network topology analysis (infrastructure dependency mapping). "
                "When to choose a graph database: when your core queries involve multi-hop relationship traversals, "
                "when the number of hops is variable or deep (more than 2-3 levels), or when relationship types "
                "and properties are complex. When NOT to choose: for simple CRUD with few relationships (overkill), "
                "for aggregate analytics (graph DBs lack efficient full-scan aggregations), or when you need "
                "horizontal write scaling (Neo4j's clustering is read-scale, not write-scale)."
            ),
        },
        {
            "name": "Decision Framework and Polyglot Persistence",
            "explanation": (
                "The decision framework for choosing databases starts with one question: what are your access "
                "patterns? If your access patterns are diverse and unpredictable (ad-hoc analytics, complex "
                "joins, evolving queries), start with PostgreSQL. If your access patterns are known and specific, "
                "evaluate whether a specialized database better serves those patterns. Decision tree: Need "
                "full-text search? -> Add Elasticsearch alongside your primary DB. Need sub-millisecond caching "
                "or shared state? -> Add Redis. Need to store social graph with multi-hop traversals? -> Add "
                "Neo4j. Need to handle 100K+ writes per second for time-series data? -> Consider Cassandra. "
                "Need a managed serverless database with single-digit ms latency? -> DynamoDB. Need flexible "
                "schema for a content catalog? -> MongoDB (or PostgreSQL JSONB). Polyglot persistence means "
                "using the right database for each job. A social media platform might use: PostgreSQL for user "
                "accounts and authentication (ACID transactions for money and identity), Redis for session "
                "storage and caching (sub-ms latency), Cassandra for the activity feed (write-heavy, append-only, "
                "time-sorted), Neo4j for friend recommendations (graph traversal), Elasticsearch for user and "
                "content search (full-text with relevance), and Kafka as the event backbone connecting them all. "
                "The cost of polyglot persistence is operational complexity — each database requires monitoring, "
                "backup, expertise, and data synchronization. The interview skill is articulating this trade-off "
                "explicitly: 'I would add Elasticsearch here because the search requirements justify the "
                "operational cost, and I would keep PostgreSQL as the source of truth for transactional data.' "
                "CAP implications: PostgreSQL (CP — consistent, partition-tolerant, blocks writes if replica is "
                "unreachable), Cassandra (AP or CP depending on consistency level — tunable), DynamoDB (CP in "
                "strongly consistent mode, AP in eventual), MongoDB (CP — primary handles writes, secondaries "
                "lag), Redis Cluster (AP — available during partitions, eventual consistency between replicas)."
            ),
        },
    ],
    "real_world_examples": [
        "Instagram started with PostgreSQL and still uses it for core data (users, photos, likes) but added Cassandra for feed storage, Redis for caching, and Elasticsearch for user search — a textbook polyglot persistence architecture",
        "Airbnb uses PostgreSQL for bookings and payments (requires ACID), Elasticsearch for listing search (full-text with geo-distance), and Redis for session management and caching",
        "Discord stores messages in Cassandra (billions of messages, write-heavy, time-sorted per channel) but uses PostgreSQL for user accounts and server metadata (relational, needs transactions)",
        "LinkedIn uses Espresso (document store) for member profiles, Voldemort (key-value) for caching, Pinot (OLAP) for analytics, and a graph database for connection traversals — each database serves a specific access pattern",
    ],
    "common_interview_questions": [
        "When would you choose MongoDB over PostgreSQL? (Flexible schema, document-oriented access patterns, horizontal write scaling. But PostgreSQL JSONB covers many of the same use cases with ACID guarantees)",
        "Design a database architecture for a social media platform that needs user profiles, a social graph, an activity feed, and search. Which databases would you use for each component?",
        "What is the CAP theorem and how does it influence your database choice? (Can only guarantee 2 of 3: Consistency, Availability, Partition tolerance. In practice, P is not optional in distributed systems, so you choose between CP and AP)",
        "Your application needs to store 1 billion time-series data points per day with queries over the last 30 days. What database do you recommend and why? (Cassandra or InfluxDB for write throughput, partition by sensor/device ID, cluster by timestamp)",
        "You are building an e-commerce platform. Would you use SQL or NoSQL for the product catalog? What about for order processing? (Product catalog: MongoDB or PostgreSQL JSONB for flexible attributes. Orders: PostgreSQL for ACID transactions — you cannot lose or double-count orders)",
        "Explain polyglot persistence. What are the benefits and costs? (Benefits: each DB optimized for its workload. Costs: operational complexity, data sync, team expertise across multiple systems)",
    ],
    "key_trade_offs": [
        "Schema rigidity (SQL — prevents bad data, enables joins) vs schema flexibility (document stores — adapts to changing requirements, but no referential integrity)",
        "Strong consistency (SQL, CP systems — correct reads, higher latency) vs eventual consistency (AP systems — faster reads, stale data possible)",
        "Vertical scaling (SQL — simpler, limited by hardware ceiling) vs horizontal scaling (NoSQL — linear scaling, more operational complexity)",
        "Query flexibility (SQL — any query on any column with joins) vs access pattern optimization (NoSQL — blazing fast for designed patterns, unusable for unplanned queries)",
        "Operational simplicity (one database for everything — PostgreSQL can handle a lot) vs polyglot persistence (best tool per job, but N databases to operate)",
    ],
    "common_mistakes": [
        "Choosing NoSQL because it is 'modern' or 'webscale' without a specific access pattern that demands it — PostgreSQL handles the majority of workloads well",
        "Assuming NoSQL means no schema — your application code still enforces a schema, it is just implicit and harder to maintain than an explicit database schema",
        "Using MongoDB for highly relational data and then trying to fake joins in application code — this is worse than using SQL in the first place",
        "Forgetting that DynamoDB requires you to know your access patterns upfront — adding a new query pattern may require a new GSI or table redesign",
        "Over-normalizing in a document store (many small documents with references) — you lose the single-read advantage that makes document stores fast",
        "Ignoring the operational cost of polyglot persistence — each additional database is another system to monitor, backup, secure, and hire expertise for",
    ],
    "interview_tips": [
        "Start every database discussion with 'I would default to PostgreSQL because...' and then articulate what specific requirement pushes you toward an alternative. This shows mature engineering judgment, not hype-driven decisions",
        "For the classic 'SQL vs NoSQL' question, do not pick one — describe the trade-off spectrum and give a concrete scenario where each shines. Then propose a polyglot architecture for a realistic system",
        "When discussing CAP theorem, point out that it is about behavior during network partitions specifically — when the network is healthy, you can have all three. The real question is: what does your system do when a partition occurs?",
    ],
    "related_concepts": ["database_indexing", "sharding", "cap_theorem", "caching", "consistent_hashing"],
},
}
