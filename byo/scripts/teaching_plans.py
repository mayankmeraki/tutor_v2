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
    # -----------------------------------------------------------------------
    # 1. Networking
    # -----------------------------------------------------------------------
    "networking": {
        "title": "Networking Fundamentals",
        "introduction": (
            "Every distributed system sits on top of networking primitives.  Understanding "
            "TCP vs UDP, how DNS resolves names to IPs, how HTTP works, and how load "
            "balancers distribute traffic is foundational.  In system design interviews you "
            "will not be asked to implement TCP, but you need to reason about latency, "
            "reliability, connection overhead, and where in the stack to place various "
            "components."
        ),
        "key_concepts": [
            {
                "name": "TCP vs UDP",
                "explanation": (
                    "TCP is connection-oriented with guaranteed delivery, ordering, and flow/congestion control.  "
                    "The 3-way handshake adds latency.  UDP is connectionless, no guarantees, but fast — used "
                    "for video streaming, gaming, DNS queries.  Choose TCP when correctness matters; UDP when "
                    "speed matters and you can tolerate loss."
                ),
            },
            {
                "name": "DNS Resolution",
                "explanation": (
                    "DNS translates domain names to IP addresses.  Resolution chain: browser cache -> OS cache -> "
                    "recursive resolver -> root NS -> TLD NS -> authoritative NS.  TTL controls caching.  In "
                    "system design, DNS-based load balancing (e.g., Route 53 with weighted records) is a first-level "
                    "routing mechanism."
                ),
            },
            {
                "name": "HTTP/HTTPS",
                "explanation": (
                    "HTTP is request-response over TCP.  HTTP/1.1 supports persistent connections and pipelining.  "
                    "HTTP/2 adds multiplexing (multiple streams on one connection), header compression, and server push.  "
                    "HTTP/3 uses QUIC (over UDP) to reduce connection setup time.  HTTPS adds TLS encryption."
                ),
            },
            {
                "name": "Load Balancing",
                "explanation": (
                    "Distributes traffic across multiple servers.  L4 (transport layer) routes based on IP/port — fast "
                    "but no content awareness.  L7 (application layer) can route based on URL, headers, cookies — "
                    "enables sticky sessions and path-based routing.  Algorithms: round-robin, least connections, "
                    "consistent hashing.  Tools: Nginx, HAProxy, AWS ALB/NLB."
                ),
            },
        ],
        "real_world_examples": [
            "Netflix uses UDP-based QUIC for video delivery to reduce buffering",
            "Cloudflare's DNS (1.1.1.1) caches aggressively with Anycast routing",
            "AWS ALB (L7) routes /api/* to backend servers and /* to the CDN",
            "Google's Maglev: a custom L4 load balancer using consistent hashing",
        ],
        "common_interview_questions": [
            "What happens when you type google.com in your browser? (DNS, TCP handshake, TLS, HTTP request, rendering)",
            "When would you choose UDP over TCP?",
            "Explain the difference between L4 and L7 load balancing.  When do you need L7?",
            "How does a CDN reduce latency?  Where do you place it in the architecture?",
            "How would you handle load balancer failover?  (Active-passive, health checks, DNS failover)",
        ],
        "key_trade_offs": [
            "TCP reliability vs UDP speed — choose based on whether you can tolerate loss",
            "L4 simplicity/speed vs L7 flexibility/overhead",
            "DNS TTL: short TTL = faster failover but more DNS traffic; long TTL = more caching but slow updates",
        ],
        "related_concepts": ["api_design", "caching", "consistent_hashing"],
    },

    # -----------------------------------------------------------------------
    # 2. API Design
    # -----------------------------------------------------------------------
    "api_design": {
        "title": "API Design",
        "introduction": (
            "APIs are the contracts between services.  Good API design is stable, intuitive, "
            "and evolvable.  REST and gRPC are the two dominant paradigms — REST for external/ "
            "public APIs, gRPC for internal service-to-service communication.  In interviews, "
            "you need to design API endpoints, choose HTTP methods, handle pagination, "
            "versioning, and rate limiting."
        ),
        "key_concepts": [
            {
                "name": "REST Principles",
                "explanation": (
                    "Resources are nouns (/users, /orders/{id}).  HTTP methods map to CRUD: GET (read), "
                    "POST (create), PUT (full update), PATCH (partial update), DELETE.  Stateless — each "
                    "request carries all needed context.  Use proper status codes: 200 OK, 201 Created, "
                    "400 Bad Request, 404 Not Found, 429 Too Many Requests, 500 Internal Server Error."
                ),
            },
            {
                "name": "gRPC and Protocol Buffers",
                "explanation": (
                    "gRPC uses HTTP/2 and Protocol Buffers (binary serialization) — much faster than JSON/REST "
                    "for internal communication.  Supports streaming (unary, server-streaming, client-streaming, "
                    "bidirectional).  Strongly typed contracts (.proto files).  Drawback: not browser-friendly "
                    "without a proxy (gRPC-Web)."
                ),
            },
            {
                "name": "Pagination",
                "explanation": (
                    "Offset-based: ?page=3&size=20 — simple but slow for large offsets (DB skips rows).  "
                    "Cursor-based: ?after=<cursor>&limit=20 — cursor encodes the last seen item (e.g., timestamp + ID).  "
                    "Cursor pagination is consistent under writes and efficient for large datasets.  "
                    "Always return a 'next_cursor' in the response."
                ),
            },
            {
                "name": "Rate Limiting",
                "explanation": (
                    "Protects services from abuse and thundering herds.  Algorithms: token bucket (smooth), "
                    "sliding window log (precise), sliding window counter (efficient).  Typically applied per-user "
                    "or per-API-key.  Return 429 Too Many Requests with Retry-After header.  Implement at the "
                    "API gateway or load balancer level for consistency."
                ),
            },
            {
                "name": "Versioning",
                "explanation": (
                    "URL versioning (/v1/users) is explicit and easy to route.  Header versioning "
                    "(Accept: application/vnd.api+json;version=2) is cleaner but harder to test.  "
                    "Never break backward compatibility in the same version — add fields, do not remove or rename."
                ),
            },
        ],
        "real_world_examples": [
            "Stripe's REST API: clean resource naming, idempotency keys for POST retries, cursor pagination",
            "Google's internal services communicate via gRPC with Protocol Buffers",
            "Twitter API v2 uses cursor-based pagination with a 'next_token' field",
            "GitHub API uses rate limiting with X-RateLimit-Remaining headers",
        ],
        "common_interview_questions": [
            "Design the API for a URL shortener (POST /urls, GET /urls/{short_code}, GET /{short_code} redirect)",
            "How would you handle pagination for a feed with real-time inserts?",
            "REST vs gRPC — when would you choose each?",
            "How would you implement rate limiting in a distributed system with multiple API servers?",
            "How do you version your API without breaking existing clients?",
        ],
        "key_trade_offs": [
            "REST (human-readable, browser-friendly) vs gRPC (fast, typed, streaming)",
            "Offset pagination (simple) vs cursor pagination (scalable)",
            "Strict rate limiting (protects backend) vs generous limits (better UX)",
        ],
        "related_concepts": ["networking", "caching", "message_queues"],
    },

    # -----------------------------------------------------------------------
    # 3. Caching
    # -----------------------------------------------------------------------
    "caching": {
        "title": "Caching",
        "introduction": (
            "Caching stores frequently accessed data in a faster storage layer to reduce "
            "latency and load on the primary data store.  The two key decisions are: (1) what "
            "caching strategy to use (cache-aside, write-through, write-behind), and (2) how "
            "to handle invalidation (TTL, event-driven, versioning).  Phil Karlton famously "
            "said there are only two hard things in CS: cache invalidation and naming things."
        ),
        "key_concepts": [
            {
                "name": "Cache-Aside (Lazy Loading)",
                "explanation": (
                    "Application checks the cache first.  On miss, read from DB, store in cache, return.  "
                    "Pros: only caches what is actually requested; cache failure is non-fatal (falls back to DB).  "
                    "Cons: first request is always slow (cold cache); data can become stale between DB write and "
                    "cache TTL expiry."
                ),
            },
            {
                "name": "Write-Through",
                "explanation": (
                    "Every write goes to cache AND DB synchronously.  The cache is always fresh.  "
                    "Pros: reads are always fast and consistent.  Cons: write latency is higher (two writes); "
                    "caches data that may never be read (wasted space)."
                ),
            },
            {
                "name": "Write-Behind (Write-Back)",
                "explanation": (
                    "Write to cache immediately, then asynchronously flush to DB (batched).  "
                    "Pros: very fast writes; can batch/coalesce DB writes.  Cons: data loss risk if cache "
                    "crashes before flushing; eventual consistency between cache and DB."
                ),
            },
            {
                "name": "Eviction Policies",
                "explanation": (
                    "LRU (Least Recently Used): evicts the item not accessed for the longest time — most common.  "
                    "LFU (Least Frequently Used): evicts the item with the fewest accesses — good for skewed workloads.  "
                    "TTL (Time To Live): items expire after a fixed duration — simplest but may evict hot data."
                ),
            },
            {
                "name": "Cache Invalidation",
                "explanation": (
                    "TTL-based: set an expiry; stale data is tolerated for the TTL window.  "
                    "Event-driven: on DB write, publish an event that deletes/updates the cache entry.  "
                    "Versioning: cache key includes a version number; bump version on write, old entries naturally expire.  "
                    "Stampede protection: use locking or probabilistic early expiry to prevent all threads from hitting DB at once."
                ),
            },
        ],
        "real_world_examples": [
            "Redis as a cache-aside layer in front of PostgreSQL — standard web application pattern",
            "Facebook's Memcached (TAO): cache-aside with lease-based invalidation to prevent thundering herds",
            "CDN caching (CloudFront, Cloudflare): caches static assets at edge locations worldwide",
            "CPU L1/L2/L3 caches: hardware-level caching with LRU-like eviction",
        ],
        "common_interview_questions": [
            "Design a caching layer for a social media feed.  What strategy do you use?  How do you handle invalidation?",
            "What happens when your cache goes down?  How do you prevent a thundering herd (cache stampede)?",
            "Cache-aside vs write-through: when would you pick each?",
            "How do you ensure cache consistency in a distributed system with multiple app servers?",
            "Your cache hit rate is 60%.  How would you investigate and improve it?",
        ],
        "key_trade_offs": [
            "Freshness vs latency: shorter TTL = fresher data but more DB load; longer TTL = faster but staler",
            "Cache-aside simplicity vs write-through consistency",
            "Memory cost of caching vs latency savings — cache the hot 20%, not everything",
            "Write-behind speed vs data loss risk",
        ],
        "related_concepts": ["database_indexing", "consistent_hashing", "sharding"],
    },

    # -----------------------------------------------------------------------
    # 4. Sharding
    # -----------------------------------------------------------------------
    "sharding": {
        "title": "Sharding (Database Partitioning)",
        "introduction": (
            "Sharding splits a large dataset across multiple database instances (shards) "
            "so that no single machine is a bottleneck.  Each shard holds a subset of the "
            "data.  The two main strategies are range-based sharding (shard by key range) and "
            "hash-based sharding (shard by hash of key).  Sharding introduces complexity: "
            "cross-shard queries, rebalancing, and hot spots.  It is a last resort after "
            "vertical scaling, read replicas, and caching are exhausted."
        ),
        "key_concepts": [
            {
                "name": "Range-Based Sharding",
                "explanation": (
                    "Assign key ranges to shards (e.g., users A-M on shard 1, N-Z on shard 2).  "
                    "Pros: efficient range queries (all data in a range is on one shard).  "
                    "Cons: hot spots if keys are not uniformly distributed (e.g., more users with name starting with 'S')."
                ),
            },
            {
                "name": "Hash-Based Sharding",
                "explanation": (
                    "shard_id = hash(key) % num_shards.  Distributes data uniformly.  "
                    "Pros: no hot spots (assuming a good hash function).  "
                    "Cons: range queries require hitting all shards (scatter-gather); adding/removing shards "
                    "requires rehashing and data migration."
                ),
            },
            {
                "name": "Rebalancing",
                "explanation": (
                    "When a shard is overloaded or you add capacity, data must be moved.  Fixed hash "
                    "(key % N) is terrible for rebalancing — changing N moves almost all data.  "
                    "Consistent hashing moves only ~1/N of the data.  Alternatively, use a lookup table "
                    "(shard map) managed by a coordinator service."
                ),
            },
            {
                "name": "Hot Spots",
                "explanation": (
                    "Even with hashing, a single key (e.g., a celebrity's profile) can receive disproportionate "
                    "traffic.  Mitigations: add a random suffix to the key to spread across shards (then aggregate "
                    "on read), or cache hot keys aggressively."
                ),
            },
            {
                "name": "Cross-Shard Queries and Joins",
                "explanation": (
                    "Queries that span multiple shards are expensive: scatter the query to all shards, gather "
                    "and merge results.  Joins across shards are even worse.  Mitigation: co-locate related data "
                    "on the same shard (e.g., shard by user_id so all of a user's data is together)."
                ),
            },
        ],
        "real_world_examples": [
            "Instagram shards by user_id — all of a user's photos, likes, and comments are on the same shard",
            "MongoDB supports both range and hash sharding natively with automatic balancing",
            "Vitess (YouTube's MySQL sharding layer) adds sharding on top of MySQL with a routing proxy",
            "DynamoDB partitions by partition key hash, with automatic splitting of hot partitions",
        ],
        "common_interview_questions": [
            "How would you shard a user database?  What is the shard key?  What if one user has 100x more data than others?",
            "Range vs hash sharding — when do you choose each?",
            "How do you handle cross-shard queries (e.g., 'find all orders this week' when orders are sharded by user_id)?",
            "A shard is overloaded.  How do you rebalance without downtime?",
            "How does sharding interact with transactions?  (Distributed transactions, 2PC, saga pattern)",
        ],
        "key_trade_offs": [
            "Range sharding (efficient range queries) vs hash sharding (uniform distribution)",
            "More shards = more parallelism but more operational complexity",
            "Co-locating data (fast local queries) vs distributing it (better load balance)",
            "Sharding introduces complexity — make sure you actually need it before adding it",
        ],
        "related_concepts": ["consistent_hashing", "database_indexing", "cap_theorem"],
    },

    # -----------------------------------------------------------------------
    # 5. Consistent Hashing
    # -----------------------------------------------------------------------
    "consistent_hashing": {
        "title": "Consistent Hashing",
        "introduction": (
            "Consistent hashing is a technique for distributing keys across nodes so that "
            "adding or removing a node only moves ~1/N of the keys (instead of almost all "
            "of them with key % N).  Nodes and keys are mapped onto a hash ring.  Each key "
            "is assigned to the first node clockwise from its position.  Virtual nodes "
            "improve balance by giving each physical node multiple positions on the ring."
        ),
        "key_concepts": [
            {
                "name": "The Hash Ring",
                "explanation": (
                    "Imagine a circle from 0 to 2^32.  Hash each node's identifier to a point on the ring.  "
                    "Hash each key to a point on the ring.  The key is assigned to the first node encountered "
                    "when walking clockwise.  This means adding/removing a node only affects keys between it "
                    "and the previous node."
                ),
            },
            {
                "name": "Virtual Nodes (Vnodes)",
                "explanation": (
                    "With few physical nodes, the ring can be unbalanced (one node owns a much larger arc).  "
                    "Solution: each physical node gets many virtual nodes (e.g., 150-200) spread around the ring.  "
                    "This smooths out the distribution and makes rebalancing more gradual."
                ),
            },
            {
                "name": "Node Addition / Removal",
                "explanation": (
                    "Adding a node: the new node takes ownership of a portion of the ring from its clockwise "
                    "neighbour.  Only the keys in that portion need to move.  Removing a node: its keys move to "
                    "the next clockwise node.  Total data movement is proportional to 1/N."
                ),
            },
            {
                "name": "Replication on the Ring",
                "explanation": (
                    "For fault tolerance, replicate each key to the next K-1 distinct physical nodes clockwise "
                    "on the ring.  On a write, coordinate with all K replicas.  On a read, read from the closest "
                    "replica (or from a quorum of R replicas for stronger consistency)."
                ),
            },
        ],
        "real_world_examples": [
            "Amazon DynamoDB and Apache Cassandra use consistent hashing for partition placement",
            "Memcached clients use consistent hashing to route keys to cache servers",
            "Akamai CDN uses consistent hashing to assign content to edge servers",
            "Discord uses consistent hashing to route voice traffic to voice servers",
        ],
        "common_interview_questions": [
            "Explain consistent hashing and why it is better than key % N.",
            "What problem do virtual nodes solve?  How many virtual nodes per physical node is typical?",
            "How would you handle a hot key on a consistent hash ring?",
            "How does consistent hashing support replication?",
            "If you add a new cache server, how much data needs to move?  Compare with modular hashing.",
        ],
        "key_trade_offs": [
            "More virtual nodes = better balance but more memory for the ring data structure",
            "Consistent hashing adds complexity vs simple modular hashing — only worth it if nodes change frequently",
            "Ring-based routing adds a lookup step vs direct hash — usually negligible but worth noting",
        ],
        "related_concepts": ["sharding", "caching", "cap_theorem"],
    },

    # -----------------------------------------------------------------------
    # 6. CAP Theorem
    # -----------------------------------------------------------------------
    "cap_theorem": {
        "title": "CAP Theorem",
        "introduction": (
            "The CAP theorem states that a distributed system can provide at most two of "
            "three guarantees: Consistency (every read sees the most recent write), "
            "Availability (every request gets a response), and Partition tolerance (the "
            "system operates despite network partitions).  Since network partitions are "
            "unavoidable in practice, the real choice is CP (consistency over availability) "
            "vs AP (availability over consistency).  Understanding this trade-off is "
            "essential for every system design interview."
        ),
        "key_concepts": [
            {
                "name": "Consistency",
                "explanation": (
                    "Linearizability / strong consistency: every read returns the latest write.  "
                    "Weaker forms: sequential consistency, causal consistency, eventual consistency.  "
                    "Stronger consistency is more expensive — requires coordination between replicas."
                ),
            },
            {
                "name": "Availability",
                "explanation": (
                    "Every non-failing node returns a response in reasonable time.  An 'available' system "
                    "does not hang or return errors for reads/writes, even during partitions.  "
                    "Note: CAP availability is stricter than '99.99% uptime' — it means literally every request succeeds."
                ),
            },
            {
                "name": "Partition Tolerance",
                "explanation": (
                    "The system continues to function even when network messages between nodes are lost or delayed.  "
                    "In any real distributed system, partitions WILL happen (transient network issues, switch failures).  "
                    "So you must tolerate partitions — the choice is between C and A."
                ),
            },
            {
                "name": "CP vs AP Systems",
                "explanation": (
                    "CP systems (e.g., ZooKeeper, HBase, Spanner): during a partition, reject writes/reads to maintain consistency.  "
                    "AP systems (e.g., Cassandra, DynamoDB, CouchDB): during a partition, serve (possibly stale) data to maintain availability.  "
                    "Most real systems are tunable — e.g., Cassandra lets you choose consistency level per query."
                ),
            },
            {
                "name": "PACELC Extension",
                "explanation": (
                    "CAP only describes behaviour during partitions.  PACELC adds: even when there is no partition (E), "
                    "there is a trade-off between latency (L) and consistency (C).  Example: DynamoDB is PA/EL — "
                    "available during partitions, low latency otherwise.  Spanner is PC/EC — consistent always, but higher latency."
                ),
            },
        ],
        "real_world_examples": [
            "Google Spanner: CP — uses TrueTime (GPS + atomic clocks) for global strong consistency, sacrifices availability during partitions",
            "Amazon DynamoDB: AP by default — highly available, eventually consistent; offers strongly consistent reads as an option",
            "Apache Cassandra: AP — tunable consistency (ONE, QUORUM, ALL) per query",
            "ZooKeeper: CP — used for leader election and configuration; unavailable during leader re-election",
        ],
        "common_interview_questions": [
            "Explain the CAP theorem.  Why can you only have two out of three?",
            "Is your design CP or AP?  Justify your choice for the given use case.",
            "How would you design a banking system (strong consistency) vs a social media feed (availability)?",
            "What is eventual consistency?  Give an example of when it is acceptable.",
            "What is the difference between CAP consistency and ACID consistency?",
        ],
        "key_trade_offs": [
            "Strong consistency (correct but slow/unavailable during partitions) vs eventual consistency (fast and available but stale reads possible)",
            "Per-operation tuning: some reads need strong consistency (account balance) while others tolerate staleness (follower count)",
            "The cost of coordination: consensus protocols (Paxos, Raft) add latency proportional to network round-trips",
        ],
        "related_concepts": ["sharding", "message_queues", "consistent_hashing"],
    },

    # -----------------------------------------------------------------------
    # 7. Message Queues
    # -----------------------------------------------------------------------
    "message_queues": {
        "title": "Message Queues",
        "introduction": (
            "Message queues decouple producers from consumers: the producer sends a message "
            "to the queue and moves on; the consumer processes it asynchronously.  This "
            "enables load levelling (absorb traffic spikes), fault isolation (consumer crash "
            "does not affect producer), and workflow orchestration.  The two main paradigms "
            "are point-to-point queues (one consumer per message) and pub/sub (message "
            "delivered to all subscribers).  Kafka and RabbitMQ are the dominant technologies."
        ),
        "key_concepts": [
            {
                "name": "Point-to-Point vs Pub/Sub",
                "explanation": (
                    "Point-to-point: each message is consumed by exactly one consumer — work distribution.  "
                    "Pub/Sub: each message is delivered to every subscriber — event broadcasting.  "
                    "Kafka supports both: consumer groups for point-to-point, multiple consumer groups for pub/sub."
                ),
            },
            {
                "name": "Apache Kafka",
                "explanation": (
                    "Distributed log-based message broker.  Messages are appended to partitioned topics and retained "
                    "for a configurable duration (not deleted on consumption).  Consumer groups track offsets.  "
                    "High throughput, strong ordering within a partition.  Use case: event streaming, change data capture, "
                    "log aggregation."
                ),
            },
            {
                "name": "RabbitMQ",
                "explanation": (
                    "Traditional message broker (AMQP-based).  Messages are routed via exchanges to queues.  "
                    "Supports complex routing (topic, fanout, headers).  Messages are deleted after acknowledgement.  "
                    "Lower throughput than Kafka but richer routing and simpler semantics for task queues."
                ),
            },
            {
                "name": "Delivery Guarantees",
                "explanation": (
                    "At-most-once: send and forget — fast but messages can be lost.  "
                    "At-least-once: retry until acknowledged — messages can be duplicated (consumer must be idempotent).  "
                    "Exactly-once: the holy grail — Kafka achieves it with idempotent producers + transactional consumers, "
                    "but it is complex and has a performance cost."
                ),
            },
            {
                "name": "Dead Letter Queues (DLQ)",
                "explanation": (
                    "Messages that fail processing repeatedly are moved to a DLQ instead of blocking the main queue.  "
                    "DLQ messages can be inspected, debugged, and replayed.  Essential for production reliability."
                ),
            },
        ],
        "real_world_examples": [
            "LinkedIn uses Kafka for real-time activity tracking (views, clicks, messages) — trillions of messages/day",
            "Uber uses Kafka for trip events and driver location updates",
            "Shopify uses RabbitMQ for background job processing (order fulfilment, email sending)",
            "AWS SQS + Lambda: serverless event processing with automatic scaling",
        ],
        "common_interview_questions": [
            "Why use a message queue instead of direct API calls between services?",
            "How would you ensure exactly-once processing in a distributed system?",
            "Kafka vs RabbitMQ — when would you choose each?",
            "How would you handle a consumer that is slower than the producer (backpressure)?",
            "Design a notification system that sends emails, push notifications, and SMS — how do you use queues?",
        ],
        "key_trade_offs": [
            "Kafka (high throughput, log retention, replay) vs RabbitMQ (routing flexibility, simpler operations)",
            "At-least-once simplicity vs exactly-once correctness — most systems use at-least-once with idempotent consumers",
            "More partitions = more parallelism but more complexity in ordering and rebalancing",
            "Async processing improves resilience but adds latency and debugging complexity",
        ],
        "related_concepts": ["api_design", "cap_theorem", "sharding"],
    },

    # -----------------------------------------------------------------------
    # 8. Database Indexing
    # -----------------------------------------------------------------------
    "database_indexing": {
        "title": "Database Indexing",
        "introduction": (
            "An index is a data structure that speeds up reads at the cost of extra storage "
            "and slower writes.  Without an index, every query is a full table scan — O(n).  "
            "With a B-tree index, point lookups are O(log n) and range scans are efficient.  "
            "Choosing the right indexes is one of the highest-leverage skills in system design "
            "and backend engineering.  Over-indexing wastes space and slows writes; under-indexing "
            "causes slow queries and cascading performance problems."
        ),
        "key_concepts": [
            {
                "name": "B-Tree Indexes",
                "explanation": (
                    "The default index type in most relational databases (PostgreSQL, MySQL).  A balanced "
                    "tree where each node contains multiple keys and pointers.  Supports point lookups (=), "
                    "range queries (BETWEEN, <, >), and prefix searches (LIKE 'foo%').  Maintains sorted order, "
                    "so ORDER BY on the indexed column is free."
                ),
            },
            {
                "name": "Hash Indexes",
                "explanation": (
                    "Maps keys to values via a hash function.  O(1) point lookups (=) but does NOT support "
                    "range queries, sorting, or prefix matching.  Used in memory-based systems (e.g., Redis, "
                    "PostgreSQL's hash index type).  Rarely the right choice for on-disk databases."
                ),
            },
            {
                "name": "Composite (Multi-Column) Indexes",
                "explanation": (
                    "An index on (col_a, col_b, col_c) supports queries filtering on: (a), (a, b), or (a, b, c) — "
                    "but NOT (b) alone or (b, c) alone.  This is the 'leftmost prefix' rule.  Column order matters: "
                    "put the highest-cardinality or most-filtered column first.  One good composite index often "
                    "replaces multiple single-column indexes."
                ),
            },
            {
                "name": "Covering Indexes",
                "explanation": (
                    "If an index contains all columns needed by a query, the DB can answer the query from the index "
                    "alone without touching the main table (an 'index-only scan').  This is extremely fast.  "
                    "Use INCLUDE (in PostgreSQL) to add non-key columns to an index."
                ),
            },
            {
                "name": "Write Amplification and Trade-offs",
                "explanation": (
                    "Every index must be updated on every INSERT, UPDATE, and DELETE.  More indexes = slower writes.  "
                    "B-tree writes are O(log n).  LSM-tree based storage (RocksDB, Cassandra) amortises writes "
                    "with compaction but at the cost of read amplification.  The right balance depends on your "
                    "read/write ratio."
                ),
            },
        ],
        "real_world_examples": [
            "PostgreSQL: B-tree by default; GIN indexes for full-text search and JSONB containment queries",
            "MySQL InnoDB: clustered index on the primary key — rows are physically ordered by PK",
            "MongoDB: B-tree indexes; compound indexes for multi-field queries; TTL indexes for auto-expiry",
            "DynamoDB: primary key (partition + sort key) is the main index; GSIs for alternative access patterns",
        ],
        "common_interview_questions": [
            "You have a slow query.  How do you investigate?  (EXPLAIN ANALYZE, check for seq scans, add indexes)",
            "What is the difference between a clustered and non-clustered index?",
            "How does a composite index work?  Can a query on (b, c) use an index on (a, b, c)?",
            "When would you NOT add an index?  (Write-heavy table, low cardinality column, tiny table)",
            "How do indexes interact with joins?  (Nested loop join uses index lookups; hash join does not)",
        ],
        "key_trade_offs": [
            "Read speed (more indexes) vs write speed (fewer indexes) — optimize for your workload's read/write ratio",
            "B-tree (range queries, sorting) vs hash index (fastest point lookups but no ranges)",
            "Covering index (fastest reads) vs storage cost of duplicating columns in the index",
            "Indexing high-cardinality columns (selective) vs low-cardinality (less selective, less useful)",
        ],
        "related_concepts": ["sharding", "caching", "cap_theorem"],
    },
}
