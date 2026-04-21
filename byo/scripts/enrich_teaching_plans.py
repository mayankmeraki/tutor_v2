#!/usr/bin/env python3
"""
Enrich ALL existing teaching plans in MongoDB with richer pedagogical content.

Adds new fields (teaching_flow, board_plan, difficulty_progression,
check_questions, when_to_use, related_topics) to every document in
tutor_v2.teaching_plans WITHOUT overwriting existing fields.

Usage:
    python -m byo.scripts.enrich_teaching_plans
    python -m byo.scripts.enrich_teaching_plans --dry-run
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


# ═══════════════════════════════════════════════════════════════════════════
# ENRICHMENT DATA — keyed by slug
# ═══════════════════════════════════════════════════════════════════════════

ENRICHMENTS = {

    # =====================================================================
    # DSA TOPICS — Original 12
    # =====================================================================

    "arrays_hashing": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Pose this problem: 'Given a list of expenses, find two that sum to your budget.' Let the student think brute-force O(n^2). Don't mention hash maps yet."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce hash maps: O(1) average lookup. Draw an array and a hash map side by side. Show how storing complements eliminates the inner loop. Use the ds command to visualize a hash_map."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Two Sum step by step. For each element, check if complement exists in the map, then insert. Animate the hash map filling up using ds commands."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name the pattern: 'Complement Lookup.' Show that this same idea applies to frequency counting (Valid Anagram) and grouping (Group Anagrams). The core trick: trade O(n) space for O(1) lookup."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give the student 'Valid Anagram.' Let them try using frequency counting. If they struggle, hint: 'What if you counted each character?' If they solve it fast, jump to Group Anagrams."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Hash maps turn O(n) search into O(1) lookup. Three sub-patterns: complement lookup, frequency counting, grouping by key. Preview: Two Pointers uses similar ideas on sorted data."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Arrays & Hashing' + text 'You have a list of expenses. Find two that add up to $100. How?'"},
            {"step": 2, "content": "ds hash_map showing key-value pairs + callout 'O(1) avg lookup — the complement trick'"},
            {"step": 3, "content": "Step-by-step Two Sum: ds array with pointer scanning left to right, ds hash_map growing with each step"},
            {"step": 4, "content": "callout 'Pattern: Complement Lookup' + text listing 3 sub-patterns"},
            {"step": 5, "content": "New problem: h2 'Valid Anagram' + push_code with function signature: def isAnagram(s: str, t: str) -> bool"},
        ],
        "difficulty_progression": "Start with Two Sum (easy, single hash map lookup). If solved quickly, skip to Group Anagrams (medium, grouping by sorted key). If struggling, add Contains Duplicate as an intermediate step before progressing.",
        "check_questions": [
            "What's the brute force for Two Sum? What's its time complexity?",
            "Why does a hash map make this O(n) instead of O(n^2)?",
            "For Group Anagrams, what should we use as the hash map key?",
            "What happens if there are duplicate values in Two Sum?",
        ],
        "when_to_use": "Use hash maps when you see a nested search loop (O(n^2)) that can be replaced with a lookup table. Key signals: 'find a pair,' 'count occurrences,' 'group by some property,' or 'check if X exists.'",
        "related_topics": ["two_pointers", "sliding_window", "sorting"],
    },

    "two_pointers": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show a sorted array and ask: 'Find two numbers that add to a target.' Student knows hash map from previous topic — now challenge them: 'Can you do it without extra space?' Don't reveal the technique yet."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce two pointers: left at start, right at end. If sum < target, move left right. If sum > target, move right left. Draw the sorted array with two arrows converging. Explain why this works: sorted order guarantees progress."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Two Sum II on a sorted array. Animate L and R converging. Show exactly why we move the smaller pointer up (can't increase sum by moving the larger pointer left)."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name the three flavors: (1) Opposite-end squeeze (converging), (2) Slow/fast (cycle detection), (3) Two arrays (merge). Show that 3Sum is just 'fix one + two-pointer on the rest.'"},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Container With Most Water. Let the student figure out: always move the shorter side. If they solve quickly, try 3Sum with duplicate handling."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Two pointers prune O(n^2) to O(n) by moving intelligently. Need sorted data or a convergence invariant. Preview: Sliding Window extends this to subarray problems."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Two Pointers' + ds array (sorted) + text 'Find two numbers summing to target — without extra space'"},
            {"step": 2, "content": "ds array with L and R arrows annotated, callout 'Move L right if sum too small, R left if too big'"},
            {"step": 3, "content": "Step-by-step Two Sum II: ds array with L/R arrows moving, showing sum at each step"},
            {"step": 4, "content": "callout 'Three flavors' + text: squeeze, slow/fast, merge-style"},
            {"step": 5, "content": "h2 'Container With Most Water' + push_code: def maxArea(height: List[int]) -> int"},
        ],
        "difficulty_progression": "Start with Valid Palindrome (easy, pure squeeze). Move to Two Sum II (medium, squeeze with arithmetic). Then Container With Most Water (medium, greedy squeeze). If strong, try 3Sum with dedup or Trapping Rain Water.",
        "check_questions": [
            "Why does the two-pointer approach work on sorted data?",
            "In Container With Most Water, why do we move the shorter side?",
            "What's the key difference between opposite-end squeeze and slow/fast pointers?",
            "For 3Sum, how do you handle duplicate triplets?",
        ],
        "when_to_use": "Use two pointers when the input is sorted (or can be sorted) and you need to find pairs/triplets satisfying a condition. Also use slow/fast pointers for cycle detection in linked lists. Key signal: 'find a pair in sorted data' or 'detect a cycle.'",
        "related_topics": ["sliding_window", "binary_search", "linked_list", "arrays_hashing"],
    },

    "sliding_window": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Find the longest substring with no repeating characters in abcabcbb.' Let the student consider brute force (check all substrings). Then ask: 'What if I told you there's an O(n) way?'"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce the sliding window: a contiguous subarray bounded by left and right pointers. Right expands, left contracts. Two types: fixed-size (slide in lockstep) and variable-size (expand/contract). Draw the window bracket on the array."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Longest Substring Without Repeating Characters. Show the window expanding right, and contracting left when a duplicate enters. Use a frequency map beside the array. Animate each step."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name the pattern: 'Variable Sliding Window.' Show the template: expand right, check condition, shrink left until valid, update answer. Contrast with fixed window (e.g., max sum of k consecutive elements)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Permutation in String (fixed window). Let them figure out the frequency-match counter trick. If fast, try Minimum Window Substring."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Each element enters and leaves the window at most once — O(n). The window invariant defines what 'valid' means. Preview: Monotonic stack/deque for Sliding Window Maximum."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Sliding Window' + text 'Find the longest substring with no repeating chars in: abcabcbb'"},
            {"step": 2, "content": "ds array with bracket highlighting a subarray, callout 'Right expands, left contracts'"},
            {"step": 3, "content": "Animated walkthrough: ds array with window bracket moving, ds hash_map showing char frequencies"},
            {"step": 4, "content": "callout 'Template: expand right, shrink left, update best' + text fixed vs variable"},
            {"step": 5, "content": "h2 'Permutation in String' + push_code: def checkInclusion(s1: str, s2: str) -> bool"},
        ],
        "difficulty_progression": "Start with Best Time to Buy and Sell Stock (easy, track running min). Then Longest Substring Without Repeating Characters (medium, variable window). Then Permutation in String (medium, fixed window). If strong, Minimum Window Substring (hard).",
        "check_questions": [
            "What defines the 'window invariant' for this problem?",
            "When should we shrink the left pointer?",
            "What's the difference between a fixed-size and variable-size window?",
            "Why is the time complexity O(n) even though we have two pointers?",
        ],
        "when_to_use": "Use sliding window when the problem involves a contiguous subarray or substring and you need to optimize over all possible windows. Key signals: 'longest/shortest subarray with property X,' 'substring containing all characters of Y,' or 'maximum sum of k consecutive elements.'",
        "related_topics": ["two_pointers", "arrays_hashing", "heap"],
    },

    "stack": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show the string '({[]})' and ask: 'How do you check if brackets are balanced?' Let the student think about it. Then show '([)]' — how do you detect the mismatch?"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce the stack: LIFO. Push openers, pop on closers. If mismatch or stack non-empty at end, invalid. Draw a stack growing/shrinking. Then introduce monotonic stack: maintain sorted order for 'next greater element' queries."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Valid Parentheses with several test cases. Animate the stack push/pop. Then show Daily Temperatures with a monotonic decreasing stack: pop smaller elements when a warmer day arrives."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name three stack patterns: (1) Matching/nesting, (2) Monotonic stack (next greater/smaller), (3) Expression evaluation. The common thread: 'remember something and come back to it later.'"},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Daily Temperatures. Let the student implement the monotonic stack approach. If fast, try Evaluate Reverse Polish Notation."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Stacks handle anything with nesting or 'next element' queries. Monotonic stacks are O(n) because each element is pushed and popped at most once. Preview: Stacks underlie recursion and DFS."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Stack' + text '({[]})  — balanced?   ([)]  — balanced?' "},
            {"step": 2, "content": "ds stack showing push/pop operations + callout 'LIFO: last in, first out'"},
            {"step": 3, "content": "Valid Parentheses walkthrough with ds stack animations, then Daily Temperatures with monotonic stack"},
            {"step": 4, "content": "callout 'Three patterns: matching, monotonic, evaluation'"},
            {"step": 5, "content": "h2 'Daily Temperatures' + push_code: def dailyTemperatures(temperatures: List[int]) -> List[int]"},
        ],
        "difficulty_progression": "Start with Valid Parentheses (easy). Then Min Stack (medium, auxiliary stack design). Then Daily Temperatures (medium, monotonic stack). If strong, Largest Rectangle in Histogram (hard).",
        "check_questions": [
            "Why is a stack the right data structure for bracket matching?",
            "In a monotonic decreasing stack, what happens when we encounter a larger element?",
            "Why is the monotonic stack approach O(n) even though it has nested loops?",
            "How would you evaluate '3 4 + 2 *' using a stack?",
        ],
        "when_to_use": "Use a stack when you need to process elements in LIFO order: matching brackets, nested structures, undo operations. Use a monotonic stack when you need 'next greater/smaller element' — the key signal is comparing each element with previous ones.",
        "related_topics": ["arrays_hashing", "linked_list", "trees"],
    },

    "binary_search": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Play the number-guessing game: 'I'm thinking of a number between 1 and 100. You get yes/no for too high/too low.' Student naturally discovers halving. Ask: 'How many guesses for a million elements?'"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce binary search on a sorted array. Draw the array, show lo/hi/mid. The key: each comparison eliminates half the search space. O(log n). Then show the generalized version: binary search on an answer space (min/max that satisfies a condition)."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through standard binary search. Show the three cases: found, go left, go right. Then demonstrate Search in Rotated Sorted Array: find the sorted half, determine which half the target is in."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name two flavors: (1) Search for exact value in sorted data, (2) Search for a boundary/condition (first True, last True). The boundary version is more powerful — it handles Koko Eating Bananas, minimum capacity, etc."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Find Minimum in Rotated Sorted Array. Let the student figure out the invariant. If fast, try Koko Eating Bananas (binary search on answer)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Binary search works whenever you have a monotonic condition (sorted array, feasibility threshold). O(log n). Preview: Binary search appears inside other algorithms (merge sort, tree operations)."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Binary Search' + text 'Guess a number 1-100. Too high / too low. How many guesses?'"},
            {"step": 2, "content": "ds array (sorted) with lo/mid/hi markers + callout 'Each step eliminates half'"},
            {"step": 3, "content": "Walkthrough: ds array with lo/hi converging, showing mid calculations"},
            {"step": 4, "content": "callout 'Two flavors: exact match vs boundary search'"},
            {"step": 5, "content": "h2 'Find Min in Rotated Sorted Array' + push_code: def findMin(nums: List[int]) -> int"},
        ],
        "difficulty_progression": "Start with standard Binary Search (easy). Then Find Minimum in Rotated Sorted Array (medium). Then Search in Rotated Sorted Array (medium). If strong, Koko Eating Bananas or Median of Two Sorted Arrays (hard).",
        "check_questions": [
            "What's the loop invariant for standard binary search?",
            "In a rotated sorted array, how do you determine which half is sorted?",
            "When do you use lo < hi vs lo <= hi?",
            "How does binary search on an answer space work for Koko Eating Bananas?",
        ],
        "when_to_use": "Use binary search when the search space is sorted or has a monotonic property (all False then all True). Key signals: sorted array, 'find minimum/maximum that satisfies condition,' or 'minimize the maximum' / 'maximize the minimum.'",
        "related_topics": ["two_pointers", "sorting", "heap"],
    },

    "linked_list": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'You have a chain of nodes. How do you find the middle without knowing the length?' Pause for thought. Then ask: 'How do you detect if the chain has a loop?'"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce linked list: nodes with data + next pointer. Draw a singly linked list. Show slow/fast pointer technique: slow moves 1, fast moves 2. When fast hits end, slow is at middle. For cycles, they'll meet inside the loop (Floyd's algorithm)."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Reverse Linked List iteratively: maintain prev, curr, next. Animate pointer rewiring at each step. Then show the recursive version. Both O(n) time, O(1) vs O(n) space."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name the core linked list techniques: (1) Slow/fast pointers (middle, cycle), (2) Pointer reversal, (3) Dummy head node (simplifies edge cases), (4) Merge two lists. Show that many problems combine these."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Merge Two Sorted Lists. Let the student use a dummy head. If fast, try Linked List Cycle (detect and find entry point) or Reorder List."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Linked lists test pointer manipulation skills. The dummy head trick eliminates special cases for the head node. Slow/fast pointers solve middle/cycle problems. Preview: Trees are linked lists with two children."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Linked List' + text 'Find the middle of a chain without knowing its length'"},
            {"step": 2, "content": "ds linked_list with slow/fast pointer annotations + callout 'Slow moves 1, fast moves 2'"},
            {"step": 3, "content": "Reverse Linked List: step-by-step pointer rewiring with ds linked_list animations"},
            {"step": 4, "content": "callout 'Techniques: slow/fast, reversal, dummy head, merge'"},
            {"step": 5, "content": "h2 'Merge Two Sorted Lists' + push_code: def mergeTwoLists(l1, l2) -> ListNode"},
        ],
        "difficulty_progression": "Start with Reverse Linked List (easy). Then Merge Two Sorted Lists (easy). Then Linked List Cycle (medium, Floyd's). If strong, Merge K Sorted Lists or LRU Cache (hard).",
        "check_questions": [
            "Why does slow/fast pointer find the middle of a linked list?",
            "In Floyd's cycle detection, why do the pointers always meet inside the cycle?",
            "What's the benefit of using a dummy head node?",
            "How do you reverse a linked list without extra space?",
        ],
        "when_to_use": "Use linked list techniques when you need O(1) insertion/deletion at known positions, or when the problem explicitly involves node chains. Key signals: 'reverse a list,' 'detect cycle,' 'merge sorted lists,' or 'find middle/kth from end.'",
        "related_topics": ["two_pointers", "stack", "trees"],
    },

    "trees": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Draw a family tree and ask: 'How would you visit every person? How would you find the oldest common ancestor of two people?' Trees are everywhere — file systems, org charts, HTML DOM."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce binary trees: each node has left and right children. Show the three DFS traversals (preorder, inorder, postorder) and BFS (level-order). Draw a BST and show the sorted-order property. Use ds tree to visualize."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Invert Binary Tree recursively: swap left and right children, recurse. Then Maximum Depth: 1 + max(depth(left), depth(right)). Animate the recursive calls on the tree."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name the patterns: (1) Recursive DFS with return value (depth, diameter), (2) Recursive DFS with global variable (max path sum), (3) BFS level-order (right side view, zigzag), (4) BST in-order = sorted. Most tree problems are 'compute something bottom-up.'"},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Validate BST. Let the student figure out the range-based approach (each node has a valid min/max range). If fast, try Lowest Common Ancestor."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Trees = recursion. Think about what info you need from children to compute the answer at the current node. BST property enables O(log n) search. Preview: Graphs generalize trees (with cycles and multiple parents)."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Trees' + ds tree showing a binary tree + text 'How to visit every node?'"},
            {"step": 2, "content": "ds tree with traversal order labeled (preorder, inorder, postorder) + callout 'BST: left < root < right'"},
            {"step": 3, "content": "Invert Binary Tree and Max Depth: animated ds tree showing recursive swaps and depth computation"},
            {"step": 4, "content": "callout 'Patterns: DFS with return, DFS with global, BFS level-order, BST in-order'"},
            {"step": 5, "content": "h2 'Validate BST' + push_code: def isValidBST(root: TreeNode) -> bool"},
        ],
        "difficulty_progression": "Start with Invert Binary Tree (easy). Then Maximum Depth (easy). Then Validate BST (medium, range-based). If strong, Binary Tree Maximum Path Sum (hard) or Serialize/Deserialize Binary Tree (hard).",
        "check_questions": [
            "What's the difference between preorder, inorder, and postorder traversal?",
            "How do you validate a BST? Why isn't just checking left < root < right sufficient?",
            "What information do you need from the children to compute the diameter?",
            "When would you use BFS instead of DFS on a tree?",
        ],
        "when_to_use": "Trees appear in any hierarchical structure. Use recursive DFS when you need to compute something bottom-up (depth, path sum). Use BFS when you need level-by-level processing. Use BST properties when the tree is sorted.",
        "related_topics": ["graphs", "dynamic_programming", "backtracking"],
    },

    "graphs": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show a social network: 'You and your friends form a graph. Can you reach everyone from anyone? How do you find the shortest path between two people?' Maps, flights, dependencies — all graphs."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce graphs: nodes (vertices) and edges. Directed vs undirected. Adjacency list vs adjacency matrix. Show BFS (shortest path in unweighted) vs DFS (explore fully, detect cycles). Use ds graph to visualize."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Number of Islands using DFS on a grid. Each cell is a node, 4-directional neighbors are edges. Flood-fill each unvisited '1', increment count. Show the visited marking."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name the patterns: (1) DFS/BFS traversal + visited set, (2) Connected components, (3) Topological sort (DAGs), (4) Shortest path (BFS unweighted, Dijkstra weighted), (5) Union-Find for dynamic connectivity."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Clone Graph. Let the student handle the visited map to avoid infinite loops. If fast, try Course Schedule (cycle detection with topological sort)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Graphs = nodes + edges. BFS for shortest path, DFS for full exploration. Always use a visited set. Grids are graphs in disguise. Preview: Topological sort for dependency ordering, Dijkstra for weighted paths."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Graphs' + ds graph showing a social network + text 'Can you reach everyone? Shortest path?'"},
            {"step": 2, "content": "ds graph with adjacency list representation + callout 'BFS = shortest path, DFS = full exploration'"},
            {"step": 3, "content": "Number of Islands: ds grid showing flood-fill DFS, cells colored as visited"},
            {"step": 4, "content": "callout 'Patterns: traversal, components, topo sort, shortest path, union-find'"},
            {"step": 5, "content": "h2 'Clone Graph' + push_code: def cloneGraph(node: Node) -> Node"},
        ],
        "difficulty_progression": "Start with Number of Islands (medium, grid DFS). Then Clone Graph (medium, DFS with hash map). Then Course Schedule (medium, cycle detection). If strong, Word Ladder (hard, BFS) or Network Delay Time (Dijkstra).",
        "check_questions": [
            "What's the difference between BFS and DFS on a graph?",
            "Why do we need a visited set for graphs but not for trees?",
            "How do you detect a cycle in a directed graph vs an undirected graph?",
            "When would you use Dijkstra instead of BFS?",
        ],
        "when_to_use": "Use graph algorithms when the problem involves connections between entities: social networks, maps, dependencies, grids. Key signals: 'connected components,' 'shortest path,' 'can you reach X from Y,' or 'order of dependencies.'",
        "related_topics": ["trees", "dynamic_programming", "heap"],
    },

    "dynamic_programming": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'How many ways can you climb a staircase with 1 or 2 steps at a time?' Let the student try recursive brute force. Show the recursion tree — exponential! 'Notice we're recomputing the same things...'"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Draw the Fibonacci recursion tree. Circle the repeated subproblems. Introduce memoization (top-down: cache results) and tabulation (bottom-up: fill a table). Show how O(2^n) becomes O(n). Use ds array to show the DP table."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Climbing Stairs: dp[i] = dp[i-1] + dp[i-2]. Then House Robber: dp[i] = max(dp[i-1], dp[i-2] + nums[i]). Show the take/skip decision at each step. Animate the DP table filling."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name the DP families: (1) Linear (Climbing Stairs, House Robber), (2) Knapsack (Coin Change, 0/1 Knapsack), (3) Two-string (LCS, Edit Distance), (4) Interval (Burst Balloons), (5) Grid (Unique Paths). The recipe: define state, write recurrence, identify base cases."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Coin Change. Let the student define the state (dp[amount] = min coins). If they struggle, hint: 'For each coin, what's the subproblem?' If fast, try Longest Common Subsequence (2D DP)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: DP = overlapping subproblems + optimal substructure. Recipe: state -> recurrence -> base case. Start top-down (easier to think), optimize to bottom-up (faster, saves stack). Preview: DP appears in trees (tree DP) and graphs (shortest path)."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Dynamic Programming' + text 'Climb n stairs: 1 or 2 steps. How many ways?'"},
            {"step": 2, "content": "ds tree showing Fibonacci recursion tree with repeated nodes circled + callout 'Overlapping subproblems!'"},
            {"step": 3, "content": "ds array showing DP table for Climbing Stairs filling left to right, then House Robber take/skip"},
            {"step": 4, "content": "callout 'Five DP families: linear, knapsack, two-string, interval, grid'"},
            {"step": 5, "content": "h2 'Coin Change' + push_code: def coinChange(coins: List[int], amount: int) -> int"},
        ],
        "difficulty_progression": "Start with Climbing Stairs (easy, Fibonacci variant). Then House Robber (medium, take/skip). Then Coin Change (medium, unbounded knapsack). If strong, Longest Common Subsequence (2D) or Burst Balloons (interval DP).",
        "check_questions": [
            "What are the two properties a problem needs for DP to apply?",
            "What's the difference between top-down and bottom-up DP?",
            "For House Robber, what's the recurrence relation?",
            "How do you identify the state for a DP problem?",
        ],
        "when_to_use": "Use DP when the problem has overlapping subproblems (same computation repeated) and optimal substructure (optimal solution built from optimal sub-solutions). Key signals: 'how many ways,' 'minimum/maximum cost,' 'longest/shortest sequence,' or 'can you partition into...'",
        "related_topics": ["backtracking", "greedy", "graphs", "trees"],
    },

    "backtracking": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Generate all possible subsets of {1, 2, 3}.' Let the student think about it. Then: 'Now generate all permutations.' These are decision trees — at each step, choose or don't choose."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce backtracking: build candidates incrementally, abandon a candidate as soon as it violates constraints ('prune'). Draw the decision tree for subsets. Show the choose-explore-unchoose pattern. This is DFS on a decision tree."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Subsets: for each element, include or exclude. Show the binary decision tree. Then Permutations: at each position, try each unused element. Show the pruning of already-used elements."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name the templates: (1) Subsets (include/exclude), (2) Permutations (choose from remaining), (3) Combinations (choose k from n), (4) Constraint satisfaction (N-Queens, Sudoku). All follow: choose, explore, unchoose."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Combination Sum. Let the student figure out: at each step, choose a number (can reuse) and reduce the target. If fast, try N-Queens."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Backtracking = DFS on a decision tree with pruning. The three templates (subsets, permutations, combinations) cover 90% of problems. Pruning is what makes it tractable. Preview: Backtracking + memoization = DP."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Backtracking' + text 'Generate all subsets of {1, 2, 3}'"},
            {"step": 2, "content": "ds tree showing the binary decision tree for subsets + callout 'Choose, explore, unchoose'"},
            {"step": 3, "content": "Subsets tree with include/exclude at each level, then Permutations tree with used-element pruning"},
            {"step": 4, "content": "callout 'Templates: subsets, permutations, combinations, constraint satisfaction'"},
            {"step": 5, "content": "h2 'Combination Sum' + push_code: def combinationSum(candidates: List[int], target: int) -> List[List[int]]"},
        ],
        "difficulty_progression": "Start with Subsets (medium, but conceptually simple). Then Permutations (medium). Then Combination Sum (medium, with reuse). If strong, N-Queens (hard) or Word Search (medium, grid backtracking).",
        "check_questions": [
            "What's the difference between subsets and permutations?",
            "How does pruning improve backtracking performance?",
            "In Combination Sum, how do you avoid duplicate combinations?",
            "What's the time complexity of generating all subsets of n elements?",
        ],
        "when_to_use": "Use backtracking when you need to enumerate all valid configurations: subsets, permutations, combinations, or constraint satisfaction. Key signals: 'generate all,' 'find all valid,' 'N-Queens,' 'Sudoku solver,' or 'word search on a grid.'",
        "related_topics": ["dynamic_programming", "trees", "graphs"],
    },

    "heap": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'You have a stream of numbers. At any point, tell me the median.' A sorted array works but is O(n) per insert. 'What if we could keep track of the top half and bottom half efficiently?'"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce the heap: a complete binary tree where parent >= children (max-heap) or parent <= children (min-heap). O(log n) insert and extract. Draw the heap as a tree and show the array representation. heapq in Python is a min-heap."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Kth Largest Element: maintain a min-heap of size k. If new element > heap top, replace top. The heap top is always the kth largest. Animate insertions and removals."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name the patterns: (1) Top-K (keep k elements in a heap), (2) Two-heap (find median with a max-heap for lower half + min-heap for upper half), (3) Merge K sorted (heap of k pointers), (4) Priority scheduling (task scheduler, meeting rooms)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Merge K Sorted Lists. Let the student figure out: push the head of each list into a min-heap, pop the smallest, push the next from that list. If fast, try Find Median from Data Stream."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Heaps give O(log n) access to the min/max. Use when you repeatedly need the smallest/largest element. Two-heap pattern solves running median. Preview: Dijkstra's algorithm uses a min-heap for shortest paths."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Heap / Priority Queue' + text 'Stream of numbers — find the median at any point'"},
            {"step": 2, "content": "ds tree showing a min-heap + callout 'Parent <= children. O(log n) insert/extract'"},
            {"step": 3, "content": "Kth Largest: ds array becoming a min-heap of size k, showing insertions and top replacement"},
            {"step": 4, "content": "callout 'Patterns: Top-K, Two-Heap, Merge-K, Priority scheduling'"},
            {"step": 5, "content": "h2 'Merge K Sorted Lists' + push_code: def mergeKLists(lists: List[ListNode]) -> ListNode"},
        ],
        "difficulty_progression": "Start with Kth Largest Element (medium, top-K with min-heap). Then Last Stone Weight (easy). Then Merge K Sorted Lists (hard but elegant). If strong, Find Median from Data Stream (two-heap).",
        "check_questions": [
            "Why do we use a min-heap of size k for the kth largest element (not a max-heap)?",
            "How does the two-heap approach maintain the running median?",
            "What's the time complexity of merging K sorted lists with a heap?",
            "When would you use a heap vs sorting the entire array?",
        ],
        "when_to_use": "Use a heap when you repeatedly need the minimum or maximum element: 'kth largest/smallest,' 'merge K sorted,' 'find median of a stream,' 'schedule by priority.' Key signal: you need quick access to extremes in a dynamic collection.",
        "related_topics": ["arrays_hashing", "binary_search", "graphs"],
    },

    "greedy": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'You have coins of 25, 10, 5, 1 cent. Make change for 47 cents using the fewest coins.' Student naturally uses the largest coin first — that's greedy! Then ask: 'Does this always work?' (Hint: coins [1, 3, 4], amount 6)."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce greedy: at each step, make the locally optimal choice. It works when the greedy choice is provably optimal (exchange argument or greedy stays ahead). Contrast with DP where you explore all choices. Greedy is faster but only works for specific problems."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Jump Game: from each position, can you reach the end? Track the farthest reachable index. If current position > farthest reachable, return False. Show that greedy works because reaching further is always at least as good."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Name the common greedy patterns: (1) Interval scheduling (sort by end, pick non-overlapping), (2) Activity selection, (3) Huffman coding, (4) Jump game (farthest reach). The key: prove the greedy choice doesn't miss a better solution."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Jump Game II (minimum jumps). Let the student figure out the BFS-like greedy: at each 'level,' find the farthest you can reach. If fast, try Gas Station."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Greedy makes the best local choice at each step. Prove it works with exchange argument: swapping a non-greedy choice for the greedy choice never makes things worse. If greedy doesn't work, use DP. Preview: Greedy appears in graph algorithms (Dijkstra, Prim, Kruskal)."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Greedy' + text 'Make 47 cents with fewest coins: 25, 10, 5, 1. Does greedy always work?'"},
            {"step": 2, "content": "callout 'Greedy: locally optimal choice at each step' + text 'Works when greedy choice is provably optimal'"},
            {"step": 3, "content": "Jump Game: ds array with farthest-reachable index tracker, showing greedy progress"},
            {"step": 4, "content": "callout 'Patterns: interval scheduling, activity selection, farthest reach, exchange argument'"},
            {"step": 5, "content": "h2 'Jump Game II' + push_code: def jump(nums: List[int]) -> int"},
        ],
        "difficulty_progression": "Start with Jump Game (medium, reachability). Then Maximum Subarray (Kadane's, medium). Then Jump Game II (medium). If strong, Gas Station or Merge Intervals (greedy after sorting).",
        "check_questions": [
            "How do you prove a greedy algorithm is correct?",
            "Why does greedy work for US coin denominations but not all coin sets?",
            "What's the greedy invariant in Jump Game?",
            "When should you use DP instead of greedy?",
        ],
        "when_to_use": "Use greedy when you can prove the locally optimal choice leads to the globally optimal solution. Key signals: 'minimum number of X,' 'maximum non-overlapping intervals,' 'furthest reach,' or any problem where choosing the best available option at each step is provably optimal.",
        "related_topics": ["dynamic_programming", "heap", "sorting"],
    },

    # =====================================================================
    # DSA TOPICS — Missing plans (seed_missing_plans.py)
    # =====================================================================

    "dp": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show Fibonacci recursion tree: fib(5) calls fib(4) and fib(3), fib(4) calls fib(3) and fib(2)... 'We're computing fib(3) twice, fib(2) three times! Can we fix this?'"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce memoization: store computed results in a cache. Show the same recursion tree but crossing out already-computed nodes. Then show tabulation: fill a table bottom-up. O(2^n) becomes O(n). Use ds array to show the DP table."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Climbing Stairs: dp[i] = dp[i-1] + dp[i-2], base cases dp[0]=1, dp[1]=1. Then House Robber with take/skip: dp[i] = max(dp[i-1], dp[i-2]+nums[i])."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "The DP recipe: (1) Define state, (2) Write recurrence, (3) Identify base cases, (4) Determine fill order, (5) Optimize space if possible. Five families: linear, knapsack, two-string, interval, grid."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Coin Change (unbounded knapsack). Let the student define dp[amount] = min coins. If fast, try Longest Common Subsequence (2D DP on two strings)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: DP = recursion + caching. The hardest part is defining the state correctly. Start top-down for correctness, convert to bottom-up for performance. Space optimization: if dp[i] only depends on dp[i-1], use rolling variables."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Dynamic Programming' + ds tree showing Fibonacci recursion tree with duplicate nodes highlighted"},
            {"step": 2, "content": "Same tree with crossed-out duplicates + ds array showing DP table filling left-to-right"},
            {"step": 3, "content": "Climbing Stairs DP table + House Robber take/skip decision at each index"},
            {"step": 4, "content": "callout 'DP Recipe: state -> recurrence -> base case -> fill order -> optimize space'"},
            {"step": 5, "content": "h2 'Coin Change' + push_code: def coinChange(coins: List[int], amount: int) -> int"},
        ],
        "difficulty_progression": "Start with Climbing Stairs (easy). Then House Robber (medium, take/skip). Then Coin Change (medium, unbounded knapsack). If strong, Longest Common Subsequence (2D) or Burst Balloons (interval DP, hard).",
        "check_questions": [
            "What's the difference between memoization and tabulation?",
            "How do you identify overlapping subproblems?",
            "For Coin Change, why is the state dp[amount] and not dp[coin_index]?",
            "When can you optimize a 2D DP to 1D?",
        ],
        "when_to_use": "Use DP when the problem has overlapping subproblems and optimal substructure. Key signals: 'minimum/maximum cost,' 'number of ways,' 'longest/shortest sequence,' 'can you partition.' If the recursion tree has repeated states, add memoization.",
        "related_topics": ["dynamic_programming", "backtracking", "greedy"],
    },

    "string": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Is racecar a palindrome? How about A man, a plan, a canal: Panama?' Show that strings are just arrays of characters — most string problems are array problems with a 26-letter alphabet constraint."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Key string techniques: (1) Two-pointer for palindromes, (2) Sliding window for substrings, (3) Frequency counting with int[26], (4) StringBuilder for efficient concatenation. Strings are immutable in most languages — know the cost."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Longest Palindromic Substring: expand from each center (2n-1 centers including between-character positions). Show the expansion stopping when characters mismatch."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "String patterns map to array patterns: palindrome check (two pointers), longest substring (sliding window), anagram check (frequency count), prefix matching (trie). The alphabet is usually size 26 — constant space."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Longest Substring Without Repeating Characters. Let the student use sliding window + set. If fast, try Minimum Window Substring."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Strings = arrays of chars. Leverage the small alphabet (26 letters = O(1) space). Most string problems reduce to sliding window, two pointers, or frequency counting. Immutability means O(n) to modify."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Strings' + text 'Is \"racecar\" a palindrome? What about \"A man, a plan, a canal: Panama\"?'"},
            {"step": 2, "content": "ds array showing a string as char array + callout '26 letters = constant-size frequency map'"},
            {"step": 3, "content": "Palindromic Substring: expand-from-center animation on 'babad'"},
            {"step": 4, "content": "callout 'String patterns = array patterns: two pointers, sliding window, frequency count, trie'"},
            {"step": 5, "content": "h2 'Longest Substring Without Repeating Characters' + push_code: def lengthOfLongestSubstring(s: str) -> int"},
        ],
        "difficulty_progression": "Start with Valid Palindrome (easy, two pointers). Then Longest Palindromic Substring (medium, expand from center). Then Longest Substring Without Repeating Characters (medium, sliding window). If strong, Minimum Window Substring (hard).",
        "check_questions": [
            "Why do we check 2n-1 centers for palindromic substrings?",
            "What's the time complexity of string concatenation in a loop?",
            "How does a frequency array of size 26 replace a hash map for lowercase strings?",
            "When would you use a trie instead of a hash set for string problems?",
        ],
        "when_to_use": "Use string-specific techniques when the problem involves characters, substrings, or patterns. The 26-letter alphabet constraint often simplifies space complexity. Key signals: 'palindrome,' 'anagram,' 'substring with property X,' 'longest/shortest string matching.'",
        "related_topics": ["arrays_hashing", "sliding_window", "two_pointers", "trie"],
    },

    "dfs": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show a maze and ask: 'How would you find a path from start to end?' The student's natural instinct — go forward, hit a wall, backtrack — is DFS. 'What if you wanted to explore every room in a house?'"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "DFS = go as deep as possible, then backtrack. Implemented with recursion (implicit stack) or explicit stack. For trees: preorder/inorder/postorder. For graphs: need visited set. For grids: 4-directional neighbors."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Maximum Depth of Binary Tree: base case (null = 0), recurse (1 + max(left, right)). Then Number of Islands: DFS flood-fill from each unvisited '1', mark visited, count components."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "DFS patterns: (1) Tree DFS (depth, path sum, validate BST), (2) Grid DFS (islands, word search), (3) Graph DFS (connected components, cycle detection), (4) DFS + memoization = top-down DP. Post-order computes bottom-up."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Pacific Atlantic Water Flow. Let the student figure out: DFS from each ocean edge inward. If fast, try Binary Tree Maximum Path Sum (post-order with global max)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: DFS = recursion. Trees don't need visited; graphs do. Post-order processes children before parent (bottom-up). DFS + memo = DP. Preview: BFS for shortest path, topological sort for dependencies."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Depth-First Search' + text 'Explore a maze: go deep, hit a wall, backtrack'"},
            {"step": 2, "content": "ds tree showing DFS traversal order + callout 'Recursion = implicit stack. Need visited set for graphs.'"},
            {"step": 3, "content": "Max Depth of Binary Tree: recursive call tree. Number of Islands: ds grid with flood-fill coloring"},
            {"step": 4, "content": "callout 'Patterns: tree DFS, grid DFS, graph DFS, DFS + memo = DP'"},
            {"step": 5, "content": "h2 'Pacific Atlantic Water Flow' + push_code: def pacificAtlantic(heights: List[List[int]]) -> List[List[int]]"},
        ],
        "difficulty_progression": "Start with Maximum Depth of Binary Tree (easy). Then Number of Islands (medium). Then Pacific Atlantic Water Flow (medium). If strong, Binary Tree Maximum Path Sum (hard) or Longest Increasing Path in Matrix (hard).",
        "check_questions": [
            "When do you need a visited set for DFS?",
            "What's the difference between preorder and postorder DFS?",
            "In Number of Islands, why is marking cells as visited enough to avoid revisiting?",
            "How does DFS + memoization relate to dynamic programming?",
        ],
        "when_to_use": "Use DFS when you need to explore all paths, detect cycles, or compute bottom-up (postorder) information. Key signals: 'connected components,' 'path exists,' 'all paths from A to B,' or 'compute height/depth/diameter.'",
        "related_topics": ["bfs", "trees", "graphs", "backtracking", "dynamic_programming"],
    },

    "hash_map": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'You have a million users. Given a user ID, find their profile. With an array, that's O(n) scan. Can we do O(1)?' Introduce the phone book analogy — you don't read every entry, you jump to the right letter."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Hash map: key -> hash function -> index -> value. O(1) average for get/set/delete. Collisions handled by chaining or open addressing. In Python: dict. In Java: HashMap. Show the complement lookup pattern."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Two Sum: for each number, check if (target - number) is in the map. If yes, return indices. If no, store number -> index. One pass, O(n)."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Three hash map patterns: (1) Complement lookup (Two Sum), (2) Frequency counting (anagrams, top K), (3) Grouping by key (group anagrams). Also: hash set for existence checks (Contains Duplicate, Longest Consecutive Sequence)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give LRU Cache. Let the student design hash map + doubly linked list. If that's too complex, start with Group Anagrams instead."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Hash maps = O(1) lookup. The most useful data structure in interviews. Three patterns: complement, frequency, grouping. Hash sets for existence. Be aware of O(n) worst case due to collisions."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Hash Maps' + text 'Given a user ID, find their profile in O(1)'"},
            {"step": 2, "content": "ds hash_map showing key->value pairs + callout 'O(1) avg lookup via hash function'"},
            {"step": 3, "content": "Two Sum walkthrough: ds array with scanning pointer, ds hash_map growing with complements"},
            {"step": 4, "content": "callout 'Three patterns: complement lookup, frequency counting, grouping by key'"},
            {"step": 5, "content": "h2 'LRU Cache' + push_code: class LRUCache: def get(self, key: int) -> int ..."},
        ],
        "difficulty_progression": "Start with Two Sum (easy). Then Group Anagrams (medium). Then Top K Frequent Elements (medium). If strong, LRU Cache (medium, hash map + linked list) or Longest Consecutive Sequence (medium, hash set).",
        "check_questions": [
            "What's the average and worst-case time complexity of hash map operations?",
            "How does a hash map handle collisions?",
            "For Group Anagrams, what's the best choice for the hash key?",
            "How does LRU Cache combine a hash map with a linked list?",
        ],
        "when_to_use": "Use a hash map whenever you need fast lookup, counting, or grouping. Key signals: 'find if X exists,' 'count occurrences,' 'group by property,' 'two sum / complement.' If you only need existence checks, a hash set suffices.",
        "related_topics": ["arrays_hashing", "sliding_window", "sorting"],
    },

    "matrix": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show a grid map with islands and water. 'How many islands are there? How would you rotate this image 90 degrees without extra space?' Grids are graphs where each cell has 4 neighbors."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Matrix = 2D array = grid graph. Key techniques: (1) DFS/BFS with 4-directional neighbors, (2) Spiral traversal with boundaries, (3) In-place rotation (transpose + reverse), (4) Binary search on sorted matrix. Direction arrays: dr = [-1,1,0,0], dc = [0,0,-1,1]."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Rotate Image: first transpose (swap matrix[i][j] with matrix[j][i]), then reverse each row. Show before and after. No extra space needed."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Matrix patterns: (1) Grid DFS/BFS (islands, word search), (2) Layer operations (spiral, rotate), (3) Search (binary search on sorted matrix, staircase search), (4) In-place marking (set matrix zeroes using first row/col as flags)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Spiral Matrix. Let the student manage four boundaries. If fast, try Word Search (DFS backtracking on grid)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Matrices are grids. Grids are graphs. Most matrix problems are graph problems or layer-by-layer operations. Always use boundary checks and direction arrays for clean code."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Matrix Problems' + ds grid showing islands and water"},
            {"step": 2, "content": "ds grid with direction arrows (up/down/left/right) + callout 'Each cell has 4 neighbors'"},
            {"step": 3, "content": "Rotate Image: ds grid before -> ds grid after transpose -> ds grid after reverse"},
            {"step": 4, "content": "callout 'Patterns: grid DFS/BFS, layer ops, search, in-place marking'"},
            {"step": 5, "content": "h2 'Spiral Matrix' + push_code: def spiralOrder(matrix: List[List[int]]) -> List[int]"},
        ],
        "difficulty_progression": "Start with Rotate Image (medium, transpose + reverse). Then Spiral Matrix (medium, boundary management). Then Set Matrix Zeroes (medium, in-place marking). If strong, Word Search (medium, grid backtracking).",
        "check_questions": [
            "How do you rotate a matrix 90 degrees clockwise in-place?",
            "What's the direction array technique and why is it useful?",
            "For Set Matrix Zeroes, how do you achieve O(1) extra space?",
            "How do you search a row-sorted and column-sorted matrix efficiently?",
        ],
        "when_to_use": "Use matrix techniques when the input is a 2D grid. If the problem involves connected regions, use DFS/BFS. If it involves traversal patterns, use boundary management. If the matrix is sorted, use binary search or staircase search.",
        "related_topics": ["dfs", "bfs", "graphs", "binary_search"],
    },

    "sorting": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'You have a list of meeting times. How do you find if any overlap?' Student might try O(n^2) pairwise comparison. 'What if you sort by start time first?' Sorting unlocks simpler algorithms."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Sorting basics: O(n log n) lower bound for comparison sorts. Merge sort (stable, always O(n log n)), quicksort (in-place, O(n log n) average), counting/bucket sort (O(n) for bounded ranges). Sorting is usually a preprocessing step, not the solution itself."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Merge Intervals: sort by start time, then scan left to right merging overlapping intervals. Show that sorting makes the problem linear. Animate the merge pass."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Sorting as enabler: (1) Sort + two pointers (3Sum), (2) Sort + merge (intervals), (3) Sort + greedy (activity selection), (4) Partial sorting (quickselect for kth element), (5) Custom comparators (sort by computed key)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Kth Largest Element. Let the student consider full sort vs quickselect (partition-based, O(n) average). If fast, try Car Fleet (sort by position, stack-based simulation)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Sorting costs O(n log n) but unlocks O(n) algorithms. If brute force is O(n^2), consider sorting + linear scan. Quickselect gives O(n) for kth element. Custom comparators handle complex ordering."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Sorting' + text 'Meeting times: [[0,30],[5,10],[15,20]]. Any overlaps?'"},
            {"step": 2, "content": "ds tree showing merge sort divide-and-conquer + callout 'O(n log n) — the cost of order'"},
            {"step": 3, "content": "Merge Intervals: ds array of intervals before sort, after sort, after merge"},
            {"step": 4, "content": "callout 'Sorting enables: two pointers, merge, greedy, partial sort, custom keys'"},
            {"step": 5, "content": "h2 'Kth Largest Element' + push_code: def findKthLargest(nums: List[int], k: int) -> int"},
        ],
        "difficulty_progression": "Start with Valid Anagram (easy, sort and compare). Then Merge Intervals (medium, sort + merge). Then Kth Largest Element (medium, quickselect). If strong, Car Fleet (medium) or custom comparator problems.",
        "check_questions": [
            "What's the lower bound for comparison-based sorting and why?",
            "When would you use counting sort instead of merge sort?",
            "How does quickselect achieve O(n) average for the kth element?",
            "Why is sorting + linear scan often better than O(n^2) brute force?",
        ],
        "when_to_use": "Sort as a preprocessing step when the problem becomes simpler on ordered data. Key signals: 'find overlapping intervals,' 'closest pair,' '3Sum,' 'kth largest/smallest.' If the brute force is O(n^2) and sorting gives O(n log n) total, sort first.",
        "related_topics": ["two_pointers", "binary_search", "heap", "intervals"],
    },

    "bfs": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'In a grid, find the shortest path from top-left to bottom-right through open cells.' DFS finds A path, but not necessarily the shortest. 'What if we explored all neighbors at distance 1 before distance 2?'"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "BFS = explore level by level using a queue. Guarantees shortest path in unweighted graphs. The queue-size trick: process all nodes at the current level before moving to the next. Multi-source BFS: start from multiple nodes simultaneously."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Rotting Oranges: multi-source BFS. Enqueue all rotten oranges at time 0. Each level = 1 minute. When queue is empty, check if any fresh oranges remain. Animate the rot spreading level by level."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "BFS patterns: (1) Shortest path in unweighted graph, (2) Level-order tree traversal, (3) Multi-source BFS (rotting oranges, walls and gates), (4) BFS on implicit graph (word ladder: words connected by single-letter change)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Binary Tree Level Order Traversal. Let the student implement the queue-size trick. If fast, try Word Ladder (BFS on an implicit graph)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: BFS = shortest path in unweighted graphs. Always mark visited BEFORE enqueuing (not after dequeuing). Multi-source BFS handles 'minimum distance to any source.' Preview: Dijkstra extends BFS to weighted graphs."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Breadth-First Search' + text 'Shortest path through a grid — explore level by level'"},
            {"step": 2, "content": "ds graph showing BFS exploration order + callout 'Queue-size trick: process all nodes at current level'"},
            {"step": 3, "content": "Rotting Oranges: ds grid with multi-source BFS spreading level by level, time labels on cells"},
            {"step": 4, "content": "callout 'Patterns: shortest path, level-order, multi-source, implicit graph'"},
            {"step": 5, "content": "h2 'Binary Tree Level Order Traversal' + push_code: def levelOrder(root: TreeNode) -> List[List[int]]"},
        ],
        "difficulty_progression": "Start with Binary Tree Level Order Traversal (medium). Then Rotting Oranges (medium, multi-source). Then Binary Tree Right Side View (medium, last node per level). If strong, Word Ladder (hard, implicit graph BFS).",
        "check_questions": [
            "Why does BFS guarantee shortest path in unweighted graphs?",
            "When should you mark nodes as visited — before or after enqueuing?",
            "What's the difference between single-source and multi-source BFS?",
            "How do you handle BFS on an implicit graph (like Word Ladder)?",
        ],
        "when_to_use": "Use BFS when you need the shortest path in an unweighted graph or level-by-level processing. Key signals: 'minimum number of steps,' 'shortest path,' 'level-order traversal,' or 'spread from multiple sources simultaneously.'",
        "related_topics": ["dfs", "graphs", "trees"],
    },

    "math": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Compute 2^1000000. How long would brute-force multiplication take? What if I said you can do it in 20 steps?' Introduce binary exponentiation. Math problems reward pattern spotting."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Key math tricks: (1) Modular arithmetic (avoid overflow), (2) Fast exponentiation (square and multiply, O(log n)), (3) Digit manipulation (% 10 and // 10), (4) Matrix rotation (transpose + reverse). No advanced math needed — just clever number manipulation."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Pow(x, n): if n is even, x^n = (x^(n/2))^2. If odd, x^n = x * x^(n-1). Handle negative n: x^(-n) = 1/x^n. Show the recursion tree collapsing to O(log n) depth."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Math patterns: (1) Simulation replacement (use a formula instead of simulating), (2) Cycle detection (Floyd's, Happy Number), (3) Digit extraction (reverse integer, palindrome number), (4) Geometry (rotation, area). Replace brute force with math."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Happy Number (cycle detection). Let the student detect the cycle with a hash set or slow/fast pointers. If fast, try Multiply Strings (digit-by-digit multiplication)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Math problems replace simulation with formulas/properties. Fast exponentiation is O(log n). Digit manipulation uses % and //. Watch for overflow and negative number edge cases."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Math & Geometry' + text 'Compute 2^1000000 in ~20 steps. How?'"},
            {"step": 2, "content": "Fast exponentiation tree: x^10 = (x^5)^2, x^5 = x*(x^2)^2 + callout 'O(log n)'"},
            {"step": 3, "content": "Pow(x,n) walkthrough with recursion tree, handling even/odd/negative cases"},
            {"step": 4, "content": "callout 'Patterns: formula replacement, cycle detection, digit manipulation, geometry'"},
            {"step": 5, "content": "h2 'Happy Number' + push_code: def isHappy(n: int) -> bool"},
        ],
        "difficulty_progression": "Start with Happy Number (easy, cycle detection). Then Plus One (easy, carry propagation). Then Pow(x, n) (medium). If strong, Multiply Strings (medium, digit math) or Rotate Image (medium, geometry).",
        "check_questions": [
            "How does binary exponentiation achieve O(log n)?",
            "How do you extract individual digits from a number?",
            "Why is Happy Number a cycle detection problem?",
            "What's the risk of integer overflow in math problems?",
        ],
        "when_to_use": "Use math techniques when the problem has a mathematical structure that eliminates brute-force simulation. Key signals: 'compute x^n,' 'reverse a number,' 'detect repeating pattern,' 'rotate matrix.' Look for formulas that replace loops.",
        "related_topics": ["bit_manipulation", "arrays_hashing", "matrix"],
    },

    "bit_manipulation": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Every number in this array appears twice except one. Find it in O(1) space.' Student might try a hash set. Then reveal: XOR everything together — duplicates cancel, unique remains. Magic!"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Bit operators: & (AND), | (OR), ^ (XOR), ~ (NOT), << (left shift), >> (right shift). Key properties: a ^ a = 0, a ^ 0 = a. Brian Kernighan's trick: n & (n-1) clears the lowest set bit. Show binary representations."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Single Number: XOR all elements. [4,1,2,1,2] -> 4^1^2^1^2 = 4^(1^1)^(2^2) = 4^0^0 = 4. Then Counting Bits: dp[i] = dp[i >> 1] + (i & 1)."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Bit patterns: (1) XOR for pairing/cancellation (Single Number), (2) Bit counting (Brian Kernighan), (3) Bit manipulation DP (Counting Bits), (4) Arithmetic via bits (Sum of Two Integers). Bit ops give O(1) space where hash maps use O(n)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Number of 1 Bits. Let the student try both approaches: check each of 32 bits, and Brian Kernighan's n & (n-1). If fast, try Sum of Two Integers (add without +)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: XOR is the most useful bit operation for interviews. It cancels duplicates and finds unique elements. Bit manipulation replaces hash maps with O(1) space for certain problems. Python quirk: arbitrary precision integers need masking for 32-bit behavior."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Bit Manipulation' + text 'Find the unique number: [4,1,2,1,2]. O(1) space!'"},
            {"step": 2, "content": "Binary representations of operators + callout 'XOR: a^a=0, a^0=a'"},
            {"step": 3, "content": "Single Number XOR walkthrough step by step + Counting Bits DP relation"},
            {"step": 4, "content": "callout 'Patterns: XOR pairing, bit counting, bit DP, arithmetic via bits'"},
            {"step": 5, "content": "h2 'Number of 1 Bits' + push_code: def hammingWeight(n: int) -> int"},
        ],
        "difficulty_progression": "Start with Single Number (easy, XOR). Then Number of 1 Bits (easy, Kernighan). Then Counting Bits (easy, DP). Then Reverse Bits (easy). If strong, Sum of Two Integers (medium).",
        "check_questions": [
            "Why does XORing all elements find the unique number?",
            "How does n & (n-1) clear the lowest set bit?",
            "How would you add two numbers without using + or -?",
            "Why do Python bit manipulation solutions need & 0xFFFFFFFF?",
        ],
        "when_to_use": "Use bit manipulation when the problem involves finding unique elements (XOR), counting bits, or performing arithmetic without standard operators. Key signals: 'every element appears twice except one,' 'count set bits,' 'add without arithmetic operators.'",
        "related_topics": ["math", "arrays_hashing"],
    },

    "intervals": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show overlapping meeting times: [[9,10], [9:30,11], [10:30,12]]. 'How many meeting rooms do you need?' The answer depends on overlaps. 'What if I said sorting is the key?'"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Interval problems: always sort first (by start or end time). Overlap detection: [a,b] and [c,d] overlap if a < d and c < b. Three patterns: merge overlapping, count max concurrent (sweep line/heap), schedule maximum non-overlapping (sort by end, greedy)."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Merge Intervals: sort by start, iterate, extend current if overlap (max(end1, end2)), else emit and start new. Show the sorted intervals being merged step by step."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Interval patterns: (1) Merge (sort by start, extend), (2) Scheduling (sort by end, greedy pick), (3) Max concurrent (min-heap of end times or sweep line), (4) Insert (find position, merge affected). All require sorting first."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Meeting Rooms II. Let the student figure out: min-heap of end times tracks active meetings, peak size = answer. If fast, try Non-overlapping Intervals (greedy, sort by end)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Sort first, then process linearly. Merge = extend overlapping. Schedule = pick by earliest end. Max concurrent = heap or sweep line. Always clarify: are endpoints inclusive or exclusive?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Intervals' + text 'Meetings: [[9,10],[9:30,11],[10:30,12]]. How many rooms?'"},
            {"step": 2, "content": "ds array of intervals on a number line showing overlaps + callout 'Step 1: SORT'"},
            {"step": 3, "content": "Merge Intervals: before sort, after sort, after merge — step by step"},
            {"step": 4, "content": "callout 'Patterns: merge, schedule, max concurrent, insert'"},
            {"step": 5, "content": "h2 'Meeting Rooms II' + push_code: def minMeetingRooms(intervals: List[List[int]]) -> int"},
        ],
        "difficulty_progression": "Start with Meeting Rooms (easy, detect any overlap). Then Merge Intervals (medium). Then Meeting Rooms II (medium, heap). If strong, Insert Interval (medium) or Non-overlapping Intervals (medium, greedy).",
        "check_questions": [
            "Why is sorting the first step in almost every interval problem?",
            "How do you detect if two intervals overlap?",
            "In Meeting Rooms II, why does a min-heap of end times work?",
            "For interval scheduling, why sort by end time instead of start time?",
        ],
        "when_to_use": "Use interval techniques when the problem involves ranges with start/end times. Key signals: 'merge overlapping intervals,' 'minimum meeting rooms,' 'maximum non-overlapping,' 'insert an interval.' Always sort first.",
        "related_topics": ["sorting", "heap", "greedy"],
    },

    "trie": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Type 'app' into a search bar — it suggests 'apple,' 'application,' 'approve.' How does autocomplete work efficiently? A hash map of all strings requires checking each one. 'What if the data structure shared prefixes?'"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Introduce the trie: a tree where each node is a character, paths from root form words. Shared prefixes share paths. O(L) for insert/search/startsWith where L = word length. Each node has children (dict or array[26]) and an is_end flag."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Build a trie with ['apple', 'app', 'apt', 'bat']. Show shared prefix 'ap' between 'apple' and 'apt'. Insert: create nodes along the path, mark is_end. Search: follow the path, check is_end. startsWith: follow the path, return True if path exists."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Trie patterns: (1) Prefix matching / autocomplete, (2) Wildcard search with DFS (word with '.' matches any char), (3) Trie + grid backtracking (Word Search II — prune search space). Tries are space-efficient when many words share prefixes."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Implement Trie. Let the student build insert, search, startsWith from scratch. If fast, try Design Add and Search Words Data Structure (trie + DFS for wildcard)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Tries store strings character by character, sharing prefixes. O(L) operations independent of number of stored strings. Use when you need prefix-based lookups. The trie is to strings what a BST is to numbers."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Trie (Prefix Tree)' + text 'Autocomplete: type \"app\" -> apple, application, approve'"},
            {"step": 2, "content": "ds tree showing trie with ['apple','app','apt','bat'] + callout 'Shared prefixes share paths'"},
            {"step": 3, "content": "Insert and search animations on the trie, highlighting is_end flags"},
            {"step": 4, "content": "callout 'Patterns: prefix match, wildcard DFS, trie + grid backtracking'"},
            {"step": 5, "content": "h2 'Implement Trie' + push_code: class Trie: def insert(self, word: str) -> None ..."},
        ],
        "difficulty_progression": "Start with Implement Trie (medium, build from scratch). Then Design Add and Search Words (medium, trie + DFS). If strong, Word Search II (hard, trie + grid backtracking).",
        "check_questions": [
            "What's the time complexity of trie operations? What determines it?",
            "Why do we need an is_end flag? What goes wrong without it?",
            "How does a trie improve Word Search II compared to checking each word separately?",
            "When is a trie better than a hash set for string lookups?",
        ],
        "when_to_use": "Use a trie when you need prefix-based operations: autocomplete, spell check, word search on a grid. Key signals: 'find all words with prefix X,' 'search with wildcards,' 'find words on a grid from a dictionary.' If you only need exact match, a hash set is simpler.",
        "related_topics": ["string", "dfs", "backtracking"],
    },

    "union_find": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show a graph of friends: 'A knows B, B knows C. Are A and C in the same friend group? What if D knows E — how many groups are there?' As friendships form, groups merge. How to track this efficiently?"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Union-Find: parent[] array. find(x) follows parents to root. union(x,y) connects their roots. Path compression: point every node directly to root. Union by rank: attach shorter tree under taller. Both optimizations give near-O(1) amortized."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Number of Connected Components: start with n components. For each edge (u,v), if find(u) != find(v), union them and decrement count. Show the parent array evolving with path compression."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Union-Find patterns: (1) Connected components (count roots), (2) Cycle detection in undirected graphs (if find(u) == find(v) before union, cycle exists), (3) Kruskal's MST (sort edges, union non-cyclic). Alternative to DFS for connectivity queries."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Redundant Connection. Let the student detect the first edge that creates a cycle. If fast, try Graph Valid Tree (n-1 edges + connected)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Union-Find tracks dynamic connectivity in near-O(1) per operation. Path compression + union by rank are essential optimizations. Use when you need to merge groups and query 'are X and Y connected?'"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Union Find' + text 'A-B, B-C: same group? D-E: how many groups?'"},
            {"step": 2, "content": "ds array showing parent[] + ds tree showing forest structure + callout 'Path compression flattens'"},
            {"step": 3, "content": "Connected Components: parent array evolving as edges are added, component count decreasing"},
            {"step": 4, "content": "callout 'Patterns: connected components, cycle detection, Kruskal MST'"},
            {"step": 5, "content": "h2 'Redundant Connection' + push_code: def findRedundantConnection(edges: List[List[int]]) -> List[int]"},
        ],
        "difficulty_progression": "Start with Number of Connected Components (medium). Then Redundant Connection (medium, cycle detection). Then Graph Valid Tree (medium, both conditions). If strong, Accounts Merge or similar.",
        "check_questions": [
            "What does path compression do and why is it important?",
            "How does union by rank keep the tree balanced?",
            "How do you detect a cycle using Union-Find?",
            "When would you use Union-Find vs DFS for connected components?",
        ],
        "when_to_use": "Use Union-Find when you need to dynamically merge groups and query connectivity. Key signals: 'connected components with edges added over time,' 'detect cycle in undirected graph,' 'merge accounts/groups,' or Kruskal's MST. DFS works too but Union-Find is better for incremental edge additions.",
        "related_topics": ["graphs", "dfs", "bfs", "topological_sort"],
    },

    "topological_sort": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show course prerequisites: 'To take Data Structures, you need Intro to Programming. To take Algorithms, you need Data Structures.' In what order should you take courses? 'What if there's a circular dependency?'"},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Topological sort: linear ordering of DAG nodes where every edge u->v has u before v. Two approaches: Kahn's (BFS, in-degree tracking) and DFS (reverse postorder). Cycle detection: if not all nodes are processed, cycle exists."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through Course Schedule II with Kahn's algorithm: compute in-degrees, enqueue nodes with in-degree 0, process each (decrement neighbors' in-degrees, enqueue if 0), collect result. Show the queue and in-degree table evolving."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Topological sort patterns: (1) Dependency ordering (courses, build systems), (2) Cycle detection in directed graphs, (3) Alien Dictionary (build graph from word order, then topo sort). Always check: is the graph a DAG? If cycles exist, no valid ordering."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Give Course Schedule (just detect if valid ordering exists). Let the student implement Kahn's or DFS-based. If fast, try Alien Dictionary (build graph from sorted words, then topo sort)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Topological sort = dependency resolution. Kahn's (BFS) is more intuitive and naturally detects cycles. DFS-based gives reverse postorder. Only works on DAGs. Preview: Topological sort enables DP on DAGs."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Topological Sort' + text 'Course prerequisites: Intro -> DS -> Algorithms. What order?'"},
            {"step": 2, "content": "ds graph showing DAG with directed edges + callout 'Linear ordering: every edge u->v has u before v'"},
            {"step": 3, "content": "Kahn's algorithm step by step: in-degree table + queue contents + processing order"},
            {"step": 4, "content": "callout 'Patterns: dependency ordering, cycle detection, Alien Dictionary'"},
            {"step": 5, "content": "h2 'Course Schedule' + push_code: def canFinish(numCourses: int, prerequisites: List[List[int]]) -> bool"},
        ],
        "difficulty_progression": "Start with Course Schedule (medium, cycle detection). Then Course Schedule II (medium, produce the ordering). If strong, Alien Dictionary (hard, build graph from sorted words).",
        "check_questions": [
            "What's the difference between Kahn's and DFS-based topological sort?",
            "How does Kahn's algorithm detect cycles?",
            "Why does topological sort only work on DAGs?",
            "For Alien Dictionary, how do you build the graph from the word list?",
        ],
        "when_to_use": "Use topological sort when you need to order elements with dependencies. Key signals: 'prerequisites,' 'build order,' 'compile order,' 'determine alphabet order.' If the problem asks 'is this ordering possible?' it's cycle detection on a directed graph.",
        "related_topics": ["graphs", "dfs", "bfs", "union_find"],
    },

    # =====================================================================
    # SYSTEM DESIGN — Original 8
    # =====================================================================

    "networking": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'What happens when you type google.com in your browser?' This question touches DNS, TCP, TLS, HTTP, and load balancing — the full networking stack. Let the student try before filling gaps."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Walk through the networking stack: DNS resolution -> TCP 3-way handshake -> TLS negotiation -> HTTP request -> load balancer -> application server -> response. Show latencies at each step."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Trace a request to google.com end-to-end. Show DNS caching layers. Show TCP connection reuse (HTTP/2 multiplexing). Show how a CDN short-circuits the path for static content."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Key decisions in system design: TCP vs UDP (reliability vs speed), L4 vs L7 load balancing (speed vs intelligence), short vs long DNS TTL (failover speed vs DNS traffic). These trade-offs appear in every SD interview."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Ask: 'You're designing a video streaming service. Should you use TCP or UDP? Where does the CDN sit? How does the load balancer work?' Let the student apply networking concepts to a real design."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Know the latency hierarchy (LAN < same-DC < cross-continent). Understand TCP vs UDP trade-offs. CDN for static content. L7 LB for intelligent routing. These appear in every system design answer."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Networking Fundamentals' + text 'What happens when you type google.com?'"},
            {"step": 2, "content": "Sequence diagram: Browser -> DNS -> TCP handshake -> TLS -> HTTP -> LB -> Server -> Response"},
            {"step": 3, "content": "End-to-end request trace with latency annotations at each step"},
            {"step": 4, "content": "callout 'Trade-offs: TCP/UDP, L4/L7, short/long TTL'"},
            {"step": 5, "content": "Video streaming architecture: client -> CDN -> origin, with networking decisions highlighted"},
        ],
        "difficulty_progression": "Start with understanding DNS resolution and TCP basics. Then move to HTTP/2 multiplexing and TLS. Then L4 vs L7 load balancing. Finally, apply to real system designs.",
        "check_questions": [
            "What are the steps in DNS resolution?",
            "When would you choose UDP over TCP?",
            "What's the difference between L4 and L7 load balancing?",
            "How does HTTP/2 improve over HTTP/1.1?",
        ],
        "when_to_use": "Networking knowledge is foundational for every system design interview. You'll reference it when discussing latency, CDNs, load balancers, and protocol choices. Know the latency numbers by heart.",
        "related_topics": ["api_design", "caching", "consistent_hashing", "load-balancing"],
    },

    "api_design": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show two API designs for a URL shortener: a messy one (POST /doShorten?url=...) and a clean one (POST /urls with JSON body). Which is easier to use? Why? Good API design is a core SD skill."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "REST: resources as nouns (/users, /posts), HTTP verbs (GET/POST/PUT/DELETE), status codes (200/201/400/404/500). gRPC: protocol buffers, binary encoding, streaming — ideal for internal microservice communication. GraphQL: client specifies exact data shape."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Design the API for a Twitter-like service: POST /tweets (create), GET /users/{id}/feed (read feed), PUT /tweets/{id} (edit), DELETE /tweets/{id}. Show pagination (cursor-based vs offset), rate limiting headers."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "API design patterns: (1) REST for external APIs, (2) gRPC for internal services, (3) Pagination (cursor for feeds, offset for search), (4) Idempotency keys for POST, (5) Versioning (URL path vs header). Always design the API early in SD interviews."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the API for a ride-sharing app: request ride, update location, accept ride, complete ride. Discuss: which endpoints need WebSocket vs REST? How to handle ride status updates?"},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: API design is the contract between client and server. REST for external, gRPC for internal. Always include pagination, error handling, and idempotency. Design APIs early in the interview — it clarifies the system's capabilities."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'API Design' + text comparing messy vs clean API for URL shortener"},
            {"step": 2, "content": "REST table: verb + path + body + response for CRUD operations + callout 'REST vs gRPC vs GraphQL'"},
            {"step": 3, "content": "Twitter API: POST /tweets, GET /feed, with request/response shapes and pagination"},
            {"step": 4, "content": "callout 'Patterns: REST external, gRPC internal, cursor pagination, idempotency keys'"},
            {"step": 5, "content": "Ride-sharing API design exercise on the board"},
        ],
        "difficulty_progression": "Start with basic REST CRUD for a simple entity. Then add pagination and filtering. Then discuss gRPC for internal services. Finally, handle complex scenarios like WebSocket upgrades and webhooks.",
        "check_questions": [
            "When would you use gRPC instead of REST?",
            "What's the difference between cursor-based and offset-based pagination?",
            "Why are idempotency keys important for POST requests?",
            "How would you version your API?",
        ],
        "when_to_use": "Design the API early in every system design interview. It clarifies the system's capabilities and helps structure the rest of the design. Use REST for external-facing APIs and gRPC for high-performance internal communication.",
        "related_topics": ["networking", "caching", "api-gateway"],
    },

    "caching": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Your database serves 10,000 reads/second. Traffic spikes to 100,000. How do you handle it without 10x-ing your database?' The answer: cache. 90% of reads can be served from memory."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Cache = fast storage layer between client and slow backend. Strategies: cache-aside (app manages), read-through (cache manages reads), write-through (cache manages writes), write-behind (async writes). Eviction: LRU, LFU, TTL."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through cache-aside for a user profile service: check cache -> miss -> query DB -> store in cache -> return. Then show what happens on write: write to DB -> invalidate cache. Discuss the race condition."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Caching patterns: (1) Cache-aside (most common), (2) Read/write-through (for strong consistency), (3) Write-behind (for write-heavy), (4) CDN caching (edge), (5) Application-level caching (Redis/Memcached). Cache invalidation is the hard part."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the caching layer for an Instagram feed: What to cache? Where? TTL? How to invalidate when a new post is created? Discuss cache stampede (many concurrent misses for the same key)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Caching reduces load on the database by 90%+. Cache-aside is the default pattern. Always set a TTL. The two hard problems: cache invalidation and cache stampede. Redis is the go-to in-memory cache."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Caching' + text 'DB handles 10K reads/sec. Traffic spikes to 100K. Now what?'"},
            {"step": 2, "content": "Flow diagram: Client -> Cache (hit/miss) -> DB, with read-through and write-through variants"},
            {"step": 3, "content": "Cache-aside walkthrough: read miss -> DB query -> populate cache, write -> DB -> invalidate cache"},
            {"step": 4, "content": "callout 'Patterns: cache-aside, read/write-through, write-behind, CDN, app-level'"},
            {"step": 5, "content": "Instagram caching design: what to cache, where, TTL, invalidation strategy"},
        ],
        "difficulty_progression": "Start with understanding cache-aside pattern. Then discuss invalidation strategies. Then handle cache stampede and thundering herd. Finally, design multi-layer caching (CDN + Redis + application).",
        "check_questions": [
            "What's the difference between cache-aside and read-through?",
            "What happens when a cached item is updated in the database?",
            "How do you handle cache stampede?",
            "When would you use write-behind instead of write-through?",
        ],
        "when_to_use": "Use caching when your system is read-heavy and the database is the bottleneck. Key signals: 'high read volume,' 'reduce latency,' 'database is slow,' 'same data accessed repeatedly.' Always discuss caching in system design interviews.",
        "related_topics": ["redis", "scaling-reads", "database_indexing"],
    },

    "sharding": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Your single database server has 1TB of data and 50K writes/sec. It's maxed out. You can't buy a bigger server. What do you do?' Answer: split the data across multiple servers — sharding."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Sharding = horizontal partitioning across database servers. Choose a shard key (user_id, region, etc.). Hash-based sharding (consistent hashing) or range-based. Each shard handles a fraction of data and traffic. Trade-off: no cross-shard joins."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Design sharding for a chat app. Shard key = conversation_id. Hash(conversation_id) % N determines the shard. All messages for a conversation are on the same shard — enables efficient range queries by timestamp. Show what happens when adding a new shard."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Sharding decisions: (1) Choose key to distribute writes evenly, (2) Co-locate related data on the same shard, (3) Use consistent hashing to minimize reshuffling when adding shards, (4) Handle cross-shard queries with scatter-gather."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design sharding for Twitter: What's the shard key for tweets? For user timelines? What happens when a celebrity tweets (hot shard)? How do you handle cross-shard fan-out?"},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Sharding splits data across servers for horizontal scaling. Choose the shard key to distribute evenly and co-locate related data. Consistent hashing minimizes reshuffling. The hard parts: hot shards, cross-shard queries, rebalancing."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Sharding' + text 'Single DB maxed at 1TB / 50K writes/sec. How to scale?'"},
            {"step": 2, "content": "Diagram: data split across 4 shards by hash(user_id) % 4 + callout 'Each shard = fraction of data + traffic'"},
            {"step": 3, "content": "Chat app sharding: conversation_id as shard key, messages co-located by conversation"},
            {"step": 4, "content": "callout 'Decisions: shard key, co-location, consistent hashing, scatter-gather'"},
            {"step": 5, "content": "Twitter sharding exercise on the board: tweets, timelines, celebrity hot shard problem"},
        ],
        "difficulty_progression": "Start with understanding why sharding is needed. Then choose appropriate shard keys. Then handle hot shards and rebalancing. Finally, design scatter-gather for cross-shard queries.",
        "check_questions": [
            "What makes a good shard key?",
            "What's the problem with hash(id) % N when adding a new shard?",
            "How does consistent hashing solve the reshuffling problem?",
            "How do you handle queries that span multiple shards?",
        ],
        "when_to_use": "Use sharding when a single database server can't handle the data volume or write throughput. Key signals: 'TB of data,' 'write-heavy workload,' 'need horizontal scaling.' Always consider sharding alongside replication.",
        "related_topics": ["consistent_hashing", "database_indexing", "scaling-writes", "replication"],
    },

    "consistent_hashing": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show hash(key) % N for 3 servers. Now add a 4th server: hash(key) % 4 remaps almost every key. 'How do you add servers without reshuffling everything?' Enter consistent hashing."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Consistent hashing: arrange hash space in a ring (0 to 2^32). Place servers at positions on the ring. Each key hashes to a position and is assigned to the next server clockwise. Adding/removing a server only affects neighboring keys."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Draw the hash ring with 3 servers. Show key assignment. Add a 4th server — only keys between the new server and the previous server move. Compare: with hash % N, all keys reshuffle. With consistent hashing, only 1/N keys move."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Consistent hashing improvements: virtual nodes (each server has multiple positions on the ring for better distribution). Used in: CDN (assign users to edge servers), distributed cache (Redis Cluster, Memcached), database sharding (DynamoDB, Cassandra)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design a distributed cache with consistent hashing: 5 cache servers, virtual nodes for even distribution. What happens when server 3 goes down? How do you handle replication (next K servers clockwise)?"},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Consistent hashing minimizes reshuffling when servers are added/removed. Virtual nodes improve distribution. Used in CDNs, distributed caches, and database sharding. Know this for any 'design a distributed X' question."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Consistent Hashing' + text 'hash(key) % 3 -> add server -> hash(key) % 4 remaps everything!'"},
            {"step": 2, "content": "Hash ring diagram: servers placed on ring, keys assigned to next clockwise server"},
            {"step": 3, "content": "Adding server 4: only keys between server 4 and server 3 move, rest unchanged"},
            {"step": 4, "content": "callout 'Virtual nodes for even distribution' + text: CDN, cache, DB sharding use cases"},
            {"step": 5, "content": "Distributed cache design with consistent hashing ring and replication"},
        ],
        "difficulty_progression": "Start with understanding why hash % N is bad for dynamic server counts. Then understand the hash ring concept. Then add virtual nodes. Finally, apply to real system designs with replication.",
        "check_questions": [
            "Why does hash(key) % N cause problems when N changes?",
            "How does consistent hashing minimize key movement?",
            "What problem do virtual nodes solve?",
            "How is consistent hashing used in Redis Cluster?",
        ],
        "when_to_use": "Use consistent hashing when you need to distribute data across servers that may be added or removed dynamically. Key signals: 'distributed cache,' 'CDN server assignment,' 'database sharding with dynamic scaling.'",
        "related_topics": ["sharding", "caching", "load-balancing", "redis"],
    },

    "cap_theorem": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Scenario: Your database is replicated across two data centers. The network link breaks. One DC gets a write. Should the other DC serve stale reads (Available) or reject requests until the link heals (Consistent)? You can't have both."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "CAP Theorem: during a network partition (P), you must choose between Consistency (C, all nodes see the same data) and Availability (A, every request gets a response). CP systems: wait for consistency (HBase, MongoDB). AP systems: serve potentially stale data (Cassandra, DynamoDB). In practice: you always have partitions, so the real choice is C vs A."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Walk through a banking system (CP): transfer $100 from account A to B. During a partition, reject the transfer rather than risk inconsistency. Then a social media feed (AP): during a partition, serve slightly stale timeline rather than showing errors."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "When to choose CP vs AP: financial data, inventory, bookings = CP (correctness matters). Social feeds, analytics, caches = AP (availability matters). Most real systems are 'tunable': per-operation consistency level (e.g., Cassandra QUORUM vs ONE)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "For each scenario, choose CP or AP and justify: (1) Bank account balance, (2) Instagram like count, (3) Uber driver location, (4) Ticketmaster seat booking, (5) YouTube view count."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: CAP says you can't have C+A during a partition. Real systems choose per operation. Financial = CP, social = AP. In interviews, mention PACELC (extends CAP to latency trade-off during normal operation). Always justify your choice."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'CAP Theorem' + text 'Network partitions your two data centers. Choose: consistency or availability?'"},
            {"step": 2, "content": "Venn diagram: C, A, P with regions labeled CP and AP + callout 'During partition, choose C or A'"},
            {"step": 3, "content": "Banking (CP) vs social feed (AP): two scenarios side by side with trade-offs"},
            {"step": 4, "content": "callout 'Per-operation tuning: Cassandra QUORUM (CP) vs ONE (AP)'"},
            {"step": 5, "content": "Exercise: classify 5 scenarios as CP or AP on the board"},
        ],
        "difficulty_progression": "Start with understanding the CAP triangle. Then classify real systems (MongoDB = CP, Cassandra = AP). Then discuss PACELC (what happens when there's no partition). Finally, design systems with tunable consistency.",
        "check_questions": [
            "What does the CAP theorem actually say?",
            "Why can't you have both C and A during a partition?",
            "Is MongoDB CP or AP? What about Cassandra?",
            "What does PACELC add to CAP?",
        ],
        "when_to_use": "Reference CAP when discussing database choices and replication strategies in system design. Use it to justify why you chose a specific database or consistency level. Always ask: 'Is it okay for this data to be slightly stale?'",
        "related_topics": ["replication", "sharding", "caching", "cassandra", "dynamodb"],
    },

    "message_queues": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Scenario: User uploads a video. Transcoding takes 30 minutes. Should the user wait? No — accept the upload, return 202 Accepted, process async. 'How does the transcoding service know there's work to do?' Message queue."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Message queue: producer sends message, queue stores it, consumer processes it. Decouples producer from consumer. Key properties: guaranteed delivery (at-least-once), ordering (Kafka), fan-out (pub/sub). Tools: Kafka, RabbitMQ, SQS."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Design the video upload pipeline: Upload API -> message to queue (video_id, format) -> transcoding workers consume messages -> encode to multiple resolutions -> store results -> update database -> notify user."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Queue patterns: (1) Work queue (multiple consumers, each message processed once), (2) Pub/Sub (broadcast to all subscribers), (3) Event sourcing (immutable event log), (4) Dead-letter queue (failed messages after N retries). Queues appear in every distributed system."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the notification pipeline: events (new follower, new comment, new like) -> queue -> notification workers (push, email, SMS). How to handle: ordering? deduplication? retry?"},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Message queues decouple producers and consumers, enable async processing, and smooth traffic spikes. Key decisions: at-least-once vs exactly-once, ordering guarantees, consumer group vs broadcast. Kafka for event streaming, SQS/RabbitMQ for task queues."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Message Queues' + text 'Video upload: 30min transcoding. Should user wait?'"},
            {"step": 2, "content": "Producer -> Queue -> Consumer diagram + callout 'Decouples, buffers, enables async'"},
            {"step": 3, "content": "Video pipeline: Upload API -> Queue -> Workers -> S3 + DB + Notification"},
            {"step": 4, "content": "callout 'Patterns: work queue, pub/sub, event sourcing, dead-letter queue'"},
            {"step": 5, "content": "Notification pipeline design exercise on the board"},
        ],
        "difficulty_progression": "Start with understanding the work queue pattern. Then pub/sub. Then event sourcing with Kafka. Finally, handle complex scenarios: ordering, deduplication, exactly-once processing.",
        "check_questions": [
            "What's the difference between a work queue and pub/sub?",
            "How does a dead-letter queue work?",
            "What's the difference between at-least-once and exactly-once delivery?",
            "When would you use Kafka vs RabbitMQ?",
        ],
        "when_to_use": "Use message queues whenever you need async processing, service decoupling, or traffic smoothing. Key signals: 'process takes too long for synchronous response,' 'decouple services,' 'smooth traffic spikes,' or 'fan-out events to multiple consumers.'",
        "related_topics": ["kafka", "long-tasks", "sagas", "scaling-writes"],
    },

    "database_indexing": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Your users table has 10 million rows. SELECT * WHERE email = ?' takes 5 seconds. After adding an index, it takes 2ms. What happened?' An index is like a book's index — instead of reading every page, jump to the right one."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Database index: a separate data structure (usually B-tree) that maps column values to row locations. O(log n) lookup instead of O(n) full table scan. Trade-offs: faster reads, slower writes (index must be updated), extra storage."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Show a B-tree index on an email column. Walk through a lookup: traverse from root to leaf, each level halves the search space. Show composite indexes (email + created_at) and covering indexes (index contains all queried columns)."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Index types: (1) B-tree (default, range queries), (2) Hash (exact match only, O(1)), (3) GIN (full-text search, JSONB), (4) BRIN (sorted data, time series). Composite index rule: leftmost prefix. Partial index: index only rows matching a condition."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Given these queries for a Twitter-like app: (1) Get user by email, (2) Get tweets by user_id ordered by created_at DESC, (3) Full-text search on tweet content. Design the indexes."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Indexes are the single biggest performance lever for databases. B-tree for range queries, hash for exact match, GIN for text search. Trade-off: faster reads, slower writes. Always mention indexing strategy in system design."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Database Indexing' + text 'SELECT WHERE email = ? goes from 5 sec to 2ms. How?'"},
            {"step": 2, "content": "B-tree diagram: root -> internal nodes -> leaf nodes pointing to rows + callout 'O(log n) lookup'"},
            {"step": 3, "content": "Email lookup walkthrough through B-tree levels + composite index on (email, created_at)"},
            {"step": 4, "content": "callout 'Index types: B-tree, Hash, GIN, BRIN' + text: composite index leftmost prefix rule"},
            {"step": 5, "content": "Twitter indexes exercise: design indexes for 3 query patterns"},
        ],
        "difficulty_progression": "Start with understanding B-tree indexes. Then composite indexes and the leftmost prefix rule. Then specialized indexes (GIN, BRIN). Finally, trade-offs: when NOT to add an index.",
        "check_questions": [
            "Why does a B-tree index speed up lookups?",
            "What's the 'leftmost prefix' rule for composite indexes?",
            "When would you use a hash index instead of a B-tree?",
            "What's the downside of adding too many indexes?",
        ],
        "when_to_use": "Discuss indexing whenever database performance comes up in system design. Index columns that appear in WHERE, JOIN, and ORDER BY clauses. Key signals: 'slow queries,' 'full table scan,' 'need to support multiple query patterns.'",
        "related_topics": ["postgresql", "caching", "sharding", "scaling-reads"],
    },

    # =====================================================================
    # SYSTEM DESIGN — Missing SD Concepts
    # =====================================================================

    "data-modeling": {
        "teaching_flow": [
            {"step": 1, "title": "Requirements", "duration_min": 3,
             "instructions": "Start with access patterns: 'What queries will this system run 90% of the time?' Data modeling serves queries. Don't model entities first — model the questions you need to answer."},
            {"step": 2, "title": "Entity Identification", "duration_min": 5,
             "instructions": "Identify the core entities (nouns) and relationships (verbs). For Instagram: User, Post, Comment, Like, Follow. Draw the ER diagram. Determine cardinality: User 1:N Post, User M:N User (followers)."},
            {"step": 3, "title": "Normalization vs Denormalization", "duration_min": 5,
             "instructions": "Walk through normalization (3NF): eliminate redundancy. Then show the problem at scale: joins are expensive. Denormalize: embed follower count in User, embed recent comments in Post. Trade write complexity for read speed."},
            {"step": 4, "title": "Storage Engine Choice", "duration_min": 5,
             "instructions": "SQL (PostgreSQL) for relational data with complex queries. NoSQL document (MongoDB) for flexible schemas. Wide-column (Cassandra) for write-heavy with known access patterns. Key-value (DynamoDB) for simple lookups."},
            {"step": 5, "title": "Practice", "duration_min": 7,
             "instructions": "Model a chat system: Users, Conversations, Messages. Discuss: partition by conversation_id? Store recent messages denormalized? SQL for user profiles, Cassandra for messages?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Data Modeling' + text 'Start with queries, not entities'"},
            {"step": 2, "content": "ER diagram: Users -> Posts (1:N), Users <-> Users (M:N followers)"},
            {"step": 3, "content": "Normalized vs denormalized: separate tables vs embedded documents, trade-offs"},
            {"step": 4, "content": "callout 'SQL vs Document vs Wide-column vs Key-value: choose by access pattern'"},
            {"step": 5, "content": "Chat system data model exercise"},
        ],
        "difficulty_progression": "Start with ER modeling basics. Then normalization/denormalization trade-offs. Then storage engine selection. Finally, model for complex systems with multiple access patterns requiring multiple stores.",
        "check_questions": [
            "What's the difference between normalization and denormalization?",
            "When should you denormalize?",
            "How do you choose between SQL and NoSQL for a given use case?",
            "What does 'model your data around your queries' mean?",
        ],
        "when_to_use": "Data modeling is the second step in every system design interview (after requirements). Model entities, choose storage engines, and justify normalization/denormalization decisions based on access patterns.",
        "related_topics": ["postgresql", "cassandra", "dynamodb", "sharding"],
    },

    "numbers-to-know": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Your system has 10M daily active users. Each makes 10 requests. How many requests per second at peak?' Make them estimate: 100M/86400 = ~1200 RPS average, ~12K peak. This is back-of-envelope estimation."},
            {"step": 2, "title": "Core Numbers", "duration_min": 5,
             "instructions": "Latency hierarchy: L1 cache 0.5ns, RAM 100ns, SSD 100us, HDD 10ms, same-DC 0.5ms, cross-continent 150ms. Storage: 1M users * 1KB = 1GB. Throughput: SSD 1GB/s, HDD 100MB/s, 1Gbps = 100MB/s."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Estimate for a URL shortener: 100M URLs/day = ~1200 writes/sec. Read:write 100:1 = 120K reads/sec. 5 years * 100M/day * 365 * 100 bytes = ~18TB. Need sharding? Need caching? Numbers drive design decisions."},
            {"step": 4, "title": "Estimation Framework", "duration_min": 3,
             "instructions": "The framework: (1) DAU -> RPS (divide by 86400, multiply by 10 for peak), (2) Storage (users * size * retention), (3) Bandwidth (RPS * response size), (4) Memory for cache (cache the hot 20%, Pareto principle)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Estimate for YouTube: 1B DAU, 5 videos/day watched, 5 min avg, 5Mbps bitrate. How much bandwidth? How much storage per day for uploads (1% of users upload, 10min avg)?"},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Know the latency hierarchy by heart. Estimate RPS, storage, bandwidth, and cache size. Round aggressively — order of magnitude is what matters. These numbers justify your design decisions."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Numbers Every Engineer Should Know' + text '10M DAU, 10 requests each. RPS?'"},
            {"step": 2, "content": "Latency hierarchy chart: L1 -> L2 -> RAM -> SSD -> HDD -> DC -> Cross-continent"},
            {"step": 3, "content": "URL shortener estimation: writes/sec, reads/sec, 5-year storage, caching needs"},
            {"step": 4, "content": "callout 'Framework: DAU -> RPS -> Storage -> Bandwidth -> Cache'"},
            {"step": 5, "content": "YouTube estimation exercise on the board"},
        ],
        "difficulty_progression": "Start with memorizing the latency hierarchy. Then simple RPS calculations. Then full estimation (storage + bandwidth + cache). Finally, use estimates to make design decisions.",
        "check_questions": [
            "What's the latency of a RAM access vs SSD vs cross-continent network call?",
            "How do you convert DAU to peak RPS?",
            "How do you estimate storage needs for a 5-year retention period?",
            "Why does the 80/20 rule matter for cache sizing?",
        ],
        "when_to_use": "Use estimation in every system design interview. It demonstrates engineering judgment and justifies design decisions. Always estimate before designing — it tells you whether you need sharding, caching, CDN, etc.",
        "related_topics": ["caching", "sharding", "scaling-reads", "scaling-writes"],
    },

    "realtime-updates": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Open a chat app. Messages appear instantly. Open Google Docs — changes appear as your collaborator types. 'How does the server push data to the client without the client asking?' This is realtime."},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "Three approaches: (1) Long polling (client holds open request), (2) SSE (server pushes events over HTTP), (3) WebSocket (full-duplex over TCP). Compare latency, complexity, and scalability. WebSocket for bidirectional (chat), SSE for server-to-client (feeds)."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Design realtime chat: WebSocket connection per user. On message send: client -> WS -> server -> look up recipient's WS connection -> push. Handle: what if recipient is offline? (store and push on reconnect) What about multiple devices?"},
            {"step": 4, "title": "Scaling Challenge", "duration_min": 5,
             "instructions": "1M concurrent WebSocket connections. Each connection = ~40KB RAM. Total = 40GB. Multiple connection servers needed. Problem: sender's connection server != recipient's. Solution: message broker (Redis Pub/Sub) between connection servers."},
            {"step": 5, "title": "Practice", "duration_min": 6,
             "instructions": "Design realtime for Uber: driver location updates. Which protocol? How often? How to handle 100K concurrent drivers sending GPS every 5 seconds?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Realtime Updates' + text 'How does the server push data without the client asking?'"},
            {"step": 2, "content": "Comparison: Polling vs Long Polling vs SSE vs WebSocket — timeline diagrams"},
            {"step": 3, "content": "Chat WebSocket architecture: client <-> WS server <-> message broker <-> WS server <-> client"},
            {"step": 4, "content": "callout 'Scaling: 1M connections = 40GB RAM, need multiple servers + broker'"},
            {"step": 5, "content": "Uber driver location update design exercise"},
        ],
        "difficulty_progression": "Start with understanding polling vs WebSocket. Then design basic WebSocket chat. Then handle scaling (multiple connection servers + broker). Finally, handle edge cases (offline, reconnection, message buffering).",
        "check_questions": [
            "When would you use SSE instead of WebSocket?",
            "How do you handle WebSocket reconnection on mobile?",
            "How do you scale to 1M concurrent connections?",
            "What's the role of a message broker in a WebSocket architecture?",
        ],
        "when_to_use": "Use realtime updates when the system needs to push data to clients: chat, live dashboards, collaborative editing, location tracking, notifications. Choose WebSocket for bidirectional, SSE for server-to-client.",
        "related_topics": ["networking", "message_queues", "redis", "kafka"],
    },

    "contention": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Scenario: Two users book the last seat on a flight simultaneously. Both see it available, both click book. Without proper handling, both get confirmed — but there's only one seat. This is contention."},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "Three strategies: (1) Pessimistic locking (SELECT FOR UPDATE — block others), (2) Optimistic concurrency (read version, write with WHERE version=X, retry on conflict), (3) Queue serialization (route all writes for a key to one worker)."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Ticketmaster seat booking with pessimistic locking: BEGIN -> SELECT seat WHERE id=123 FOR UPDATE -> check available -> UPDATE seat SET status='booked' -> COMMIT. Other transaction waits at SELECT FOR UPDATE."},
            {"step": 4, "title": "Trade-offs", "duration_min": 5,
             "instructions": "Pessimistic: simple but blocks others (bad for high traffic). Optimistic: no blocking but retries (bad for high contention). Queue: no contention by design but adds latency. Choose based on contention level."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design concurrency control for a payment system: debit account A, credit account B. What happens if the system crashes between debit and credit? Discuss: distributed locks, idempotency keys, saga pattern."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Contention & Concurrency' + text 'Two users book the last seat simultaneously. Who wins?'"},
            {"step": 2, "content": "Three strategies side by side: pessimistic lock, optimistic CAS, queue serialization"},
            {"step": 3, "content": "Ticketmaster SELECT FOR UPDATE walkthrough: two concurrent transactions on a timeline"},
            {"step": 4, "content": "callout 'Choose by contention level: low = optimistic, high = pessimistic or queue'"},
            {"step": 5, "content": "Payment system concurrency exercise"},
        ],
        "difficulty_progression": "Start with understanding race conditions. Then pessimistic locking. Then optimistic concurrency with CAS. Finally, distributed locks and queue serialization for distributed systems.",
        "check_questions": [
            "What's the difference between pessimistic and optimistic concurrency control?",
            "When is optimistic concurrency a bad choice?",
            "How does queue serialization eliminate contention?",
            "Why are idempotency keys important for retry logic?",
        ],
        "when_to_use": "Address contention whenever multiple users can modify the same resource: seat booking, inventory, account balances, rate limiting. Choose pessimistic locking for high contention, optimistic for low contention.",
        "related_topics": ["postgresql", "redis", "sagas", "scaling-writes"],
    },

    "sagas": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Scenario: Order flow — reserve inventory, charge credit card, ship package. Card charge fails. You've already reserved inventory. How do you undo it? You can't use a database transaction because services are separate."},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "Saga: sequence of local transactions, each with a compensating action. If step N fails, run compensations N-1 down to 1. Two styles: choreography (events, decentralized) and orchestration (central coordinator). Sagas trade atomicity for availability."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Order saga (orchestration): (1) Reserve inventory, (2) Charge card, (3) Create shipment. Card fails at step 2 -> compensate step 1: release inventory. Show the orchestrator managing the sequence and handling failures."},
            {"step": 4, "title": "Key Concerns", "duration_min": 5,
             "instructions": "Critical requirements: (1) Every step needs a compensation, (2) Steps and compensations must be idempotent (retries happen), (3) Handle compensation failures (dead-letter queue), (4) No isolation — other sagas may see intermediate states."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the saga for Uber ride booking: match driver -> reserve driver -> charge rider -> start trip. What's the compensation for each step? What if the driver cancels mid-saga?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Sagas' + text 'Reserve inventory -> charge card (FAILS) -> how to undo inventory?'"},
            {"step": 2, "content": "Saga flow: Step 1 -> Step 2 -> Step 3 (FAIL) -> Compensate 2 -> Compensate 1"},
            {"step": 3, "content": "Order saga with orchestrator: forward steps and compensation arrows"},
            {"step": 4, "content": "callout 'Requirements: compensations, idempotency, DLQ, no isolation'"},
            {"step": 5, "content": "Uber ride booking saga exercise"},
        ],
        "difficulty_progression": "Start with understanding why distributed transactions don't work across services. Then the saga pattern with compensations. Then orchestration vs choreography. Finally, handle complex failure scenarios.",
        "check_questions": [
            "Why can't you use a traditional database transaction across microservices?",
            "What's the difference between choreography and orchestration?",
            "Why must saga steps be idempotent?",
            "What happens if a compensation itself fails?",
        ],
        "when_to_use": "Use sagas when a business process spans multiple microservices and you need a form of distributed transaction. Key signals: 'order flow across services,' 'multi-step booking,' 'payment + inventory + shipping.' Prefer orchestration for complex flows.",
        "related_topics": ["message_queues", "kafka", "contention"],
    },

    "scaling-reads": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Your app goes viral. 90% of traffic is reads. Database CPU is at 100%. You need to serve 10x more reads without rewriting the app. Three layers of defense: caching, read replicas, CDN."},
            {"step": 2, "title": "Core Strategies", "duration_min": 5,
             "instructions": "Layer 1: CDN for static assets (images, JS, CSS) — serves from edge, 90% cache hit rate. Layer 2: Application cache (Redis) for dynamic data — cache-aside pattern. Layer 3: Read replicas — route reads to replicas, writes to primary."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Instagram read scaling: (1) CDN for images/thumbnails, (2) Redis for user timelines (LPUSH + LTRIM), (3) PostgreSQL read replicas for profile lookups. Show the read path: client -> CDN -> Redis -> read replica -> primary."},
            {"step": 4, "title": "Trade-offs", "duration_min": 5,
             "instructions": "Caching trade-off: stale data (set TTL). Replica trade-off: replication lag (read-after-write inconsistency). CDN trade-off: invalidation latency. Solution: route reads-after-writes to primary for consistency-sensitive operations."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design read scaling for YouTube: video serving (CDN), video metadata (cache), recommendations (pre-computed and cached), search (Elasticsearch). Where does each read go?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Scaling Reads' + text 'App goes viral. 90% reads. DB at 100% CPU. How to 10x?'"},
            {"step": 2, "content": "Three layers: CDN (edge) -> Redis (app cache) -> Read replicas (DB) + callout 'Each layer absorbs traffic'"},
            {"step": 3, "content": "Instagram read path: client -> CDN -> Redis -> read replica -> primary"},
            {"step": 4, "content": "callout 'Trade-offs: stale data, replication lag, invalidation latency'"},
            {"step": 5, "content": "YouTube read scaling exercise"},
        ],
        "difficulty_progression": "Start with CDN for static content. Then cache-aside with Redis. Then read replicas. Finally, handle consistency issues (read-after-write, cache stampede).",
        "check_questions": [
            "What's the difference between CDN caching and application caching?",
            "How do you handle read-after-write consistency with replicas?",
            "What is cache stampede and how do you prevent it?",
            "When would you NOT cache something?",
        ],
        "when_to_use": "Scale reads when your system is read-heavy (90%+ reads) and the database is the bottleneck. Layer defenses: CDN for static, Redis for dynamic hot data, read replicas for overflow. Always discuss in system design interviews.",
        "related_topics": ["caching", "redis", "replication", "database_indexing"],
    },

    "scaling-writes": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Twitter has 500M tweets/day. A single PostgreSQL server handles maybe 10K writes/sec. 500M / 86400 = ~6K avg, 60K peak. One server isn't enough. How do you scale writes?"},
            {"step": 2, "title": "Core Strategies", "duration_min": 5,
             "instructions": "Sharding: partition data across database servers (by user_id, conversation_id). Message queues: buffer writes, batch-process. CQRS: separate write model from read model. Append-only logs (Kafka): sequential writes are 100x faster than random writes."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Chat system write scaling: shard by conversation_id (all messages for a chat on one shard). Cassandra for write-optimized storage. Kafka for buffering high-throughput writes. Show write path: client -> API -> Kafka -> Cassandra."},
            {"step": 4, "title": "Key Concerns", "duration_min": 5,
             "instructions": "Hot partitions: one shard gets disproportionate writes (celebrity tweets). Idempotency: retries cause duplicates. Rebalancing: adding shards requires data migration. CQRS sync: write model and read model may diverge temporarily."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design write scaling for a payment system: 100K transactions/sec. Must be exactly-once. How to shard? How to ensure idempotency? What's the write path?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Scaling Writes' + text '500M tweets/day. One DB server maxes at 10K writes/sec. How?'"},
            {"step": 2, "content": "Strategies: sharding, message queues, CQRS, append-only logs — with diagrams"},
            {"step": 3, "content": "Chat system write path: client -> API -> Kafka -> Cassandra (sharded by conversation_id)"},
            {"step": 4, "content": "callout 'Concerns: hot partitions, idempotency, rebalancing, CQRS sync lag'"},
            {"step": 5, "content": "Payment system write scaling exercise"},
        ],
        "difficulty_progression": "Start with understanding why writes are harder to scale than reads. Then sharding strategies. Then message queues for buffering. Finally, CQRS and exactly-once processing.",
        "check_questions": [
            "Why is scaling writes harder than scaling reads?",
            "What makes a good shard key for writes?",
            "How does a message queue help with write scaling?",
            "What is CQRS and when should you use it?",
        ],
        "when_to_use": "Scale writes when a single database can't handle write throughput. Key signals: 'millions of writes per day,' 'write-heavy workload,' 'time-series data,' 'event streaming.' Shard for throughput, buffer with queues for spikes.",
        "related_topics": ["sharding", "kafka", "cassandra", "message_queues"],
    },

    "large-blobs": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Should you store a 10MB image in PostgreSQL? What about a 2GB video?' No — binary large objects don't belong in your primary database. Object storage (S3) was built for this. But how does the client upload directly to S3?"},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "Pre-signed URLs: server generates a signed S3 URL, client uploads directly — no blob data touches your servers. Multipart upload for large files. CDN for serving. Async processing pipeline for thumbnails/transcoding."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Instagram photo upload: (1) Client requests upload URL, (2) Server generates pre-signed S3 URL, (3) Client uploads directly to S3, (4) S3 triggers Lambda for thumbnail generation (multiple sizes), (5) Lambda stores thumbnails + updates DB, (6) CDN serves images."},
            {"step": 4, "title": "Key Concerns", "duration_min": 5,
             "instructions": "Content-addressable storage: hash the file content as the key — enables deduplication. Resumable uploads: multipart upload with checkpointing. Virus scanning: async after upload. Cost: S3 storage tiers (Standard -> Infrequent Access -> Glacier)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the upload/serving pipeline for Dropbox: chunked upload with deduplication, delta sync for modified files, version history. How to detect changed chunks efficiently?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Large Blob Storage' + text 'Store a 10MB image in PostgreSQL? A 2GB video? No!'"},
            {"step": 2, "content": "Pre-signed URL flow: client -> API (get URL) -> client -> S3 (direct upload)"},
            {"step": 3, "content": "Instagram upload pipeline: client -> S3 -> Lambda (thumbnails) -> CDN (serve)"},
            {"step": 4, "content": "callout 'Key techniques: pre-signed URLs, multipart upload, CDN, deduplication'"},
            {"step": 5, "content": "Dropbox chunked upload and delta sync exercise"},
        ],
        "difficulty_progression": "Start with pre-signed URLs for simple uploads. Then multipart upload for large files. Then async processing pipelines. Finally, deduplication and delta sync.",
        "check_questions": [
            "Why shouldn't you store blobs in a relational database?",
            "How do pre-signed URLs work?",
            "How does content-addressable storage enable deduplication?",
            "What's the benefit of multipart upload?",
        ],
        "when_to_use": "Use object storage (S3/GCS) for any file larger than a few KB: images, videos, documents, backups. Never route blob data through application servers — use pre-signed URLs. Always serve via CDN.",
        "related_topics": ["caching", "long-tasks", "scaling-reads"],
    },

    "long-tasks": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "User uploads a video. Transcoding takes 30 minutes. HTTP request timeout is 30 seconds. You can't make the user wait. 'How do you handle a task that takes 1000x longer than a request?'"},
            {"step": 2, "title": "Core Pattern", "duration_min": 5,
             "instructions": "Async job pattern: (1) Accept request -> return 202 + job_id, (2) Enqueue job to task queue, (3) Worker picks up job, processes it, (4) Client polls GET /jobs/{id} for status or receives webhook/push. Key infrastructure: task queue (SQS, Celery) + status store (Redis)."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Video transcoding pipeline: POST /videos -> 202 {job_id} -> Kafka topic -> transcoding workers (multiple resolutions) -> S3 upload -> DB update (status=complete, URLs) -> push notification to client."},
            {"step": 4, "title": "Key Concerns", "duration_min": 5,
             "instructions": "Idempotency: worker crashes mid-task, job retries — must be safe to re-process. Progress tracking: update job status (queued -> processing 30% -> processing 60% -> complete). Dead-letter queue: after N failures, move to DLQ for investigation. Timeout: max execution time per job."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the pipeline for a web crawler: URL is a task, workers fetch/parse/extract links, new URLs become new tasks. How to handle: deduplication, politeness (rate limit per domain), failures?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Long-Running Tasks' + text 'Video transcoding: 30 min. HTTP timeout: 30 sec. Now what?'"},
            {"step": 2, "content": "Async job flow: POST -> 202 {job_id} -> Queue -> Worker -> Status update -> GET status"},
            {"step": 3, "content": "Video transcoding pipeline with all components"},
            {"step": 4, "content": "callout 'Key concerns: idempotency, progress tracking, DLQ, timeout'"},
            {"step": 5, "content": "Web crawler pipeline exercise"},
        ],
        "difficulty_progression": "Start with the basic async job pattern. Then add progress tracking. Then handle failures (retry, DLQ). Finally, design complex multi-step pipelines with dependencies.",
        "check_questions": [
            "Why can't long tasks be handled synchronously?",
            "How does the client know when a long task is complete?",
            "Why must long-running tasks be idempotent?",
            "What's the purpose of a dead-letter queue?",
        ],
        "when_to_use": "Use async jobs for any task that takes longer than a request timeout: transcoding, report generation, ML inference, data migration, web crawling. Key signal: 'processing takes minutes/hours, not milliseconds.'",
        "related_topics": ["message_queues", "kafka", "large-blobs"],
    },

    "replication": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Your database server's disk fails. All data is gone. If you had a copy on another server, you'd be fine. That's replication. But replication isn't just about durability — it's about availability and performance too."},
            {"step": 2, "title": "Core Models", "duration_min": 5,
             "instructions": "Single-leader: one primary (writes), N replicas (reads). Multi-leader: multiple primaries (for multi-datacenter). Leaderless: any node handles reads/writes, quorum ensures consistency (W+R > N). Sync vs async replication trade-off."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Design replication for a key-value store (DynamoDB model): N=3 replicas, W=2 (write to 2), R=2 (read from 2). W+R > N guarantees at least one read hits the latest write. Show a write being sent to 3 nodes, 2 ACKs sufficient."},
            {"step": 4, "title": "Consistency Challenges", "duration_min": 5,
             "instructions": "Replication lag: async replicas are seconds behind. Problems: (1) Read your own writes (user updates profile, reads stale), (2) Monotonic reads (different replicas return different versions). Solutions: read-after-write routing, session stickiness."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design replication for a chat system: users in US and EU. Which replication model? How to handle message ordering across datacenters? What consistency level for message reads?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Replication' + text 'Your disk fails. All data gone. Unless you had a copy...'"},
            {"step": 2, "content": "Three models: single-leader, multi-leader, leaderless — with diagrams"},
            {"step": 3, "content": "Quorum: N=3, W=2, R=2 — write/read paths showing ACKs"},
            {"step": 4, "content": "callout 'Challenges: replication lag, read-your-writes, split-brain'"},
            {"step": 5, "content": "Multi-datacenter chat replication exercise"},
        ],
        "difficulty_progression": "Start with single-leader replication. Then understand sync vs async. Then quorum replication. Finally, multi-leader with conflict resolution.",
        "check_questions": [
            "What's the difference between single-leader and leaderless replication?",
            "What does W+R > N guarantee in quorum replication?",
            "How do you handle read-your-own-writes with async replication?",
            "What is split-brain and how do you prevent it?",
        ],
        "when_to_use": "Discuss replication whenever availability or durability matters. Single-leader for most cases. Multi-leader for multi-datacenter. Leaderless for tunable consistency. Always mention the consistency-latency trade-off.",
        "related_topics": ["cap_theorem", "sharding", "cassandra", "postgresql"],
    },

    "load-balancing": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "You have 5 servers. All traffic hits server 1 — it crashes from overload. The other 4 are idle. 'How do you distribute traffic evenly?' Load balancer. 'But it's not just round-robin...'"},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "L4 (transport): routes by IP/port, fast, no content inspection. L7 (application): inspects HTTP, routes by URL/header/cookie, enables path-based routing and sticky sessions. Algorithms: round-robin, least connections, IP hash, consistent hashing."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Design LB for a web app: L7 LB routes /api/* to backend pool, /static/* to CDN, /ws/* to WebSocket servers. Health checks: active (ping /health every 10s), remove unhealthy servers. Show failover when a server goes down."},
            {"step": 4, "title": "Scaling the LB", "duration_min": 5,
             "instructions": "The LB itself is a single point of failure. Solutions: active-passive pair (floating IP), DNS round-robin to multiple LBs, cloud LBs (AWS ALB/NLB auto-scale). For global traffic: GeoDNS routes to nearest datacenter's LB."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design load balancing for a chat app with WebSocket: need sticky sessions (same client reconnects to same server). Options: IP hash, cookie-based routing, or connection registry. Discuss trade-offs."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Load Balancing' + text '5 servers, all traffic hits server 1. It crashes. Now what?'"},
            {"step": 2, "content": "L4 vs L7 comparison + algorithms: round-robin, least connections, consistent hashing"},
            {"step": 3, "content": "L7 routing: /api -> backend, /static -> CDN, /ws -> WebSocket servers"},
            {"step": 4, "content": "callout 'LB is SPOF: active-passive, DNS round-robin, cloud auto-scale'"},
            {"step": 5, "content": "Chat WebSocket load balancing exercise"},
        ],
        "difficulty_progression": "Start with basic round-robin. Then L4 vs L7 differences. Then health checks and failover. Finally, sticky sessions and global load balancing.",
        "check_questions": [
            "What's the difference between L4 and L7 load balancing?",
            "When would you use least connections instead of round-robin?",
            "How do you prevent the load balancer from being a single point of failure?",
            "How do sticky sessions work and when are they needed?",
        ],
        "when_to_use": "Include a load balancer in every system design. L7 for web traffic (path routing, SSL termination). L4 for high-performance/non-HTTP traffic. Always mention health checks and HA for the LB itself.",
        "related_topics": ["networking", "consistent_hashing", "api-gateway"],
    },

    # =====================================================================
    # SYSTEM DESIGN — Technologies (SD Tech)
    # =====================================================================

    "redis": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Why is your database slow?' Because it reads from disk. 'What if we could keep hot data in memory?' Redis: sub-millisecond reads. But it's not just a cache — it's a data structure server."},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "Redis data structures: Strings (cache/counter), Hashes (objects), Lists (queues/feeds), Sets (unique items), Sorted Sets (leaderboards), Streams (event log). Single-threaded event loop = no lock contention. Persistence: RDB snapshots + AOF log."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Design a rate limiter with Redis: INCR key (user:123:minute:42) -> if count > limit, reject. EXPIRE key 60 (auto-cleanup). Atomic increment + expiry in one command. Show sliding window variant with sorted sets."},
            {"step": 4, "title": "Scaling Redis", "duration_min": 5,
             "instructions": "Redis Cluster: 16384 hash slots distributed across masters. Each master has a replica. Consistent hashing assigns keys to slots. Adding a node = migrate some slots. Redis Sentinel for HA without clustering (auto-failover)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design a leaderboard with Redis Sorted Sets: ZADD leaderboard score user, ZREVRANGE for top-K, ZRANK for user's rank. How to handle: millions of users? Real-time updates? Regional leaderboards?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Redis' + text 'Why is your DB slow? Disk. What if hot data lived in memory?'"},
            {"step": 2, "content": "Redis data structures: Strings, Hashes, Lists, Sets, Sorted Sets — with use cases"},
            {"step": 3, "content": "Rate limiter: INCR + EXPIRE walkthrough, sliding window with sorted set"},
            {"step": 4, "content": "Redis Cluster: 16384 hash slots, masters + replicas + callout 'Sentinel for HA'"},
            {"step": 5, "content": "Leaderboard design with Sorted Sets exercise"},
        ],
        "difficulty_progression": "Start with Redis as a simple cache (GET/SET/TTL). Then advanced data structures (sorted sets, streams). Then Redis Cluster for horizontal scaling. Finally, design patterns: rate limiter, session store, pub/sub.",
        "check_questions": [
            "What's the difference between RDB and AOF persistence?",
            "Why is Redis single-threaded and how is it still fast?",
            "How does Redis Cluster distribute data?",
            "When would you use a Redis Sorted Set instead of a regular Set?",
        ],
        "when_to_use": "Use Redis as a caching layer, session store, rate limiter, leaderboard, or message broker. Key signals: 'need sub-millisecond latency,' 'cache hot data,' 'real-time counter,' 'ranking/leaderboard.' Don't use as primary storage (data must fit in memory).",
        "related_topics": ["caching", "scaling-reads", "realtime-updates", "consistent_hashing"],
    },

    "elasticsearch": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'How does Google search billions of web pages in 200ms?' It's not scanning every page — it's using an inverted index. Elasticsearch brings this to your application."},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "Inverted index: maps terms to documents (like the index at the back of a book). Elasticsearch shards indexes for horizontal scaling. Near-real-time: documents searchable ~1 second after indexing. BM25 scoring for relevance ranking."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Design tweet search for Twitter: index each tweet (content, hashtags, author, timestamp) in Elasticsearch. Query: full-text search on content + filter by hashtag + sort by recency. Show the mapping and a sample query."},
            {"step": 4, "title": "Key Concerns", "duration_min": 5,
             "instructions": "Elasticsearch is NOT a primary database (eventually consistent, no ACID). Sync from source of truth: use change data capture or event-driven indexing. Mapping design: define fields upfront. Shard planning: ~50GB per shard."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the search system for an e-commerce platform: product search with filters (category, price range, brand), autocomplete, typo tolerance. How to keep the index in sync with the product catalog?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Elasticsearch' + text 'Google searches billions of pages in 200ms. How?'"},
            {"step": 2, "content": "Inverted index: term -> [doc1, doc3, doc7] + callout 'O(1) lookup for any term'"},
            {"step": 3, "content": "Tweet search: mapping + query example with filters and sorting"},
            {"step": 4, "content": "callout 'NOT a primary DB. Sync via CDC or events. Plan shards at ~50GB each.'"},
            {"step": 5, "content": "E-commerce search design exercise"},
        ],
        "difficulty_progression": "Start with understanding inverted indexes. Then basic search queries and mappings. Then sharding and replication. Finally, advanced features: autocomplete, fuzzy matching, aggregations.",
        "check_questions": [
            "What is an inverted index and why is it fast?",
            "Why shouldn't you use Elasticsearch as a primary database?",
            "How do you keep Elasticsearch in sync with your source of truth?",
            "What's the right shard size for an Elasticsearch index?",
        ],
        "when_to_use": "Use Elasticsearch when you need full-text search, autocomplete, or log analysis. Key signals: 'search across text content,' 'autocomplete suggestions,' 'filter + rank results,' 'log aggregation.' Always have a separate source of truth.",
        "related_topics": ["database_indexing", "kafka", "postgresql"],
    },

    "kafka": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "A celebrity tweets and it needs to appear on 10 million followers' timelines. Processing them one by one would take hours. 'What if we had a firehose that multiple workers could read from in parallel?' That's Kafka."},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "Kafka = distributed commit log. Topics hold events, split into partitions for parallelism. Producers write, consumers read. Consumer groups: each partition consumed by one consumer in the group. Key feature: retention — replay events from any point in time."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Twitter fan-out: tweet published -> 'tweets' Kafka topic (partitioned by tweet_id) -> timeline workers consume, update each follower's cached timeline in Redis. Consumer group with 100 workers processes partitions in parallel."},
            {"step": 4, "title": "Key Concerns", "duration_min": 5,
             "instructions": "Partition key choice: determines parallelism and ordering. Same key = same partition = ordered. Consumer lag: if consumers are slow, lag builds up. Exactly-once: achievable with idempotent producers + transactional consumers but adds latency."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the event pipeline for a payment system: payment events -> Kafka -> (1) ledger service, (2) notification service, (3) analytics, (4) fraud detection. What's the partition key? How to ensure exactly-once for the ledger?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Apache Kafka' + text 'Celebrity tweets -> 10M followers. Process in parallel?'"},
            {"step": 2, "content": "Kafka topic with 3 partitions, producer writing by key, consumer group reading in parallel"},
            {"step": 3, "content": "Twitter fan-out: tweet -> Kafka -> timeline workers -> Redis"},
            {"step": 4, "content": "callout 'Key decisions: partition key, consumer lag, exactly-once semantics'"},
            {"step": 5, "content": "Payment event pipeline exercise"},
        ],
        "difficulty_progression": "Start with understanding topics and partitions. Then consumer groups for parallel processing. Then partition key selection. Finally, exactly-once semantics and event sourcing.",
        "check_questions": [
            "What's the difference between a Kafka topic and a partition?",
            "How do consumer groups enable parallel processing?",
            "Why is partition key choice critical?",
            "What's the difference between at-least-once and exactly-once delivery?",
        ],
        "when_to_use": "Use Kafka for high-throughput event streaming, async processing, and service decoupling. Key signals: 'events need to be processed by multiple consumers,' 'need event replay,' 'high-throughput writes,' 'event-driven architecture.' Not for request-response (use REST/gRPC).",
        "related_topics": ["message_queues", "scaling-writes", "sagas", "realtime-updates"],
    },

    "api-gateway": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Your app has 10 microservices. The mobile client needs to know the URL of each one, handle auth for each, deal with different rate limits. 'What if there was a single entry point that handled all this?' API Gateway."},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "API Gateway = reverse proxy + cross-cutting concerns. Routes requests to the right service. Handles: auth, rate limiting, SSL termination, request/response transformation, logging, circuit breaking. Backend for Frontend (BFF): separate gateways for web vs mobile."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Design gateway for Uber: mobile client -> API Gateway -> route /rides to ride service, /drivers to driver service, /payments to payment service. Gateway validates JWT, applies rate limits, transforms responses for mobile (aggregate driver + ride data)."},
            {"step": 4, "title": "Key Concerns", "duration_min": 5,
             "instructions": "Gateway as SPOF: deploy multiple instances behind a load balancer. Don't put business logic in the gateway — only cross-cutting concerns. Circuit breaking: if a backend is slow, fail fast instead of cascading failures. Latency: gateway adds a hop."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the API gateway for an e-commerce platform: web client, mobile client, third-party API. Different rate limits for each. Different response shapes for web vs mobile. How to handle versioning?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'API Gateway' + text '10 microservices. Mobile client needs one entry point.'"},
            {"step": 2, "content": "Gateway diagram: client -> gateway (auth, rate limit, route) -> services A, B, C"},
            {"step": 3, "content": "Uber gateway: /rides, /drivers, /payments routing + JWT validation + rate limiting"},
            {"step": 4, "content": "callout 'Concerns: SPOF, no business logic, circuit breaking, latency overhead'"},
            {"step": 5, "content": "E-commerce multi-client gateway exercise"},
        ],
        "difficulty_progression": "Start with basic request routing. Then auth and rate limiting. Then BFF pattern for different clients. Finally, circuit breaking and observability.",
        "check_questions": [
            "What cross-cutting concerns does an API gateway handle?",
            "What's the Backend for Frontend (BFF) pattern?",
            "Why shouldn't you put business logic in the gateway?",
            "How do you prevent the gateway from being a single point of failure?",
        ],
        "when_to_use": "Include an API gateway in any microservices architecture. It simplifies client-side logic and centralizes cross-cutting concerns. Key signals: 'multiple microservices,' 'different clients (web/mobile),' 'need centralized auth/rate limiting.'",
        "related_topics": ["load-balancing", "networking", "api_design"],
    },

    "cassandra": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Your chat app generates 100K messages per second. PostgreSQL tops out at 10K writes/sec per server. You need a database built for writes. Enter Cassandra — designed for massive write throughput with no single point of failure."},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "Cassandra = ring of nodes with consistent hashing. Partition key determines node. Clustering key sorts within a partition. Write path: commit log -> memtable -> SSTable. No master node = no SPOF. Trade-off: no joins, no ad-hoc queries — model data around your queries."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Model a chat app in Cassandra: table messages (chat_id UUID, timestamp TIMESTAMP, sender TEXT, content TEXT, PRIMARY KEY (chat_id, timestamp)). chat_id is partition key, timestamp is clustering key. Query: all messages in a chat, sorted by time. One table per query."},
            {"step": 4, "title": "Key Concerns", "duration_min": 5,
             "instructions": "Large partitions: keep under 100MB (too much data under one partition key). Tombstones: deletes create tombstones that slow reads until compaction. Tunable consistency: ONE (fast, eventual), QUORUM (balanced), ALL (strong, slow)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Model Twitter in Cassandra: how to store (1) user tweets, (2) user timeline/feed, (3) user profile. Each is a separate table with its own partition key. Design for the query patterns."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Apache Cassandra' + text '100K messages/sec. PostgreSQL maxes at 10K. Need a write-optimized DB.'"},
            {"step": 2, "content": "Cassandra ring: 6 nodes, consistent hashing, RF=3 + callout 'No master = no SPOF'"},
            {"step": 3, "content": "Chat table design: partition key (chat_id) + clustering key (timestamp) with sample data"},
            {"step": 4, "content": "callout 'Concerns: large partitions, tombstones, tunable consistency'"},
            {"step": 5, "content": "Twitter data modeling exercise: 3 tables for 3 query patterns"},
        ],
        "difficulty_progression": "Start with understanding partition key vs clustering key. Then data modeling (one table per query). Then tunable consistency. Finally, handle operational concerns (tombstones, compaction, large partitions).",
        "check_questions": [
            "What's the difference between a partition key and a clustering key?",
            "Why does Cassandra use 'one table per query' modeling?",
            "What are tombstones and why do they matter?",
            "When would you choose Cassandra over PostgreSQL?",
        ],
        "when_to_use": "Use Cassandra for write-heavy workloads with known access patterns: chat messages, time-series data, IoT sensor data, activity logs. Key signals: 'massive write throughput,' 'no single point of failure,' 'known query patterns.' Don't use for ad-hoc queries or joins.",
        "related_topics": ["sharding", "cap_theorem", "scaling-writes", "dynamodb"],
    },

    "dynamodb": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'What if you could have a database with single-digit millisecond latency at any scale, and you never had to manage a server?' DynamoDB: fully managed, serverless, auto-scaling. But you must design your access patterns upfront."},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "DynamoDB: partition key (hash) + optional sort key (range). Items are distributed by partition key hash. GSI (Global Secondary Index) enables alternative query patterns. Provisioned vs on-demand capacity. Conditional writes for optimistic concurrency."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Design a URL shortener with DynamoDB: partition key = short_code, attributes = long_url, created_at, user_id. GSI on user_id for 'list my URLs.' TTL attribute for auto-deletion. Conditional write: PutItem IF short_code does not exist."},
            {"step": 4, "title": "Key Concerns", "duration_min": 5,
             "instructions": "Hot partitions: one partition key gets all traffic (celebrity user). Solution: write sharding (append random suffix). Scan is expensive: never scan in production, always Query with partition key. GSI eventual consistency: reads from GSI may miss recent writes."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design DynamoDB tables for a booking system: Events, Bookings, Users. How to query: (1) Bookings for an event, (2) Bookings by a user, (3) Available seats for an event. What are the partition keys? Do you need GSIs?"},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Amazon DynamoDB' + text 'Single-digit ms latency. Any scale. No servers. The catch: design upfront.'"},
            {"step": 2, "content": "Table with partition key + sort key + GSI diagram + callout 'Partition key distributes, sort key orders'"},
            {"step": 3, "content": "URL shortener: table design, GSI for user lookup, conditional write for uniqueness"},
            {"step": 4, "content": "callout 'Pitfalls: hot partitions, never Scan, GSI eventual consistency'"},
            {"step": 5, "content": "Booking system table design exercise"},
        ],
        "difficulty_progression": "Start with single-table design basics. Then GSIs for alternative access patterns. Then conditional writes for concurrency. Finally, handle hot partitions and advanced patterns (single-table design with overloaded keys).",
        "check_questions": [
            "What's the difference between a partition key and a sort key?",
            "When do you need a Global Secondary Index?",
            "How do conditional writes provide optimistic concurrency?",
            "What causes hot partitions and how do you fix them?",
        ],
        "when_to_use": "Use DynamoDB for serverless key-value or key-range access with predictable latency. Key signals: 'simple access patterns,' 'need auto-scaling,' 'serverless architecture,' 'low-latency reads/writes.' Not for complex queries, joins, or ad-hoc analytics.",
        "related_topics": ["cassandra", "sharding", "cap_theorem"],
    },

    "postgresql": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Ask: 'Your payment system needs to debit account A and credit account B atomically. If it crashes midway, neither should happen. What database guarantees this?' ACID transactions. PostgreSQL is the gold standard for relational data."},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "ACID: Atomicity (all or nothing), Consistency (constraints respected), Isolation (concurrent transactions don't interfere), Durability (committed data survives crashes). MVCC: readers don't block writers. Indexes: B-tree, GIN, BRIN."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Payment transfer: BEGIN -> UPDATE accounts SET balance = balance - 100 WHERE id = 'A' -> UPDATE accounts SET balance = balance + 100 WHERE id = 'B' -> COMMIT. If either fails, ROLLBACK. Show MVCC: concurrent read sees pre-transaction balance."},
            {"step": 4, "title": "Scaling PostgreSQL", "duration_min": 5,
             "instructions": "Vertical: bigger machine (128 cores, TB of RAM). Read replicas: async replication for read scaling. Citus extension: transparent sharding. Connection pooling (PgBouncer): handle 10K+ concurrent connections. Partitioning: range/hash partitions for large tables."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the database schema for an e-commerce platform: Users, Products, Orders, OrderItems, Payments. Show indexes, constraints, and how a checkout transaction works (decrement inventory + create order + process payment atomically)."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'PostgreSQL' + text 'Debit A, credit B. Crash midway. Neither should happen. ACID.'"},
            {"step": 2, "content": "ACID properties explained + MVCC diagram: two transactions, different row versions"},
            {"step": 3, "content": "Payment transfer transaction walkthrough with BEGIN/COMMIT/ROLLBACK"},
            {"step": 4, "content": "callout 'Scaling: vertical, read replicas, Citus, PgBouncer, partitioning'"},
            {"step": 5, "content": "E-commerce schema design exercise"},
        ],
        "difficulty_progression": "Start with ACID transactions. Then index types and query optimization. Then scaling (replicas, partitioning). Finally, advanced features (JSONB, full-text search, pg_vector).",
        "check_questions": [
            "What does ACID stand for and why does it matter?",
            "How does MVCC allow concurrent reads and writes?",
            "When would you use a GIN index instead of a B-tree?",
            "How do you scale PostgreSQL beyond a single server?",
        ],
        "when_to_use": "Use PostgreSQL as the default database for data that needs strong consistency, complex relationships, and flexible querying. Key signals: 'financial data,' 'complex joins,' 'need transactions,' 'relational data.' Most systems start with PostgreSQL and add specialized stores later.",
        "related_topics": ["database_indexing", "sharding", "replication", "contention"],
    },

    "zookeeper": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "You have 3 database replicas. One must be the leader (handles writes). If the leader crashes, another must take over. 'How do the replicas agree on who is the leader?' Coordination. ZooKeeper is the coordinator."},
            {"step": 2, "title": "Core Concepts", "duration_min": 5,
             "instructions": "ZooKeeper: hierarchical namespace of znodes (like a filesystem). Ephemeral znodes: auto-delete when session ends. Watches: get notified on changes. Use cases: leader election, distributed locks, service discovery, configuration management. ZAB consensus protocol ensures strong consistency."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Leader election: each node creates ephemeral sequential znode /election/n_0001. The lowest number is the leader. Others watch the znode just below theirs. When the leader crashes, its ephemeral znode disappears, the next in line detects via watch and becomes leader."},
            {"step": 4, "title": "Key Concerns", "duration_min": 5,
             "instructions": "ZooKeeper is NOT for high-throughput data. It's for coordination (low-volume, high-importance). Deploy as an ensemble (3 or 5 nodes) for fault tolerance. Handle session expiry: ephemeral nodes disappear, locks are released — app must re-acquire. Alternatives: etcd (Kubernetes uses this), Consul."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design service discovery using ZooKeeper: services register under /services/payment/instances/. API gateway watches /services/ for changes. When a new instance starts or crashes, the gateway automatically updates its routing table."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Apache ZooKeeper' + text '3 DB replicas. Who is the leader? What if leader crashes?'"},
            {"step": 2, "content": "Znode tree: /election/n_0001 (ephemeral), /services/payment/instance-1 + callout 'Coordination, not data storage'"},
            {"step": 3, "content": "Leader election: sequential znodes, lowest = leader, others watch, failover on crash"},
            {"step": 4, "content": "callout 'Deploy as ensemble (3/5 nodes). Handle session expiry. Alternatives: etcd, Consul'"},
            {"step": 5, "content": "Service discovery design exercise"},
        ],
        "difficulty_progression": "Start with understanding znodes and watches. Then leader election. Then distributed locks. Finally, service discovery and configuration management.",
        "check_questions": [
            "What are ephemeral znodes and why are they useful?",
            "How does ZooKeeper-based leader election work?",
            "Why deploy ZooKeeper as an ensemble of 3 or 5 nodes?",
            "What happens when a ZooKeeper session expires?",
        ],
        "when_to_use": "Use ZooKeeper (or etcd/Consul) for distributed coordination: leader election, distributed locks, service discovery, configuration management. Key signals: 'elect a leader,' 'distributed lock,' 'service registry.' Never use for high-throughput data storage.",
        "related_topics": ["replication", "kafka", "load-balancing"],
    },

    # =====================================================================
    # LLD TOPICS
    # =====================================================================

    "oop-principles": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show a 500-line function that handles parking, pricing, notifications, and reporting all in one. 'This works. Why is it bad? What happens when you need to change the pricing logic?' Introduce the four OOP pillars as the solution."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Four pillars: (1) Encapsulation — hide internal state, expose interface. (2) Inheritance — is-a relationship, code reuse. (3) Polymorphism — one interface, many implementations. (4) Abstraction — define what, hide how. Show each with Parking Lot examples."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Parking Lot OOP: Vehicle hierarchy (abstract Vehicle, concrete Car/Motorcycle/Truck) = inheritance + polymorphism. ParkingSpot encapsulates availability = encapsulation. PricingStrategy interface = abstraction. Walk through the class diagram."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "When to use each pillar: Encapsulation = always (private fields, public methods). Inheritance = when there's a clear is-a relationship (limit depth to 2-3). Polymorphism = when behavior varies by type. Prefer composition over inheritance for has-a relationships."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the class hierarchy for a Chess Game: abstract Piece with get_valid_moves(), concrete King/Queen/Rook/etc. Board encapsulates the grid. Show polymorphism: board.get_valid_moves(piece) works for any piece type."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: OOP organizes code around objects with clear responsibilities. Encapsulation protects invariants. Polymorphism eliminates switch/case. Prefer composition for flexibility. These principles are the foundation of LLD interviews."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'OOP Principles' + text showing the 500-line monolithic function problem"},
            {"step": 2, "content": "Four pillars with definitions + Parking Lot examples for each"},
            {"step": 3, "content": "UML class diagram: Vehicle hierarchy + PricingStrategy + ParkingSpot encapsulation"},
            {"step": 4, "content": "callout 'Composition over inheritance for has-a relationships'"},
            {"step": 5, "content": "Chess Game class hierarchy exercise"},
        ],
        "difficulty_progression": "Start with encapsulation (private fields, public methods). Then inheritance and polymorphism with a Vehicle hierarchy. Then composition vs inheritance. Finally, apply all four to a full LLD problem.",
        "check_questions": [
            "What's the difference between encapsulation and abstraction?",
            "When should you prefer composition over inheritance?",
            "How does polymorphism eliminate if/else chains?",
            "Why should inheritance hierarchies be kept shallow (2-3 levels)?",
        ],
        "when_to_use": "Apply OOP principles in every LLD interview. Encapsulation: always. Inheritance: for clear is-a hierarchies. Polymorphism: when behavior varies by type. Abstraction: when defining interfaces/contracts. Composition: for has-a relationships.",
        "related_topics": ["solid-principles", "design-patterns-creational", "design-patterns-structural", "design-patterns-behavioral"],
    },

    "solid-principles": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show a bad code example: a ParkingService class with methods for parking, pricing, notifications, AND reporting. 'Every time pricing changes, you risk breaking parking logic. Every time notification format changes, you risk breaking pricing. Why?' Because it has too many reasons to change."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Walk through each principle with a bad-to-good refactoring: S — split ParkingService into ParkingManager + FeeCalculator + NotificationService. O — add new discount types via DiscountStrategy interface, not by editing existing code. L — Square extends Rectangle but breaks setWidth semantics. I — split fat Machine interface into Printable + Scannable. D — ParkingLot depends on PricingStrategy interface, not HourlyPricing."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Refactor a Vending Machine step by step: SRP (separate Inventory from Payment from Display). OCP (State pattern — add new states without modifying VendingMachine). DIP (VendingMachine depends on PaymentMethod interface, not CashPayment directly)."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "SOLID connects to design patterns: OCP -> Strategy, State, Observer. DIP -> Dependency Injection. ISP -> role interfaces. SRP -> microservices at a larger scale. In interviews, name the principle you're applying when you make a design decision."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Review a Shopping Cart design that violates SOLID. Identify which principles are violated and refactor. The Cart handles items, discounts, tax calculation, and email receipts — all in one class."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: SOLID makes code easier to extend and maintain. SRP = one reason to change. OCP = extend without modifying. LSP = subtypes are substitutable. ISP = focused interfaces. DIP = depend on abstractions. Name these principles in interviews."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'SOLID Principles' + text showing ParkingService with too many responsibilities"},
            {"step": 2, "content": "Before/after for each principle: SRP split, OCP Strategy, LSP Square/Rectangle, ISP split, DIP inversion"},
            {"step": 3, "content": "Vending Machine refactoring: monolith -> SRP classes -> State pattern (OCP) -> DIP"},
            {"step": 4, "content": "callout 'SOLID -> Design Patterns: OCP=Strategy/State, DIP=DI, ISP=role interfaces'"},
            {"step": 5, "content": "Shopping Cart review exercise: identify violations and refactor"},
        ],
        "difficulty_progression": "Start with SRP (easiest to understand). Then OCP with Strategy pattern. Then DIP with dependency injection. Then LSP with the Square/Rectangle example. Finally, ISP with interface segregation.",
        "check_questions": [
            "Give an example of a class that violates SRP. How would you fix it?",
            "How does the Strategy pattern help with OCP?",
            "What's the classic LSP violation with Square and Rectangle?",
            "How does DIP relate to dependency injection?",
        ],
        "when_to_use": "Apply SOLID in every LLD interview. SRP when designing classes. OCP when new behavior is needed. LSP when using inheritance. ISP when defining interfaces. DIP when connecting layers. Name the principle explicitly — interviewers look for this.",
        "related_topics": ["oop-principles", "design-patterns-creational", "design-patterns-behavioral", "lld-framework"],
    },

    "design-patterns-creational": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show code: if vehicle_type == 'car': return Car() elif vehicle_type == 'truck': return Truck() ... 'Every time you add a new vehicle type, you modify this code. What if object creation was abstracted?' That's what creational patterns solve."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Five creational patterns: Factory Method (create objects without specifying concrete class), Abstract Factory (families of related objects), Builder (step-by-step complex construction), Singleton (exactly one instance), Prototype (clone existing objects). Focus on Factory and Builder — most common in interviews."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Factory for Parking Lot: VehicleFactory.create('car', 'ABC123') returns a Car instance. Adding a new vehicle type = adding one line to the factory, not modifying client code. Builder for Hotel Reservation: ReservationBuilder().setGuest(g).setRoom(r).setDates(in, out).addService(s).build()."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "When to use each: Factory — when client shouldn't know the concrete class. Builder — when constructor has many optional parameters. Singleton — when exactly one instance is needed (use sparingly). Prototype — when creation is expensive and you can clone."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design the object creation for a Pizza ordering system: PizzaFactory for different types, PizzaBuilder for customization (size, toppings, crust). Show how Factory and Builder can work together."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Creational patterns abstract object creation. Factory for 'which class to instantiate.' Builder for 'how to construct step by step.' Singleton for 'only one instance.' In interviews, use Factory to eliminate type-switching code."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Creational Patterns' + text showing if/elif chain for vehicle creation"},
            {"step": 2, "content": "Five patterns with one-line descriptions and UML sketches"},
            {"step": 3, "content": "VehicleFactory UML + ReservationBuilder UML with method chaining"},
            {"step": 4, "content": "callout 'Factory: which class. Builder: how to construct. Singleton: only one.'"},
            {"step": 5, "content": "Pizza ordering exercise: Factory + Builder combined"},
        ],
        "difficulty_progression": "Start with Simple Factory. Then Factory Method (with inheritance). Then Builder (with validation). Then Singleton (thread-safe). Finally, Abstract Factory for related object families.",
        "check_questions": [
            "What problem does the Factory pattern solve?",
            "When would you use Builder instead of a constructor?",
            "Why is Singleton considered an anti-pattern by some?",
            "What's the difference between Factory Method and Abstract Factory?",
        ],
        "when_to_use": "Use Factory when client code shouldn't depend on concrete classes. Use Builder when constructors have many optional parameters. Use Singleton sparingly for truly global instances (connection pools, loggers). Name the pattern in LLD interviews.",
        "related_topics": ["oop-principles", "solid-principles", "design-patterns-structural"],
    },

    "design-patterns-structural": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show a file system: files and directories. A directory contains files AND other directories. You want to call .size() on both. 'How do you treat files and directories uniformly?' That's the Composite pattern. Structural patterns compose objects into larger structures."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Six structural patterns: Adapter (convert interface), Decorator (add behavior dynamically), Composite (tree with uniform interface), Facade (simplified entry point), Proxy (control access), Bridge (decouple abstraction from implementation). Focus on Decorator and Composite."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "File System with Composite: FSEntry (abstract, size() method), File (leaf, size = content length), Directory (composite, size = sum of children sizes). Decorator for Shopping Cart: BasicCartItem wrapped by GiftWrapDecorator (adds $5) wrapped by InsuranceDecorator (adds 10%)."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "When to use each: Composite — tree structures (file system, org chart, UI widgets). Decorator — stackable enhancements (I/O streams, middleware). Adapter — make incompatible interfaces work together. Facade — simplify a complex subsystem. Proxy — lazy loading, access control, logging."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design a notification system: NotificationDecorator pattern. Base notification. Wrapped by: EmailDecorator, SMSDecorator, PushDecorator. Each adds a delivery channel. Show how decorators stack."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Structural patterns compose objects. Composite for part-whole hierarchies. Decorator for stackable behavior. Adapter for interface conversion. Facade for simplification. In interviews, show the UML diagram before coding."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Structural Patterns' + text 'File system: .size() on files AND directories. How?'"},
            {"step": 2, "content": "Six patterns with one-line descriptions and relationship types"},
            {"step": 3, "content": "Composite: FSEntry/File/Directory UML + Decorator: CartItem with wrapping"},
            {"step": 4, "content": "callout 'Composite=tree, Decorator=stack, Adapter=convert, Facade=simplify, Proxy=control'"},
            {"step": 5, "content": "Notification decorator exercise"},
        ],
        "difficulty_progression": "Start with Composite (file system). Then Decorator (cart item enhancements). Then Adapter (interface conversion). Then Facade (simplifying subsystems). Finally, Proxy (lazy loading, access control).",
        "check_questions": [
            "What's the difference between Adapter and Decorator?",
            "Why does the Composite pattern require a shared interface between leaf and composite?",
            "How do decorators stack? Can you have multiple decorators on one object?",
            "When would you use a Proxy instead of direct access?",
        ],
        "when_to_use": "Use Composite for tree structures. Decorator for adding behavior without subclassing. Adapter when integrating incompatible interfaces. Facade to simplify complex subsystems. Proxy for access control, caching, or lazy loading.",
        "related_topics": ["oop-principles", "solid-principles", "design-patterns-creational", "design-patterns-behavioral"],
    },

    "design-patterns-behavioral": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "Show a Vending Machine with a giant if/else: if state == IDLE and action == INSERT_COIN: ... elif state == HAS_MONEY and action == SELECT: ... 'This is unmaintainable. Adding a new state means editing 10 places.' The State pattern eliminates this."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "Key behavioral patterns: Observer (event notification), Strategy (interchangeable algorithms), State (behavior changes with state), Command (request as object, enables undo). These control how objects communicate and distribute responsibility."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Vending Machine with State pattern: IdleState, HasMoneyState, DispensingState. Each state implements handleInsertCoin(), handleSelectProduct(), handleDispense(). The machine delegates to its current state object. Adding a new state = adding a new class, no existing code changes."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "When to use each: Strategy — varying algorithms (pricing, sorting, compression). State — object behavior depends on internal state (vending machine, elevator, order status). Observer — decoupled event notification (booking confirmed -> email + analytics). Command — undo/redo, macro commands."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Design an Elevator System using behavioral patterns: State (idle, moving up, moving down, door open). Strategy (dispatch algorithm: nearest car, SCAN, LOOK). Observer (floor display updates when elevator arrives). Command (button press)."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Behavioral patterns manage object interaction. State eliminates state-dependent if/else. Strategy makes algorithms pluggable. Observer decouples event producers from consumers. Command encapsulates actions for undo/redo. Use these to score well in LLD interviews."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'Behavioral Patterns' + text showing giant if/else state machine"},
            {"step": 2, "content": "Four key patterns: Observer, Strategy, State, Command — with one-line descriptions"},
            {"step": 3, "content": "Vending Machine State pattern: state diagram + class diagram showing delegation"},
            {"step": 4, "content": "callout 'Strategy=algorithm, State=behavior, Observer=events, Command=undo'"},
            {"step": 5, "content": "Elevator System exercise: combine State + Strategy + Observer + Command"},
        ],
        "difficulty_progression": "Start with Strategy (simplest, just interchangeable algorithms). Then State (object behavior changes). Then Observer (event notification). Finally, Command (undo/redo capability).",
        "check_questions": [
            "What's the difference between Strategy and State patterns?",
            "How does Observer prevent tight coupling between event producers and consumers?",
            "How does the Command pattern enable undo/redo?",
            "When should you use State instead of if/else on a state variable?",
        ],
        "when_to_use": "Use Strategy when algorithms need to be interchangeable. State when object behavior depends on its state. Observer for event-driven communication. Command for undo/redo and action queuing. Name the pattern explicitly in LLD interviews.",
        "related_topics": ["oop-principles", "solid-principles", "design-patterns-creational", "design-patterns-structural"],
    },

    "uml-class-diagrams": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "In an LLD interview, you have 40 minutes. You can't start coding immediately — you need to communicate your design first. A class diagram takes 5 minutes and prevents 20 minutes of wrong-direction coding. It's the most important 5 minutes."},
            {"step": 2, "title": "Core Concept", "duration_min": 5,
             "instructions": "UML class diagram elements: class box (name, attributes, methods), visibility (+public, -private, #protected), relationships (association, aggregation, composition, inheritance, realization), multiplicity (1, 0..1, 0..*, 1..*), stereotypes (<<interface>>, <<abstract>>)."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Draw the Parking Lot class diagram: ParkingLot --* ParkingFloor --* ParkingSpot (composition). Vehicle <|-- Car, Truck (inheritance). PricingStrategy <|.. HourlyPricing (realization). ParkingLot --> PricingStrategy (association). Show multiplicity at each relationship."},
            {"step": 4, "title": "Pattern Recognition", "duration_min": 3,
             "instructions": "Relationship decision tree: 'dies with the whole?' -> composition (filled diamond). 'Exists independently?' -> aggregation (empty diamond). 'is-a?' -> inheritance (triangle). 'implements?' -> realization (dashed triangle). 'uses temporarily?' -> dependency (dashed arrow)."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Draw the class diagram for a Library Management System from scratch: Book, BookItem, Member, Librarian, Library, Loan, Fine. Show all relationships with correct arrow types and multiplicity."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: Draw a class diagram BEFORE coding in every LLD interview. Focus on entities, relationships, and interfaces. Use composition for strong ownership, aggregation for weak. Show multiplicity. This diagram guides your implementation."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'UML Class Diagrams' + text 'The most important 5 minutes of your LLD interview'"},
            {"step": 2, "content": "UML notation reference: class box, visibility symbols, relationship arrows"},
            {"step": 3, "content": "Complete Parking Lot class diagram with all relationship types and multiplicity"},
            {"step": 4, "content": "callout 'Relationship decision tree: composition vs aggregation vs inheritance vs realization'"},
            {"step": 5, "content": "Library Management System class diagram exercise"},
        ],
        "difficulty_progression": "Start with class boxes (name, attributes, methods). Then relationships (association, inheritance). Then composition vs aggregation. Then multiplicity. Finally, draw complete diagrams under time pressure.",
        "check_questions": [
            "What's the difference between composition and aggregation?",
            "Which direction does the inheritance arrow point?",
            "What does multiplicity '0..*' mean?",
            "When would you use a dashed arrow (dependency) vs a solid arrow (association)?",
        ],
        "when_to_use": "Draw a class diagram at the start of every LLD interview. It takes 5 minutes and communicates your design clearly. Focus on: entities, their responsibilities, relationships, and interfaces. The diagram guides your code.",
        "related_topics": ["oop-principles", "solid-principles", "lld-framework"],
    },

    "lld-framework": {
        "teaching_flow": [
            {"step": 1, "title": "Hook", "duration_min": 2,
             "instructions": "LLD interviews are 45 minutes. Most candidates jump to code and run out of time with a half-finished mess. 'What if you had a 7-step framework that structures your entire interview?' The framework ensures you hit every point interviewers look for."},
            {"step": 2, "title": "The Framework", "duration_min": 5,
             "instructions": "7 steps: (1) Requirements (5 min), (2) Entities (3 min), (3) Relationships + class diagram (5 min), (4) Responsibilities / SRP (2 min), (5) Design patterns (3 min), (6) API design (2 min), (7) Implementation (20 min) + edge cases (5 min)."},
            {"step": 3, "title": "Worked Example", "duration_min": 5,
             "instructions": "Apply the framework to Parking Lot: (1) Requirements: multi-floor, vehicle types, pricing. (2) Entities: ParkingLot, Floor, Spot, Vehicle, Ticket, PricingStrategy. (3) Relationships: UML diagram. (4) SRP: separate parking from pricing from notification. (5) Patterns: Strategy, Factory, Singleton. (6) API: park(), unpark(). (7) Code the core classes."},
            {"step": 4, "title": "Time Management", "duration_min": 3,
             "instructions": "Budget strictly: 5 min requirements, 5 min design, 25 min code, 5 min edge cases. Don't spend 20 min on requirements. Don't try to code everything — implement the core flow, mention extensions. Communicate constantly."},
            {"step": 5, "title": "Practice", "duration_min": 8,
             "instructions": "Run through the framework for an Elevator System: requirements (floors, elevators, dispatch), entities (Elevator, Floor, Button, Request, Scheduler), relationships, patterns (State, Strategy, Observer), API, then code the core dispatch logic."},
            {"step": 6, "title": "Wrap-up", "duration_min": 2,
             "instructions": "Summarize: The framework structures your interview. Requirements -> Entities -> Relationships -> Responsibilities -> Patterns -> API -> Code. Draw the class diagram before coding. Name patterns explicitly. Communicate trade-offs. This framework works for any LLD problem."},
        ],
        "board_plan": [
            {"step": 1, "content": "h1 'LLD Framework' + text 'Jump to code = run out of time. Framework = structure.'"},
            {"step": 2, "content": "7-step flow diagram with time budgets: Requirements(5) -> Entities(3) -> Diagram(5) -> SRP(2) -> Patterns(3) -> API(2) -> Code(20) -> Edge(5)"},
            {"step": 3, "content": "Parking Lot: each step filled in with concrete content"},
            {"step": 4, "content": "callout 'Communicate constantly. Implement core flow. Mention extensions.'"},
            {"step": 5, "content": "Elevator System framework walkthrough exercise"},
        ],
        "difficulty_progression": "Start by memorizing the 7 steps. Then practice on simple problems (Parking Lot). Then medium problems (Hotel Booking). Then hard problems (Elevator, Chess) under time constraints. The goal: framework becomes second nature.",
        "check_questions": [
            "What are the 7 steps of the LLD framework?",
            "How much time should you spend on requirements vs coding?",
            "Why should you draw a class diagram before coding?",
            "What design patterns should you look for in step 5?",
        ],
        "when_to_use": "Use this framework for every LLD interview. It ensures you cover requirements, design, patterns, and code systematically. The framework prevents the two most common failures: jumping to code too early, and spending too long on design without coding.",
        "related_topics": ["oop-principles", "solid-principles", "uml-class-diagrams", "design-patterns-creational", "design-patterns-structural", "design-patterns-behavioral"],
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# MAIN SCRIPT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Enrich teaching plans in MongoDB with pedagogical content"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be updated without writing to DB"
    )
    parser.add_argument(
        "--uri", type=str, default=None,
        help="MongoDB URI override"
    )
    args = parser.parse_args()

    uri = args.uri or os.environ.get("MONGODB_URI", "")
    if not uri:
        print("ERROR: MONGODB_URI not set. Load backend/.env or set the env var.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Connect
    # ------------------------------------------------------------------
    if not args.dry_run:
        import certifi
        from pymongo import MongoClient
        client = MongoClient(uri, tlsCAFile=certifi.where())
        db = client["tutor_v2"]
        collection = db["teaching_plans"]
    else:
        collection = None

    # ------------------------------------------------------------------
    # Read all existing plans
    # ------------------------------------------------------------------
    if not args.dry_run:
        existing = list(collection.find({}, {"slug": 1, "_id": 0}))
        existing_slugs = {doc["slug"] for doc in existing}
        print(f"Found {len(existing_slugs)} existing teaching plans in tutor_v2.teaching_plans")
    else:
        existing_slugs = set(ENRICHMENTS.keys())
        print(f"[DRY RUN] Enrichment data prepared for {len(ENRICHMENTS)} slugs")

    # ------------------------------------------------------------------
    # Enrich
    # ------------------------------------------------------------------
    enriched = 0
    skipped_no_plan = 0
    skipped_no_data = 0
    already_enriched = 0

    enrichment_fields = [
        "teaching_flow", "board_plan", "difficulty_progression",
        "check_questions", "when_to_use", "related_topics",
    ]

    for slug in sorted(ENRICHMENTS.keys()):
        data = ENRICHMENTS[slug]

        if slug not in existing_slugs:
            skipped_no_plan += 1
            print(f"  [SKIP] {slug:<40s}  (no matching plan in DB)")
            continue

        if args.dry_run:
            enriched += 1
            print(f"  [DRY]  {slug:<40s}  would add {len(enrichment_fields)} fields")
            continue

        # Check if already enriched (has teaching_flow)
        existing_doc = collection.find_one(
            {"slug": slug},
            {"teaching_flow": 1, "_id": 0}
        )
        if existing_doc and existing_doc.get("teaching_flow"):
            already_enriched += 1
            # Still update to ensure latest content
            pass

        # Build the $set payload — only new fields
        set_payload = {}
        for field in enrichment_fields:
            if field in data:
                set_payload[field] = data[field]

        if not set_payload:
            skipped_no_data += 1
            print(f"  [SKIP] {slug:<40s}  (no enrichment data)")
            continue

        result = collection.update_one(
            {"slug": slug},
            {"$set": set_payload},
        )

        if result.modified_count > 0:
            enriched += 1
            status = "ENRICH" if not (existing_doc and existing_doc.get("teaching_flow")) else "UPDATE"
            print(f"  [{status}] {slug:<40s}  +{len(set_payload)} fields")
        else:
            already_enriched += 1
            print(f"  [SAME] {slug:<40s}  (already up to date)")

    # ------------------------------------------------------------------
    # Also handle plans that exist in DB but have no enrichment data
    # ------------------------------------------------------------------
    if not args.dry_run:
        plans_without_enrichment = existing_slugs - set(ENRICHMENTS.keys())
        if plans_without_enrichment:
            print(f"\n  Plans in DB without enrichment data ({len(plans_without_enrichment)}):")
            for slug in sorted(plans_without_enrichment):
                print(f"    - {slug}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print(f"  Enriched:          {enriched}")
    print(f"  Already up-to-date:{already_enriched}")
    print(f"  Skipped (no plan): {skipped_no_plan}")
    print(f"  Skipped (no data): {skipped_no_data}")
    print(f"  Total enrichments: {len(ENRICHMENTS)}")
    print("=" * 60)

    if not args.dry_run:
        total = collection.count_documents({})
        print(f"  Total documents in tutor_v2.teaching_plans: {total}")

    print("\nDone!")


if __name__ == "__main__":
    main()
