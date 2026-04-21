#!/usr/bin/env python3
"""
Seed script for DSA and System Design problem collections.
Populates MongoDB with all 150 NeetCode problems and 15 system design problems.

Usage:
    python -m byo.scripts.seed_dsa_problems [--drop]
"""

import argparse
import os
import sys

# Load env
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root, "backend", ".env"), override=False)
except ImportError:
    pass

from pymongo import MongoClient, ASCENDING
from pymongo.errors import BulkWriteError


# ---------------------------------------------------------------------------
# 1. Arrays & Hashing (9 problems)
# ---------------------------------------------------------------------------
ARRAYS_HASHING = [
    {
        "num": 1,
        "name": "Two Sum",
        "slug": "two-sum",
        "difficulty": "easy",
        "topics": ["arrays", "hash_map"],
        "pattern": "hash_map_lookup",
        "companies": ["google", "amazon", "meta"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 52,
        "description": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
        "examples": [
            {"input": "nums = [2,7,11,15], target = 9", "output": "[0,1]", "explanation": "nums[0] + nums[1] = 9"}
        ],
        "constraints": ["2 <= nums.length <= 10^4", "-10^9 <= nums[i] <= 10^9", "Only one valid answer exists"],
        "starter_code": {
            "python": "class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\n        pass",
            "javascript": "var twoSum = function(nums, target) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums": [2, 7, 11, 15], "target": 9}, "expected": [0, 1]},
            {"input": {"nums": [3, 2, 4], "target": 6}, "expected": [1, 2]},
            {"input": {"nums": [3, 3], "target": 6}, "expected": [0, 1]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Try using a hash map to store seen values", "What is the complement of the current number?"]
    },
    {
        "num": 2,
        "name": "Contains Duplicate",
        "slug": "contains-duplicate",
        "difficulty": "easy",
        "topics": ["arrays", "hash_map"],
        "pattern": "hash_set",
        "companies": ["amazon", "apple", "adobe"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 61,
        "description": "Given an integer array nums, return true if any value appears at least twice in the array, and return false if every element is distinct.",
        "examples": [
            {"input": "nums = [1,2,3,1]", "output": "true", "explanation": "1 appears twice"},
            {"input": "nums = [1,2,3,4]", "output": "false", "explanation": "All elements are distinct"}
        ],
        "constraints": ["1 <= nums.length <= 10^5", "-10^9 <= nums[i] <= 10^9"],
        "starter_code": {
            "python": "class Solution:\n    def containsDuplicate(self, nums: List[int]) -> bool:\n        pass",
            "javascript": "var containsDuplicate = function(nums) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums": [1, 2, 3, 1]}, "expected": True},
            {"input": {"nums": [1, 2, 3, 4]}, "expected": False},
            {"input": {"nums": [1, 1, 1, 3, 3, 4, 3, 2, 4, 2]}, "expected": True}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Use a set to track seen numbers", "Compare set size with array length"]
    },
    {
        "num": 3,
        "name": "Valid Anagram",
        "slug": "valid-anagram",
        "difficulty": "easy",
        "topics": ["arrays", "hash_map", "sorting"],
        "pattern": "frequency_count",
        "companies": ["amazon", "microsoft", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 63,
        "description": "Given two strings s and t, return true if t is an anagram of s, and false otherwise.",
        "examples": [
            {"input": 's = "anagram", t = "nagaram"', "output": "true", "explanation": "Both strings have the same character frequencies"},
            {"input": 's = "rat", t = "car"', "output": "false", "explanation": "Different character frequencies"}
        ],
        "constraints": ["1 <= s.length, t.length <= 5 * 10^4", "s and t consist of lowercase English letters"],
        "starter_code": {
            "python": "class Solution:\n    def isAnagram(self, s: str, t: str) -> bool:\n        pass",
            "javascript": "var isAnagram = function(s, t) {\n    \n};"
        },
        "test_cases": [
            {"input": {"s": "anagram", "t": "nagaram"}, "expected": True},
            {"input": {"s": "rat", "t": "car"}, "expected": False},
            {"input": {"s": "a", "t": "a"}, "expected": True}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Count character frequencies in both strings", "If lengths differ, they can't be anagrams"]
    },
    {
        "num": 4,
        "name": "Group Anagrams",
        "slug": "group-anagrams",
        "difficulty": "medium",
        "topics": ["arrays", "hash_map", "sorting"],
        "pattern": "hash_map_grouping",
        "companies": ["amazon", "meta", "bloomberg"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 67,
        "description": "Given an array of strings strs, group the anagrams together. You can return the answer in any order.",
        "examples": [
            {"input": 'strs = ["eat","tea","tan","ate","nat","bat"]', "output": '[["bat"],["nat","tan"],["ate","eat","tea"]]', "explanation": "Anagrams are grouped together"}
        ],
        "constraints": ["1 <= strs.length <= 10^4", "0 <= strs[i].length <= 100", "strs[i] consists of lowercase English letters"],
        "starter_code": {
            "python": "class Solution:\n    def groupAnagrams(self, strs: List[str]) -> List[List[str]]:\n        pass",
            "javascript": "var groupAnagrams = function(strs) {\n    \n};"
        },
        "test_cases": [
            {"input": {"strs": ["eat", "tea", "tan", "ate", "nat", "bat"]}, "expected": [["eat", "tea", "ate"], ["tan", "nat"], ["bat"]]},
            {"input": {"strs": [""]}, "expected": [[""]]},
            {"input": {"strs": ["a"]}, "expected": [["a"]]}
        ],
        "optimal_complexity": {"time": "O(n * k)", "space": "O(n * k)"},
        "hints": ["Use sorted string or character count tuple as hash key", "defaultdict(list) is your friend"]
    },
    {
        "num": 5,
        "name": "Top K Frequent Elements",
        "slug": "top-k-frequent-elements",
        "difficulty": "medium",
        "topics": ["arrays", "hash_map", "heap"],
        "pattern": "frequency_count",
        "companies": ["amazon", "meta", "oracle"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 65,
        "description": "Given an integer array nums and an integer k, return the k most frequent elements. You may return the answer in any order.",
        "examples": [
            {"input": "nums = [1,1,1,2,2,3], k = 2", "output": "[1,2]", "explanation": "1 appears 3 times, 2 appears 2 times"}
        ],
        "constraints": ["1 <= nums.length <= 10^5", "-10^4 <= nums[i] <= 10^4", "k is in range [1, number of unique elements]", "Answer is guaranteed to be unique"],
        "starter_code": {
            "python": "class Solution:\n    def topKFrequent(self, nums: List[int], k: int) -> List[int]:\n        pass",
            "javascript": "var topKFrequent = function(nums, k) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums": [1, 1, 1, 2, 2, 3], "k": 2}, "expected": [1, 2]},
            {"input": {"nums": [1], "k": 1}, "expected": [1]},
            {"input": {"nums": [4, 4, 4, 1, 1, 2, 2, 2], "k": 2}, "expected": [4, 2]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Bucket sort by frequency avoids O(n log n)", "Count frequencies first, then use bucket index = frequency"]
    },
    {
        "num": 6,
        "name": "Encode and Decode Strings",
        "slug": "encode-and-decode-strings",
        "difficulty": "medium",
        "topics": ["arrays", "string"],
        "pattern": "string_encoding",
        "companies": ["google", "meta", "apple"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 45,
        "description": "Design an algorithm to encode a list of strings to a single string. The encoded string is then decoded back to the original list of strings.",
        "examples": [
            {"input": 'strs = ["lint","code","love","you"]', "output": '["lint","code","love","you"]', "explanation": "Encode then decode returns the original list"}
        ],
        "constraints": ["0 <= strs.length <= 200", "0 <= strs[i].length <= 200", "strs[i] contains any possible characters including special characters"],
        "starter_code": {
            "python": "class Codec:\n    def encode(self, strs: List[str]) -> str:\n        pass\n    def decode(self, s: str) -> List[str]:\n        pass",
            "javascript": "var encode = function(strs) {\n    \n};\nvar decode = function(s) {\n    \n};"
        },
        "test_cases": [
            {"input": {"strs": ["lint", "code", "love", "you"]}, "expected": ["lint", "code", "love", "you"]},
            {"input": {"strs": ["we", "say", ":", "yes"]}, "expected": ["we", "say", ":", "yes"]},
            {"input": {"strs": []}, "expected": []}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Prefix each string with its length and a delimiter", "Use length#string format to avoid delimiter conflicts"]
    },
    {
        "num": 7,
        "name": "Product of Array Except Self",
        "slug": "product-of-array-except-self",
        "difficulty": "medium",
        "topics": ["arrays"],
        "pattern": "prefix_suffix",
        "companies": ["amazon", "meta", "apple"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 65,
        "description": "Given an integer array nums, return an array answer such that answer[i] is equal to the product of all the elements of nums except nums[i]. You must write an algorithm that runs in O(n) time and without using the division operation.",
        "examples": [
            {"input": "nums = [1,2,3,4]", "output": "[24,12,8,6]", "explanation": "For each index, multiply all other elements"}
        ],
        "constraints": ["2 <= nums.length <= 10^5", "-30 <= nums[i] <= 30", "The product of any prefix or suffix is guaranteed to fit in a 32-bit integer"],
        "starter_code": {
            "python": "class Solution:\n    def productExceptSelf(self, nums: List[int]) -> List[int]:\n        pass",
            "javascript": "var productExceptSelf = function(nums) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums": [1, 2, 3, 4]}, "expected": [24, 12, 8, 6]},
            {"input": {"nums": [-1, 1, 0, -3, 3]}, "expected": [0, 0, 9, 0, 0]},
            {"input": {"nums": [2, 3]}, "expected": [3, 2]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Build prefix products left to right, then suffix products right to left", "You can use the output array to store prefix products to achieve O(1) extra space"]
    },
    {
        "num": 8,
        "name": "Valid Sudoku",
        "slug": "valid-sudoku",
        "difficulty": "medium",
        "topics": ["arrays", "hash_map"],
        "pattern": "hash_set_validation",
        "companies": ["amazon", "uber", "apple"],
        "lists": ["neetcode_150"],
        "acceptance": 58,
        "description": "Determine if a 9x9 Sudoku board is valid. Only the filled cells need to be validated according to the rules: each row, column, and 3x3 sub-box must contain the digits 1-9 without repetition.",
        "examples": [
            {"input": "board = [[\"5\",\"3\",\".\",\".\",\"7\",...],...]", "output": "true", "explanation": "The board is valid according to Sudoku rules"}
        ],
        "constraints": ["board.length == 9", "board[i].length == 9", "board[i][j] is a digit 1-9 or '.'"],
        "starter_code": {
            "python": "class Solution:\n    def isValidSudoku(self, board: List[List[str]]) -> bool:\n        pass",
            "javascript": "var isValidSudoku = function(board) {\n    \n};"
        },
        "test_cases": [
            {"input": {"board": [["5","3",".",".","7",".",".",".","."],["6",".",".","1","9","5",".",".","."],[".","9","8",".",".",".",".","6","."],["8",".",".",".","6",".",".",".","3"],["4",".",".","8",".","3",".",".","1"],["7",".",".",".","2",".",".",".","6"],[".","6",".",".",".",".","2","8","."],[".",".",".","4","1","9",".",".","5"],[".",".",".",".","8",".",".","7","9"]]}, "expected": True},
            {"input": {"board": [["8","3",".",".","7",".",".",".","."],["6",".",".","1","9","5",".",".","."],[".","9","8",".",".",".",".","6","."],["8",".",".",".","6",".",".",".","3"],["4",".",".","8",".","3",".",".","1"],["7",".",".",".","2",".",".",".","6"],[".","6",".",".",".",".","2","8","."],[".",".",".","4","1","9",".",".","5"],[".",".",".",".","8",".",".","7","9"]]}, "expected": False},
            {"input": {"board": [[".",".",".",".",".",".",".",".","."],[".",".",".",".",".",".",".",".","."],[".",".",".",".",".",".",".",".","."],[".",".",".",".",".",".",".",".","."],[".",".",".",".",".",".",".",".","."],[".",".",".",".",".",".",".",".","."],[".",".",".",".",".",".",".",".","."],[".",".",".",".",".",".",".",".","."],[".",".",".",".",".",".",".",".","."]]}, "expected": True}
        ],
        "optimal_complexity": {"time": "O(1)", "space": "O(1)"},
        "hints": ["Use sets for each row, column, and 3x3 box", "Box index can be computed as (row//3, col//3)"]
    },
    {
        "num": 9,
        "name": "Longest Consecutive Sequence",
        "slug": "longest-consecutive-sequence",
        "difficulty": "medium",
        "topics": ["arrays", "hash_map"],
        "pattern": "hash_set",
        "companies": ["google", "amazon", "meta"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 47,
        "description": "Given an unsorted array of integers nums, return the length of the longest consecutive elements sequence. You must write an algorithm that runs in O(n) time.",
        "examples": [
            {"input": "nums = [100,4,200,1,3,2]", "output": "4", "explanation": "The longest consecutive sequence is [1,2,3,4]"}
        ],
        "constraints": ["0 <= nums.length <= 10^5", "-10^9 <= nums[i] <= 10^9"],
        "starter_code": {
            "python": "class Solution:\n    def longestConsecutive(self, nums: List[int]) -> int:\n        pass",
            "javascript": "var longestConsecutive = function(nums) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums": [100, 4, 200, 1, 3, 2]}, "expected": 4},
            {"input": {"nums": [0, 3, 7, 2, 5, 8, 4, 6, 0, 1]}, "expected": 9},
            {"input": {"nums": []}, "expected": 0}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Put all numbers in a set, then find sequence starts (no num-1 in set)", "Only start counting from sequence beginnings to maintain O(n)"]
    },
]

# ---------------------------------------------------------------------------
# 2. Two Pointers (5 problems)
# ---------------------------------------------------------------------------
TWO_POINTERS = [
    {
        "num": 10,
        "name": "Valid Palindrome",
        "slug": "valid-palindrome",
        "difficulty": "easy",
        "topics": ["two_pointers", "string"],
        "pattern": "two_pointer_inward",
        "companies": ["meta", "microsoft", "amazon"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 44,
        "description": "A phrase is a palindrome if, after converting all uppercase letters into lowercase letters and removing all non-alphanumeric characters, it reads the same forward and backward. Given a string s, return true if it is a palindrome, or false otherwise.",
        "examples": [
            {"input": 's = "A man, a plan, a canal: Panama"', "output": "true", "explanation": "After filtering: 'amanaplanacanalpanama' is a palindrome"}
        ],
        "constraints": ["1 <= s.length <= 2 * 10^5", "s consists only of printable ASCII characters"],
        "starter_code": {
            "python": "class Solution:\n    def isPalindrome(self, s: str) -> bool:\n        pass",
            "javascript": "var isPalindrome = function(s) {\n    \n};"
        },
        "test_cases": [
            {"input": {"s": "A man, a plan, a canal: Panama"}, "expected": True},
            {"input": {"s": "race a car"}, "expected": False},
            {"input": {"s": " "}, "expected": True}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Use two pointers from both ends, skip non-alphanumeric", "Compare lowercase versions of characters"]
    },
    {
        "num": 11,
        "name": "Two Sum II - Input Array Is Sorted",
        "slug": "two-sum-ii-input-array-is-sorted",
        "difficulty": "medium",
        "topics": ["two_pointers", "arrays"],
        "pattern": "two_pointer_inward",
        "companies": ["amazon", "meta", "bloomberg"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 60,
        "description": "Given a 1-indexed array of integers numbers that is already sorted in non-decreasing order, find two numbers such that they add up to a specific target number. Return the indices of the two numbers (1-indexed) as an array [index1, index2].",
        "examples": [
            {"input": "numbers = [2,7,11,15], target = 9", "output": "[1,2]", "explanation": "2 + 7 = 9, indices are 1 and 2"}
        ],
        "constraints": ["2 <= numbers.length <= 3 * 10^4", "-1000 <= numbers[i] <= 1000", "numbers is sorted in non-decreasing order", "Exactly one solution exists"],
        "starter_code": {
            "python": "class Solution:\n    def twoSum(self, numbers: List[int], target: int) -> List[int]:\n        pass",
            "javascript": "var twoSum = function(numbers, target) {\n    \n};"
        },
        "test_cases": [
            {"input": {"numbers": [2, 7, 11, 15], "target": 9}, "expected": [1, 2]},
            {"input": {"numbers": [2, 3, 4], "target": 6}, "expected": [1, 3]},
            {"input": {"numbers": [-1, 0], "target": -1}, "expected": [1, 2]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Use two pointers at start and end", "If sum is too large, move right pointer left; if too small, move left pointer right"]
    },
    {
        "num": 12,
        "name": "3Sum",
        "slug": "3sum",
        "difficulty": "medium",
        "topics": ["two_pointers", "arrays", "sorting"],
        "pattern": "two_pointer_inward",
        "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 33,
        "description": "Given an integer array nums, return all the triplets [nums[i], nums[j], nums[k]] such that i != j, i != k, and j != k, and nums[i] + nums[j] + nums[k] == 0. The solution set must not contain duplicate triplets.",
        "examples": [
            {"input": "nums = [-1,0,1,2,-1,-4]", "output": "[[-1,-1,2],[-1,0,1]]", "explanation": "The distinct triplets that sum to zero"}
        ],
        "constraints": ["3 <= nums.length <= 3000", "-10^5 <= nums[i] <= 10^5"],
        "starter_code": {
            "python": "class Solution:\n    def threeSum(self, nums: List[int]) -> List[List[int]]:\n        pass",
            "javascript": "var threeSum = function(nums) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums": [-1, 0, 1, 2, -1, -4]}, "expected": [[-1, -1, 2], [-1, 0, 1]]},
            {"input": {"nums": [0, 1, 1]}, "expected": []},
            {"input": {"nums": [0, 0, 0]}, "expected": [[0, 0, 0]]}
        ],
        "optimal_complexity": {"time": "O(n^2)", "space": "O(1)"},
        "hints": ["Sort the array first, then fix one element and use two pointers for the rest", "Skip duplicates by checking if current == previous"]
    },
    {
        "num": 13,
        "name": "Container With Most Water",
        "slug": "container-with-most-water",
        "difficulty": "medium",
        "topics": ["two_pointers", "arrays"],
        "pattern": "two_pointer_inward",
        "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 54,
        "description": "You are given an integer array height of length n. There are n vertical lines drawn such that the two endpoints of the ith line are (i, 0) and (i, height[i]). Find two lines that together with the x-axis form a container that holds the most water. Return the maximum amount of water a container can store.",
        "examples": [
            {"input": "height = [1,8,6,2,5,4,8,3,7]", "output": "49", "explanation": "Lines at index 1 and 8 form the container with most water: min(8,7) * (8-1) = 49"}
        ],
        "constraints": ["n == height.length", "2 <= n <= 10^5", "0 <= height[i] <= 10^4"],
        "starter_code": {
            "python": "class Solution:\n    def maxArea(self, height: List[int]) -> int:\n        pass",
            "javascript": "var maxArea = function(height) {\n    \n};"
        },
        "test_cases": [
            {"input": {"height": [1, 8, 6, 2, 5, 4, 8, 3, 7]}, "expected": 49},
            {"input": {"height": [1, 1]}, "expected": 1},
            {"input": {"height": [4, 3, 2, 1, 4]}, "expected": 16}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Start with widest container (two pointers at ends)", "Move the shorter line inward since it limits the height"]
    },
    {
        "num": 14,
        "name": "Trapping Rain Water",
        "slug": "trapping-rain-water",
        "difficulty": "hard",
        "topics": ["two_pointers", "arrays", "stack"],
        "pattern": "two_pointer_inward",
        "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 59,
        "description": "Given n non-negative integers representing an elevation map where the width of each bar is 1, compute how much water it can trap after raining.",
        "examples": [
            {"input": "height = [0,1,0,2,1,0,1,3,2,1,2,1]", "output": "6", "explanation": "6 units of rain water are trapped"}
        ],
        "constraints": ["n == height.length", "1 <= n <= 2 * 10^4", "0 <= height[i] <= 10^5"],
        "starter_code": {
            "python": "class Solution:\n    def trap(self, height: List[int]) -> int:\n        pass",
            "javascript": "var trap = function(height) {\n    \n};"
        },
        "test_cases": [
            {"input": {"height": [0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1]}, "expected": 6},
            {"input": {"height": [4, 2, 0, 3, 2, 5]}, "expected": 9},
            {"input": {"height": [4, 2, 3]}, "expected": 1}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Water at each position = min(maxLeft, maxRight) - height", "Two pointer approach tracks maxLeft and maxRight from both ends"]
    },
]

# ---------------------------------------------------------------------------
# 3. Sliding Window (6 problems)
# ---------------------------------------------------------------------------
SLIDING_WINDOW = [
    {
        "num": 15,
        "name": "Best Time to Buy and Sell Stock",
        "slug": "best-time-to-buy-and-sell-stock",
        "difficulty": "easy",
        "topics": ["sliding_window", "arrays"],
        "pattern": "sliding_window",
        "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 54,
        "description": "You are given an array prices where prices[i] is the price of a given stock on the ith day. You want to maximize your profit by choosing a single day to buy one stock and choosing a different day in the future to sell that stock. Return the maximum profit you can achieve. If no profit is possible, return 0.",
        "examples": [
            {"input": "prices = [7,1,5,3,6,4]", "output": "5", "explanation": "Buy on day 2 (price=1) and sell on day 5 (price=6), profit = 5"}
        ],
        "constraints": ["1 <= prices.length <= 10^5", "0 <= prices[i] <= 10^4"],
        "starter_code": {
            "python": "class Solution:\n    def maxProfit(self, prices: List[int]) -> int:\n        pass",
            "javascript": "var maxProfit = function(prices) {\n    \n};"
        },
        "test_cases": [
            {"input": {"prices": [7, 1, 5, 3, 6, 4]}, "expected": 5},
            {"input": {"prices": [7, 6, 4, 3, 1]}, "expected": 0},
            {"input": {"prices": [2, 4, 1]}, "expected": 2}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Track the minimum price seen so far", "At each step, compute profit if selling today"]
    },
    {
        "num": 16,
        "name": "Longest Substring Without Repeating Characters",
        "slug": "longest-substring-without-repeating-characters",
        "difficulty": "medium",
        "topics": ["sliding_window", "hash_map", "string"],
        "pattern": "sliding_window_variable",
        "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 34,
        "description": "Given a string s, find the length of the longest substring without repeating characters.",
        "examples": [
            {"input": 's = "abcabcbb"', "output": "3", "explanation": "The answer is 'abc', with length 3"}
        ],
        "constraints": ["0 <= s.length <= 5 * 10^4", "s consists of English letters, digits, symbols and spaces"],
        "starter_code": {
            "python": "class Solution:\n    def lengthOfLongestSubstring(self, s: str) -> int:\n        pass",
            "javascript": "var lengthOfLongestSubstring = function(s) {\n    \n};"
        },
        "test_cases": [
            {"input": {"s": "abcabcbb"}, "expected": 3},
            {"input": {"s": "bbbbb"}, "expected": 1},
            {"input": {"s": "pwwkew"}, "expected": 3}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(min(m,n))"},
        "hints": ["Use a sliding window with a set to track characters", "When a duplicate is found, shrink the window from the left"]
    },
    {
        "num": 17,
        "name": "Longest Repeating Character Replacement",
        "slug": "longest-repeating-character-replacement",
        "difficulty": "medium",
        "topics": ["sliding_window", "string"],
        "pattern": "sliding_window_variable",
        "companies": ["google", "amazon", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 52,
        "description": "You are given a string s and an integer k. You can choose any character of the string and change it to any other uppercase English character. You can perform this operation at most k times. Return the length of the longest substring containing the same letter you can get after performing the above operations.",
        "examples": [
            {"input": 's = "ABAB", k = 2', "output": "4", "explanation": "Replace the two A's with B's or vice versa"}
        ],
        "constraints": ["1 <= s.length <= 10^5", "s consists of only uppercase English letters", "0 <= k <= s.length"],
        "starter_code": {
            "python": "class Solution:\n    def characterReplacement(self, s: str, k: int) -> int:\n        pass",
            "javascript": "var characterReplacement = function(s, k) {\n    \n};"
        },
        "test_cases": [
            {"input": {"s": "ABAB", "k": 2}, "expected": 4},
            {"input": {"s": "AABABBA", "k": 1}, "expected": 4},
            {"input": {"s": "AAAA", "k": 0}, "expected": 4}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Window is valid when windowLen - maxFreq <= k", "Track the max frequency character count in the window"]
    },
    {
        "num": 18,
        "name": "Permutation in String",
        "slug": "permutation-in-string",
        "difficulty": "medium",
        "topics": ["sliding_window", "hash_map", "string"],
        "pattern": "sliding_window_fixed",
        "companies": ["microsoft", "amazon", "google"],
        "lists": ["neetcode_150"],
        "acceptance": 44,
        "description": "Given two strings s1 and s2, return true if s2 contains a permutation of s1, or false otherwise. In other words, return true if one of s1's permutations is the substring of s2.",
        "examples": [
            {"input": 's1 = "ab", s2 = "eidbaooo"', "output": "true", "explanation": "s2 contains 'ba' which is a permutation of 'ab'"}
        ],
        "constraints": ["1 <= s1.length, s2.length <= 10^4", "s1 and s2 consist of lowercase English letters"],
        "starter_code": {
            "python": "class Solution:\n    def checkInclusion(self, s1: str, s2: str) -> bool:\n        pass",
            "javascript": "var checkInclusion = function(s1, s2) {\n    \n};"
        },
        "test_cases": [
            {"input": {"s1": "ab", "s2": "eidbaooo"}, "expected": True},
            {"input": {"s1": "ab", "s2": "eidboaoo"}, "expected": False},
            {"input": {"s1": "adc", "s2": "dcda"}, "expected": True}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Use a fixed-size sliding window of length s1", "Compare character frequency counts"]
    },
    {
        "num": 19,
        "name": "Minimum Window Substring",
        "slug": "minimum-window-substring",
        "difficulty": "hard",
        "topics": ["sliding_window", "hash_map", "string"],
        "pattern": "sliding_window_variable",
        "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 40,
        "description": "Given two strings s and t of lengths m and n respectively, return the minimum window substring of s such that every character in t (including duplicates) is included in the window. If there is no such substring, return the empty string.",
        "examples": [
            {"input": 's = "ADOBECODEBANC", t = "ABC"', "output": '"BANC"', "explanation": "The minimum window substring containing A, B, and C"}
        ],
        "constraints": ["m == s.length", "n == t.length", "1 <= m, n <= 10^5", "s and t consist of uppercase and lowercase English letters"],
        "starter_code": {
            "python": "class Solution:\n    def minWindow(self, s: str, t: str) -> str:\n        pass",
            "javascript": "var minWindow = function(s, t) {\n    \n};"
        },
        "test_cases": [
            {"input": {"s": "ADOBECODEBANC", "t": "ABC"}, "expected": "BANC"},
            {"input": {"s": "a", "t": "a"}, "expected": "a"},
            {"input": {"s": "a", "t": "aa"}, "expected": ""}
        ],
        "optimal_complexity": {"time": "O(m + n)", "space": "O(m + n)"},
        "hints": ["Expand right until window contains all chars of t, then shrink left", "Track how many required characters are satisfied with a 'formed' counter"]
    },
    {
        "num": 20,
        "name": "Sliding Window Maximum",
        "slug": "sliding-window-maximum",
        "difficulty": "hard",
        "topics": ["sliding_window", "deque"],
        "pattern": "monotonic_deque",
        "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150"],
        "acceptance": 46,
        "description": "You are given an array of integers nums and an integer k. There is a sliding window of size k which is moving from the very left to the very right. You can only see the k numbers in the window. Each time the sliding window moves right by one position, return the max of each window.",
        "examples": [
            {"input": "nums = [1,3,-1,-3,5,3,6,7], k = 3", "output": "[3,3,5,5,6,7]", "explanation": "Max of each window of size 3"}
        ],
        "constraints": ["1 <= nums.length <= 10^5", "-10^4 <= nums[i] <= 10^4", "1 <= k <= nums.length"],
        "starter_code": {
            "python": "class Solution:\n    def maxSlidingWindow(self, nums: List[int], k: int) -> List[int]:\n        pass",
            "javascript": "var maxSlidingWindow = function(nums, k) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums": [1, 3, -1, -3, 5, 3, 6, 7], "k": 3}, "expected": [3, 3, 5, 5, 6, 7]},
            {"input": {"nums": [1], "k": 1}, "expected": [1]},
            {"input": {"nums": [1, -1], "k": 1}, "expected": [1, -1]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(k)"},
        "hints": ["Use a monotonic decreasing deque", "Remove elements from back that are smaller than current, and front that are out of window"]
    },
]

# ---------------------------------------------------------------------------
# 4. Stack (7 problems)
# ---------------------------------------------------------------------------
STACK = [
    {
        "num": 21,
        "name": "Valid Parentheses",
        "slug": "valid-parentheses",
        "difficulty": "easy",
        "topics": ["stack", "string"],
        "pattern": "stack_matching",
        "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 41,
        "description": "Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid. An input string is valid if open brackets are closed by the same type of brackets in the correct order.",
        "examples": [
            {"input": 's = "()"', "output": "true", "explanation": "Single pair of matching parentheses"},
            {"input": 's = "()[]{}"', "output": "true", "explanation": "All brackets match correctly"}
        ],
        "constraints": ["1 <= s.length <= 10^4", "s consists of parentheses only '()[]{}'"],
        "starter_code": {
            "python": "class Solution:\n    def isValid(self, s: str) -> bool:\n        pass",
            "javascript": "var isValid = function(s) {\n    \n};"
        },
        "test_cases": [
            {"input": {"s": "()"}, "expected": True},
            {"input": {"s": "()[]{}"}, "expected": True},
            {"input": {"s": "(]"}, "expected": False}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Push opening brackets onto stack", "Pop and compare when encountering closing brackets"]
    },
    {
        "num": 22,
        "name": "Min Stack",
        "slug": "min-stack",
        "difficulty": "medium",
        "topics": ["stack", "design"],
        "pattern": "stack_auxiliary",
        "companies": ["amazon", "bloomberg", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 52,
        "description": "Design a stack that supports push, pop, top, and retrieving the minimum element in constant time.",
        "examples": [
            {"input": '["MinStack","push","push","push","getMin","pop","top","getMin"]\n[[],[-2],[0],[-3],[],[],[],[]]', "output": "[null,null,null,null,-3,null,0,-2]", "explanation": "Operations on the min stack"}
        ],
        "constraints": ["-2^31 <= val <= 2^31 - 1", "Methods pop, top and getMin operations will always be called on non-empty stacks", "At most 3 * 10^4 calls will be made"],
        "starter_code": {
            "python": "class MinStack:\n    def __init__(self):\n        pass\n    def push(self, val: int) -> None:\n        pass\n    def pop(self) -> None:\n        pass\n    def top(self) -> int:\n        pass\n    def getMin(self) -> int:\n        pass",
            "javascript": "var MinStack = function() {\n    \n};\nMinStack.prototype.push = function(val) {\n    \n};\nMinStack.prototype.pop = function() {\n    \n};\nMinStack.prototype.top = function() {\n    \n};\nMinStack.prototype.getMin = function() {\n    \n};"
        },
        "test_cases": [
            {"input": {"operations": ["MinStack","push","push","push","getMin","pop","top","getMin"], "values": [[],[-2],[0],[-3],[],[],[],[]]}, "expected": [None,None,None,None,-3,None,0,-2]},
            {"input": {"operations": ["MinStack","push","push","getMin"], "values": [[],[1],[2],[]]}, "expected": [None,None,None,1]},
            {"input": {"operations": ["MinStack","push","push","pop","getMin"], "values": [[],[0],[1],[],[]]}, "expected": [None,None,None,None,0]}
        ],
        "optimal_complexity": {"time": "O(1)", "space": "O(n)"},
        "hints": ["Use a second stack to track minimums at each level", "Each entry can store (value, current_min) pair"]
    },
    {
        "num": 23,
        "name": "Evaluate Reverse Polish Notation",
        "slug": "evaluate-reverse-polish-notation",
        "difficulty": "medium",
        "topics": ["stack"],
        "pattern": "stack_evaluation",
        "companies": ["amazon", "google", "linkedin"],
        "lists": ["neetcode_150"],
        "acceptance": 44,
        "description": "You are given an array of strings tokens that represents an arithmetic expression in Reverse Polish Notation. Evaluate the expression and return an integer that represents the value.",
        "examples": [
            {"input": 'tokens = ["2","1","+","3","*"]', "output": "9", "explanation": "((2 + 1) * 3) = 9"}
        ],
        "constraints": ["1 <= tokens.length <= 10^4", "tokens[i] is an operator or an integer in range [-200, 200]"],
        "starter_code": {
            "python": "class Solution:\n    def evalRPN(self, tokens: List[str]) -> int:\n        pass",
            "javascript": "var evalRPN = function(tokens) {\n    \n};"
        },
        "test_cases": [
            {"input": {"tokens": ["2", "1", "+", "3", "*"]}, "expected": 9},
            {"input": {"tokens": ["4", "13", "5", "/", "+"]}, "expected": 6},
            {"input": {"tokens": ["10", "6", "9", "3", "+", "-11", "*", "/", "*", "17", "+", "5", "+"]}, "expected": 22}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Push numbers onto stack; pop two when encountering an operator", "Be careful with integer division truncating toward zero"]
    },
    {
        "num": 24,
        "name": "Generate Parentheses",
        "slug": "generate-parentheses",
        "difficulty": "medium",
        "topics": ["stack", "backtracking", "string"],
        "pattern": "backtracking",
        "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 73,
        "description": "Given n pairs of parentheses, write a function to generate all combinations of well-formed parentheses.",
        "examples": [
            {"input": "n = 3", "output": '["((()))","(()())","(())()","()(())","()()()"]', "explanation": "All valid combinations of 3 pairs"}
        ],
        "constraints": ["1 <= n <= 8"],
        "starter_code": {
            "python": "class Solution:\n    def generateParenthesis(self, n: int) -> List[str]:\n        pass",
            "javascript": "var generateParenthesis = function(n) {\n    \n};"
        },
        "test_cases": [
            {"input": {"n": 3}, "expected": ["((()))", "(()())", "(())()", "()(())", "()()()"]},
            {"input": {"n": 1}, "expected": ["()"]},
            {"input": {"n": 2}, "expected": ["(())", "()()"]}
        ],
        "optimal_complexity": {"time": "O(4^n / sqrt(n))", "space": "O(n)"},
        "hints": ["Use backtracking with open and close counts", "Can add '(' if open < n, can add ')' if close < open"]
    },
    {
        "num": 25,
        "name": "Daily Temperatures",
        "slug": "daily-temperatures",
        "difficulty": "medium",
        "topics": ["stack", "arrays"],
        "pattern": "monotonic_stack",
        "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150"],
        "acceptance": 66,
        "description": "Given an array of integers temperatures represents the daily temperatures, return an array answer such that answer[i] is the number of days you have to wait after the ith day to get a warmer temperature. If there is no future day for which this is possible, keep answer[i] == 0.",
        "examples": [
            {"input": "temperatures = [73,74,75,71,69,72,76,73]", "output": "[1,1,4,2,1,1,0,0]", "explanation": "Days to wait for warmer temperature"}
        ],
        "constraints": ["1 <= temperatures.length <= 10^5", "30 <= temperatures[i] <= 100"],
        "starter_code": {
            "python": "class Solution:\n    def dailyTemperatures(self, temperatures: List[int]) -> List[int]:\n        pass",
            "javascript": "var dailyTemperatures = function(temperatures) {\n    \n};"
        },
        "test_cases": [
            {"input": {"temperatures": [73, 74, 75, 71, 69, 72, 76, 73]}, "expected": [1, 1, 4, 2, 1, 1, 0, 0]},
            {"input": {"temperatures": [30, 40, 50, 60]}, "expected": [1, 1, 1, 0]},
            {"input": {"temperatures": [30, 60, 90]}, "expected": [1, 1, 0]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Use a monotonic decreasing stack of indices", "When current temp > stack top, pop and compute the difference"]
    },
    {
        "num": 26,
        "name": "Car Fleet",
        "slug": "car-fleet",
        "difficulty": "medium",
        "topics": ["stack", "sorting"],
        "pattern": "monotonic_stack",
        "companies": ["google", "amazon", "bloomberg"],
        "lists": ["neetcode_150"],
        "acceptance": 49,
        "description": "There are n cars going to the same destination along a one-lane road. The destination is target miles away. You are given two integer arrays position and speed. A car can never pass another car ahead of it but can catch up and drive at the same speed. A car fleet is some non-empty set of cars driving at the same position and same speed. Return the number of car fleets that will arrive at the destination.",
        "examples": [
            {"input": "target = 12, position = [10,8,0,5,3], speed = [2,4,1,1,3]", "output": "3", "explanation": "Cars at positions 10&8 form a fleet, car at 0 is alone, cars at 5&3 form a fleet"}
        ],
        "constraints": ["n == position.length == speed.length", "1 <= n <= 10^5", "0 < target <= 10^6", "0 <= position[i] < target", "0 < speed[i] <= 10^6", "All positions are unique"],
        "starter_code": {
            "python": "class Solution:\n    def carFleet(self, target: int, position: List[int], speed: List[int]) -> int:\n        pass",
            "javascript": "var carFleet = function(target, position, speed) {\n    \n};"
        },
        "test_cases": [
            {"input": {"target": 12, "position": [10, 8, 0, 5, 3], "speed": [2, 4, 1, 1, 3]}, "expected": 3},
            {"input": {"target": 10, "position": [3], "speed": [3]}, "expected": 1},
            {"input": {"target": 100, "position": [0, 2, 4], "speed": [4, 2, 1]}, "expected": 1}
        ],
        "optimal_complexity": {"time": "O(n log n)", "space": "O(n)"},
        "hints": ["Sort cars by position descending, compute time to reach target", "If a car behind takes less time, it joins the fleet ahead"]
    },
    {
        "num": 27,
        "name": "Largest Rectangle in Histogram",
        "slug": "largest-rectangle-in-histogram",
        "difficulty": "hard",
        "topics": ["stack", "arrays"],
        "pattern": "monotonic_stack",
        "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150"],
        "acceptance": 43,
        "description": "Given an array of integers heights representing the histogram's bar height where the width of each bar is 1, return the area of the largest rectangle in the histogram.",
        "examples": [
            {"input": "heights = [2,1,5,6,2,3]", "output": "10", "explanation": "The largest rectangle has area 10 (heights 5 and 6, width 2)"}
        ],
        "constraints": ["1 <= heights.length <= 10^5", "0 <= heights[i] <= 10^4"],
        "starter_code": {
            "python": "class Solution:\n    def largestRectangleArea(self, heights: List[int]) -> int:\n        pass",
            "javascript": "var largestRectangleArea = function(heights) {\n    \n};"
        },
        "test_cases": [
            {"input": {"heights": [2, 1, 5, 6, 2, 3]}, "expected": 10},
            {"input": {"heights": [2, 4]}, "expected": 4},
            {"input": {"heights": [1]}, "expected": 1}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Use a monotonic increasing stack of indices", "When a shorter bar is found, pop and compute area with popped bar as height"]
    },
]

# ---------------------------------------------------------------------------
# 5. Binary Search (7 problems)
# ---------------------------------------------------------------------------
BINARY_SEARCH = [
    {
        "num": 28,
        "name": "Binary Search",
        "slug": "binary-search",
        "difficulty": "easy",
        "topics": ["binary_search", "arrays"],
        "pattern": "binary_search",
        "companies": ["amazon", "microsoft", "apple"],
        "lists": ["neetcode_150"],
        "acceptance": 55,
        "description": "Given an array of integers nums which is sorted in ascending order, and an integer target, write a function to search target in nums. If target exists, return its index. Otherwise, return -1.",
        "examples": [
            {"input": "nums = [-1,0,3,5,9,12], target = 9", "output": "4", "explanation": "9 exists at index 4"}
        ],
        "constraints": ["1 <= nums.length <= 10^4", "-10^4 < nums[i], target < 10^4", "All integers in nums are unique", "nums is sorted in ascending order"],
        "starter_code": {
            "python": "class Solution:\n    def search(self, nums: List[int], target: int) -> int:\n        pass",
            "javascript": "var search = function(nums, target) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums": [-1, 0, 3, 5, 9, 12], "target": 9}, "expected": 4},
            {"input": {"nums": [-1, 0, 3, 5, 9, 12], "target": 2}, "expected": -1},
            {"input": {"nums": [5], "target": 5}, "expected": 0}
        ],
        "optimal_complexity": {"time": "O(log n)", "space": "O(1)"},
        "hints": ["Use left and right pointers, compute mid", "Compare mid value with target to decide which half to search"]
    },
    {
        "num": 29,
        "name": "Search a 2D Matrix",
        "slug": "search-a-2d-matrix",
        "difficulty": "medium",
        "topics": ["binary_search", "matrix"],
        "pattern": "binary_search",
        "companies": ["amazon", "microsoft", "meta"],
        "lists": ["neetcode_150"],
        "acceptance": 47,
        "description": "You are given an m x n integer matrix with the following properties: each row is sorted in non-decreasing order, and the first integer of each row is greater than the last integer of the previous row. Given an integer target, return true if target is in matrix or false otherwise. You must write a solution in O(log(m * n)) time complexity.",
        "examples": [
            {"input": "matrix = [[1,3,5,7],[10,11,16,20],[23,30,34,60]], target = 3", "output": "true", "explanation": "3 is found in the matrix"}
        ],
        "constraints": ["m == matrix.length", "n == matrix[i].length", "1 <= m, n <= 100", "-10^4 <= matrix[i][j], target <= 10^4"],
        "starter_code": {
            "python": "class Solution:\n    def searchMatrix(self, matrix: List[List[int]], target: int) -> bool:\n        pass",
            "javascript": "var searchMatrix = function(matrix, target) {\n    \n};"
        },
        "test_cases": [
            {"input": {"matrix": [[1,3,5,7],[10,11,16,20],[23,30,34,60]], "target": 3}, "expected": True},
            {"input": {"matrix": [[1,3,5,7],[10,11,16,20],[23,30,34,60]], "target": 13}, "expected": False},
            {"input": {"matrix": [[1]], "target": 1}, "expected": True}
        ],
        "optimal_complexity": {"time": "O(log(m*n))", "space": "O(1)"},
        "hints": ["Treat the 2D matrix as a flattened sorted array", "Convert 1D index to 2D: row = idx // n, col = idx % n"]
    },
    {
        "num": 30,
        "name": "Koko Eating Bananas",
        "slug": "koko-eating-bananas",
        "difficulty": "medium",
        "topics": ["binary_search"],
        "pattern": "binary_search_on_answer",
        "companies": ["google", "amazon", "facebook"],
        "lists": ["neetcode_150"],
        "acceptance": 49,
        "description": "Koko loves to eat bananas. There are n piles of bananas. The ith pile has piles[i] bananas. The guards have gone and will come back in h hours. Koko can decide her bananas-per-hour eating speed of k. Return the minimum integer k such that she can eat all the bananas within h hours.",
        "examples": [
            {"input": "piles = [3,6,7,11], h = 8", "output": "4", "explanation": "At speed 4, Koko can finish all piles in 8 hours"}
        ],
        "constraints": ["1 <= piles.length <= 10^4", "piles.length <= h <= 10^9", "1 <= piles[i] <= 10^9"],
        "starter_code": {
            "python": "class Solution:\n    def minEatingSpeed(self, piles: List[int], h: int) -> int:\n        pass",
            "javascript": "var minEatingSpeed = function(piles, h) {\n    \n};"
        },
        "test_cases": [
            {"input": {"piles": [3, 6, 7, 11], "h": 8}, "expected": 4},
            {"input": {"piles": [30, 11, 23, 4, 20], "h": 5}, "expected": 30},
            {"input": {"piles": [30, 11, 23, 4, 20], "h": 6}, "expected": 23}
        ],
        "optimal_complexity": {"time": "O(n log m)", "space": "O(1)"},
        "hints": ["Binary search on the eating speed k from 1 to max(piles)", "For each k, check if total hours <= h using ceil(pile/k)"]
    },
    {
        "num": 31,
        "name": "Find Minimum in Rotated Sorted Array",
        "slug": "find-minimum-in-rotated-sorted-array",
        "difficulty": "medium",
        "topics": ["binary_search", "arrays"],
        "pattern": "binary_search_modified",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 49,
        "description": "Suppose an array of length n sorted in ascending order is rotated between 1 and n times. Given the sorted rotated array nums of unique elements, return the minimum element of this array. You must write an algorithm that runs in O(log n) time.",
        "examples": [
            {"input": "nums = [3,4,5,1,2]", "output": "1", "explanation": "The original array was [1,2,3,4,5] rotated 3 times"}
        ],
        "constraints": ["n == nums.length", "1 <= n <= 5000", "-5000 <= nums[i] <= 5000", "All integers are unique", "nums was sorted and rotated 1 to n times"],
        "starter_code": {
            "python": "class Solution:\n    def findMin(self, nums: List[int]) -> int:\n        pass",
            "javascript": "var findMin = function(nums) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums": [3, 4, 5, 1, 2]}, "expected": 1},
            {"input": {"nums": [4, 5, 6, 7, 0, 1, 2]}, "expected": 0},
            {"input": {"nums": [11, 13, 15, 17]}, "expected": 11}
        ],
        "optimal_complexity": {"time": "O(log n)", "space": "O(1)"},
        "hints": ["Compare mid element with right element to determine which half is sorted", "The minimum is in the unsorted half"]
    },
    {
        "num": 32,
        "name": "Search in Rotated Sorted Array",
        "slug": "search-in-rotated-sorted-array",
        "difficulty": "medium",
        "topics": ["binary_search", "arrays"],
        "pattern": "binary_search_modified",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 39,
        "description": "There is an integer array nums sorted in ascending order (with distinct values). Prior to being passed to your function, nums is possibly rotated at an unknown pivot. Given the array nums after the possible rotation and an integer target, return the index of target if it is in nums, or -1 if it is not.",
        "examples": [
            {"input": "nums = [4,5,6,7,0,1,2], target = 0", "output": "4", "explanation": "0 is found at index 4"}
        ],
        "constraints": ["1 <= nums.length <= 5000", "-10^4 <= nums[i] <= 10^4", "All values are unique", "nums may be rotated at some pivot"],
        "starter_code": {
            "python": "class Solution:\n    def search(self, nums: List[int], target: int) -> int:\n        pass",
            "javascript": "var search = function(nums, target) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums": [4, 5, 6, 7, 0, 1, 2], "target": 0}, "expected": 4},
            {"input": {"nums": [4, 5, 6, 7, 0, 1, 2], "target": 3}, "expected": -1},
            {"input": {"nums": [1], "target": 0}, "expected": -1}
        ],
        "optimal_complexity": {"time": "O(log n)", "space": "O(1)"},
        "hints": ["Determine which half is sorted, then check if target is in that half", "If target is in the sorted half, search there; otherwise search the other half"]
    },
    {
        "num": 33,
        "name": "Time Based Key-Value Store",
        "slug": "time-based-key-value-store",
        "difficulty": "medium",
        "topics": ["binary_search", "hash_map", "design"],
        "pattern": "binary_search",
        "companies": ["google", "amazon", "lyft"],
        "lists": ["neetcode_150"],
        "acceptance": 49,
        "description": "Design a time-based key-value data structure that can store multiple values for the same key at different time stamps and retrieve the key's value at a certain timestamp. Implement the TimeMap class with set and get operations.",
        "examples": [
            {"input": '["TimeMap","set","get","get","set","get","get"]\n[[],["foo","bar",1],["foo",1],["foo",3],["foo","bar2",4],["foo",4],["foo",5]]', "output": '[null,null,"bar","bar",null,"bar2","bar2"]', "explanation": "Get returns value at largest timestamp <= given timestamp"}
        ],
        "constraints": ["1 <= key.length, value.length <= 100", "key and value consist of lowercase English letters and digits", "1 <= timestamp <= 10^7", "All timestamps of set are strictly increasing", "At most 2 * 10^5 calls to set and get"],
        "starter_code": {
            "python": "class TimeMap:\n    def __init__(self):\n        pass\n    def set(self, key: str, value: str, timestamp: int) -> None:\n        pass\n    def get(self, key: str, timestamp: int) -> str:\n        pass",
            "javascript": "var TimeMap = function() {\n    \n};\nTimeMap.prototype.set = function(key, value, timestamp) {\n    \n};\nTimeMap.prototype.get = function(key, timestamp) {\n    \n};"
        },
        "test_cases": [
            {"input": {"operations": ["TimeMap","set","get","get","set","get","get"], "values": [[],["foo","bar",1],["foo",1],["foo",3],["foo","bar2",4],["foo",4],["foo",5]]}, "expected": [None,None,"bar","bar",None,"bar2","bar2"]},
            {"input": {"operations": ["TimeMap","set","set","get","get"], "values": [[],["key","v1",1],["key","v2",2],["key",1],["key",3]]}, "expected": [None,None,None,"v1","v2"]},
            {"input": {"operations": ["TimeMap","get"], "values": [[],["key",1]]}, "expected": [None,""]}
        ],
        "optimal_complexity": {"time": "O(log n) per get", "space": "O(n)"},
        "hints": ["Store values in a list per key, binary search on timestamp for get", "Since timestamps are strictly increasing, the list is already sorted"]
    },
    {
        "num": 34,
        "name": "Median of Two Sorted Arrays",
        "slug": "median-of-two-sorted-arrays",
        "difficulty": "hard",
        "topics": ["binary_search", "arrays"],
        "pattern": "binary_search",
        "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150"],
        "acceptance": 38,
        "description": "Given two sorted arrays nums1 and nums2 of size m and n respectively, return the median of the two sorted arrays. The overall run time complexity should be O(log(m+n)).",
        "examples": [
            {"input": "nums1 = [1,3], nums2 = [2]", "output": "2.0", "explanation": "Merged array = [1,2,3], median is 2"}
        ],
        "constraints": ["nums1.length == m", "nums2.length == n", "0 <= m <= 1000", "0 <= n <= 1000", "1 <= m + n <= 2000", "-10^6 <= nums1[i], nums2[i] <= 10^6"],
        "starter_code": {
            "python": "class Solution:\n    def findMedianSortedArrays(self, nums1: List[int], nums2: List[int]) -> float:\n        pass",
            "javascript": "var findMedianSortedArrays = function(nums1, nums2) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums1": [1, 3], "nums2": [2]}, "expected": 2.0},
            {"input": {"nums1": [1, 2], "nums2": [3, 4]}, "expected": 2.5},
            {"input": {"nums1": [], "nums2": [1]}, "expected": 1.0}
        ],
        "optimal_complexity": {"time": "O(log(min(m,n)))", "space": "O(1)"},
        "hints": ["Binary search on the smaller array's partition point", "Ensure left partitions from both arrays equal half of total elements"]
    },
]

# ---------------------------------------------------------------------------
# 6. Linked List (11 problems)
# ---------------------------------------------------------------------------
LINKED_LIST = [
    {
        "num": 35,
        "name": "Reverse Linked List",
        "slug": "reverse-linked-list",
        "difficulty": "easy",
        "topics": ["linked_list"],
        "pattern": "iterative_reversal",
        "companies": ["amazon", "microsoft", "apple"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 73,
        "description": "Given the head of a singly linked list, reverse the list, and return the reversed list.",
        "examples": [
            {"input": "head = [1,2,3,4,5]", "output": "[5,4,3,2,1]", "explanation": "The list is reversed"}
        ],
        "constraints": ["The number of nodes is in the range [0, 5000]", "-5000 <= Node.val <= 5000"],
        "starter_code": {
            "python": "class Solution:\n    def reverseList(self, head: Optional[ListNode]) -> Optional[ListNode]:\n        pass",
            "javascript": "var reverseList = function(head) {\n    \n};"
        },
        "test_cases": [
            {"input": {"head": [1, 2, 3, 4, 5]}, "expected": [5, 4, 3, 2, 1]},
            {"input": {"head": [1, 2]}, "expected": [2, 1]},
            {"input": {"head": []}, "expected": []}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Use three pointers: prev, curr, next", "At each step, reverse the pointer direction"]
    },
    {
        "num": 36,
        "name": "Merge Two Sorted Lists",
        "slug": "merge-two-sorted-lists",
        "difficulty": "easy",
        "topics": ["linked_list"],
        "pattern": "two_pointer_merge",
        "companies": ["amazon", "microsoft", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 62,
        "description": "You are given the heads of two sorted linked lists list1 and list2. Merge the two lists into one sorted list by splicing together the nodes. Return the head of the merged linked list.",
        "examples": [
            {"input": "list1 = [1,2,4], list2 = [1,3,4]", "output": "[1,1,2,3,4,4]", "explanation": "Merge two sorted lists"}
        ],
        "constraints": ["The number of nodes in both lists is in range [0, 50]", "-100 <= Node.val <= 100", "Both lists are sorted in non-decreasing order"],
        "starter_code": {
            "python": "class Solution:\n    def mergeTwoLists(self, list1: Optional[ListNode], list2: Optional[ListNode]) -> Optional[ListNode]:\n        pass",
            "javascript": "var mergeTwoLists = function(list1, list2) {\n    \n};"
        },
        "test_cases": [
            {"input": {"list1": [1, 2, 4], "list2": [1, 3, 4]}, "expected": [1, 1, 2, 3, 4, 4]},
            {"input": {"list1": [], "list2": []}, "expected": []},
            {"input": {"list1": [], "list2": [0]}, "expected": [0]}
        ],
        "optimal_complexity": {"time": "O(n + m)", "space": "O(1)"},
        "hints": ["Use a dummy head node to simplify edge cases", "Compare values from both lists and append the smaller one"]
    },
    {
        "num": 37,
        "name": "Reorder List",
        "slug": "reorder-list",
        "difficulty": "medium",
        "topics": ["linked_list"],
        "pattern": "linked_list_manipulation",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 51,
        "description": "You are given the head of a singly linked-list. The list can be represented as L0 -> L1 -> ... -> Ln-1 -> Ln. Reorder the list to be L0 -> Ln -> L1 -> Ln-1 -> L2 -> Ln-2 -> ...",
        "examples": [
            {"input": "head = [1,2,3,4]", "output": "[1,4,2,3]", "explanation": "Reorder by interleaving from both ends"}
        ],
        "constraints": ["The number of nodes is in range [1, 5 * 10^4]", "1 <= Node.val <= 1000"],
        "starter_code": {
            "python": "class Solution:\n    def reorderList(self, head: Optional[ListNode]) -> None:\n        pass",
            "javascript": "var reorderList = function(head) {\n    \n};"
        },
        "test_cases": [
            {"input": {"head": [1, 2, 3, 4]}, "expected": [1, 4, 2, 3]},
            {"input": {"head": [1, 2, 3, 4, 5]}, "expected": [1, 5, 2, 4, 3]},
            {"input": {"head": [1]}, "expected": [1]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Find the middle, reverse the second half, then merge alternately", "Use slow/fast pointers to find the middle"]
    },
    {
        "num": 38,
        "name": "Remove Nth Node From End of List",
        "slug": "remove-nth-node-from-end-of-list",
        "difficulty": "medium",
        "topics": ["linked_list", "two_pointers"],
        "pattern": "two_pointer_offset",
        "companies": ["meta", "amazon", "apple"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 41,
        "description": "Given the head of a linked list, remove the nth node from the end of the list and return its head.",
        "examples": [
            {"input": "head = [1,2,3,4,5], n = 2", "output": "[1,2,3,5]", "explanation": "Remove the 2nd node from end (value 4)"}
        ],
        "constraints": ["The number of nodes is sz", "1 <= sz <= 30", "0 <= Node.val <= 100", "1 <= n <= sz"],
        "starter_code": {
            "python": "class Solution:\n    def removeNthFromEnd(self, head: Optional[ListNode], n: int) -> Optional[ListNode]:\n        pass",
            "javascript": "var removeNthFromEnd = function(head, n) {\n    \n};"
        },
        "test_cases": [
            {"input": {"head": [1, 2, 3, 4, 5], "n": 2}, "expected": [1, 2, 3, 5]},
            {"input": {"head": [1], "n": 1}, "expected": []},
            {"input": {"head": [1, 2], "n": 1}, "expected": [1]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Use two pointers separated by n nodes", "When fast reaches end, slow is at the node before the target"]
    },
    {
        "num": 39,
        "name": "Copy List with Random Pointer",
        "slug": "copy-list-with-random-pointer",
        "difficulty": "medium",
        "topics": ["linked_list", "hash_map"],
        "pattern": "hash_map_clone",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150"],
        "acceptance": 50,
        "description": "A linked list of length n is given such that each node contains an additional random pointer, which could point to any node in the list, or null. Construct a deep copy of the list.",
        "examples": [
            {"input": "head = [[7,null],[13,0],[11,4],[10,2],[1,0]]", "output": "[[7,null],[13,0],[11,4],[10,2],[1,0]]", "explanation": "Deep copy with all random pointers preserved"}
        ],
        "constraints": ["0 <= n <= 1000", "-10^4 <= Node.val <= 10^4", "Node.random is null or points to a node in the list"],
        "starter_code": {
            "python": "class Solution:\n    def copyRandomList(self, head: 'Optional[Node]') -> 'Optional[Node]':\n        pass",
            "javascript": "var copyRandomList = function(head) {\n    \n};"
        },
        "test_cases": [
            {"input": {"head": [[7,None],[13,0],[11,4],[10,2],[1,0]]}, "expected": [[7,None],[13,0],[11,4],[10,2],[1,0]]},
            {"input": {"head": [[1,1],[2,1]]}, "expected": [[1,1],[2,1]]},
            {"input": {"head": [[3,None],[3,0],[3,None]]}, "expected": [[3,None],[3,0],[3,None]]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Use a hash map from original node to its copy", "Two passes: first create all nodes, then set next and random pointers"]
    },
    {
        "num": 40,
        "name": "Add Two Numbers",
        "slug": "add-two-numbers",
        "difficulty": "medium",
        "topics": ["linked_list", "math"],
        "pattern": "linked_list_traversal",
        "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150"],
        "acceptance": 40,
        "description": "You are given two non-empty linked lists representing two non-negative integers. The digits are stored in reverse order, and each of their nodes contains a single digit. Add the two numbers and return the sum as a linked list.",
        "examples": [
            {"input": "l1 = [2,4,3], l2 = [5,6,4]", "output": "[7,0,8]", "explanation": "342 + 465 = 807"}
        ],
        "constraints": ["The number of nodes in each list is in range [1, 100]", "0 <= Node.val <= 9", "The number does not contain any leading zero except the number 0 itself"],
        "starter_code": {
            "python": "class Solution:\n    def addTwoNumbers(self, l1: Optional[ListNode], l2: Optional[ListNode]) -> Optional[ListNode]:\n        pass",
            "javascript": "var addTwoNumbers = function(l1, l2) {\n    \n};"
        },
        "test_cases": [
            {"input": {"l1": [2, 4, 3], "l2": [5, 6, 4]}, "expected": [7, 0, 8]},
            {"input": {"l1": [0], "l2": [0]}, "expected": [0]},
            {"input": {"l1": [9, 9, 9, 9, 9, 9, 9], "l2": [9, 9, 9, 9]}, "expected": [8, 9, 9, 9, 0, 0, 0, 1]}
        ],
        "optimal_complexity": {"time": "O(max(m,n))", "space": "O(max(m,n))"},
        "hints": ["Traverse both lists simultaneously, tracking carry", "Don't forget the final carry if it's non-zero"]
    },
    {
        "num": 41,
        "name": "Linked List Cycle",
        "slug": "linked-list-cycle",
        "difficulty": "easy",
        "topics": ["linked_list", "two_pointers"],
        "pattern": "fast_slow_pointer",
        "companies": ["amazon", "microsoft", "apple"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 47,
        "description": "Given head, the head of a linked list, determine if the linked list has a cycle in it. There is a cycle if there is some node in the list that can be reached again by continuously following the next pointer.",
        "examples": [
            {"input": "head = [3,2,0,-4], pos = 1", "output": "true", "explanation": "Tail connects to the 1st node (0-indexed)"}
        ],
        "constraints": ["The number of nodes is in range [0, 10^4]", "-10^5 <= Node.val <= 10^5", "pos is -1 or a valid index"],
        "starter_code": {
            "python": "class Solution:\n    def hasCycle(self, head: Optional[ListNode]) -> bool:\n        pass",
            "javascript": "var hasCycle = function(head) {\n    \n};"
        },
        "test_cases": [
            {"input": {"head": [3, 2, 0, -4], "pos": 1}, "expected": True},
            {"input": {"head": [1, 2], "pos": 0}, "expected": True},
            {"input": {"head": [1], "pos": -1}, "expected": False}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Use Floyd's cycle detection: slow moves 1 step, fast moves 2", "If they meet, there's a cycle; if fast reaches null, no cycle"]
    },
    {
        "num": 42,
        "name": "Find The Duplicate Number",
        "slug": "find-the-duplicate-number",
        "difficulty": "medium",
        "topics": ["linked_list", "two_pointers", "binary_search"],
        "pattern": "fast_slow_pointer",
        "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150"],
        "acceptance": 59,
        "description": "Given an array of integers nums containing n + 1 integers where each integer is in the range [1, n] inclusive, there is only one repeated number. Return this repeated number. You must solve it without modifying the array and using only constant extra space.",
        "examples": [
            {"input": "nums = [1,3,4,2,2]", "output": "2", "explanation": "2 is the duplicate number"}
        ],
        "constraints": ["1 <= n <= 10^5", "nums.length == n + 1", "1 <= nums[i] <= n", "There is only one repeated number, but it may repeat more than once"],
        "starter_code": {
            "python": "class Solution:\n    def findDuplicate(self, nums: List[int]) -> int:\n        pass",
            "javascript": "var findDuplicate = function(nums) {\n    \n};"
        },
        "test_cases": [
            {"input": {"nums": [1, 3, 4, 2, 2]}, "expected": 2},
            {"input": {"nums": [3, 1, 3, 4, 2]}, "expected": 3},
            {"input": {"nums": [2, 2, 2, 2, 2]}, "expected": 2}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Treat it as a linked list cycle problem (value -> next index)", "Use Floyd's algorithm to find the cycle entrance"]
    },
    {
        "num": 43,
        "name": "LRU Cache",
        "slug": "lru-cache",
        "difficulty": "medium",
        "topics": ["linked_list", "hash_map", "design"],
        "pattern": "hash_map_doubly_linked_list",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 40,
        "description": "Design a data structure that follows the constraints of a Least Recently Used (LRU) cache. Implement the LRUCache class with get and put operations that run in O(1) average time complexity.",
        "examples": [
            {"input": '["LRUCache","put","put","get","put","get","put","get","get","get"]\n[[2],[1,1],[2,2],[1],[3,3],[2],[4,4],[1],[3],[4]]', "output": "[null,null,null,1,null,-1,null,-1,3,4]", "explanation": "LRU cache operations with capacity 2"}
        ],
        "constraints": ["1 <= capacity <= 3000", "0 <= key <= 10^4", "0 <= value <= 10^5", "At most 2 * 10^5 calls to get and put"],
        "starter_code": {
            "python": "class LRUCache:\n    def __init__(self, capacity: int):\n        pass\n    def get(self, key: int) -> int:\n        pass\n    def put(self, key: int, value: int) -> None:\n        pass",
            "javascript": "var LRUCache = function(capacity) {\n    \n};\nLRUCache.prototype.get = function(key) {\n    \n};\nLRUCache.prototype.put = function(key, value) {\n    \n};"
        },
        "test_cases": [
            {"input": {"operations": ["LRUCache","put","put","get","put","get","put","get","get","get"], "values": [[2],[1,1],[2,2],[1],[3,3],[2],[4,4],[1],[3],[4]]}, "expected": [None,None,None,1,None,-1,None,-1,3,4]},
            {"input": {"operations": ["LRUCache","put","get"], "values": [[1],[2,1],[2]]}, "expected": [None,None,1]},
            {"input": {"operations": ["LRUCache","put","put","get"], "values": [[1],[1,1],[2,2],[1]]}, "expected": [None,None,None,-1]}
        ],
        "optimal_complexity": {"time": "O(1)", "space": "O(capacity)"},
        "hints": ["Combine hash map with doubly linked list", "Hash map gives O(1) lookup, linked list gives O(1) removal and insertion"]
    },
    {
        "num": 44,
        "name": "Merge K Sorted Lists",
        "slug": "merge-k-sorted-lists",
        "difficulty": "hard",
        "topics": ["linked_list", "heap", "divide_and_conquer"],
        "pattern": "min_heap_merge",
        "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 49,
        "description": "You are given an array of k linked-lists lists, each linked-list is sorted in ascending order. Merge all the linked-lists into one sorted linked-list and return it.",
        "examples": [
            {"input": "lists = [[1,4,5],[1,3,4],[2,6]]", "output": "[1,1,2,3,4,4,5,6]", "explanation": "Merge three sorted lists into one"}
        ],
        "constraints": ["k == lists.length", "0 <= k <= 10^4", "0 <= lists[i].length <= 500", "-10^4 <= lists[i][j] <= 10^4", "lists[i] is sorted in ascending order", "Sum of lists[i].length <= 10^4"],
        "starter_code": {
            "python": "class Solution:\n    def mergeKLists(self, lists: List[Optional[ListNode]]) -> Optional[ListNode]:\n        pass",
            "javascript": "var mergeKLists = function(lists) {\n    \n};"
        },
        "test_cases": [
            {"input": {"lists": [[1, 4, 5], [1, 3, 4], [2, 6]]}, "expected": [1, 1, 2, 3, 4, 4, 5, 6]},
            {"input": {"lists": []}, "expected": []},
            {"input": {"lists": [[]]}, "expected": []}
        ],
        "optimal_complexity": {"time": "O(N log k)", "space": "O(k)"},
        "hints": ["Use a min-heap to always pick the smallest current node", "Divide and conquer by merging pairs also works in O(N log k)"]
    },
    {
        "num": 45,
        "name": "Reverse Nodes in K-Group",
        "slug": "reverse-nodes-in-k-group",
        "difficulty": "hard",
        "topics": ["linked_list"],
        "pattern": "linked_list_reversal",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150"],
        "acceptance": 54,
        "description": "Given the head of a linked list, reverse the nodes of the list k at a time, and return the modified list. k is a positive integer and is less than or equal to the length of the linked list. If the number of nodes is not a multiple of k then left-out nodes at the end should remain as they are.",
        "examples": [
            {"input": "head = [1,2,3,4,5], k = 2", "output": "[2,1,4,3,5]", "explanation": "Reverse in groups of 2"}
        ],
        "constraints": ["The number of nodes is n", "1 <= k <= n <= 5000", "0 <= Node.val <= 1000"],
        "starter_code": {
            "python": "class Solution:\n    def reverseKGroup(self, head: Optional[ListNode], k: int) -> Optional[ListNode]:\n        pass",
            "javascript": "var reverseKGroup = function(head, k) {\n    \n};"
        },
        "test_cases": [
            {"input": {"head": [1, 2, 3, 4, 5], "k": 2}, "expected": [2, 1, 4, 3, 5]},
            {"input": {"head": [1, 2, 3, 4, 5], "k": 3}, "expected": [3, 2, 1, 4, 5]},
            {"input": {"head": [1, 2, 3, 4, 5], "k": 1}, "expected": [1, 2, 3, 4, 5]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["First check if there are k nodes remaining before reversing", "Reverse k nodes, then recursively handle the rest"]
    },
]


# Placeholder for remaining categories - will be defined below
TREES = [
    {
        "num": 46,
        "name": "Invert Binary Tree",
        "slug": "invert-binary-tree",
        "difficulty": "easy",
        "topics": ["trees", "bfs", "dfs"],
        "pattern": "tree_recursion",
        "companies": ["google", "amazon", "meta"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 73,
        "description": "Given the root of a binary tree, invert the tree, and return its root.",
        "examples": [{"input": "root = [4,2,7,1,3,6,9]", "output": "[4,7,2,9,6,3,1]", "explanation": "Swap left and right children at every node"}],
        "constraints": ["The number of nodes is in range [0, 100]", "-100 <= Node.val <= 100"],
        "starter_code": {"python": "class Solution:\n    def invertTree(self, root: Optional[TreeNode]) -> Optional[TreeNode]:\n        pass", "javascript": "var invertTree = function(root) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [4,2,7,1,3,6,9]}, "expected": [4,7,2,9,6,3,1]},
            {"input": {"root": [2,1,3]}, "expected": [2,3,1]},
            {"input": {"root": []}, "expected": []}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(h)"},
        "hints": ["Recursively swap left and right children", "Base case: null node returns null"]
    },
    {
        "num": 47,
        "name": "Maximum Depth of Binary Tree",
        "slug": "maximum-depth-of-binary-tree",
        "difficulty": "easy",
        "topics": ["trees", "dfs", "bfs"],
        "pattern": "tree_recursion",
        "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 73,
        "description": "Given the root of a binary tree, return its maximum depth. A binary tree's maximum depth is the number of nodes along the longest path from the root node down to the farthest leaf node.",
        "examples": [{"input": "root = [3,9,20,null,null,15,7]", "output": "3", "explanation": "Longest path has 3 nodes"}],
        "constraints": ["The number of nodes is in range [0, 10^4]", "-100 <= Node.val <= 100"],
        "starter_code": {"python": "class Solution:\n    def maxDepth(self, root: Optional[TreeNode]) -> int:\n        pass", "javascript": "var maxDepth = function(root) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [3,9,20,None,None,15,7]}, "expected": 3},
            {"input": {"root": [1,None,2]}, "expected": 2},
            {"input": {"root": []}, "expected": 0}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(h)"},
        "hints": ["Depth = 1 + max(left depth, right depth)", "Base case: null node has depth 0"]
    },
    {
        "num": 48,
        "name": "Diameter of Binary Tree",
        "slug": "diameter-of-binary-tree",
        "difficulty": "easy",
        "topics": ["trees", "dfs"],
        "pattern": "tree_recursion",
        "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150"],
        "acceptance": 57,
        "description": "Given the root of a binary tree, return the length of the diameter of the tree. The diameter is the length of the longest path between any two nodes in a tree. This path may or may not pass through the root.",
        "examples": [{"input": "root = [1,2,3,4,5]", "output": "3", "explanation": "The path [4,2,1,3] or [5,2,1,3] has length 3"}],
        "constraints": ["The number of nodes is in range [1, 10^4]", "-100 <= Node.val <= 100"],
        "starter_code": {"python": "class Solution:\n    def diameterOfBinaryTree(self, root: Optional[TreeNode]) -> int:\n        pass", "javascript": "var diameterOfBinaryTree = function(root) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [1,2,3,4,5]}, "expected": 3},
            {"input": {"root": [1,2]}, "expected": 1},
            {"input": {"root": [1]}, "expected": 0}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(h)"},
        "hints": ["At each node, diameter through it = left height + right height", "Track the global maximum diameter while computing heights"]
    },
    {
        "num": 49,
        "name": "Balanced Binary Tree",
        "slug": "balanced-binary-tree",
        "difficulty": "easy",
        "topics": ["trees", "dfs"],
        "pattern": "tree_recursion",
        "companies": ["amazon", "google", "bloomberg"],
        "lists": ["neetcode_150"],
        "acceptance": 49,
        "description": "Given a binary tree, determine if it is height-balanced. A height-balanced binary tree is a binary tree in which the depth of the two subtrees of every node never differs by more than one.",
        "examples": [{"input": "root = [3,9,20,null,null,15,7]", "output": "true", "explanation": "All subtree height differences are at most 1"}],
        "constraints": ["The number of nodes is in range [0, 5000]", "-10^4 <= Node.val <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def isBalanced(self, root: Optional[TreeNode]) -> bool:\n        pass", "javascript": "var isBalanced = function(root) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [3,9,20,None,None,15,7]}, "expected": True},
            {"input": {"root": [1,2,2,3,3,None,None,4,4]}, "expected": False},
            {"input": {"root": []}, "expected": True}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(h)"},
        "hints": ["Return -1 from height function if subtree is unbalanced", "Check |leftHeight - rightHeight| <= 1 at every node"]
    },
    {
        "num": 50,
        "name": "Same Tree",
        "slug": "same-tree",
        "difficulty": "easy",
        "topics": ["trees", "dfs"],
        "pattern": "tree_recursion",
        "companies": ["amazon", "microsoft", "bloomberg"],
        "lists": ["neetcode_150"],
        "acceptance": 57,
        "description": "Given the roots of two binary trees p and q, write a function to check if they are the same or not. Two binary trees are considered the same if they are structurally identical, and the nodes have the same value.",
        "examples": [{"input": "p = [1,2,3], q = [1,2,3]", "output": "true", "explanation": "Both trees are identical"}],
        "constraints": ["The number of nodes in both trees is in range [0, 100]", "-10^4 <= Node.val <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def isSameTree(self, p: Optional[TreeNode], q: Optional[TreeNode]) -> bool:\n        pass", "javascript": "var isSameTree = function(p, q) {\n    \n};"},
        "test_cases": [
            {"input": {"p": [1,2,3], "q": [1,2,3]}, "expected": True},
            {"input": {"p": [1,2], "q": [1,None,2]}, "expected": False},
            {"input": {"p": [1,2,1], "q": [1,1,2]}, "expected": False}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(h)"},
        "hints": ["Both null -> true; one null -> false; values differ -> false", "Recurse on left and right subtrees"]
    },
    {
        "num": 51,
        "name": "Subtree of Another Tree",
        "slug": "subtree-of-another-tree",
        "difficulty": "easy",
        "topics": ["trees", "dfs"],
        "pattern": "tree_recursion",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 46,
        "description": "Given the roots of two binary trees root and subRoot, return true if there is a subtree of root with the same structure and node values of subRoot and false otherwise.",
        "examples": [{"input": "root = [3,4,5,1,2], subRoot = [4,1,2]", "output": "true", "explanation": "The subtree rooted at node 4 matches subRoot"}],
        "constraints": ["The number of nodes in root is in range [1, 2000]", "The number of nodes in subRoot is in range [1, 1000]", "-10^4 <= root.val, subRoot.val <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def isSubtree(self, root: Optional[TreeNode], subRoot: Optional[TreeNode]) -> bool:\n        pass", "javascript": "var isSubtree = function(root, subRoot) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [3,4,5,1,2], "subRoot": [4,1,2]}, "expected": True},
            {"input": {"root": [3,4,5,1,2,None,None,None,None,0], "subRoot": [4,1,2]}, "expected": False},
            {"input": {"root": [1], "subRoot": [1]}, "expected": True}
        ],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(m + n)"},
        "hints": ["At each node of root, check if the subtree matches subRoot", "Reuse the isSameTree logic as a helper"]
    },
    {
        "num": 52,
        "name": "Lowest Common Ancestor of a Binary Search Tree",
        "slug": "lowest-common-ancestor-of-a-binary-search-tree",
        "difficulty": "medium",
        "topics": ["trees", "bst"],
        "pattern": "bst_traversal",
        "companies": ["meta", "amazon", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 60,
        "description": "Given a binary search tree (BST), find the lowest common ancestor (LCA) node of two given nodes in the BST. The LCA is the lowest node that has both p and q as descendants (a node can be a descendant of itself).",
        "examples": [{"input": "root = [6,2,8,0,4,7,9,null,null,3,5], p = 2, q = 8", "output": "6", "explanation": "LCA of 2 and 8 is 6"}],
        "constraints": ["The number of nodes is in range [2, 10^5]", "-10^9 <= Node.val <= 10^9", "All values are unique", "p != q", "p and q exist in the BST"],
        "starter_code": {"python": "class Solution:\n    def lowestCommonAncestor(self, root: 'TreeNode', p: 'TreeNode', q: 'TreeNode') -> 'TreeNode':\n        pass", "javascript": "var lowestCommonAncestor = function(root, p, q) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [6,2,8,0,4,7,9,None,None,3,5], "p": 2, "q": 8}, "expected": 6},
            {"input": {"root": [6,2,8,0,4,7,9,None,None,3,5], "p": 2, "q": 4}, "expected": 2},
            {"input": {"root": [2,1], "p": 2, "q": 1}, "expected": 2}
        ],
        "optimal_complexity": {"time": "O(h)", "space": "O(1)"},
        "hints": ["If both p and q are less than root, go left; both greater, go right", "Otherwise, current root is the LCA (split point)"]
    },
    {
        "num": 53,
        "name": "Binary Tree Level Order Traversal",
        "slug": "binary-tree-level-order-traversal",
        "difficulty": "medium",
        "topics": ["trees", "bfs"],
        "pattern": "bfs_level_order",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 63,
        "description": "Given the root of a binary tree, return the level order traversal of its nodes' values (i.e., from left to right, level by level).",
        "examples": [{"input": "root = [3,9,20,null,null,15,7]", "output": "[[3],[9,20],[15,7]]", "explanation": "Each subarray represents one level"}],
        "constraints": ["The number of nodes is in range [0, 2000]", "-1000 <= Node.val <= 1000"],
        "starter_code": {"python": "class Solution:\n    def levelOrder(self, root: Optional[TreeNode]) -> List[List[int]]:\n        pass", "javascript": "var levelOrder = function(root) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [3,9,20,None,None,15,7]}, "expected": [[3],[9,20],[15,7]]},
            {"input": {"root": [1]}, "expected": [[1]]},
            {"input": {"root": []}, "expected": []}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Use a queue (BFS), process one level at a time", "Track level size at the start of each iteration"]
    },
    {
        "num": 54,
        "name": "Binary Tree Right Side View",
        "slug": "binary-tree-right-side-view",
        "difficulty": "medium",
        "topics": ["trees", "bfs", "dfs"],
        "pattern": "bfs_level_order",
        "companies": ["meta", "amazon", "bloomberg"],
        "lists": ["neetcode_150"],
        "acceptance": 61,
        "description": "Given the root of a binary tree, imagine yourself standing on the right side of it, return the values of the nodes you can see ordered from top to bottom.",
        "examples": [{"input": "root = [1,2,3,null,5,null,4]", "output": "[1,3,4]", "explanation": "From right side you see nodes 1, 3, and 4"}],
        "constraints": ["The number of nodes is in range [0, 100]", "-100 <= Node.val <= 100"],
        "starter_code": {"python": "class Solution:\n    def rightSideView(self, root: Optional[TreeNode]) -> List[int]:\n        pass", "javascript": "var rightSideView = function(root) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [1,2,3,None,5,None,4]}, "expected": [1,3,4]},
            {"input": {"root": [1,None,3]}, "expected": [1,3]},
            {"input": {"root": []}, "expected": []}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["BFS level order, take the last node of each level", "DFS with right-first traversal, tracking depth"]
    },
    {
        "num": 55,
        "name": "Count Good Nodes in Binary Tree",
        "slug": "count-good-nodes-in-binary-tree",
        "difficulty": "medium",
        "topics": ["trees", "dfs"],
        "pattern": "dfs_with_state",
        "companies": ["amazon", "microsoft", "google"],
        "lists": ["neetcode_150"],
        "acceptance": 74,
        "description": "Given a binary tree root, a node X in the tree is named good if in the path from root to X there are no nodes with a value greater than X. Return the number of good nodes in the binary tree.",
        "examples": [{"input": "root = [3,1,4,3,null,1,5]", "output": "4", "explanation": "Nodes 3, 3, 4, 5 are good nodes"}],
        "constraints": ["The number of nodes is in range [1, 10^5]", "-10^4 <= Node.val <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def goodNodes(self, root: TreeNode) -> int:\n        pass", "javascript": "var goodNodes = function(root) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [3,1,4,3,None,1,5]}, "expected": 4},
            {"input": {"root": [3,3,None,4,2]}, "expected": 3},
            {"input": {"root": [1]}, "expected": 1}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(h)"},
        "hints": ["DFS passing the maximum value seen so far on the path", "A node is good if its value >= max value on path from root"]
    },
    {
        "num": 56,
        "name": "Validate Binary Search Tree",
        "slug": "validate-binary-search-tree",
        "difficulty": "medium",
        "topics": ["trees", "bst", "dfs"],
        "pattern": "bst_validation",
        "companies": ["amazon", "meta", "bloomberg"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 32,
        "description": "Given the root of a binary tree, determine if it is a valid binary search tree (BST). A valid BST has: left subtree values < node value, right subtree values > node value, and both subtrees are valid BSTs.",
        "examples": [{"input": "root = [2,1,3]", "output": "true", "explanation": "Left < root < right at every node"}],
        "constraints": ["The number of nodes is in range [1, 10^4]", "-2^31 <= Node.val <= 2^31 - 1"],
        "starter_code": {"python": "class Solution:\n    def isValidBST(self, root: Optional[TreeNode]) -> bool:\n        pass", "javascript": "var isValidBST = function(root) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [2,1,3]}, "expected": True},
            {"input": {"root": [5,1,4,None,None,3,6]}, "expected": False},
            {"input": {"root": [5,4,6,None,None,3,7]}, "expected": False}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(h)"},
        "hints": ["Pass valid range (min, max) down during recursion", "Alternatively, inorder traversal should produce sorted values"]
    },
    {
        "num": 57,
        "name": "Kth Smallest Element in a BST",
        "slug": "kth-smallest-element-in-a-bst",
        "difficulty": "medium",
        "topics": ["trees", "bst", "dfs"],
        "pattern": "inorder_traversal",
        "companies": ["amazon", "meta", "uber"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 71,
        "description": "Given the root of a binary search tree, and an integer k, return the kth smallest value (1-indexed) of all the values of the nodes in the tree.",
        "examples": [{"input": "root = [3,1,4,null,2], k = 1", "output": "1", "explanation": "The 1st smallest element is 1"}],
        "constraints": ["The number of nodes is n", "1 <= k <= n <= 10^4", "0 <= Node.val <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def kthSmallest(self, root: Optional[TreeNode], k: int) -> int:\n        pass", "javascript": "var kthSmallest = function(root, k) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [3,1,4,None,2], "k": 1}, "expected": 1},
            {"input": {"root": [5,3,6,2,4,None,None,1], "k": 3}, "expected": 3},
            {"input": {"root": [1], "k": 1}, "expected": 1}
        ],
        "optimal_complexity": {"time": "O(H + k)", "space": "O(H)"},
        "hints": ["Inorder traversal of BST gives sorted order", "Count nodes visited during inorder; return when count == k"]
    },
    {
        "num": 58,
        "name": "Construct Binary Tree from Preorder and Inorder Traversal",
        "slug": "construct-binary-tree-from-preorder-and-inorder-traversal",
        "difficulty": "medium",
        "topics": ["trees", "dfs", "hash_map"],
        "pattern": "tree_construction",
        "companies": ["amazon", "microsoft", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 61,
        "description": "Given two integer arrays preorder and inorder where preorder is the preorder traversal and inorder is the inorder traversal of the same tree, construct and return the binary tree.",
        "examples": [{"input": "preorder = [3,9,20,15,7], inorder = [9,3,15,20,7]", "output": "[3,9,20,null,null,15,7]", "explanation": "Construct tree from traversals"}],
        "constraints": ["1 <= preorder.length <= 3000", "inorder.length == preorder.length", "-3000 <= preorder[i], inorder[i] <= 3000", "All values are unique"],
        "starter_code": {"python": "class Solution:\n    def buildTree(self, preorder: List[int], inorder: List[int]) -> Optional[TreeNode]:\n        pass", "javascript": "var buildTree = function(preorder, inorder) {\n    \n};"},
        "test_cases": [
            {"input": {"preorder": [3,9,20,15,7], "inorder": [9,3,15,20,7]}, "expected": [3,9,20,None,None,15,7]},
            {"input": {"preorder": [-1], "inorder": [-1]}, "expected": [-1]},
            {"input": {"preorder": [1,2], "inorder": [2,1]}, "expected": [1,2]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["First element of preorder is always the root", "Find root in inorder to split into left and right subtrees; use a hash map for O(1) lookup"]
    },
    {
        "num": 59,
        "name": "Binary Tree Maximum Path Sum",
        "slug": "binary-tree-maximum-path-sum",
        "difficulty": "hard",
        "topics": ["trees", "dfs"],
        "pattern": "tree_recursion",
        "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 38,
        "description": "A path in a binary tree is a sequence of nodes where each pair of adjacent nodes has an edge connecting them. A node can only appear in the path at most once. The path sum is the sum of node values in the path. Given the root, return the maximum path sum of any non-empty path.",
        "examples": [{"input": "root = [-10,9,20,null,null,15,7]", "output": "42", "explanation": "Path 15 -> 20 -> 7 has sum 42"}],
        "constraints": ["The number of nodes is in range [1, 3 * 10^4]", "-1000 <= Node.val <= 1000"],
        "starter_code": {"python": "class Solution:\n    def maxPathSum(self, root: Optional[TreeNode]) -> int:\n        pass", "javascript": "var maxPathSum = function(root) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [-10,9,20,None,None,15,7]}, "expected": 42},
            {"input": {"root": [1,2,3]}, "expected": 6},
            {"input": {"root": [-3]}, "expected": -3}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(h)"},
        "hints": ["At each node, compute max gain from left and right (clamped to 0)", "Update global max with node.val + leftGain + rightGain, but return node.val + max(leftGain, rightGain) upward"]
    },
    {
        "num": 60,
        "name": "Serialize and Deserialize Binary Tree",
        "slug": "serialize-and-deserialize-binary-tree",
        "difficulty": "hard",
        "topics": ["trees", "bfs", "dfs", "design"],
        "pattern": "tree_serialization",
        "companies": ["meta", "amazon", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 55,
        "description": "Design an algorithm to serialize and deserialize a binary tree. Serialization is the process of converting a data structure into a sequence of bits. Deserialization is the reverse process.",
        "examples": [{"input": "root = [1,2,3,null,null,4,5]", "output": "[1,2,3,null,null,4,5]", "explanation": "Serialize then deserialize returns same tree"}],
        "constraints": ["The number of nodes is in range [0, 10^4]", "-1000 <= Node.val <= 1000"],
        "starter_code": {"python": "class Codec:\n    def serialize(self, root):\n        pass\n    def deserialize(self, data):\n        pass", "javascript": "var serialize = function(root) {\n    \n};\nvar deserialize = function(data) {\n    \n};"},
        "test_cases": [
            {"input": {"root": [1,2,3,None,None,4,5]}, "expected": [1,2,3,None,None,4,5]},
            {"input": {"root": []}, "expected": []},
            {"input": {"root": [1]}, "expected": [1]}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Use preorder DFS with a marker for null nodes", "For deserialization, use an iterator/queue over the serialized tokens"]
    },
]
TRIES = [
    {
        "num": 61,
        "name": "Implement Trie (Prefix Tree)",
        "slug": "implement-trie-prefix-tree",
        "difficulty": "medium",
        "topics": ["trie", "design", "string"],
        "pattern": "trie",
        "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 62,
        "description": "A trie (prefix tree) is a tree data structure used to efficiently store and retrieve keys in a dataset of strings. Implement the Trie class with insert, search, and startsWith methods.",
        "examples": [{"input": '["Trie","insert","search","search","startsWith","insert","search"]\n[[],["apple"],["apple"],["app"],["app"],["app"],["app"]]', "output": "[null,null,true,false,true,null,true]", "explanation": "Trie operations"}],
        "constraints": ["1 <= word.length, prefix.length <= 2000", "word and prefix consist only of lowercase English letters", "At most 3 * 10^4 calls in total"],
        "starter_code": {"python": "class Trie:\n    def __init__(self):\n        pass\n    def insert(self, word: str) -> None:\n        pass\n    def search(self, word: str) -> bool:\n        pass\n    def startsWith(self, prefix: str) -> bool:\n        pass", "javascript": "var Trie = function() {\n    \n};\nTrie.prototype.insert = function(word) {\n    \n};\nTrie.prototype.search = function(word) {\n    \n};\nTrie.prototype.startsWith = function(prefix) {\n    \n};"},
        "test_cases": [
            {"input": {"operations": ["Trie","insert","search","search","startsWith","insert","search"], "values": [[],["apple"],["apple"],["app"],["app"],["app"],["app"]]}, "expected": [None,None,True,False,True,None,True]},
            {"input": {"operations": ["Trie","insert","search"], "values": [[],["hello"],["hell"]]}, "expected": [None,None,False]},
            {"input": {"operations": ["Trie","insert","startsWith"], "values": [[],["abc"],["ab"]]}, "expected": [None,None,True]}
        ],
        "optimal_complexity": {"time": "O(m) per operation", "space": "O(n * m)"},
        "hints": ["Each node has a map of children and an end-of-word flag", "Traverse character by character for all operations"]
    },
    {
        "num": 62,
        "name": "Design Add and Search Words Data Structure",
        "slug": "design-add-and-search-words-data-structure",
        "difficulty": "medium",
        "topics": ["trie", "design", "dfs", "string"],
        "pattern": "trie_with_dfs",
        "companies": ["meta", "amazon", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 44,
        "description": "Design a data structure that supports adding new words and finding if a string matches any previously added string. The search word can contain dots '.' where dots can match any letter.",
        "examples": [{"input": '["WordDictionary","addWord","addWord","addWord","search","search","search","search"]\n[[],["bad"],["dad"],["mad"],["pad"],["bad"],[".ad"],["b.."]]', "output": "[null,null,null,null,false,true,true,true]", "explanation": "Wildcard search with dot matching"}],
        "constraints": ["1 <= word.length <= 25", "word in addWord consists of lowercase English letters", "word in search consists of '.' or lowercase English letters", "At most 10^4 calls to addWord and search"],
        "starter_code": {"python": "class WordDictionary:\n    def __init__(self):\n        pass\n    def addWord(self, word: str) -> None:\n        pass\n    def search(self, word: str) -> bool:\n        pass", "javascript": "var WordDictionary = function() {\n    \n};\nWordDictionary.prototype.addWord = function(word) {\n    \n};\nWordDictionary.prototype.search = function(word) {\n    \n};"},
        "test_cases": [
            {"input": {"operations": ["WordDictionary","addWord","addWord","addWord","search","search","search","search"], "values": [[],["bad"],["dad"],["mad"],["pad"],["bad"],[".ad"],["b.."]]}, "expected": [None,None,None,None,False,True,True,True]},
            {"input": {"operations": ["WordDictionary","addWord","search","search"], "values": [[],["a"],["a"],["."]]}, "expected": [None,None,True,True]},
            {"input": {"operations": ["WordDictionary","addWord","search"], "values": [[],["ab"],["a."]]}, "expected": [None,None,True]}
        ],
        "optimal_complexity": {"time": "O(m) add, O(26^m) worst search", "space": "O(n * m)"},
        "hints": ["Build on a standard Trie, but handle '.' with DFS branching", "When encountering '.', try all children recursively"]
    },
    {
        "num": 63,
        "name": "Word Search II",
        "slug": "word-search-ii",
        "difficulty": "hard",
        "topics": ["trie", "backtracking", "matrix"],
        "pattern": "trie_with_backtracking",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 36,
        "description": "Given an m x n board of characters and a list of strings words, return all words on the board. Each word must be constructed from letters of sequentially adjacent cells (horizontally or vertically neighboring). The same letter cell may not be used more than once in a word.",
        "examples": [{"input": 'board = [["o","a","a","n"],["e","t","a","e"],["i","h","k","r"],["i","f","l","v"]], words = ["oath","pea","eat","rain"]', "output": '["eat","oath"]', "explanation": "Only eat and oath can be found on the board"}],
        "constraints": ["m == board.length", "n == board[i].length", "1 <= m, n <= 12", "1 <= words.length <= 3 * 10^4", "1 <= words[i].length <= 10", "board and words[i] consist of lowercase English letters"],
        "starter_code": {"python": "class Solution:\n    def findWords(self, board: List[List[str]], words: List[str]) -> List[str]:\n        pass", "javascript": "var findWords = function(board, words) {\n    \n};"},
        "test_cases": [
            {"input": {"board": [["o","a","a","n"],["e","t","a","e"],["i","h","k","r"],["i","f","l","v"]], "words": ["oath","pea","eat","rain"]}, "expected": ["eat","oath"]},
            {"input": {"board": [["a","b"],["c","d"]], "words": ["abcb"]}, "expected": []},
            {"input": {"board": [["a"]], "words": ["a"]}, "expected": ["a"]}
        ],
        "optimal_complexity": {"time": "O(m * n * 4^L)", "space": "O(W * L)"},
        "hints": ["Build a trie from words, then DFS from each cell on the board", "Prune trie branches as words are found to avoid redundant searches"]
    },
]
HEAP_PQ = [
    {
        "num": 64,
        "name": "Kth Largest Element in a Stream",
        "slug": "kth-largest-element-in-a-stream",
        "difficulty": "easy",
        "topics": ["heap", "design"],
        "pattern": "min_heap",
        "companies": ["amazon", "meta", "apple"],
        "lists": ["neetcode_150"],
        "acceptance": 56,
        "description": "Design a class to find the kth largest element in a stream. Note that it is the kth largest element in sorted order, not the kth distinct element.",
        "examples": [{"input": '["KthLargest","add","add","add","add","add"]\n[[3,[4,5,8,2]],[3],[5],[10],[9],[4]]', "output": "[null,4,5,5,8,8]", "explanation": "Track kth largest as elements are added"}],
        "constraints": ["1 <= k <= 10^4", "0 <= nums.length <= 10^4", "-10^4 <= val <= 10^4", "At most 10^4 calls to add"],
        "starter_code": {"python": "class KthLargest:\n    def __init__(self, k: int, nums: List[int]):\n        pass\n    def add(self, val: int) -> int:\n        pass", "javascript": "var KthLargest = function(k, nums) {\n    \n};\nKthLargest.prototype.add = function(val) {\n    \n};"},
        "test_cases": [
            {"input": {"operations": ["KthLargest","add","add","add","add","add"], "values": [[3,[4,5,8,2]],[3],[5],[10],[9],[4]]}, "expected": [None,4,5,5,8,8]},
            {"input": {"operations": ["KthLargest","add"], "values": [[1,[]],[1]]}, "expected": [None,1]},
            {"input": {"operations": ["KthLargest","add","add"], "values": [[2,[0]],[1],[2]]}, "expected": [None,0,1]}
        ],
        "optimal_complexity": {"time": "O(log k) per add", "space": "O(k)"},
        "hints": ["Maintain a min-heap of size k", "The root of the heap is always the kth largest element"]
    },
    {
        "num": 65,
        "name": "Last Stone Weight",
        "slug": "last-stone-weight",
        "difficulty": "easy",
        "topics": ["heap"],
        "pattern": "max_heap",
        "companies": ["amazon", "google", "adobe"],
        "lists": ["neetcode_150"],
        "acceptance": 65,
        "description": "You are given an array of integers stones where stones[i] is the weight of the ith stone. On each turn, choose the heaviest two stones and smash them together. If they have the same weight, both are destroyed. Otherwise, the heavier stone loses weight equal to the lighter stone. Return the weight of the last remaining stone, or 0 if none remain.",
        "examples": [{"input": "stones = [2,7,4,1,8,1]", "output": "1", "explanation": "Smash 7&8->1, 2&4->2, 1&2->1, 1&1->0, last=1"}],
        "constraints": ["1 <= stones.length <= 30", "1 <= stones[i] <= 1000"],
        "starter_code": {"python": "class Solution:\n    def lastStoneWeight(self, stones: List[int]) -> int:\n        pass", "javascript": "var lastStoneWeight = function(stones) {\n    \n};"},
        "test_cases": [
            {"input": {"stones": [2,7,4,1,8,1]}, "expected": 1},
            {"input": {"stones": [1]}, "expected": 1},
            {"input": {"stones": [2,2]}, "expected": 0}
        ],
        "optimal_complexity": {"time": "O(n log n)", "space": "O(n)"},
        "hints": ["Use a max-heap to always get the two heaviest stones", "In Python, negate values since heapq is a min-heap"]
    },
    {
        "num": 66,
        "name": "K Closest Points to Origin",
        "slug": "k-closest-points-to-origin",
        "difficulty": "medium",
        "topics": ["heap", "sorting"],
        "pattern": "min_heap",
        "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150"],
        "acceptance": 66,
        "description": "Given an array of points where points[i] = [xi, yi] represents a point on the X-Y plane and an integer k, return the k closest points to the origin (0, 0).",
        "examples": [{"input": "points = [[1,3],[-2,2]], k = 1", "output": "[[-2,2]]", "explanation": "Distance of (-2,2) is sqrt(8), (1,3) is sqrt(10)"}],
        "constraints": ["1 <= k <= points.length <= 10^4", "-10^4 <= xi, yi <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def kClosest(self, points: List[List[int]], k: int) -> List[List[int]]:\n        pass", "javascript": "var kClosest = function(points, k) {\n    \n};"},
        "test_cases": [
            {"input": {"points": [[1,3],[-2,2]], "k": 1}, "expected": [[-2,2]]},
            {"input": {"points": [[3,3],[5,-1],[-2,4]], "k": 2}, "expected": [[3,3],[-2,4]]},
            {"input": {"points": [[0,1],[1,0]], "k": 2}, "expected": [[0,1],[1,0]]}
        ],
        "optimal_complexity": {"time": "O(n log k)", "space": "O(k)"},
        "hints": ["Use a max-heap of size k to track closest points", "Compare squared distances to avoid computing square roots"]
    },
    {
        "num": 67,
        "name": "Kth Largest Element in an Array",
        "slug": "kth-largest-element-in-an-array",
        "difficulty": "medium",
        "topics": ["heap", "sorting", "quickselect"],
        "pattern": "quickselect",
        "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150"],
        "acceptance": 66,
        "description": "Given an integer array nums and an integer k, return the kth largest element in the array. Note that it is the kth largest element in sorted order, not the kth distinct element. Solve it without sorting.",
        "examples": [{"input": "nums = [3,2,1,5,6,4], k = 2", "output": "5", "explanation": "The 2nd largest element is 5"}],
        "constraints": ["1 <= k <= nums.length <= 10^5", "-10^4 <= nums[i] <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def findKthLargest(self, nums: List[int], k: int) -> int:\n        pass", "javascript": "var findKthLargest = function(nums, k) {\n    \n};"},
        "test_cases": [
            {"input": {"nums": [3,2,1,5,6,4], "k": 2}, "expected": 5},
            {"input": {"nums": [3,2,3,1,2,4,5,5,6], "k": 4}, "expected": 4},
            {"input": {"nums": [1], "k": 1}, "expected": 1}
        ],
        "optimal_complexity": {"time": "O(n) average", "space": "O(1)"},
        "hints": ["Quickselect partitions like quicksort but only recurses on one side", "A min-heap of size k also works in O(n log k)"]
    },
    {
        "num": 68,
        "name": "Task Scheduler",
        "slug": "task-scheduler",
        "difficulty": "medium",
        "topics": ["heap", "greedy", "hash_map"],
        "pattern": "greedy_scheduling",
        "companies": ["meta", "amazon", "microsoft"],
        "lists": ["neetcode_150"],
        "acceptance": 57,
        "description": "Given a characters array tasks representing CPU tasks (A-Z) and a non-negative integer n representing the cooldown period between two same tasks, return the least number of units of time the CPU will take to finish all tasks.",
        "examples": [{"input": 'tasks = ["A","A","A","B","B","B"], n = 2', "output": "8", "explanation": "A -> B -> idle -> A -> B -> idle -> A -> B"}],
        "constraints": ["1 <= tasks.length <= 10^4", "tasks[i] is uppercase English letter", "0 <= n <= 100"],
        "starter_code": {"python": "class Solution:\n    def leastInterval(self, tasks: List[str], n: int) -> int:\n        pass", "javascript": "var leastInterval = function(tasks, n) {\n    \n};"},
        "test_cases": [
            {"input": {"tasks": ["A","A","A","B","B","B"], "n": 2}, "expected": 8},
            {"input": {"tasks": ["A","A","A","B","B","B"], "n": 0}, "expected": 6},
            {"input": {"tasks": ["A","A","A","A","A","A","B","C","D","E","F","G"], "n": 2}, "expected": 16}
        ],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["The most frequent task determines the frame structure", "Result = max(total_tasks, (maxFreq-1) * (n+1) + countOfMaxFreq)"]
    },
    {
        "num": 69,
        "name": "Design Twitter",
        "slug": "design-twitter",
        "difficulty": "medium",
        "topics": ["heap", "hash_map", "design", "linked_list"],
        "pattern": "merge_k_sorted",
        "companies": ["amazon", "twitter", "meta"],
        "lists": ["neetcode_150"],
        "acceptance": 37,
        "description": "Design a simplified version of Twitter where users can post tweets, follow/unfollow another user, and retrieve the 10 most recent tweets in the user's news feed.",
        "examples": [{"input": '["Twitter","postTweet","getNewsFeed","follow","getNewsFeed","unfollow","getNewsFeed"]\n[[],[1,5],[1],[1,2],[1],[1,2],[1]]', "output": "[null,null,[5],null,[5],null,[5]]", "explanation": "Post, follow/unfollow, and get feed operations"}],
        "constraints": ["1 <= userId, followerId, followeeId <= 500", "0 <= tweetId <= 10^4", "At most 3 * 10^4 calls total"],
        "starter_code": {"python": "class Twitter:\n    def __init__(self):\n        pass\n    def postTweet(self, userId: int, tweetId: int) -> None:\n        pass\n    def getNewsFeed(self, userId: int) -> List[int]:\n        pass\n    def follow(self, followerId: int, followeeId: int) -> None:\n        pass\n    def unfollow(self, followerId: int, followeeId: int) -> None:\n        pass", "javascript": "var Twitter = function() {\n    \n};"},
        "test_cases": [
            {"input": {"operations": ["Twitter","postTweet","getNewsFeed","follow","postTweet","getNewsFeed","unfollow","getNewsFeed"], "values": [[],[1,5],[1],[1,2],[2,6],[1],[1,2],[1]]}, "expected": [None,None,[5],None,None,[6,5],None,[5]]},
            {"input": {"operations": ["Twitter","postTweet","getNewsFeed"], "values": [[],[1,1],[1]]}, "expected": [None,None,[1]]},
            {"input": {"operations": ["Twitter","getNewsFeed"], "values": [[],[1]]}, "expected": [None,[]]}
        ],
        "optimal_complexity": {"time": "O(k log k) getNewsFeed", "space": "O(n)"},
        "hints": ["Use a heap to merge sorted tweet lists from followed users", "Keep tweets timestamped and sorted per user"]
    },
    {
        "num": 70,
        "name": "Find Median from Data Stream",
        "slug": "find-median-from-data-stream",
        "difficulty": "hard",
        "topics": ["heap", "design", "sorting"],
        "pattern": "two_heaps",
        "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 51,
        "description": "The median is the middle value in an ordered integer list. Design a data structure that supports addNum and findMedian operations efficiently.",
        "examples": [{"input": '["MedianFinder","addNum","addNum","findMedian","addNum","findMedian"]\n[[],[1],[2],[],[3],[]]', "output": "[null,null,null,1.5,null,2.0]", "explanation": "After adding 1,2 median is 1.5; after adding 3 median is 2.0"}],
        "constraints": ["-10^5 <= num <= 10^5", "There will be at least one element before findMedian", "At most 5 * 10^4 calls"],
        "starter_code": {"python": "class MedianFinder:\n    def __init__(self):\n        pass\n    def addNum(self, num: int) -> None:\n        pass\n    def findMedian(self) -> float:\n        pass", "javascript": "var MedianFinder = function() {\n    \n};\nMedianFinder.prototype.addNum = function(num) {\n    \n};\nMedianFinder.prototype.findMedian = function() {\n    \n};"},
        "test_cases": [
            {"input": {"operations": ["MedianFinder","addNum","addNum","findMedian","addNum","findMedian"], "values": [[],[1],[2],[],[3],[]]}, "expected": [None,None,None,1.5,None,2.0]},
            {"input": {"operations": ["MedianFinder","addNum","findMedian"], "values": [[],[5],[]]}, "expected": [None,None,5.0]},
            {"input": {"operations": ["MedianFinder","addNum","addNum","findMedian"], "values": [[],[1],[1],[]]}, "expected": [None,None,None,1.0]}
        ],
        "optimal_complexity": {"time": "O(log n) add, O(1) find", "space": "O(n)"},
        "hints": ["Use two heaps: max-heap for lower half, min-heap for upper half", "Balance heaps so they differ in size by at most 1"]
    },
]
BACKTRACKING = [
    {
        "num": 71,
        "name": "Subsets",
        "slug": "subsets",
        "difficulty": "medium",
        "topics": ["backtracking", "arrays"],
        "pattern": "backtracking_subsets",
        "companies": ["meta", "amazon", "bloomberg"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 74,
        "description": "Given an integer array nums of unique elements, return all possible subsets (the power set). The solution set must not contain duplicate subsets. Return the solution in any order.",
        "examples": [{"input": "nums = [1,2,3]", "output": "[[],[1],[2],[1,2],[3],[1,3],[2,3],[1,2,3]]", "explanation": "All 2^3 = 8 subsets"}],
        "constraints": ["1 <= nums.length <= 10", "-10 <= nums[i] <= 10", "All elements are unique"],
        "starter_code": {"python": "class Solution:\n    def subsets(self, nums: List[int]) -> List[List[int]]:\n        pass", "javascript": "var subsets = function(nums) {\n    \n};"},
        "test_cases": [
            {"input": {"nums": [1,2,3]}, "expected": [[],[1],[2],[1,2],[3],[1,3],[2,3],[1,2,3]]},
            {"input": {"nums": [0]}, "expected": [[],[0]]},
            {"input": {"nums": [1,2]}, "expected": [[],[1],[2],[1,2]]}
        ],
        "optimal_complexity": {"time": "O(n * 2^n)", "space": "O(n)"},
        "hints": ["At each index, choose to include or exclude the element", "Use backtracking with a start index to avoid duplicates"]
    },
    {
        "num": 72,
        "name": "Combination Sum",
        "slug": "combination-sum",
        "difficulty": "medium",
        "topics": ["backtracking", "arrays"],
        "pattern": "backtracking_combinations",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 68,
        "description": "Given an array of distinct integers candidates and a target integer target, return a list of all unique combinations of candidates where the chosen numbers sum to target. The same number may be chosen from candidates an unlimited number of times.",
        "examples": [{"input": "candidates = [2,3,6,7], target = 7", "output": "[[2,2,3],[7]]", "explanation": "2+2+3=7 and 7=7"}],
        "constraints": ["1 <= candidates.length <= 30", "2 <= candidates[i] <= 40", "All elements are distinct", "1 <= target <= 40"],
        "starter_code": {"python": "class Solution:\n    def combinationSum(self, candidates: List[int], target: int) -> List[List[int]]:\n        pass", "javascript": "var combinationSum = function(candidates, target) {\n    \n};"},
        "test_cases": [
            {"input": {"candidates": [2,3,6,7], "target": 7}, "expected": [[2,2,3],[7]]},
            {"input": {"candidates": [2,3,5], "target": 8}, "expected": [[2,2,2,2],[2,3,3],[3,5]]},
            {"input": {"candidates": [2], "target": 1}, "expected": []}
        ],
        "optimal_complexity": {"time": "O(n^(t/m))", "space": "O(t/m)"},
        "hints": ["Backtrack with start index, allowing same element to be reused", "Prune branches where remaining target < 0"]
    },
    {
        "num": 73,
        "name": "Permutations",
        "slug": "permutations",
        "difficulty": "medium",
        "topics": ["backtracking", "arrays"],
        "pattern": "backtracking_permutations",
        "companies": ["meta", "amazon", "microsoft"],
        "lists": ["neetcode_150"],
        "acceptance": 75,
        "description": "Given an array nums of distinct integers, return all possible permutations. You can return the answer in any order.",
        "examples": [{"input": "nums = [1,2,3]", "output": "[[1,2,3],[1,3,2],[2,1,3],[2,3,1],[3,1,2],[3,2,1]]", "explanation": "All 3! = 6 permutations"}],
        "constraints": ["1 <= nums.length <= 6", "-10 <= nums[i] <= 10", "All elements are unique"],
        "starter_code": {"python": "class Solution:\n    def permute(self, nums: List[int]) -> List[List[int]]:\n        pass", "javascript": "var permute = function(nums) {\n    \n};"},
        "test_cases": [
            {"input": {"nums": [1,2,3]}, "expected": [[1,2,3],[1,3,2],[2,1,3],[2,3,1],[3,1,2],[3,2,1]]},
            {"input": {"nums": [0,1]}, "expected": [[0,1],[1,0]]},
            {"input": {"nums": [1]}, "expected": [[1]]}
        ],
        "optimal_complexity": {"time": "O(n * n!)", "space": "O(n)"},
        "hints": ["Use a visited set or swap elements in place", "Backtrack by removing the last element after recursion"]
    },
    {
        "num": 74,
        "name": "Subsets II",
        "slug": "subsets-ii",
        "difficulty": "medium",
        "topics": ["backtracking", "arrays"],
        "pattern": "backtracking_subsets",
        "companies": ["amazon", "meta", "bloomberg"],
        "lists": ["neetcode_150"],
        "acceptance": 55,
        "description": "Given an integer array nums that may contain duplicates, return all possible subsets (the power set). The solution set must not contain duplicate subsets. Return the solution in any order.",
        "examples": [{"input": "nums = [1,2,2]", "output": "[[],[1],[1,2],[1,2,2],[2],[2,2]]", "explanation": "Subsets without duplicates"}],
        "constraints": ["1 <= nums.length <= 10", "-10 <= nums[i] <= 10"],
        "starter_code": {"python": "class Solution:\n    def subsetsWithDup(self, nums: List[int]) -> List[List[int]]:\n        pass", "javascript": "var subsetsWithDup = function(nums) {\n    \n};"},
        "test_cases": [
            {"input": {"nums": [1,2,2]}, "expected": [[],[1],[1,2],[1,2,2],[2],[2,2]]},
            {"input": {"nums": [0]}, "expected": [[],[0]]},
            {"input": {"nums": [4,4,4,1,4]}, "expected": [[],[1],[1,4],[1,4,4],[1,4,4,4],[1,4,4,4,4],[4],[4,4],[4,4,4],[4,4,4,4]]}
        ],
        "optimal_complexity": {"time": "O(n * 2^n)", "space": "O(n)"},
        "hints": ["Sort first, then skip duplicates at the same recursion level", "If nums[i] == nums[i-1] and i > start, skip to avoid duplicate subsets"]
    },
    {
        "num": 75,
        "name": "Combination Sum II",
        "slug": "combination-sum-ii",
        "difficulty": "medium",
        "topics": ["backtracking", "arrays"],
        "pattern": "backtracking_combinations",
        "companies": ["amazon", "meta", "apple"],
        "lists": ["neetcode_150"],
        "acceptance": 53,
        "description": "Given a collection of candidate numbers (candidates) and a target number (target), find all unique combinations in candidates where the candidate numbers sum to target. Each number in candidates may only be used once in the combination.",
        "examples": [{"input": "candidates = [10,1,2,7,6,1,5], target = 8", "output": "[[1,1,6],[1,2,5],[1,7],[2,6]]", "explanation": "Unique combinations that sum to 8"}],
        "constraints": ["1 <= candidates.length <= 100", "1 <= candidates[i] <= 50", "1 <= target <= 30"],
        "starter_code": {"python": "class Solution:\n    def combinationSum2(self, candidates: List[int], target: int) -> List[List[int]]:\n        pass", "javascript": "var combinationSum2 = function(candidates, target) {\n    \n};"},
        "test_cases": [
            {"input": {"candidates": [10,1,2,7,6,1,5], "target": 8}, "expected": [[1,1,6],[1,2,5],[1,7],[2,6]]},
            {"input": {"candidates": [2,5,2,1,2], "target": 5}, "expected": [[1,2,2],[5]]},
            {"input": {"candidates": [1], "target": 2}, "expected": []}
        ],
        "optimal_complexity": {"time": "O(2^n)", "space": "O(n)"},
        "hints": ["Sort first, skip duplicates at the same level like Subsets II", "Move to i+1 (not i) since each element can only be used once"]
    },
    {
        "num": 76,
        "name": "Word Search",
        "slug": "word-search",
        "difficulty": "medium",
        "topics": ["backtracking", "matrix"],
        "pattern": "backtracking_grid",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 40,
        "description": "Given an m x n grid of characters board and a string word, return true if word exists in the grid. The word can be constructed from letters of sequentially adjacent cells (horizontally or vertically). The same letter cell may not be used more than once.",
        "examples": [{"input": 'board = [["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]], word = "ABCCED"', "output": "true", "explanation": "The word can be traced on the board"}],
        "constraints": ["m == board.length", "n == board[i].length", "1 <= m, n <= 6", "1 <= word.length <= 15", "board and word consist of uppercase and lowercase English letters"],
        "starter_code": {"python": "class Solution:\n    def exist(self, board: List[List[str]], word: str) -> bool:\n        pass", "javascript": "var exist = function(board, word) {\n    \n};"},
        "test_cases": [
            {"input": {"board": [["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]], "word": "ABCCED"}, "expected": True},
            {"input": {"board": [["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]], "word": "SEE"}, "expected": True},
            {"input": {"board": [["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]], "word": "ABCB"}, "expected": False}
        ],
        "optimal_complexity": {"time": "O(m * n * 4^L)", "space": "O(L)"},
        "hints": ["DFS from each cell, mark visited cells temporarily", "Backtrack by unmarking the cell after exploring all directions"]
    },
    {
        "num": 77,
        "name": "Palindrome Partitioning",
        "slug": "palindrome-partitioning",
        "difficulty": "medium",
        "topics": ["backtracking", "string", "dp"],
        "pattern": "backtracking_partitioning",
        "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150"],
        "acceptance": 63,
        "description": "Given a string s, partition s such that every substring of the partition is a palindrome. Return all possible palindrome partitionings of s.",
        "examples": [{"input": 's = "aab"', "output": '[["a","a","b"],["aa","b"]]', "explanation": "Two ways to partition into palindromes"}],
        "constraints": ["1 <= s.length <= 16", "s contains only lowercase English letters"],
        "starter_code": {"python": "class Solution:\n    def partition(self, s: str) -> List[List[str]]:\n        pass", "javascript": "var partition = function(s) {\n    \n};"},
        "test_cases": [
            {"input": {"s": "aab"}, "expected": [["a","a","b"],["aa","b"]]},
            {"input": {"s": "a"}, "expected": [["a"]]},
            {"input": {"s": "aba"}, "expected": [["a","b","a"],["aba"]]}
        ],
        "optimal_complexity": {"time": "O(n * 2^n)", "space": "O(n)"},
        "hints": ["Try each prefix that is a palindrome, then recurse on the remainder", "Precompute palindrome checks with DP for efficiency"]
    },
    {
        "num": 78,
        "name": "Letter Combinations of a Phone Number",
        "slug": "letter-combinations-of-a-phone-number",
        "difficulty": "medium",
        "topics": ["backtracking", "string"],
        "pattern": "backtracking_combinations",
        "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150"],
        "acceptance": 57,
        "description": "Given a string containing digits from 2-9 inclusive, return all possible letter combinations that the number could represent. Return the answer in any order.",
        "examples": [{"input": 'digits = "23"', "output": '["ad","ae","af","bd","be","bf","cd","ce","cf"]', "explanation": "2->abc, 3->def, all combinations"}],
        "constraints": ["0 <= digits.length <= 4", "digits[i] is a digit in range ['2', '9']"],
        "starter_code": {"python": "class Solution:\n    def letterCombinations(self, digits: str) -> List[str]:\n        pass", "javascript": "var letterCombinations = function(digits) {\n    \n};"},
        "test_cases": [
            {"input": {"digits": "23"}, "expected": ["ad","ae","af","bd","be","bf","cd","ce","cf"]},
            {"input": {"digits": ""}, "expected": []},
            {"input": {"digits": "2"}, "expected": ["a","b","c"]}
        ],
        "optimal_complexity": {"time": "O(4^n)", "space": "O(n)"},
        "hints": ["Map each digit to its letters, then backtrack through each digit", "Build combinations character by character"]
    },
    {
        "num": 79,
        "name": "N-Queens",
        "slug": "n-queens",
        "difficulty": "hard",
        "topics": ["backtracking"],
        "pattern": "backtracking_constraint",
        "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150"],
        "acceptance": 63,
        "description": "The n-queens puzzle is the problem of placing n queens on an n x n chessboard such that no two queens attack each other. Given an integer n, return all distinct solutions to the n-queens puzzle.",
        "examples": [{"input": "n = 4", "output": '[[".Q..","...Q","Q...","..Q."],["..Q.","Q...","...Q",".Q.."]]', "explanation": "Two solutions for 4-queens"}],
        "constraints": ["1 <= n <= 9"],
        "starter_code": {"python": "class Solution:\n    def solveNQueens(self, n: int) -> List[List[str]]:\n        pass", "javascript": "var solveNQueens = function(n) {\n    \n};"},
        "test_cases": [
            {"input": {"n": 4}, "expected": [[".Q..","...Q","Q...","..Q."],["..Q.","Q...","...Q",".Q.."]]},
            {"input": {"n": 1}, "expected": [["Q"]]},
            {"input": {"n": 2}, "expected": []}
        ],
        "optimal_complexity": {"time": "O(n!)", "space": "O(n)"},
        "hints": ["Place queens row by row, tracking columns and diagonals", "Use sets for columns, positive diagonals (r+c), negative diagonals (r-c)"]
    },
]
GRAPHS = [
    {
        "num": 80,
        "name": "Number of Islands",
        "slug": "number-of-islands",
        "difficulty": "medium",
        "topics": ["graphs", "bfs", "dfs", "matrix"],
        "pattern": "graph_traversal",
        "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 57,
        "description": "Given an m x n 2D binary grid which represents a map of '1's (land) and '0's (water), return the number of islands.",
        "examples": [{"input": 'grid = [["1","1","0","0","0"],["1","1","0","0","0"],["0","0","1","0","0"],["0","0","0","1","1"]]', "output": "3", "explanation": "Three distinct islands"}],
        "constraints": ["m == grid.length", "n == grid[i].length", "1 <= m, n <= 300", "grid[i][j] is '0' or '1'"],
        "starter_code": {"python": "class Solution:\n    def numIslands(self, grid: List[List[str]]) -> int:\n        pass", "javascript": "var numIslands = function(grid) {\n    \n};"},
        "test_cases": [
            {"input": {"grid": [["1","1","1","1","0"],["1","1","0","1","0"],["1","1","0","0","0"],["0","0","0","0","0"]]}, "expected": 1},
            {"input": {"grid": [["1","1","0","0","0"],["1","1","0","0","0"],["0","0","1","0","0"],["0","0","0","1","1"]]}, "expected": 3},
            {"input": {"grid": [["0"]]}, "expected": 0}
        ],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(m * n)"},
        "hints": ["DFS/BFS from each unvisited '1', marking all connected land as visited", "Each new traversal represents a new island"]
    },
    {
        "num": 81,
        "name": "Max Area of Island",
        "slug": "max-area-of-island",
        "difficulty": "medium",
        "topics": ["graphs", "dfs", "matrix"],
        "pattern": "graph_traversal",
        "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150"],
        "acceptance": 71,
        "description": "You are given an m x n binary matrix grid. An island is a group of 1's connected 4-directionally. Return the maximum area of an island in grid. If there is no island, return 0.",
        "examples": [{"input": "grid = [[0,0,1,0,0,0],[0,0,0,0,0,0],[0,1,1,0,0,0]]", "output": "3", "explanation": "The largest island has area 3"}],
        "constraints": ["m == grid.length", "n == grid[i].length", "1 <= m, n <= 50", "grid[i][j] is 0 or 1"],
        "starter_code": {"python": "class Solution:\n    def maxAreaOfIsland(self, grid: List[List[int]]) -> int:\n        pass", "javascript": "var maxAreaOfIsland = function(grid) {\n    \n};"},
        "test_cases": [
            {"input": {"grid": [[0,0,1,0,0,0,0,1,0,0,0,0,0],[0,0,0,0,0,0,0,1,1,1,0,0,0],[0,1,1,0,1,0,0,0,0,0,0,0,0],[0,1,0,0,1,1,0,0,1,0,1,0,0],[0,1,0,0,1,1,0,0,1,1,1,0,0],[0,0,0,0,0,0,0,0,0,0,1,0,0],[0,0,0,0,0,0,0,1,1,1,0,0,0],[0,0,0,0,0,0,0,1,1,0,0,0,0]]}, "expected": 6},
            {"input": {"grid": [[0,0,0,0,0,0,0,0]]}, "expected": 0},
            {"input": {"grid": [[1]]}, "expected": 1}
        ],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(m * n)"},
        "hints": ["DFS from each unvisited 1, count cells in each island", "Track and return the maximum count"]
    },
    {
        "num": 82,
        "name": "Clone Graph",
        "slug": "clone-graph",
        "difficulty": "medium",
        "topics": ["graphs", "bfs", "dfs", "hash_map"],
        "pattern": "graph_clone",
        "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 51,
        "description": "Given a reference of a node in a connected undirected graph, return a deep copy (clone) of the graph.",
        "examples": [{"input": "adjList = [[2,4],[1,3],[2,4],[1,3]]", "output": "[[2,4],[1,3],[2,4],[1,3]]", "explanation": "Deep copy of the graph"}],
        "constraints": ["The number of nodes is in range [0, 100]", "1 <= Node.val <= 100", "Node.val is unique for each node"],
        "starter_code": {"python": "class Solution:\n    def cloneGraph(self, node: Optional['Node']) -> Optional['Node']:\n        pass", "javascript": "var cloneGraph = function(node) {\n    \n};"},
        "test_cases": [
            {"input": {"adjList": [[2,4],[1,3],[2,4],[1,3]]}, "expected": [[2,4],[1,3],[2,4],[1,3]]},
            {"input": {"adjList": [[]]}, "expected": [[]]},
            {"input": {"adjList": []}, "expected": []}
        ],
        "optimal_complexity": {"time": "O(V + E)", "space": "O(V)"},
        "hints": ["Use a hash map from original node to cloned node", "BFS or DFS, creating clones as you visit"]
    },
    {
        "num": 83,
        "name": "Walls and Gates",
        "slug": "walls-and-gates",
        "difficulty": "medium",
        "topics": ["graphs", "bfs", "matrix"],
        "pattern": "multi_source_bfs",
        "companies": ["meta", "google", "amazon"],
        "lists": ["neetcode_150"],
        "acceptance": 60,
        "description": "You are given an m x n grid rooms initialized with -1 (wall), 0 (gate), or INF (empty room, 2147483647). Fill each empty room with the distance to its nearest gate.",
        "examples": [{"input": "rooms = [[INF,-1,0,INF],[INF,INF,INF,-1],[INF,-1,INF,-1],[0,-1,INF,INF]]", "output": "[[3,-1,0,1],[2,2,1,-1],[1,-1,2,-1],[0,-1,3,4]]", "explanation": "Each cell shows distance to nearest gate"}],
        "constraints": ["m == rooms.length", "n == rooms[i].length", "1 <= m, n <= 250"],
        "starter_code": {"python": "class Solution:\n    def wallsAndGates(self, rooms: List[List[int]]) -> None:\n        pass", "javascript": "var wallsAndGates = function(rooms) {\n    \n};"},
        "test_cases": [
            {"input": {"rooms": [[2147483647,-1,0,2147483647],[2147483647,2147483647,2147483647,-1],[2147483647,-1,2147483647,-1],[0,-1,2147483647,2147483647]]}, "expected": [[3,-1,0,1],[2,2,1,-1],[1,-1,2,-1],[0,-1,3,4]]},
            {"input": {"rooms": [[-1]]}, "expected": [[-1]]},
            {"input": {"rooms": [[0]]}, "expected": [[0]]}
        ],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(m * n)"},
        "hints": ["Start BFS from all gates simultaneously", "This naturally computes shortest distance from each cell to nearest gate"]
    },
    {
        "num": 84,
        "name": "Pacific Atlantic Water Flow",
        "slug": "pacific-atlantic-water-flow",
        "difficulty": "medium",
        "topics": ["graphs", "dfs", "bfs", "matrix"],
        "pattern": "multi_source_dfs",
        "companies": ["google", "amazon", "meta"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 54,
        "description": "There is an m x n rectangular island bordering the Pacific Ocean (top/left) and Atlantic Ocean (bottom/right). Water can flow to neighboring cells of equal or lower height. Return all cells where water can reach both oceans.",
        "examples": [{"input": "heights = [[1,2,2,3,5],[3,2,3,4,4],[2,4,5,3,1],[6,7,1,4,5],[5,1,1,2,4]]", "output": "[[0,4],[1,3],[1,4],[2,2],[3,0],[3,1],[4,0]]", "explanation": "Cells that can reach both oceans"}],
        "constraints": ["m == heights.length", "n == heights[i].length", "1 <= m, n <= 200", "0 <= heights[i][j] <= 10^5"],
        "starter_code": {"python": "class Solution:\n    def pacificAtlantic(self, heights: List[List[int]]) -> List[List[int]]:\n        pass", "javascript": "var pacificAtlantic = function(heights) {\n    \n};"},
        "test_cases": [
            {"input": {"heights": [[1,2,2,3,5],[3,2,3,4,4],[2,4,5,3,1],[6,7,1,4,5],[5,1,1,2,4]]}, "expected": [[0,4],[1,3],[1,4],[2,2],[3,0],[3,1],[4,0]]},
            {"input": {"heights": [[1]]}, "expected": [[0,0]]},
            {"input": {"heights": [[1,1],[1,1]]}, "expected": [[0,0],[0,1],[1,0],[1,1]]}
        ],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(m * n)"},
        "hints": ["Reverse the problem: DFS from ocean edges going uphill", "Find intersection of cells reachable from Pacific and Atlantic"]
    },
    {
        "num": 85,
        "name": "Surrounded Regions",
        "slug": "surrounded-regions",
        "difficulty": "medium",
        "topics": ["graphs", "dfs", "bfs", "matrix"],
        "pattern": "boundary_dfs",
        "companies": ["google", "amazon", "microsoft"],
        "lists": ["neetcode_150"],
        "acceptance": 36,
        "description": "Given an m x n matrix board containing 'X' and 'O', capture all regions surrounded by 'X' by flipping enclosed 'O's into 'X's. Regions connected to the border are not captured.",
        "examples": [{"input": 'board = [["X","X","X","X"],["X","O","O","X"],["X","X","O","X"],["X","O","X","X"]]', "output": '[["X","X","X","X"],["X","X","X","X"],["X","X","X","X"],["X","O","X","X"]]', "explanation": "Border-connected O survives"}],
        "constraints": ["m == board.length", "n == board[i].length", "1 <= m, n <= 200", "board[i][j] is 'X' or 'O'"],
        "starter_code": {"python": "class Solution:\n    def solve(self, board: List[List[str]]) -> None:\n        pass", "javascript": "var solve = function(board) {\n    \n};"},
        "test_cases": [
            {"input": {"board": [["X","X","X","X"],["X","O","O","X"],["X","X","O","X"],["X","O","X","X"]]}, "expected": [["X","X","X","X"],["X","X","X","X"],["X","X","X","X"],["X","O","X","X"]]},
            {"input": {"board": [["X"]]}, "expected": [["X"]]},
            {"input": {"board": [["O","O"],["O","O"]]}, "expected": [["O","O"],["O","O"]]}
        ],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(m * n)"},
        "hints": ["Mark border-connected O's as safe via DFS from edges", "Then flip remaining O's to X, and safe markers back to O"]
    },
    {
        "num": 86,
        "name": "Rotting Oranges",
        "slug": "rotting-oranges",
        "difficulty": "medium",
        "topics": ["graphs", "bfs", "matrix"],
        "pattern": "multi_source_bfs",
        "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150"],
        "acceptance": 53,
        "description": "You are given an m x n grid where 0 = empty, 1 = fresh orange, 2 = rotten orange. Every minute, fresh oranges adjacent to rotten ones also become rotten. Return minimum minutes until no fresh orange remains, or -1 if impossible.",
        "examples": [{"input": "grid = [[2,1,1],[1,1,0],[0,1,1]]", "output": "4", "explanation": "4 minutes for all oranges to rot"}],
        "constraints": ["m == grid.length", "n == grid[i].length", "1 <= m, n <= 10", "grid[i][j] is 0, 1, or 2"],
        "starter_code": {"python": "class Solution:\n    def orangesRotting(self, grid: List[List[int]]) -> int:\n        pass", "javascript": "var orangesRotting = function(grid) {\n    \n};"},
        "test_cases": [
            {"input": {"grid": [[2,1,1],[1,1,0],[0,1,1]]}, "expected": 4},
            {"input": {"grid": [[2,1,1],[0,1,1],[1,0,1]]}, "expected": -1},
            {"input": {"grid": [[0,2]]}, "expected": 0}
        ],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(m * n)"},
        "hints": ["Multi-source BFS from all rotten oranges simultaneously", "Track fresh count; if any remain after BFS, return -1"]
    },
    {
        "num": 87,
        "name": "Course Schedule",
        "slug": "course-schedule",
        "difficulty": "medium",
        "topics": ["graphs", "topological_sort", "dfs"],
        "pattern": "topological_sort",
        "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 45,
        "description": "There are numCourses courses labeled 0 to numCourses-1. prerequisites[i] = [a, b] means you must take b before a. Return true if you can finish all courses (no cycle in prerequisite graph).",
        "examples": [{"input": "numCourses = 2, prerequisites = [[1,0]]", "output": "true", "explanation": "Take 0 then 1"}],
        "constraints": ["1 <= numCourses <= 2000", "0 <= prerequisites.length <= 5000"],
        "starter_code": {"python": "class Solution:\n    def canFinish(self, numCourses: int, prerequisites: List[List[int]]) -> bool:\n        pass", "javascript": "var canFinish = function(numCourses, prerequisites) {\n    \n};"},
        "test_cases": [
            {"input": {"numCourses": 2, "prerequisites": [[1,0]]}, "expected": True},
            {"input": {"numCourses": 2, "prerequisites": [[1,0],[0,1]]}, "expected": False},
            {"input": {"numCourses": 3, "prerequisites": [[1,0],[2,1]]}, "expected": True}
        ],
        "optimal_complexity": {"time": "O(V + E)", "space": "O(V + E)"},
        "hints": ["Detect if the graph has a cycle", "DFS with three states or Kahn's BFS algorithm"]
    },
    {
        "num": 88,
        "name": "Course Schedule II",
        "slug": "course-schedule-ii",
        "difficulty": "medium",
        "topics": ["graphs", "topological_sort"],
        "pattern": "topological_sort",
        "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150"],
        "acceptance": 48,
        "description": "Return an ordering of courses to finish all courses given prerequisites. If impossible, return empty array.",
        "examples": [{"input": "numCourses = 4, prerequisites = [[1,0],[2,0],[3,1],[3,2]]", "output": "[0,2,1,3]", "explanation": "A valid topological order"}],
        "constraints": ["1 <= numCourses <= 2000", "0 <= prerequisites.length <= numCourses * (numCourses - 1)"],
        "starter_code": {"python": "class Solution:\n    def findOrder(self, numCourses: int, prerequisites: List[List[int]]) -> List[int]:\n        pass", "javascript": "var findOrder = function(numCourses, prerequisites) {\n    \n};"},
        "test_cases": [
            {"input": {"numCourses": 4, "prerequisites": [[1,0],[2,0],[3,1],[3,2]]}, "expected": [0,1,2,3]},
            {"input": {"numCourses": 2, "prerequisites": [[1,0]]}, "expected": [0,1]},
            {"input": {"numCourses": 1, "prerequisites": []}, "expected": [0]}
        ],
        "optimal_complexity": {"time": "O(V + E)", "space": "O(V + E)"},
        "hints": ["Kahn's algorithm: BFS starting from nodes with in-degree 0", "DFS post-order gives reverse topological order"]
    },
    {
        "num": 89,
        "name": "Redundant Connection",
        "slug": "redundant-connection",
        "difficulty": "medium",
        "topics": ["graphs", "union_find"],
        "pattern": "union_find",
        "companies": ["google", "amazon", "microsoft"],
        "lists": ["neetcode_150"],
        "acceptance": 62,
        "description": "A tree with n nodes had one extra edge added. Find the edge that can be removed to make it a valid tree again. If multiple answers, return the one that occurs last in the input.",
        "examples": [{"input": "edges = [[1,2],[1,3],[2,3]]", "output": "[2,3]", "explanation": "Removing [2,3] makes it a tree"}],
        "constraints": ["n == edges.length", "3 <= n <= 1000", "1 <= ai < bi <= n"],
        "starter_code": {"python": "class Solution:\n    def findRedundantConnection(self, edges: List[List[int]]) -> List[int]:\n        pass", "javascript": "var findRedundantConnection = function(edges) {\n    \n};"},
        "test_cases": [
            {"input": {"edges": [[1,2],[1,3],[2,3]]}, "expected": [2,3]},
            {"input": {"edges": [[1,2],[2,3],[3,4],[1,4],[1,5]]}, "expected": [1,4]},
            {"input": {"edges": [[1,2],[1,3],[3,4],[2,4]]}, "expected": [2,4]}
        ],
        "optimal_complexity": {"time": "O(n * alpha(n))", "space": "O(n)"},
        "hints": ["Union-Find: the first edge connecting already-connected nodes is redundant", "Process edges in order, return the first one that creates a cycle"]
    },
    {
        "num": 90,
        "name": "Number of Connected Components in an Undirected Graph",
        "slug": "number-of-connected-components-in-an-undirected-graph",
        "difficulty": "medium",
        "topics": ["graphs", "union_find", "dfs"],
        "pattern": "union_find",
        "companies": ["google", "amazon", "meta"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 62,
        "description": "Given n nodes and a list of undirected edges, return the number of connected components.",
        "examples": [{"input": "n = 5, edges = [[0,1],[1,2],[3,4]]", "output": "2", "explanation": "Components: {0,1,2} and {3,4}"}],
        "constraints": ["1 <= n <= 2000", "1 <= edges.length <= 5000"],
        "starter_code": {"python": "class Solution:\n    def countComponents(self, n: int, edges: List[List[int]]) -> int:\n        pass", "javascript": "var countComponents = function(n, edges) {\n    \n};"},
        "test_cases": [
            {"input": {"n": 5, "edges": [[0,1],[1,2],[3,4]]}, "expected": 2},
            {"input": {"n": 5, "edges": [[0,1],[1,2],[2,3],[3,4]]}, "expected": 1},
            {"input": {"n": 3, "edges": []}, "expected": 3}
        ],
        "optimal_complexity": {"time": "O(V + E)", "space": "O(V)"},
        "hints": ["Union-Find: start with n components, each union decreases by 1", "DFS/BFS: count number of times you start a new traversal"]
    },
    {
        "num": 91,
        "name": "Graph Valid Tree",
        "slug": "graph-valid-tree",
        "difficulty": "medium",
        "topics": ["graphs", "union_find", "dfs"],
        "pattern": "union_find",
        "companies": ["google", "amazon", "meta"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 47,
        "description": "Given n nodes labeled 0 to n-1 and a list of undirected edges, determine if these edges form a valid tree (connected and acyclic).",
        "examples": [{"input": "n = 5, edges = [[0,1],[0,2],[0,3],[1,4]]", "output": "true", "explanation": "Connected, n-1 edges, no cycle"}],
        "constraints": ["1 <= n <= 2000", "0 <= edges.length <= 5000"],
        "starter_code": {"python": "class Solution:\n    def validTree(self, n: int, edges: List[List[int]]) -> bool:\n        pass", "javascript": "var validTree = function(n, edges) {\n    \n};"},
        "test_cases": [
            {"input": {"n": 5, "edges": [[0,1],[0,2],[0,3],[1,4]]}, "expected": True},
            {"input": {"n": 5, "edges": [[0,1],[1,2],[2,3],[1,3],[1,4]]}, "expected": False},
            {"input": {"n": 1, "edges": []}, "expected": True}
        ],
        "optimal_complexity": {"time": "O(V + E)", "space": "O(V)"},
        "hints": ["A valid tree has exactly n-1 edges and is connected", "Union-Find: if any union finds same parent, cycle exists"]
    },
    {
        "num": 92,
        "name": "Word Ladder",
        "slug": "word-ladder",
        "difficulty": "hard",
        "topics": ["graphs", "bfs", "string"],
        "pattern": "bfs_shortest_path",
        "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150"],
        "acceptance": 37,
        "description": "Given beginWord, endWord, and a wordList, find the length of the shortest transformation sequence where each adjacent pair differs by one letter and every word is in the dictionary. Return 0 if no such sequence exists.",
        "examples": [{"input": 'beginWord = "hit", endWord = "cog", wordList = ["hot","dot","dog","lot","log","cog"]', "output": "5", "explanation": "hit -> hot -> dot -> dog -> cog"}],
        "constraints": ["1 <= beginWord.length <= 10", "endWord.length == beginWord.length", "1 <= wordList.length <= 5000"],
        "starter_code": {"python": "class Solution:\n    def ladderLength(self, beginWord: str, endWord: str, wordList: List[str]) -> int:\n        pass", "javascript": "var ladderLength = function(beginWord, endWord, wordList) {\n    \n};"},
        "test_cases": [
            {"input": {"beginWord": "hit", "endWord": "cog", "wordList": ["hot","dot","dog","lot","log","cog"]}, "expected": 5},
            {"input": {"beginWord": "hit", "endWord": "cog", "wordList": ["hot","dot","dog","lot","log"]}, "expected": 0},
            {"input": {"beginWord": "a", "endWord": "c", "wordList": ["a","b","c"]}, "expected": 2}
        ],
        "optimal_complexity": {"time": "O(M^2 * N)", "space": "O(M^2 * N)"},
        "hints": ["BFS from beginWord, each level is one transformation step", "Use wildcard patterns (h*t) to find neighbors efficiently"]
    },
]

ADVANCED_GRAPHS = [
    {
        "num": 93,
        "name": "Reconstruct Itinerary",
        "slug": "reconstruct-itinerary",
        "difficulty": "hard",
        "topics": ["graphs", "dfs", "eulerian_path"],
        "pattern": "eulerian_path",
        "companies": ["google", "amazon", "meta"],
        "lists": ["neetcode_150"],
        "acceptance": 41,
        "description": "You are given a list of airline tickets represented by pairs of departure and arrival airports [from, to]. Reconstruct the itinerary in order starting from 'JFK'. If there are multiple valid itineraries, return the lexicographically smallest one.",
        "examples": [{"input": 'tickets = [["MUC","LHR"],["JFK","MUC"],["SFO","SJC"],["LHR","SFO"]]', "output": '["JFK","MUC","LHR","SFO","SJC"]', "explanation": "The only valid itinerary"}],
        "constraints": ["1 <= tickets.length <= 300", "tickets[i].length == 2", "from_i.length == 3", "to_i.length == 3", "All airports are uppercase English letters", "All tickets form at least one valid itinerary", "Must use all tickets exactly once"],
        "starter_code": {"python": "class Solution:\n    def findItinerary(self, tickets: List[List[str]]) -> List[str]:\n        pass", "javascript": "var findItinerary = function(tickets) {\n    \n};"},
        "test_cases": [
            {"input": {"tickets": [["MUC","LHR"],["JFK","MUC"],["SFO","SJC"],["LHR","SFO"]]}, "expected": ["JFK","MUC","LHR","SFO","SJC"]},
            {"input": {"tickets": [["JFK","SFO"],["JFK","ATL"],["SFO","ATL"],["ATL","JFK"],["ATL","SFO"]]}, "expected": ["JFK","ATL","JFK","SFO","ATL","SFO"]},
            {"input": {"tickets": [["JFK","A"],["A","JFK"]]}, "expected": ["JFK","A","JFK"]}
        ],
        "optimal_complexity": {"time": "O(E log E)", "space": "O(E)"},
        "hints": ["This is a Eulerian path problem - use Hierholzer's algorithm", "Sort destinations lexicographically and use DFS post-order"]
    },
    {
        "num": 94,
        "name": "Min Cost to Connect All Points",
        "slug": "min-cost-to-connect-all-points",
        "difficulty": "medium",
        "topics": ["graphs", "minimum_spanning_tree"],
        "pattern": "prims_algorithm",
        "companies": ["amazon", "microsoft", "google"],
        "lists": ["neetcode_150"],
        "acceptance": 65,
        "description": "You are given an array of points where points[i] = [xi, yi]. The cost of connecting two points is the manhattan distance |xi - xj| + |yi - yj|. Return the minimum cost to make all points connected.",
        "examples": [{"input": "points = [[0,0],[2,2],[3,10],[5,2],[7,0]]", "output": "20", "explanation": "Minimum spanning tree cost is 20"}],
        "constraints": ["1 <= points.length <= 1000", "-10^6 <= xi, yi <= 10^6", "All pairs (xi, yi) are distinct"],
        "starter_code": {"python": "class Solution:\n    def minCostConnectPoints(self, points: List[List[int]]) -> int:\n        pass", "javascript": "var minCostConnectPoints = function(points) {\n    \n};"},
        "test_cases": [
            {"input": {"points": [[0,0],[2,2],[3,10],[5,2],[7,0]]}, "expected": 20},
            {"input": {"points": [[3,12],[-2,5],[-4,1]]}, "expected": 18},
            {"input": {"points": [[0,0]]}, "expected": 0}
        ],
        "optimal_complexity": {"time": "O(n^2 log n)", "space": "O(n^2)"},
        "hints": ["Use Prim's algorithm with a min-heap", "Start from any point, greedily add the cheapest edge to an unvisited point"]
    },
    {
        "num": 95,
        "name": "Network Delay Time",
        "slug": "network-delay-time",
        "difficulty": "medium",
        "topics": ["graphs", "shortest_path"],
        "pattern": "dijkstra",
        "companies": ["google", "amazon", "meta"],
        "lists": ["neetcode_150"],
        "acceptance": 52,
        "description": "You are given a network of n nodes labeled 1 to n. Given times, a list of travel times as directed edges times[i] = (u, v, w), and a source node k, return the minimum time it takes for all nodes to receive the signal, or -1 if impossible.",
        "examples": [{"input": "times = [[2,1,1],[2,3,1],[3,4,1]], n = 4, k = 2", "output": "2", "explanation": "Signal reaches all nodes in 2 time units"}],
        "constraints": ["1 <= k <= n <= 100", "1 <= times.length <= 6000", "1 <= u, v <= n", "u != v", "0 <= w <= 100", "All (u, v) pairs are unique"],
        "starter_code": {"python": "class Solution:\n    def networkDelayTime(self, times: List[List[int]], n: int, k: int) -> int:\n        pass", "javascript": "var networkDelayTime = function(times, n, k) {\n    \n};"},
        "test_cases": [
            {"input": {"times": [[2,1,1],[2,3,1],[3,4,1]], "n": 4, "k": 2}, "expected": 2},
            {"input": {"times": [[1,2,1]], "n": 2, "k": 1}, "expected": 1},
            {"input": {"times": [[1,2,1]], "n": 2, "k": 2}, "expected": -1}
        ],
        "optimal_complexity": {"time": "O(E log V)", "space": "O(V + E)"},
        "hints": ["Use Dijkstra's algorithm from source node k", "Answer is the maximum shortest distance, or -1 if any node is unreachable"]
    },
    {
        "num": 96,
        "name": "Swim in Rising Water",
        "slug": "swim-in-rising-water",
        "difficulty": "hard",
        "topics": ["graphs", "binary_search", "heap"],
        "pattern": "dijkstra_grid",
        "companies": ["google", "amazon", "goldman_sachs"],
        "lists": ["neetcode_150"],
        "acceptance": 59,
        "description": "You are given an n x n grid where grid[i][j] represents the elevation at (i,j). At time t, the water depth is t everywhere. You can swim to adjacent cells when both cells have elevation <= t. Starting at (0,0), find the least time to reach (n-1,n-1).",
        "examples": [{"input": "grid = [[0,2],[1,3]]", "output": "3", "explanation": "At time 3, all cells are accessible"}],
        "constraints": ["n == grid.length == grid[i].length", "1 <= n <= 50", "0 <= grid[i][j] < n^2", "Each value in grid is unique"],
        "starter_code": {"python": "class Solution:\n    def swimInWater(self, grid: List[List[int]]) -> int:\n        pass", "javascript": "var swimInWater = function(grid) {\n    \n};"},
        "test_cases": [
            {"input": {"grid": [[0,2],[1,3]]}, "expected": 3},
            {"input": {"grid": [[0,1,2,3,4],[24,23,22,21,5],[12,13,14,15,16],[11,17,18,19,20],[10,9,8,7,6]]}, "expected": 16},
            {"input": {"grid": [[0]]}, "expected": 0}
        ],
        "optimal_complexity": {"time": "O(n^2 log n)", "space": "O(n^2)"},
        "hints": ["Modified Dijkstra: minimize the maximum elevation along the path", "Use a min-heap tracking max elevation to reach each cell"]
    },
    {
        "num": 97,
        "name": "Alien Dictionary",
        "slug": "alien-dictionary",
        "difficulty": "hard",
        "topics": ["graphs", "topological_sort"],
        "pattern": "topological_sort",
        "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150", "blind_75"],
        "acceptance": 35,
        "description": "There is a new alien language that uses the English alphabet but with a different order. Given a list of words sorted lexicographically by the rules of this new language, derive the order of letters. If invalid, return empty string.",
        "examples": [{"input": 'words = ["wrt","wrf","er","ett","rftt"]', "output": '"wertf"', "explanation": "The alien alphabet order"}],
        "constraints": ["1 <= words.length <= 100", "1 <= words[i].length <= 100", "words[i] consists of lowercase English letters"],
        "starter_code": {"python": "class Solution:\n    def alienOrder(self, words: List[str]) -> str:\n        pass", "javascript": "var alienOrder = function(words) {\n    \n};"},
        "test_cases": [
            {"input": {"words": ["wrt","wrf","er","ett","rftt"]}, "expected": "wertf"},
            {"input": {"words": ["z","x"]}, "expected": "zx"},
            {"input": {"words": ["z","x","z"]}, "expected": ""}
        ],
        "optimal_complexity": {"time": "O(C)", "space": "O(1)"},
        "hints": ["Compare adjacent words to find ordering constraints between characters", "Build a graph and do topological sort; detect cycles for invalid input"]
    },
    {
        "num": 98,
        "name": "Cheapest Flights Within K Stops",
        "slug": "cheapest-flights-within-k-stops",
        "difficulty": "medium",
        "topics": ["graphs", "shortest_path", "dp"],
        "pattern": "bellman_ford",
        "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150"],
        "acceptance": 39,
        "description": "There are n cities connected by some number of flights. Given flights array (from, to, price), find the cheapest price from src to dst with at most k stops. Return -1 if no such route exists.",
        "examples": [{"input": "n = 4, flights = [[0,1,100],[1,2,100],[2,0,100],[1,3,600],[2,3,200]], src = 0, dst = 3, k = 1", "output": "700", "explanation": "0->1->3 costs 700 with 1 stop"}],
        "constraints": ["1 <= n <= 100", "0 <= flights.length <= n*(n-1)/2", "0 <= src, dst, from, to < n", "1 <= price <= 10^4", "0 <= k <= n - 1"],
        "starter_code": {"python": "class Solution:\n    def findCheapestPrice(self, n: int, flights: List[List[int]], src: int, dst: int, k: int) -> int:\n        pass", "javascript": "var findCheapestPrice = function(n, flights, src, dst, k) {\n    \n};"},
        "test_cases": [
            {"input": {"n": 4, "flights": [[0,1,100],[1,2,100],[2,0,100],[1,3,600],[2,3,200]], "src": 0, "dst": 3, "k": 1}, "expected": 700},
            {"input": {"n": 3, "flights": [[0,1,100],[1,2,100],[0,2,500]], "src": 0, "dst": 2, "k": 1}, "expected": 200},
            {"input": {"n": 3, "flights": [[0,1,100],[1,2,100],[0,2,500]], "src": 0, "dst": 2, "k": 0}, "expected": 500}
        ],
        "optimal_complexity": {"time": "O(k * E)", "space": "O(V)"},
        "hints": ["Bellman-Ford with k+1 iterations works perfectly here", "Copy previous distances to avoid using updated values within same round"]
    },
]
DP_1D = [
    {
        "num": 99, "name": "Climbing Stairs", "slug": "climbing-stairs", "difficulty": "easy",
        "topics": ["dp"], "pattern": "fibonacci_dp", "companies": ["amazon", "google", "apple"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 52,
        "description": "You are climbing a staircase. It takes n steps to reach the top. Each time you can either climb 1 or 2 steps. In how many distinct ways can you climb to the top?",
        "examples": [{"input": "n = 3", "output": "3", "explanation": "1+1+1, 1+2, 2+1"}],
        "constraints": ["1 <= n <= 45"],
        "starter_code": {"python": "class Solution:\n    def climbStairs(self, n: int) -> int:\n        pass", "javascript": "var climbStairs = function(n) {\n    \n};"},
        "test_cases": [{"input": {"n": 2}, "expected": 2}, {"input": {"n": 3}, "expected": 3}, {"input": {"n": 5}, "expected": 8}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["dp[i] = dp[i-1] + dp[i-2], just like Fibonacci", "You only need the last two values"]
    },
    {
        "num": 100, "name": "Min Cost Climbing Stairs", "slug": "min-cost-climbing-stairs", "difficulty": "easy",
        "topics": ["dp"], "pattern": "linear_dp", "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150"], "acceptance": 62,
        "description": "You are given an integer array cost where cost[i] is the cost of the ith step. You can start from step 0 or step 1. Once you pay the cost, you can climb one or two steps. Return the minimum cost to reach the top of the floor.",
        "examples": [{"input": "cost = [10,15,20]", "output": "15", "explanation": "Start at step 1, pay 15 and climb two steps to the top"}],
        "constraints": ["2 <= cost.length <= 1000", "0 <= cost[i] <= 999"],
        "starter_code": {"python": "class Solution:\n    def minCostClimbingStairs(self, cost: List[int]) -> int:\n        pass", "javascript": "var minCostClimbingStairs = function(cost) {\n    \n};"},
        "test_cases": [{"input": {"cost": [10,15,20]}, "expected": 15}, {"input": {"cost": [1,100,1,1,1,100,1,1,100,1]}, "expected": 6}, {"input": {"cost": [0,0,0,1]}, "expected": 0}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["dp[i] = cost[i] + min(dp[i-1], dp[i-2])", "Answer is min(dp[n-1], dp[n-2])"]
    },
    {
        "num": 101, "name": "House Robber", "slug": "house-robber", "difficulty": "medium",
        "topics": ["dp"], "pattern": "linear_dp", "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 49,
        "description": "You are a professional robber. Each house has a certain amount of money stashed. Adjacent houses have connected security systems. Determine the maximum amount of money you can rob without alerting the police (no two adjacent houses).",
        "examples": [{"input": "nums = [1,2,3,1]", "output": "4", "explanation": "Rob house 1 and 3: 1 + 3 = 4"}],
        "constraints": ["1 <= nums.length <= 100", "0 <= nums[i] <= 400"],
        "starter_code": {"python": "class Solution:\n    def rob(self, nums: List[int]) -> int:\n        pass", "javascript": "var rob = function(nums) {\n    \n};"},
        "test_cases": [{"input": {"nums": [1,2,3,1]}, "expected": 4}, {"input": {"nums": [2,7,9,3,1]}, "expected": 12}, {"input": {"nums": [2,1,1,2]}, "expected": 4}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["dp[i] = max(dp[i-1], dp[i-2] + nums[i])", "At each house, decide to rob it or skip it"]
    },
    {
        "num": 102, "name": "House Robber II", "slug": "house-robber-ii", "difficulty": "medium",
        "topics": ["dp"], "pattern": "circular_dp", "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 41,
        "description": "All houses at this place are arranged in a circle (first and last are neighbors). Given an array representing the amount of money of each house, return the maximum amount you can rob without robbing two adjacent houses.",
        "examples": [{"input": "nums = [2,3,2]", "output": "3", "explanation": "Cannot rob house 1 and 3 (adjacent in circle), rob house 2"}],
        "constraints": ["1 <= nums.length <= 100", "0 <= nums[i] <= 1000"],
        "starter_code": {"python": "class Solution:\n    def rob(self, nums: List[int]) -> int:\n        pass", "javascript": "var rob = function(nums) {\n    \n};"},
        "test_cases": [{"input": {"nums": [2,3,2]}, "expected": 3}, {"input": {"nums": [1,2,3,1]}, "expected": 4}, {"input": {"nums": [1,2,3]}, "expected": 3}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Run House Robber on nums[0..n-2] and nums[1..n-1], take the max", "This handles the circular constraint by never picking both first and last"]
    },
    {
        "num": 103, "name": "Longest Palindromic Substring", "slug": "longest-palindromic-substring", "difficulty": "medium",
        "topics": ["dp", "string"], "pattern": "expand_from_center", "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 33,
        "description": "Given a string s, return the longest palindromic substring in s.",
        "examples": [{"input": 's = "babad"', "output": '"bab"', "explanation": "'aba' is also a valid answer"}],
        "constraints": ["1 <= s.length <= 1000", "s consists of only digits and English letters"],
        "starter_code": {"python": "class Solution:\n    def longestPalindrome(self, s: str) -> str:\n        pass", "javascript": "var longestPalindrome = function(s) {\n    \n};"},
        "test_cases": [{"input": {"s": "babad"}, "expected": "bab"}, {"input": {"s": "cbbd"}, "expected": "bb"}, {"input": {"s": "a"}, "expected": "a"}],
        "optimal_complexity": {"time": "O(n^2)", "space": "O(1)"},
        "hints": ["Expand around each center (both odd and even length palindromes)", "Track the start and length of the longest palindrome found"]
    },
    {
        "num": 104, "name": "Palindromic Substrings", "slug": "palindromic-substrings", "difficulty": "medium",
        "topics": ["dp", "string"], "pattern": "expand_from_center", "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 66,
        "description": "Given a string s, return the number of palindromic substrings in it. A string is a palindrome when it reads the same backward as forward. A substring is a contiguous sequence of characters within the string.",
        "examples": [{"input": 's = "abc"', "output": "3", "explanation": "Three palindromic substrings: a, b, c"}],
        "constraints": ["1 <= s.length <= 1000", "s consists of lowercase English letters"],
        "starter_code": {"python": "class Solution:\n    def countSubstrings(self, s: str) -> int:\n        pass", "javascript": "var countSubstrings = function(s) {\n    \n};"},
        "test_cases": [{"input": {"s": "abc"}, "expected": 3}, {"input": {"s": "aaa"}, "expected": 6}, {"input": {"s": "aba"}, "expected": 4}],
        "optimal_complexity": {"time": "O(n^2)", "space": "O(1)"},
        "hints": ["Expand around each center, count each valid expansion", "Each character is a center for odd-length, each pair for even-length"]
    },
    {
        "num": 105, "name": "Decode Ways", "slug": "decode-ways", "difficulty": "medium",
        "topics": ["dp", "string"], "pattern": "linear_dp", "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 32,
        "description": "A message containing letters from A-Z can be encoded to numbers using A=1, B=2, ..., Z=26. Given a string s containing only digits, return the number of ways to decode it.",
        "examples": [{"input": 's = "12"', "output": "2", "explanation": "'AB' (1,2) or 'L' (12)"}],
        "constraints": ["1 <= s.length <= 100", "s contains only digits and may contain leading zeros"],
        "starter_code": {"python": "class Solution:\n    def numDecodings(self, s: str) -> int:\n        pass", "javascript": "var numDecodings = function(s) {\n    \n};"},
        "test_cases": [{"input": {"s": "12"}, "expected": 2}, {"input": {"s": "226"}, "expected": 3}, {"input": {"s": "06"}, "expected": 0}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["dp[i] depends on whether s[i] and s[i-1:i+1] form valid codes", "Handle '0' carefully - it can only be part of '10' or '20'"]
    },
    {
        "num": 106, "name": "Coin Change", "slug": "coin-change", "difficulty": "medium",
        "topics": ["dp"], "pattern": "unbounded_knapsack", "companies": ["amazon", "google", "apple"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 42,
        "description": "You are given coins of different denominations and a total amount. Return the fewest number of coins needed to make up that amount. If not possible, return -1.",
        "examples": [{"input": "coins = [1,5,10,25], amount = 30", "output": "2", "explanation": "25 + 5 = 30"}],
        "constraints": ["1 <= coins.length <= 12", "1 <= coins[i] <= 2^31 - 1", "0 <= amount <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def coinChange(self, coins: List[int], amount: int) -> int:\n        pass", "javascript": "var coinChange = function(coins, amount) {\n    \n};"},
        "test_cases": [{"input": {"coins": [1,5,10,25], "amount": 30}, "expected": 2}, {"input": {"coins": [2], "amount": 3}, "expected": -1}, {"input": {"coins": [1], "amount": 0}, "expected": 0}],
        "optimal_complexity": {"time": "O(amount * n)", "space": "O(amount)"},
        "hints": ["dp[i] = min coins to make amount i", "dp[i] = min(dp[i - coin] + 1) for each coin"]
    },
    {
        "num": 107, "name": "Maximum Product Subarray", "slug": "maximum-product-subarray", "difficulty": "medium",
        "topics": ["dp", "arrays"], "pattern": "linear_dp", "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 34,
        "description": "Given an integer array nums, find a subarray that has the largest product, and return the product.",
        "examples": [{"input": "nums = [2,3,-2,4]", "output": "6", "explanation": "[2,3] has the largest product 6"}],
        "constraints": ["1 <= nums.length <= 2 * 10^4", "-10 <= nums[i] <= 10", "The product of any prefix or suffix is guaranteed to fit in a 32-bit integer"],
        "starter_code": {"python": "class Solution:\n    def maxProduct(self, nums: List[int]) -> int:\n        pass", "javascript": "var maxProduct = function(nums) {\n    \n};"},
        "test_cases": [{"input": {"nums": [2,3,-2,4]}, "expected": 6}, {"input": {"nums": [-2,0,-1]}, "expected": 0}, {"input": {"nums": [-2,3,-4]}, "expected": 24}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Track both max and min product ending at current position", "A negative number can turn a min into a max when multiplied"]
    },
    {
        "num": 108, "name": "Word Break", "slug": "word-break", "difficulty": "medium",
        "topics": ["dp", "string", "hash_map"], "pattern": "linear_dp", "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 46,
        "description": "Given a string s and a dictionary of strings wordDict, return true if s can be segmented into a space-separated sequence of one or more dictionary words.",
        "examples": [{"input": 's = "leetcode", wordDict = ["leet","code"]', "output": "true", "explanation": "'leet code' is a valid segmentation"}],
        "constraints": ["1 <= s.length <= 300", "1 <= wordDict.length <= 1000", "1 <= wordDict[i].length <= 20", "s and wordDict[i] consist of only lowercase English letters", "All strings in wordDict are unique"],
        "starter_code": {"python": "class Solution:\n    def wordBreak(self, s: str, wordDict: List[str]) -> bool:\n        pass", "javascript": "var wordBreak = function(s, wordDict) {\n    \n};"},
        "test_cases": [{"input": {"s": "leetcode", "wordDict": ["leet","code"]}, "expected": True}, {"input": {"s": "applepenapple", "wordDict": ["apple","pen"]}, "expected": True}, {"input": {"s": "catsandog", "wordDict": ["cats","dog","sand","and","cat"]}, "expected": False}],
        "optimal_complexity": {"time": "O(n^2)", "space": "O(n)"},
        "hints": ["dp[i] = true if s[0..i] can be segmented", "For each i, check all j < i where dp[j] and s[j..i] in dict"]
    },
    {
        "num": 109, "name": "Longest Increasing Subsequence", "slug": "longest-increasing-subsequence", "difficulty": "medium",
        "topics": ["dp", "binary_search"], "pattern": "patience_sort", "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 53,
        "description": "Given an integer array nums, return the length of the longest strictly increasing subsequence.",
        "examples": [{"input": "nums = [10,9,2,5,3,7,101,18]", "output": "4", "explanation": "[2,3,7,101] or [2,5,7,101]"}],
        "constraints": ["1 <= nums.length <= 2500", "-10^4 <= nums[i] <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def lengthOfLIS(self, nums: List[int]) -> int:\n        pass", "javascript": "var lengthOfLIS = function(nums) {\n    \n};"},
        "test_cases": [{"input": {"nums": [10,9,2,5,3,7,101,18]}, "expected": 4}, {"input": {"nums": [0,1,0,3,2,3]}, "expected": 4}, {"input": {"nums": [7,7,7,7,7,7,7]}, "expected": 1}],
        "optimal_complexity": {"time": "O(n log n)", "space": "O(n)"},
        "hints": ["O(n^2) DP: dp[i] = 1 + max(dp[j]) where j < i and nums[j] < nums[i]", "O(n log n): maintain a tails array and binary search for insertion point"]
    },
    {
        "num": 110, "name": "Partition Equal Subset Sum", "slug": "partition-equal-subset-sum", "difficulty": "medium",
        "topics": ["dp"], "pattern": "0_1_knapsack", "companies": ["amazon", "meta", "apple"],
        "lists": ["neetcode_150"],
        "acceptance": 46,
        "description": "Given an integer array nums, return true if you can partition the array into two subsets such that the sum of elements in both subsets is equal.",
        "examples": [{"input": "nums = [1,5,11,5]", "output": "true", "explanation": "[1,5,5] and [11] both sum to 11"}],
        "constraints": ["1 <= nums.length <= 200", "1 <= nums[i] <= 100"],
        "starter_code": {"python": "class Solution:\n    def canPartition(self, nums: List[int]) -> bool:\n        pass", "javascript": "var canPartition = function(nums) {\n    \n};"},
        "test_cases": [{"input": {"nums": [1,5,11,5]}, "expected": True}, {"input": {"nums": [1,2,3,5]}, "expected": False}, {"input": {"nums": [1,2,5]}, "expected": False}],
        "optimal_complexity": {"time": "O(n * sum)", "space": "O(sum)"},
        "hints": ["If total sum is odd, return false. Target = sum / 2", "0/1 knapsack: dp[j] = can we form sum j using some subset"]
    },
]
DP_2D = [
    {
        "num": 111, "name": "Unique Paths", "slug": "unique-paths", "difficulty": "medium",
        "topics": ["dp", "math"], "pattern": "grid_dp", "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 63,
        "description": "There is a robot on an m x n grid. The robot is initially at the top-left corner and tries to move to the bottom-right corner. It can only move either down or right. How many possible unique paths are there?",
        "examples": [{"input": "m = 3, n = 7", "output": "28", "explanation": "28 unique paths from top-left to bottom-right"}],
        "constraints": ["1 <= m, n <= 100"],
        "starter_code": {"python": "class Solution:\n    def uniquePaths(self, m: int, n: int) -> int:\n        pass", "javascript": "var uniquePaths = function(m, n) {\n    \n};"},
        "test_cases": [{"input": {"m": 3, "n": 7}, "expected": 28}, {"input": {"m": 3, "n": 2}, "expected": 3}, {"input": {"m": 1, "n": 1}, "expected": 1}],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(n)"},
        "hints": ["dp[i][j] = dp[i-1][j] + dp[i][j-1]", "Can optimize to 1D since each row only depends on previous row"]
    },
    {
        "num": 112, "name": "Longest Common Subsequence", "slug": "longest-common-subsequence", "difficulty": "medium",
        "topics": ["dp", "string"], "pattern": "two_string_dp", "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 58,
        "description": "Given two strings text1 and text2, return the length of their longest common subsequence. If there is no common subsequence, return 0.",
        "examples": [{"input": 'text1 = "abcde", text2 = "ace"', "output": "3", "explanation": "LCS is 'ace'"}],
        "constraints": ["1 <= text1.length, text2.length <= 1000", "text1 and text2 consist of only lowercase English characters"],
        "starter_code": {"python": "class Solution:\n    def longestCommonSubsequence(self, text1: str, text2: str) -> int:\n        pass", "javascript": "var longestCommonSubsequence = function(text1, text2) {\n    \n};"},
        "test_cases": [{"input": {"text1": "abcde", "text2": "ace"}, "expected": 3}, {"input": {"text1": "abc", "text2": "abc"}, "expected": 3}, {"input": {"text1": "abc", "text2": "def"}, "expected": 0}],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(min(m, n))"},
        "hints": ["If chars match, dp[i][j] = 1 + dp[i-1][j-1]", "Otherwise dp[i][j] = max(dp[i-1][j], dp[i][j-1])"]
    },
    {
        "num": 113, "name": "Best Time to Buy and Sell Stock with Cooldown", "slug": "best-time-to-buy-and-sell-stock-with-cooldown", "difficulty": "medium",
        "topics": ["dp"], "pattern": "state_machine_dp", "companies": ["amazon", "google", "goldman_sachs"],
        "lists": ["neetcode_150"], "acceptance": 54,
        "description": "You are given an array of stock prices. Find the maximum profit with as many transactions as you like, but after you sell you must wait one day before you buy again (cooldown).",
        "examples": [{"input": "prices = [1,2,3,0,2]", "output": "3", "explanation": "buy, sell, cooldown, buy, sell"}],
        "constraints": ["1 <= prices.length <= 5000", "0 <= prices[i] <= 1000"],
        "starter_code": {"python": "class Solution:\n    def maxProfit(self, prices: List[int]) -> int:\n        pass", "javascript": "var maxProfit = function(prices) {\n    \n};"},
        "test_cases": [{"input": {"prices": [1,2,3,0,2]}, "expected": 3}, {"input": {"prices": [1]}, "expected": 0}, {"input": {"prices": [1,2,4]}, "expected": 3}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Track three states: holding, sold (cooldown), not holding", "State transitions: hold = max(hold, notHold - price), sold = hold + price, notHold = max(notHold, sold)"]
    },
    {
        "num": 114, "name": "Coin Change II", "slug": "coin-change-ii", "difficulty": "medium",
        "topics": ["dp"], "pattern": "unbounded_knapsack", "companies": ["amazon", "google", "bloomberg"],
        "lists": ["neetcode_150"], "acceptance": 59,
        "description": "Return the number of combinations that make up the given amount using the given coin denominations. You may use each coin an unlimited number of times.",
        "examples": [{"input": "amount = 5, coins = [1,2,5]", "output": "4", "explanation": "5=5, 5=2+2+1, 5=2+1+1+1, 5=1+1+1+1+1"}],
        "constraints": ["1 <= coins.length <= 300", "1 <= coins[i] <= 5000", "All coins are unique", "0 <= amount <= 5000"],
        "starter_code": {"python": "class Solution:\n    def change(self, amount: int, coins: List[int]) -> int:\n        pass", "javascript": "var change = function(amount, coins) {\n    \n};"},
        "test_cases": [{"input": {"amount": 5, "coins": [1,2,5]}, "expected": 4}, {"input": {"amount": 3, "coins": [2]}, "expected": 0}, {"input": {"amount": 0, "coins": [7]}, "expected": 1}],
        "optimal_complexity": {"time": "O(amount * n)", "space": "O(amount)"},
        "hints": ["Iterate coins in outer loop to avoid counting permutations", "dp[j] += dp[j - coin] for each coin"]
    },
    {
        "num": 115, "name": "Target Sum", "slug": "target-sum", "difficulty": "medium",
        "topics": ["dp", "backtracking"], "pattern": "0_1_knapsack", "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150"], "acceptance": 45,
        "description": "You are given an integer array nums and an integer target. You want to build an expression by adding '+' or '-' before each integer. Return the number of different expressions that evaluate to target.",
        "examples": [{"input": "nums = [1,1,1,1,1], target = 3", "output": "5", "explanation": "Five ways to assign +/- to get sum 3"}],
        "constraints": ["1 <= nums.length <= 20", "0 <= nums[i] <= 1000", "0 <= sum(nums[i]) <= 1000", "-1000 <= target <= 1000"],
        "starter_code": {"python": "class Solution:\n    def findTargetSumWays(self, nums: List[int], target: int) -> int:\n        pass", "javascript": "var findTargetSumWays = function(nums, target) {\n    \n};"},
        "test_cases": [{"input": {"nums": [1,1,1,1,1], "target": 3}, "expected": 5}, {"input": {"nums": [1], "target": 1}, "expected": 1}, {"input": {"nums": [1,0], "target": 1}, "expected": 2}],
        "optimal_complexity": {"time": "O(n * sum)", "space": "O(sum)"},
        "hints": ["Convert to subset sum: find subset P where sum(P) = (target + total) / 2", "Use 0/1 knapsack DP on the transformed problem"]
    },
    {
        "num": 116, "name": "Interleaving String", "slug": "interleaving-string", "difficulty": "medium",
        "topics": ["dp", "string"], "pattern": "two_string_dp", "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150"], "acceptance": 37,
        "description": "Given strings s1, s2, and s3, determine whether s3 is formed by an interleaving of s1 and s2. An interleaving is a configuration where s3 contains all characters of s1 and s2 and preserves the relative order of each.",
        "examples": [{"input": 's1 = "aabcc", s2 = "dbbca", s3 = "aadbbcbcac"', "output": "true", "explanation": "s3 interleaves s1 and s2"}],
        "constraints": ["0 <= s1.length, s2.length <= 100", "0 <= s3.length <= 200", "s1, s2, and s3 consist of lowercase English letters"],
        "starter_code": {"python": "class Solution:\n    def isInterleave(self, s1: str, s2: str, s3: str) -> bool:\n        pass", "javascript": "var isInterleave = function(s1, s2, s3) {\n    \n};"},
        "test_cases": [{"input": {"s1": "aabcc", "s2": "dbbca", "s3": "aadbbcbcac"}, "expected": True}, {"input": {"s1": "aabcc", "s2": "dbbca", "s3": "aadbbbaccc"}, "expected": False}, {"input": {"s1": "", "s2": "", "s3": ""}, "expected": True}],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(n)"},
        "hints": ["dp[i][j] = can s1[:i] and s2[:j] interleave to form s3[:i+j]", "Check len(s1)+len(s2)==len(s3) first"]
    },
    {
        "num": 117, "name": "Longest Increasing Path in a Matrix", "slug": "longest-increasing-path-in-a-matrix", "difficulty": "hard",
        "topics": ["dp", "dfs", "matrix"], "pattern": "dfs_memoization", "companies": ["google", "amazon", "meta"],
        "lists": ["neetcode_150"], "acceptance": 52,
        "description": "Given an m x n integers matrix, return the length of the longest increasing path. From each cell, you can move in four directions (up, down, left, right). You may NOT move diagonally or move outside the boundary.",
        "examples": [{"input": "matrix = [[9,9,4],[6,6,8],[2,1,1]]", "output": "4", "explanation": "Path: 1->2->6->9"}],
        "constraints": ["m == matrix.length", "n == matrix[i].length", "1 <= m, n <= 200", "0 <= matrix[i][j] <= 2^31 - 1"],
        "starter_code": {"python": "class Solution:\n    def longestIncreasingPath(self, matrix: List[List[int]]) -> int:\n        pass", "javascript": "var longestIncreasingPath = function(matrix) {\n    \n};"},
        "test_cases": [{"input": {"matrix": [[9,9,4],[6,6,8],[2,1,1]]}, "expected": 4}, {"input": {"matrix": [[3,4,5],[3,2,6],[2,2,1]]}, "expected": 4}, {"input": {"matrix": [[1]]}, "expected": 1}],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(m * n)"},
        "hints": ["DFS with memoization from each cell", "No visited set needed since path is strictly increasing (no cycles)"]
    },
    {
        "num": 118, "name": "Distinct Subsequences", "slug": "distinct-subsequences", "difficulty": "hard",
        "topics": ["dp", "string"], "pattern": "two_string_dp", "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150"], "acceptance": 44,
        "description": "Given two strings s and t, return the number of distinct subsequences of s which equals t.",
        "examples": [{"input": 's = "rabbbit", t = "rabbit"', "output": "3", "explanation": "Three ways to choose 'rabbit' from 'rabbbit'"}],
        "constraints": ["1 <= s.length, t.length <= 1000", "s and t consist of English letters"],
        "starter_code": {"python": "class Solution:\n    def numDistinct(self, s: str, t: str) -> int:\n        pass", "javascript": "var numDistinct = function(s, t) {\n    \n};"},
        "test_cases": [{"input": {"s": "rabbbit", "t": "rabbit"}, "expected": 3}, {"input": {"s": "babgbag", "t": "bag"}, "expected": 5}, {"input": {"s": "a", "t": "b"}, "expected": 0}],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(n)"},
        "hints": ["dp[i][j] = number of ways to form t[:j] from s[:i]", "If s[i]==t[j]: dp[i][j] = dp[i-1][j-1] + dp[i-1][j], else dp[i-1][j]"]
    },
    {
        "num": 119, "name": "Edit Distance", "slug": "edit-distance", "difficulty": "medium",
        "topics": ["dp", "string"], "pattern": "two_string_dp", "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150"], "acceptance": 53,
        "description": "Given two strings word1 and word2, return the minimum number of operations required to convert word1 to word2. You have three operations: insert, delete, or replace a character.",
        "examples": [{"input": 'word1 = "horse", word2 = "ros"', "output": "3", "explanation": "horse -> rorse -> rose -> ros"}],
        "constraints": ["0 <= word1.length, word2.length <= 500", "word1 and word2 consist of lowercase English letters"],
        "starter_code": {"python": "class Solution:\n    def minDistance(self, word1: str, word2: str) -> int:\n        pass", "javascript": "var minDistance = function(word1, word2) {\n    \n};"},
        "test_cases": [{"input": {"word1": "horse", "word2": "ros"}, "expected": 3}, {"input": {"word1": "intention", "word2": "execution"}, "expected": 5}, {"input": {"word1": "", "word2": "a"}, "expected": 1}],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(n)"},
        "hints": ["dp[i][j] = min operations to convert word1[:i] to word2[:j]", "If chars match: dp[i-1][j-1]; else: 1 + min(insert, delete, replace)"]
    },
    {
        "num": 120, "name": "Burst Balloons", "slug": "burst-balloons", "difficulty": "hard",
        "topics": ["dp"], "pattern": "interval_dp", "companies": ["google", "amazon", "microsoft"],
        "lists": ["neetcode_150"], "acceptance": 57,
        "description": "You are given n balloons with numbers on them. Bursting balloon i gives coins nums[i-1]*nums[i]*nums[i+1]. Find the maximum coins you can collect by bursting all balloons wisely.",
        "examples": [{"input": "nums = [3,1,5,8]", "output": "167", "explanation": "Optimal order: 1,5,3,8 giving 3*1*5 + 3*5*8 + 1*3*8 + 1*8*1 = 167"}],
        "constraints": ["n == nums.length", "1 <= n <= 300", "0 <= nums[i] <= 100"],
        "starter_code": {"python": "class Solution:\n    def maxCoins(self, nums: List[int]) -> int:\n        pass", "javascript": "var maxCoins = function(nums) {\n    \n};"},
        "test_cases": [{"input": {"nums": [3,1,5,8]}, "expected": 167}, {"input": {"nums": [1,5]}, "expected": 10}, {"input": {"nums": [5]}, "expected": 5}],
        "optimal_complexity": {"time": "O(n^3)", "space": "O(n^2)"},
        "hints": ["Think of which balloon to burst LAST in a range, not first", "dp[l][r] = max coins from bursting all balloons between l and r"]
    },
    {
        "num": 121, "name": "Regular Expression Matching", "slug": "regular-expression-matching", "difficulty": "hard",
        "topics": ["dp", "string"], "pattern": "two_string_dp", "companies": ["google", "meta", "amazon"],
        "lists": ["neetcode_150"], "acceptance": 28,
        "description": "Given an input string s and a pattern p, implement regular expression matching with support for '.' (matches any single character) and '*' (matches zero or more of the preceding element).",
        "examples": [{"input": 's = "aa", p = "a*"', "output": "true", "explanation": "'a*' matches zero or more 'a's"}],
        "constraints": ["1 <= s.length <= 20", "1 <= p.length <= 20", "s contains only lowercase English letters", "p contains only lowercase English letters, '.', and '*'", "Each '*' has a valid preceding character"],
        "starter_code": {"python": "class Solution:\n    def isMatch(self, s: str, p: str) -> bool:\n        pass", "javascript": "var isMatch = function(s, p) {\n    \n};"},
        "test_cases": [{"input": {"s": "aa", "p": "a"}, "expected": False}, {"input": {"s": "aa", "p": "a*"}, "expected": True}, {"input": {"s": "ab", "p": ".*"}, "expected": True}],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(m * n)"},
        "hints": ["dp[i][j] = does s[:i] match p[:j]", "Handle '*': either use 0 occurrences (dp[i][j-2]) or match current char and stay (dp[i-1][j])"]
    },
]
GREEDY = [
    {
        "num": 122, "name": "Maximum Subarray", "slug": "maximum-subarray", "difficulty": "medium",
        "topics": ["greedy", "dp", "arrays"], "pattern": "kadane", "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 50,
        "description": "Given an integer array nums, find the subarray with the largest sum, and return its sum.",
        "examples": [{"input": "nums = [-2,1,-3,4,-1,2,1,-5,4]", "output": "6", "explanation": "Subarray [4,-1,2,1] has the largest sum 6"}],
        "constraints": ["1 <= nums.length <= 10^5", "-10^4 <= nums[i] <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def maxSubArray(self, nums: List[int]) -> int:\n        pass", "javascript": "var maxSubArray = function(nums) {\n    \n};"},
        "test_cases": [{"input": {"nums": [-2,1,-3,4,-1,2,1,-5,4]}, "expected": 6}, {"input": {"nums": [1]}, "expected": 1}, {"input": {"nums": [5,4,-1,7,8]}, "expected": 23}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Kadane's algorithm: track current sum and global max", "Reset current sum to 0 when it goes negative"]
    },
    {
        "num": 123, "name": "Jump Game", "slug": "jump-game", "difficulty": "medium",
        "topics": ["greedy", "arrays"], "pattern": "greedy_forward", "companies": ["amazon", "google", "microsoft"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 38,
        "description": "You are given an integer array nums. You are initially at the first index. Each element represents your maximum jump length from that position. Return true if you can reach the last index.",
        "examples": [{"input": "nums = [2,3,1,1,4]", "output": "true", "explanation": "Jump 1 to index 1, then 3 to the last index"}],
        "constraints": ["1 <= nums.length <= 10^4", "0 <= nums[i] <= 10^5"],
        "starter_code": {"python": "class Solution:\n    def canJump(self, nums: List[int]) -> bool:\n        pass", "javascript": "var canJump = function(nums) {\n    \n};"},
        "test_cases": [{"input": {"nums": [2,3,1,1,4]}, "expected": True}, {"input": {"nums": [3,2,1,0,4]}, "expected": False}, {"input": {"nums": [0]}, "expected": True}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Track the farthest reachable index as you iterate", "If current index > farthest, you can't proceed"]
    },
    {
        "num": 124, "name": "Jump Game II", "slug": "jump-game-ii", "difficulty": "medium",
        "topics": ["greedy", "arrays"], "pattern": "greedy_bfs", "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150"], "acceptance": 39,
        "description": "You are given a 0-indexed array of integers nums. You are initially at nums[0]. Each element represents the maximum length of a forward jump. Return the minimum number of jumps to reach nums[n - 1]. You can assume you can always reach the last index.",
        "examples": [{"input": "nums = [2,3,1,1,4]", "output": "2", "explanation": "Jump 1 step to index 1, then 3 steps to the last index"}],
        "constraints": ["1 <= nums.length <= 10^4", "0 <= nums[i] <= 1000", "It is guaranteed that you can reach nums[n - 1]"],
        "starter_code": {"python": "class Solution:\n    def jump(self, nums: List[int]) -> int:\n        pass", "javascript": "var jump = function(nums) {\n    \n};"},
        "test_cases": [{"input": {"nums": [2,3,1,1,4]}, "expected": 2}, {"input": {"nums": [2,3,0,1,4]}, "expected": 2}, {"input": {"nums": [1]}, "expected": 0}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Think of it as BFS levels: each jump is one level", "Track the farthest reachable in current level and the end of current level"]
    },
    {
        "num": 125, "name": "Gas Station", "slug": "gas-station", "difficulty": "medium",
        "topics": ["greedy", "arrays"], "pattern": "greedy_circular", "companies": ["amazon", "google", "bloomberg"],
        "lists": ["neetcode_150"], "acceptance": 45,
        "description": "There are n gas stations along a circular route. Given gas[i] and cost[i] for traveling from station i to i+1, return the starting gas station's index if you can travel around the circuit once clockwise, otherwise return -1. If a solution exists, it is guaranteed to be unique.",
        "examples": [{"input": "gas = [1,2,3,4,5], cost = [3,4,5,1,2]", "output": "3", "explanation": "Start at station 3 with 4 units of gas"}],
        "constraints": ["n == gas.length == cost.length", "1 <= n <= 10^5", "0 <= gas[i], cost[i] <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def canCompleteCircuit(self, gas: List[int], cost: List[int]) -> int:\n        pass", "javascript": "var canCompleteCircuit = function(gas, cost) {\n    \n};"},
        "test_cases": [{"input": {"gas": [1,2,3,4,5], "cost": [3,4,5,1,2]}, "expected": 3}, {"input": {"gas": [2,3,4], "cost": [3,4,3]}, "expected": -1}, {"input": {"gas": [5,1,2,3,4], "cost": [4,4,1,5,1]}, "expected": 4}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["If total gas >= total cost, a solution exists", "Track running tank; if it goes negative, restart from next station"]
    },
    {
        "num": 126, "name": "Hand of Straights", "slug": "hand-of-straights", "difficulty": "medium",
        "topics": ["greedy", "hash_map", "sorting"], "pattern": "greedy_grouping", "companies": ["google", "amazon", "microsoft"],
        "lists": ["neetcode_150"], "acceptance": 56,
        "description": "Alice has some cards. She wants to rearrange them into groups so that each group is of size groupSize, and consists of groupSize consecutive cards. Return true if she can, false otherwise.",
        "examples": [{"input": "hand = [1,2,3,6,2,3,4,7,8], groupSize = 3", "output": "true", "explanation": "Groups: [1,2,3], [2,3,4], [6,7,8]"}],
        "constraints": ["1 <= hand.length <= 10^4", "0 <= hand[i] <= 10^9", "1 <= groupSize <= hand.length"],
        "starter_code": {"python": "class Solution:\n    def isNStraightHand(self, hand: List[int], groupSize: int) -> bool:\n        pass", "javascript": "var isNStraightHand = function(hand, groupSize) {\n    \n};"},
        "test_cases": [{"input": {"hand": [1,2,3,6,2,3,4,7,8], "groupSize": 3}, "expected": True}, {"input": {"hand": [1,2,3,4,5], "groupSize": 4}, "expected": False}, {"input": {"hand": [1,1,2,2,3,3], "groupSize": 3}, "expected": True}],
        "optimal_complexity": {"time": "O(n log n)", "space": "O(n)"},
        "hints": ["Sort and use a frequency map", "Greedily form groups starting from the smallest available card"]
    },
    {
        "num": 127, "name": "Merge Triplets to Form Target Triplet", "slug": "merge-triplets-to-form-target-triplet", "difficulty": "medium",
        "topics": ["greedy", "arrays"], "pattern": "greedy_selection", "companies": ["google", "amazon", "meta"],
        "lists": ["neetcode_150"], "acceptance": 64,
        "description": "You are given a 2D array triplets where triplets[i] = [ai, bi, ci] and a target = [x, y, z]. Return true if it is possible to obtain the target triplet as the max of chosen triplets (element-wise max).",
        "examples": [{"input": "triplets = [[2,5,3],[1,8,4],[1,7,5]], target = [2,7,5]", "output": "true", "explanation": "Choose triplets [2,5,3] and [1,7,5], max = [2,7,5]"}],
        "constraints": ["1 <= triplets.length <= 10^5", "triplets[i].length == target.length == 3", "1 <= ai, bi, ci, x, y, z <= 1000"],
        "starter_code": {"python": "class Solution:\n    def mergeTriplets(self, triplets: List[List[int]], target: List[int]) -> bool:\n        pass", "javascript": "var mergeTriplets = function(triplets, target) {\n    \n};"},
        "test_cases": [{"input": {"triplets": [[2,5,3],[1,8,4],[1,7,5]], "target": [2,7,5]}, "expected": True}, {"input": {"triplets": [[3,4,5],[4,5,6]], "target": [3,2,5]}, "expected": False}, {"input": {"triplets": [[2,5,3],[2,3,4],[1,2,5],[5,2,3]], "target": [5,5,5]}, "expected": True}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Skip triplets where any value exceeds the target", "Track which target positions have been matched"]
    },
    {
        "num": 128, "name": "Partition Labels", "slug": "partition-labels", "difficulty": "medium",
        "topics": ["greedy", "hash_map", "string"], "pattern": "greedy_interval", "companies": ["amazon", "google", "meta"],
        "lists": ["neetcode_150"], "acceptance": 79,
        "description": "You are given a string s. We want to partition the string into as many parts as possible so that each letter appears in at most one part. Return a list of integers representing the size of these parts.",
        "examples": [{"input": 's = "ababcbacadefegdehijhklij"', "output": "[9,7,8]", "explanation": "Partition: 'ababcbaca', 'defegde', 'hijhklij'"}],
        "constraints": ["1 <= s.length <= 500", "s consists of lowercase English letters"],
        "starter_code": {"python": "class Solution:\n    def partitionLabels(self, s: str) -> List[int]:\n        pass", "javascript": "var partitionLabels = function(s) {\n    \n};"},
        "test_cases": [{"input": {"s": "ababcbacadefegdehijhklij"}, "expected": [9,7,8]}, {"input": {"s": "eccbbbbdec"}, "expected": [10]}, {"input": {"s": "abc"}, "expected": [1,1,1]}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Record the last occurrence of each character", "Extend the current partition end to the max last occurrence of chars seen"]
    },
    {
        "num": 129, "name": "Valid Parenthesis String", "slug": "valid-parenthesis-string", "difficulty": "medium",
        "topics": ["greedy", "string", "dp"], "pattern": "greedy_range", "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150"], "acceptance": 34,
        "description": "Given a string s containing only '(', ')' and '*', return true if s is valid. '*' can be treated as '(', ')', or an empty string.",
        "examples": [{"input": 's = "(*))"', "output": "true", "explanation": "Treat * as ( to balance"}],
        "constraints": ["1 <= s.length <= 100", "s consists of '(', ')' and '*'"],
        "starter_code": {"python": "class Solution:\n    def checkValidString(self, s: str) -> bool:\n        pass", "javascript": "var checkValidString = function(s) {\n    \n};"},
        "test_cases": [{"input": {"s": "()"},"expected": True}, {"input": {"s": "(*)"},"expected": True}, {"input": {"s": "(*))"},"expected": True}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Track a range [lo, hi] of possible open parenthesis counts", "lo decreases with ) or *, hi increases with ( or *; if hi < 0 -> false"]
    },
]
INTERVALS = [
    {
        "num": 130, "name": "Insert Interval", "slug": "insert-interval", "difficulty": "medium",
        "topics": ["intervals", "arrays"], "pattern": "interval_merge", "companies": ["google", "meta", "amazon"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 39,
        "description": "You are given an array of non-overlapping intervals sorted by start, and a new interval. Insert the new interval and merge if necessary. Return the resulting array of non-overlapping intervals.",
        "examples": [{"input": "intervals = [[1,3],[6,9]], newInterval = [2,5]", "output": "[[1,5],[6,9]]", "explanation": "New interval [2,5] merges with [1,3]"}],
        "constraints": ["0 <= intervals.length <= 10^4", "intervals[i].length == 2", "0 <= start_i <= end_i <= 10^5", "intervals is sorted by start_i", "newInterval.length == 2"],
        "starter_code": {"python": "class Solution:\n    def insert(self, intervals: List[List[int]], newInterval: List[int]) -> List[List[int]]:\n        pass", "javascript": "var insert = function(intervals, newInterval) {\n    \n};"},
        "test_cases": [{"input": {"intervals": [[1,3],[6,9]], "newInterval": [2,5]}, "expected": [[1,5],[6,9]]}, {"input": {"intervals": [[1,2],[3,5],[6,7],[8,10],[12,16]], "newInterval": [4,8]}, "expected": [[1,2],[3,10],[12,16]]}, {"input": {"intervals": [], "newInterval": [5,7]}, "expected": [[5,7]]}],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["Add all intervals that end before newInterval starts", "Merge overlapping intervals, then add remaining"]
    },
    {
        "num": 131, "name": "Merge Intervals", "slug": "merge-intervals", "difficulty": "medium",
        "topics": ["intervals", "arrays", "sorting"], "pattern": "interval_merge", "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 46,
        "description": "Given an array of intervals where intervals[i] = [start_i, end_i], merge all overlapping intervals and return an array of the non-overlapping intervals.",
        "examples": [{"input": "intervals = [[1,3],[2,6],[8,10],[15,18]]", "output": "[[1,6],[8,10],[15,18]]", "explanation": "[1,3] and [2,6] overlap -> [1,6]"}],
        "constraints": ["1 <= intervals.length <= 10^4", "intervals[i].length == 2", "0 <= start_i <= end_i <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def merge(self, intervals: List[List[int]]) -> List[List[int]]:\n        pass", "javascript": "var merge = function(intervals) {\n    \n};"},
        "test_cases": [{"input": {"intervals": [[1,3],[2,6],[8,10],[15,18]]}, "expected": [[1,6],[8,10],[15,18]]}, {"input": {"intervals": [[1,4],[4,5]]}, "expected": [[1,5]]}, {"input": {"intervals": [[1,4],[0,4]]}, "expected": [[0,4]]}],
        "optimal_complexity": {"time": "O(n log n)", "space": "O(n)"},
        "hints": ["Sort intervals by start time", "If current interval overlaps with previous, extend the end; otherwise add new"]
    },
    {
        "num": 132, "name": "Non-overlapping Intervals", "slug": "non-overlapping-intervals", "difficulty": "medium",
        "topics": ["intervals", "greedy", "sorting"], "pattern": "interval_scheduling", "companies": ["amazon", "meta", "google"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 50,
        "description": "Given an array of intervals, return the minimum number of intervals you need to remove to make the rest non-overlapping.",
        "examples": [{"input": "intervals = [[1,2],[2,3],[3,4],[1,3]]", "output": "1", "explanation": "Remove [1,3] to make the rest non-overlapping"}],
        "constraints": ["1 <= intervals.length <= 10^5", "intervals[i].length == 2", "-5 * 10^4 <= start_i < end_i <= 5 * 10^4"],
        "starter_code": {"python": "class Solution:\n    def eraseOverlapIntervals(self, intervals: List[List[int]]) -> int:\n        pass", "javascript": "var eraseOverlapIntervals = function(intervals) {\n    \n};"},
        "test_cases": [{"input": {"intervals": [[1,2],[2,3],[3,4],[1,3]]}, "expected": 1}, {"input": {"intervals": [[1,2],[1,2],[1,2]]}, "expected": 2}, {"input": {"intervals": [[1,2],[2,3]]}, "expected": 0}],
        "optimal_complexity": {"time": "O(n log n)", "space": "O(1)"},
        "hints": ["Sort by end time, greedily keep intervals that end earliest", "Count overlapping intervals that must be removed"]
    },
    {
        "num": 133, "name": "Meeting Rooms", "slug": "meeting-rooms", "difficulty": "easy",
        "topics": ["intervals", "sorting"], "pattern": "interval_overlap", "companies": ["meta", "amazon", "bloomberg"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 58,
        "description": "Given an array of meeting time intervals where intervals[i] = [start_i, end_i], determine if a person could attend all meetings (no overlaps).",
        "examples": [{"input": "intervals = [[0,30],[5,10],[15,20]]", "output": "false", "explanation": "[0,30] overlaps with [5,10] and [15,20]"}],
        "constraints": ["0 <= intervals.length <= 10^4", "intervals[i].length == 2", "0 <= start_i < end_i <= 10^6"],
        "starter_code": {"python": "class Solution:\n    def canAttendMeetings(self, intervals: List[List[int]]) -> bool:\n        pass", "javascript": "var canAttendMeetings = function(intervals) {\n    \n};"},
        "test_cases": [{"input": {"intervals": [[0,30],[5,10],[15,20]]}, "expected": False}, {"input": {"intervals": [[7,10],[2,4]]}, "expected": True}, {"input": {"intervals": []}, "expected": True}],
        "optimal_complexity": {"time": "O(n log n)", "space": "O(1)"},
        "hints": ["Sort by start time", "Check if any meeting starts before the previous one ends"]
    },
    {
        "num": 134, "name": "Meeting Rooms II", "slug": "meeting-rooms-ii", "difficulty": "medium",
        "topics": ["intervals", "heap", "sorting"], "pattern": "sweep_line", "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 50,
        "description": "Given an array of meeting time intervals, find the minimum number of conference rooms required.",
        "examples": [{"input": "intervals = [[0,30],[5,10],[15,20]]", "output": "2", "explanation": "[0,30] and [5,10] overlap, needing 2 rooms"}],
        "constraints": ["1 <= intervals.length <= 10^4", "0 <= start_i < end_i <= 10^6"],
        "starter_code": {"python": "class Solution:\n    def minMeetingRooms(self, intervals: List[List[int]]) -> int:\n        pass", "javascript": "var minMeetingRooms = function(intervals) {\n    \n};"},
        "test_cases": [{"input": {"intervals": [[0,30],[5,10],[15,20]]}, "expected": 2}, {"input": {"intervals": [[7,10],[2,4]]}, "expected": 1}, {"input": {"intervals": [[1,5],[2,6],[3,7]]}, "expected": 3}],
        "optimal_complexity": {"time": "O(n log n)", "space": "O(n)"},
        "hints": ["Sort start and end times separately, use two pointers", "Or use a min-heap tracking end times of current meetings"]
    },
    {
        "num": 135, "name": "Minimum Interval to Include Each Query", "slug": "minimum-interval-to-include-each-query", "difficulty": "hard",
        "topics": ["intervals", "heap", "sorting"], "pattern": "sweep_line", "companies": ["google", "amazon", "microsoft"],
        "lists": ["neetcode_150"], "acceptance": 50,
        "description": "You are given a 2D integer array intervals and an integer array queries. For each query, find the size of the smallest interval that contains it. If no interval contains a query, answer is -1.",
        "examples": [{"input": "intervals = [[1,4],[2,4],[3,6],[4,4]], queries = [2,3,4,5]", "output": "[3,3,1,4]", "explanation": "Smallest intervals containing each query"}],
        "constraints": ["1 <= intervals.length <= 10^5", "1 <= queries.length <= 10^5", "intervals[i].length == 2", "1 <= left_i <= right_i <= 10^7", "1 <= queries[j] <= 10^7"],
        "starter_code": {"python": "class Solution:\n    def minInterval(self, intervals: List[List[int]], queries: List[int]) -> List[int]:\n        pass", "javascript": "var minInterval = function(intervals, queries) {\n    \n};"},
        "test_cases": [{"input": {"intervals": [[1,4],[2,4],[3,6],[4,4]], "queries": [2,3,4,5]}, "expected": [3,3,1,4]}, {"input": {"intervals": [[2,3],[2,5],[1,8],[20,25]], "queries": [2,19,5,22]}, "expected": [2,-1,4,6]}, {"input": {"intervals": [[1,1]], "queries": [1,2]}, "expected": [1,-1]}],
        "optimal_complexity": {"time": "O((n+q) log n)", "space": "O(n + q)"},
        "hints": ["Sort intervals by start and queries by value", "Use a min-heap of (size, end) and process queries in sorted order"]
    },
]
MATH_GEOMETRY = [
    {
        "num": 136, "name": "Rotate Image", "slug": "rotate-image", "difficulty": "medium",
        "topics": ["math", "matrix"], "pattern": "matrix_rotation", "companies": ["amazon", "microsoft", "google"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 70,
        "description": "You are given an n x n 2D matrix representing an image. Rotate the image by 90 degrees clockwise. You must rotate the image in-place.",
        "examples": [{"input": "matrix = [[1,2,3],[4,5,6],[7,8,9]]", "output": "[[7,4,1],[8,5,2],[9,6,3]]", "explanation": "90 degree clockwise rotation"}],
        "constraints": ["n == matrix.length == matrix[i].length", "1 <= n <= 20", "-1000 <= matrix[i][j] <= 1000"],
        "starter_code": {"python": "class Solution:\n    def rotate(self, matrix: List[List[int]]) -> None:\n        pass", "javascript": "var rotate = function(matrix) {\n    \n};"},
        "test_cases": [{"input": {"matrix": [[1,2,3],[4,5,6],[7,8,9]]}, "expected": [[7,4,1],[8,5,2],[9,6,3]]}, {"input": {"matrix": [[5,1,9,11],[2,4,8,10],[13,3,6,7],[15,14,12,16]]}, "expected": [[15,13,2,5],[14,3,4,1],[12,6,8,9],[16,7,10,11]]}, {"input": {"matrix": [[1]]}, "expected": [[1]]}],
        "optimal_complexity": {"time": "O(n^2)", "space": "O(1)"},
        "hints": ["Transpose the matrix, then reverse each row", "Transpose: swap matrix[i][j] with matrix[j][i]"]
    },
    {
        "num": 137, "name": "Spiral Matrix", "slug": "spiral-matrix", "difficulty": "medium",
        "topics": ["math", "matrix"], "pattern": "spiral_traversal", "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 44,
        "description": "Given an m x n matrix, return all elements of the matrix in spiral order.",
        "examples": [{"input": "matrix = [[1,2,3],[4,5,6],[7,8,9]]", "output": "[1,2,3,6,9,8,7,4,5]", "explanation": "Spiral order traversal"}],
        "constraints": ["m == matrix.length", "n == matrix[i].length", "1 <= m, n <= 10", "-100 <= matrix[i][j] <= 100"],
        "starter_code": {"python": "class Solution:\n    def spiralOrder(self, matrix: List[List[int]]) -> List[int]:\n        pass", "javascript": "var spiralOrder = function(matrix) {\n    \n};"},
        "test_cases": [{"input": {"matrix": [[1,2,3],[4,5,6],[7,8,9]]}, "expected": [1,2,3,6,9,8,7,4,5]}, {"input": {"matrix": [[1,2,3,4],[5,6,7,8],[9,10,11,12]]}, "expected": [1,2,3,4,8,12,11,10,9,5,6,7]}, {"input": {"matrix": [[1]]}, "expected": [1]}],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(1)"},
        "hints": ["Use four boundaries: top, bottom, left, right", "Shrink boundaries after traversing each edge"]
    },
    {
        "num": 138, "name": "Set Matrix Zeroes", "slug": "set-matrix-zeroes", "difficulty": "medium",
        "topics": ["math", "matrix"], "pattern": "in_place_marking", "companies": ["amazon", "meta", "microsoft"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 51,
        "description": "Given an m x n integer matrix, if an element is 0, set its entire row and column to 0's. You must do it in place.",
        "examples": [{"input": "matrix = [[1,1,1],[1,0,1],[1,1,1]]", "output": "[[1,0,1],[0,0,0],[1,0,1]]", "explanation": "Row and column of the zero element are set to 0"}],
        "constraints": ["m == matrix.length", "n == matrix[0].length", "1 <= m, n <= 200", "-2^31 <= matrix[i][j] <= 2^31 - 1"],
        "starter_code": {"python": "class Solution:\n    def setZeroes(self, matrix: List[List[int]]) -> None:\n        pass", "javascript": "var setZeroes = function(matrix) {\n    \n};"},
        "test_cases": [{"input": {"matrix": [[1,1,1],[1,0,1],[1,1,1]]}, "expected": [[1,0,1],[0,0,0],[1,0,1]]}, {"input": {"matrix": [[0,1,2,0],[3,4,5,2],[1,3,1,5]]}, "expected": [[0,0,0,0],[0,4,5,0],[0,3,1,0]]}, {"input": {"matrix": [[1]]}, "expected": [[1]]}],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(1)"},
        "hints": ["Use first row and first column as markers", "Need a separate flag for whether first row/column should be zeroed"]
    },
    {
        "num": 139, "name": "Happy Number", "slug": "happy-number", "difficulty": "easy",
        "topics": ["math", "hash_map"], "pattern": "cycle_detection", "companies": ["amazon", "apple", "google"],
        "lists": ["neetcode_150"], "acceptance": 55,
        "description": "Write an algorithm to determine if a number n is happy. A happy number is defined by repeatedly replacing the number by the sum of the squares of its digits until it equals 1 (happy) or loops endlessly in a cycle (not happy).",
        "examples": [{"input": "n = 19", "output": "true", "explanation": "1^2+9^2=82, 8^2+2^2=68, 6^2+8^2=100, 1^2+0^2+0^2=1"}],
        "constraints": ["1 <= n <= 2^31 - 1"],
        "starter_code": {"python": "class Solution:\n    def isHappy(self, n: int) -> bool:\n        pass", "javascript": "var isHappy = function(n) {\n    \n};"},
        "test_cases": [{"input": {"n": 19}, "expected": True}, {"input": {"n": 2}, "expected": False}, {"input": {"n": 1}, "expected": True}],
        "optimal_complexity": {"time": "O(log n)", "space": "O(1)"},
        "hints": ["Use a set to detect cycles", "Or use Floyd's cycle detection (slow/fast pointers)"]
    },
    {
        "num": 140, "name": "Plus One", "slug": "plus-one", "difficulty": "easy",
        "topics": ["math", "arrays"], "pattern": "carry_propagation", "companies": ["google", "amazon", "apple"],
        "lists": ["neetcode_150"], "acceptance": 43,
        "description": "You are given a large integer represented as an integer array digits, where each digits[i] is the ith digit of the integer. Increment the large integer by one and return the resulting array of digits.",
        "examples": [{"input": "digits = [1,2,3]", "output": "[1,2,4]", "explanation": "123 + 1 = 124"}],
        "constraints": ["1 <= digits.length <= 100", "0 <= digits[i] <= 9", "The integer does not contain any leading zero except the number 0 itself"],
        "starter_code": {"python": "class Solution:\n    def plusOne(self, digits: List[int]) -> List[int]:\n        pass", "javascript": "var plusOne = function(digits) {\n    \n};"},
        "test_cases": [{"input": {"digits": [1,2,3]}, "expected": [1,2,4]}, {"input": {"digits": [9,9,9]}, "expected": [1,0,0,0]}, {"input": {"digits": [0]}, "expected": [1]}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["Start from the rightmost digit, add 1 with carry", "If carry propagates past the first digit, prepend 1"]
    },
    {
        "num": 141, "name": "Pow(x, n)", "slug": "powx-n", "difficulty": "medium",
        "topics": ["math", "recursion"], "pattern": "fast_exponentiation", "companies": ["meta", "amazon", "google"],
        "lists": ["neetcode_150"], "acceptance": 33,
        "description": "Implement pow(x, n), which calculates x raised to the power n.",
        "examples": [{"input": "x = 2.00000, n = 10", "output": "1024.00000", "explanation": "2^10 = 1024"}],
        "constraints": ["-100.0 < x < 100.0", "-2^31 <= n <= 2^31 - 1", "n is an integer", "Either x != 0 or n > 0", "-10^4 <= x^n <= 10^4"],
        "starter_code": {"python": "class Solution:\n    def myPow(self, x: float, n: int) -> float:\n        pass", "javascript": "var myPow = function(x, n) {\n    \n};"},
        "test_cases": [{"input": {"x": 2.0, "n": 10}, "expected": 1024.0}, {"input": {"x": 2.1, "n": 3}, "expected": 9.261}, {"input": {"x": 2.0, "n": -2}, "expected": 0.25}],
        "optimal_complexity": {"time": "O(log n)", "space": "O(1)"},
        "hints": ["Use binary exponentiation: x^n = (x^2)^(n/2)", "Handle negative n by computing 1/x^(-n)"]
    },
    {
        "num": 142, "name": "Multiply Strings", "slug": "multiply-strings", "difficulty": "medium",
        "topics": ["math", "string"], "pattern": "grade_school_multiplication", "companies": ["meta", "amazon", "microsoft"],
        "lists": ["neetcode_150"], "acceptance": 39,
        "description": "Given two non-negative integers num1 and num2 represented as strings, return the product of num1 and num2, also represented as a string. You must not use any built-in BigInteger library or convert the inputs to integer directly.",
        "examples": [{"input": 'num1 = "2", num2 = "3"', "output": '"6"', "explanation": "2 * 3 = 6"}],
        "constraints": ["1 <= num1.length, num2.length <= 200", "num1 and num2 consist of digits only", "Neither num1 nor num2 contains any leading zero except the number 0 itself"],
        "starter_code": {"python": "class Solution:\n    def multiply(self, num1: str, num2: str) -> str:\n        pass", "javascript": "var multiply = function(num1, num2) {\n    \n};"},
        "test_cases": [{"input": {"num1": "2", "num2": "3"}, "expected": "6"}, {"input": {"num1": "123", "num2": "456"}, "expected": "56088"}, {"input": {"num1": "0", "num2": "0"}, "expected": "0"}],
        "optimal_complexity": {"time": "O(m * n)", "space": "O(m + n)"},
        "hints": ["digits[i+j] += num1[i] * num2[j] with proper carry handling", "Result has at most m + n digits"]
    },
    {
        "num": 143, "name": "Detect Squares", "slug": "detect-squares", "difficulty": "medium",
        "topics": ["math", "hash_map", "design"], "pattern": "counting", "companies": ["google", "amazon", "microsoft"],
        "lists": ["neetcode_150"], "acceptance": 51,
        "description": "You are given a stream of points on the X-Y plane. Design a data structure that supports adding new points and counting the number of ways to form axis-aligned squares with a queried point as one corner.",
        "examples": [{"input": '["DetectSquares","add","add","add","count","count"]\n[[],[[3,10]],[[11,2]],[[3,2]],[[11,10]],[[14,8]]]', "output": "[null,null,null,null,1,0]", "explanation": "One square can be formed with query point [11,10]"}],
        "constraints": ["point.length == 2", "0 <= x, y <= 1000", "At most 5000 calls total"],
        "starter_code": {"python": "class DetectSquares:\n    def __init__(self):\n        pass\n    def add(self, point: List[int]) -> None:\n        pass\n    def count(self, point: List[int]) -> int:\n        pass", "javascript": "var DetectSquares = function() {\n    \n};\nDetectSquares.prototype.add = function(point) {\n    \n};\nDetectSquares.prototype.count = function(point) {\n    \n};"},
        "test_cases": [{"input": {"operations": ["DetectSquares","add","add","add","count"], "values": [[],[[3,10]],[[11,2]],[[3,2]],[[11,10]]]}, "expected": [None,None,None,None,1]}, {"input": {"operations": ["DetectSquares","add","add","add","add","count"], "values": [[],[[0,0]],[[1,1]],[[0,1]],[[1,0]],[[0,0]]]}, "expected": [None,None,None,None,None,1]}, {"input": {"operations": ["DetectSquares","count"], "values": [[],[[0,0]]]}, "expected": [None,0]}],
        "optimal_complexity": {"time": "O(n) per count", "space": "O(n)"},
        "hints": ["For a query point, try all points with same x to form vertical edge", "Then check if the other two corners exist in the point map"]
    },
]
BIT_MANIPULATION = [
    {
        "num": 144, "name": "Single Number", "slug": "single-number", "difficulty": "easy",
        "topics": ["bit_manipulation", "arrays"], "pattern": "xor", "companies": ["amazon", "apple", "google"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 71,
        "description": "Given a non-empty array of integers nums, every element appears twice except for one. Find that single one. You must implement a solution with linear time complexity and constant extra space.",
        "examples": [{"input": "nums = [2,2,1]", "output": "1", "explanation": "1 appears once, all others appear twice"}],
        "constraints": ["1 <= nums.length <= 3 * 10^4", "-3 * 10^4 <= nums[i] <= 3 * 10^4", "Each element appears twice except for one"],
        "starter_code": {"python": "class Solution:\n    def singleNumber(self, nums: List[int]) -> int:\n        pass", "javascript": "var singleNumber = function(nums) {\n    \n};"},
        "test_cases": [{"input": {"nums": [2,2,1]}, "expected": 1}, {"input": {"nums": [4,1,2,1,2]}, "expected": 4}, {"input": {"nums": [1]}, "expected": 1}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["XOR of a number with itself is 0, XOR of a number with 0 is itself", "XOR all elements together"]
    },
    {
        "num": 145, "name": "Number of 1 Bits", "slug": "number-of-1-bits", "difficulty": "easy",
        "topics": ["bit_manipulation"], "pattern": "bit_counting", "companies": ["apple", "microsoft", "amazon"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 66,
        "description": "Write a function that takes the binary representation of a positive integer and returns the number of set bits (1s) it has (also known as the Hamming weight).",
        "examples": [{"input": "n = 11", "output": "3", "explanation": "Binary 1011 has three 1 bits"}],
        "constraints": ["1 <= n <= 2^31 - 1"],
        "starter_code": {"python": "class Solution:\n    def hammingWeight(self, n: int) -> int:\n        pass", "javascript": "var hammingWeight = function(n) {\n    \n};"},
        "test_cases": [{"input": {"n": 11}, "expected": 3}, {"input": {"n": 128}, "expected": 1}, {"input": {"n": 2147483645}, "expected": 30}],
        "optimal_complexity": {"time": "O(1)", "space": "O(1)"},
        "hints": ["n & (n-1) clears the lowest set bit", "Count how many times you can clear a bit before n becomes 0"]
    },
    {
        "num": 146, "name": "Counting Bits", "slug": "counting-bits", "difficulty": "easy",
        "topics": ["bit_manipulation", "dp"], "pattern": "bit_dp", "companies": ["amazon", "apple", "google"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 76,
        "description": "Given an integer n, return an array ans of length n + 1 such that for each i (0 <= i <= n), ans[i] is the number of 1's in the binary representation of i.",
        "examples": [{"input": "n = 5", "output": "[0,1,1,2,1,2]", "explanation": "Binary: 0,1,10,11,100,101"}],
        "constraints": ["0 <= n <= 10^5"],
        "starter_code": {"python": "class Solution:\n    def countBits(self, n: int) -> List[int]:\n        pass", "javascript": "var countBits = function(n) {\n    \n};"},
        "test_cases": [{"input": {"n": 2}, "expected": [0,1,1]}, {"input": {"n": 5}, "expected": [0,1,1,2,1,2]}, {"input": {"n": 0}, "expected": [0]}],
        "optimal_complexity": {"time": "O(n)", "space": "O(n)"},
        "hints": ["dp[i] = dp[i >> 1] + (i & 1)", "Or dp[i] = dp[i & (i-1)] + 1"]
    },
    {
        "num": 147, "name": "Reverse Bits", "slug": "reverse-bits", "difficulty": "easy",
        "topics": ["bit_manipulation"], "pattern": "bit_reversal", "companies": ["apple", "amazon", "microsoft"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 54,
        "description": "Reverse bits of a given 32 bits unsigned integer.",
        "examples": [{"input": "n = 43261596 (00000010100101000001111010011100)", "output": "964176192 (00111001011110000010100101000000)", "explanation": "Reversed 32-bit representation"}],
        "constraints": ["The input is a 32-bit unsigned integer"],
        "starter_code": {"python": "class Solution:\n    def reverseBits(self, n: int) -> int:\n        pass", "javascript": "var reverseBits = function(n) {\n    \n};"},
        "test_cases": [{"input": {"n": 43261596}, "expected": 964176192}, {"input": {"n": 4294967293}, "expected": 3221225471}, {"input": {"n": 0}, "expected": 0}],
        "optimal_complexity": {"time": "O(1)", "space": "O(1)"},
        "hints": ["Iterate 32 times, shifting result left and adding the last bit of n", "result = (result << 1) | (n & 1); n >>= 1"]
    },
    {
        "num": 148, "name": "Missing Number", "slug": "missing-number", "difficulty": "easy",
        "topics": ["bit_manipulation", "math", "arrays"], "pattern": "xor", "companies": ["amazon", "microsoft", "apple"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 63,
        "description": "Given an array nums containing n distinct numbers in the range [0, n], return the only number in the range that is missing from the array.",
        "examples": [{"input": "nums = [3,0,1]", "output": "2", "explanation": "n=3, range is [0,1,2,3], missing is 2"}],
        "constraints": ["n == nums.length", "1 <= n <= 10^4", "0 <= nums[i] <= n", "All values are unique"],
        "starter_code": {"python": "class Solution:\n    def missingNumber(self, nums: List[int]) -> int:\n        pass", "javascript": "var missingNumber = function(nums) {\n    \n};"},
        "test_cases": [{"input": {"nums": [3,0,1]}, "expected": 2}, {"input": {"nums": [0,1]}, "expected": 2}, {"input": {"nums": [9,6,4,2,3,5,7,0,1]}, "expected": 8}],
        "optimal_complexity": {"time": "O(n)", "space": "O(1)"},
        "hints": ["XOR all numbers with all indices and n", "Or use sum formula: n*(n+1)/2 - sum(nums)"]
    },
    {
        "num": 149, "name": "Sum of Two Integers", "slug": "sum-of-two-integers", "difficulty": "medium",
        "topics": ["bit_manipulation"], "pattern": "bit_arithmetic", "companies": ["meta", "amazon", "apple"],
        "lists": ["neetcode_150", "blind_75"], "acceptance": 51,
        "description": "Given two integers a and b, return the sum of the two integers without using the operators + and -.",
        "examples": [{"input": "a = 1, b = 2", "output": "3", "explanation": "1 + 2 = 3 using bit manipulation"}],
        "constraints": ["-1000 <= a, b <= 1000"],
        "starter_code": {"python": "class Solution:\n    def getSum(self, a: int, b: int) -> int:\n        pass", "javascript": "var getSum = function(a, b) {\n    \n};"},
        "test_cases": [{"input": {"a": 1, "b": 2}, "expected": 3}, {"input": {"a": 2, "b": 3}, "expected": 5}, {"input": {"a": -1, "b": 1}, "expected": 0}],
        "optimal_complexity": {"time": "O(1)", "space": "O(1)"},
        "hints": ["XOR gives sum without carry, AND shifted left gives carry", "Repeat until carry is 0"]
    },
    {
        "num": 150, "name": "Reverse Integer", "slug": "reverse-integer", "difficulty": "medium",
        "topics": ["bit_manipulation", "math"], "pattern": "digit_manipulation", "companies": ["amazon", "apple", "bloomberg"],
        "lists": ["neetcode_150"], "acceptance": 28,
        "description": "Given a signed 32-bit integer x, return x with its digits reversed. If reversing x causes the value to go outside the signed 32-bit integer range [-2^31, 2^31 - 1], then return 0.",
        "examples": [{"input": "x = 123", "output": "321", "explanation": "Digits reversed"}],
        "constraints": ["-2^31 <= x <= 2^31 - 1"],
        "starter_code": {"python": "class Solution:\n    def reverse(self, x: int) -> int:\n        pass", "javascript": "var reverse = function(x) {\n    \n};"},
        "test_cases": [{"input": {"x": 123}, "expected": 321}, {"input": {"x": -123}, "expected": -321}, {"input": {"x": 120}, "expected": 21}],
        "optimal_complexity": {"time": "O(log x)", "space": "O(1)"},
        "hints": ["Pop digits with x % 10 and push to result with result * 10 + digit", "Check for overflow before multiplying/adding"]
    },
]
SD_PROBLEMS = [
    {
        "name": "URL Shortener",
        "slug": "url-shortener",
        "difficulty": "medium",
        "concepts": ["hashing", "caching", "nosql", "cdn"],
        "estimated_minutes": 45,
        "description": "Design a URL shortening service like bit.ly or TinyURL.",
        "requirements": {
            "functional": ["Shorten a long URL to a unique short URL", "Redirect short URL to original", "Optional custom alias and TTL"],
            "non_functional": ["Handle 1B total URLs", "100M DAU", "Read-heavy 100:1 ratio", "Low latency redirects (<100ms)"]
        },
        "key_decisions": [
            {"topic": "Hash Generation", "options": ["MD5 truncation", "Base62 counter", "Snowflake ID"], "considerations": "Collision handling, predictability, length"},
            {"topic": "Storage", "options": ["PostgreSQL", "DynamoDB", "Cassandra"], "considerations": "Read vs write patterns, scaling strategy"},
            {"topic": "Caching", "options": ["Redis", "Memcached", "CDN edge cache"], "considerations": "Cache eviction, hot URLs, consistency"}
        ],
        "evaluation_rubric": {
            "must_cover": ["API design", "Database schema", "Short code generation strategy", "Caching layer"],
            "bonus": ["Analytics pipeline", "Rate limiting", "Custom domain support"]
        }
    },
    {
        "name": "Design Twitter / News Feed",
        "slug": "design-twitter-news-feed",
        "difficulty": "hard",
        "concepts": ["fan_out", "caching", "message_queue", "social_graph"],
        "estimated_minutes": 60,
        "description": "Design a social media service like Twitter with timeline/news feed functionality.",
        "requirements": {
            "functional": ["Post tweets (text, images)", "Follow/unfollow users", "Home timeline (aggregated feed)", "Search tweets"],
            "non_functional": ["500M users, 200M DAU", "Highly available", "Timeline generation <500ms", "Eventual consistency acceptable for feed"]
        },
        "key_decisions": [
            {"topic": "Feed Generation", "options": ["Fan-out on write", "Fan-out on read", "Hybrid"], "considerations": "Celebrity problem, write amplification, freshness"},
            {"topic": "Storage", "options": ["MySQL sharded", "Cassandra for timelines", "Redis for cache"], "considerations": "Tweet storage vs timeline storage"},
            {"topic": "Media Storage", "options": ["S3 + CDN", "Blob storage"], "considerations": "Upload pipeline, thumbnail generation"}
        ],
        "evaluation_rubric": {
            "must_cover": ["Fan-out strategy", "Timeline storage", "Social graph storage", "Media handling"],
            "bonus": ["Trending topics", "Push notifications", "Search indexing with Elasticsearch"]
        }
    },
    {
        "name": "Design Instagram / Photo Sharing",
        "slug": "design-instagram-photo-sharing",
        "difficulty": "medium",
        "concepts": ["blob_storage", "cdn", "feed_generation", "caching"],
        "estimated_minutes": 45,
        "description": "Design a photo-sharing social network like Instagram.",
        "requirements": {
            "functional": ["Upload photos/videos", "Follow users", "Generate news feed", "Like and comment on posts"],
            "non_functional": ["500M users, 100M DAU", "Photo uploads: 2M/day", "High availability", "Low latency feed loading"]
        },
        "key_decisions": [
            {"topic": "Image Storage", "options": ["S3 + CloudFront", "HDFS", "Google Cloud Storage"], "considerations": "Multiple resolutions, storage cost, CDN distribution"},
            {"topic": "Feed Generation", "options": ["Pre-computed (fan-out on write)", "On-demand (fan-out on read)", "Hybrid approach"], "considerations": "Write amplification for popular users, staleness"},
            {"topic": "Database", "options": ["MySQL + sharding", "Cassandra", "PostgreSQL + Citus"], "considerations": "User data vs media metadata vs social graph"}
        ],
        "evaluation_rubric": {
            "must_cover": ["Image upload and storage pipeline", "Feed generation strategy", "Database schema", "CDN usage"],
            "bonus": ["Image filters/processing pipeline", "Stories feature", "Explore/discovery algorithm"]
        }
    },
    {
        "name": "Design Chat System / WhatsApp",
        "slug": "design-chat-system-whatsapp",
        "difficulty": "medium",
        "concepts": ["websockets", "message_queue", "presence", "encryption"],
        "estimated_minutes": 50,
        "description": "Design a real-time chat messaging system like WhatsApp or Facebook Messenger.",
        "requirements": {
            "functional": ["1:1 messaging", "Group chat (up to 500 members)", "Online/offline status", "Message delivery receipts (sent/delivered/read)"],
            "non_functional": ["2B users, 500M DAU", "Message delivery <100ms for online users", "Messages stored persistently", "End-to-end encryption"]
        },
        "key_decisions": [
            {"topic": "Real-time Delivery", "options": ["WebSocket", "Long polling", "Server-Sent Events"], "considerations": "Connection management, mobile battery, reconnection"},
            {"topic": "Message Storage", "options": ["Cassandra", "HBase", "DynamoDB"], "considerations": "Write-heavy, time-series queries, partition strategy"},
            {"topic": "Message Queue", "options": ["Kafka", "RabbitMQ", "Redis Streams"], "considerations": "Ordering guarantees, offline message buffering"}
        ],
        "evaluation_rubric": {
            "must_cover": ["WebSocket connection management", "Message delivery flow", "Group messaging", "Offline message handling"],
            "bonus": ["End-to-end encryption protocol", "Media sharing", "Push notifications"]
        }
    },
    {
        "name": "Design Rate Limiter",
        "slug": "design-rate-limiter",
        "difficulty": "easy",
        "concepts": ["rate_limiting", "distributed_systems", "caching", "algorithms"],
        "estimated_minutes": 35,
        "description": "Design a rate limiter that controls the rate of requests a client can send to an API.",
        "requirements": {
            "functional": ["Limit requests per client per time window", "Support different limits per API endpoint", "Return appropriate headers (remaining, retry-after)"],
            "non_functional": ["Low latency (<1ms overhead)", "Distributed across multiple servers", "Accurate rate tracking", "Memory efficient"]
        },
        "key_decisions": [
            {"topic": "Algorithm", "options": ["Token bucket", "Sliding window log", "Sliding window counter", "Fixed window"], "considerations": "Accuracy, memory usage, burst handling"},
            {"topic": "Storage", "options": ["Redis", "Local memory + sync", "Memcached"], "considerations": "Distributed coordination, latency, consistency"},
            {"topic": "Placement", "options": ["API gateway", "Middleware", "Client-side"], "considerations": "Centralized vs distributed enforcement"}
        ],
        "evaluation_rubric": {
            "must_cover": ["Rate limiting algorithm choice with tradeoffs", "Distributed rate limiting", "Race condition handling", "Client identification"],
            "bonus": ["Multi-tier rate limiting", "Graceful degradation", "Analytics on rate limited requests"]
        }
    },
    {
        "name": "Design Web Crawler",
        "slug": "design-web-crawler",
        "difficulty": "hard",
        "concepts": ["distributed_systems", "message_queue", "deduplication", "dns"],
        "estimated_minutes": 55,
        "description": "Design a web crawler that systematically browses the internet to collect and index web pages.",
        "requirements": {
            "functional": ["Crawl 1B web pages per month", "Respect robots.txt", "Handle different content types", "Detect and avoid duplicate content"],
            "non_functional": ["Scalable to thousands of crawler nodes", "Polite crawling (rate limit per domain)", "Fault tolerant", "Prioritize important pages"]
        },
        "key_decisions": [
            {"topic": "URL Frontier", "options": ["Priority queue", "Multi-queue with politeness", "Kafka partitioned by domain"], "considerations": "Priority, politeness, deduplication"},
            {"topic": "Deduplication", "options": ["URL hash set", "Content fingerprint (SimHash)", "Bloom filter"], "considerations": "Memory efficiency, false positive rate"},
            {"topic": "Storage", "options": ["HDFS for raw pages", "Elasticsearch for index", "S3 for archives"], "considerations": "Volume, query patterns, cost"}
        ],
        "evaluation_rubric": {
            "must_cover": ["URL frontier design", "Crawler architecture (workers, scheduler)", "Deduplication strategy", "Politeness and robots.txt"],
            "bonus": ["Page ranking/priority", "JavaScript rendering", "Incremental crawling"]
        }
    },
    {
        "name": "Design Notification System",
        "slug": "design-notification-system",
        "difficulty": "medium",
        "concepts": ["message_queue", "push_notifications", "email", "sms"],
        "estimated_minutes": 45,
        "description": "Design a scalable notification system that supports multiple channels (push, SMS, email).",
        "requirements": {
            "functional": ["Send notifications via push, SMS, email", "Support notification templates", "User notification preferences", "Scheduled notifications"],
            "non_functional": ["10M notifications/day", "Soft real-time delivery", "No duplicate notifications", "Rate limiting per user"]
        },
        "key_decisions": [
            {"topic": "Message Queue", "options": ["Kafka", "SQS", "RabbitMQ"], "considerations": "Ordering, retry, dead letter queue"},
            {"topic": "Delivery", "options": ["APNs/FCM for push", "Twilio for SMS", "SES for email"], "considerations": "Vendor reliability, cost, rate limits"},
            {"topic": "Deduplication", "options": ["Idempotency keys", "Event log", "Redis dedup cache"], "considerations": "At-least-once vs exactly-once delivery"}
        ],
        "evaluation_rubric": {
            "must_cover": ["Multi-channel architecture", "Message queue for reliability", "User preferences and opt-out", "Retry and failure handling"],
            "bonus": ["Analytics and tracking", "A/B testing notifications", "Priority queues for urgent notifications"]
        }
    },
    {
        "name": "Design Uber / Ride Sharing",
        "slug": "design-uber-ride-sharing",
        "difficulty": "hard",
        "concepts": ["geospatial", "real_time", "matching", "eta_estimation"],
        "estimated_minutes": 60,
        "description": "Design a ride-sharing service like Uber or Lyft.",
        "requirements": {
            "functional": ["Request a ride", "Match riders with nearby drivers", "Real-time location tracking", "ETA calculation", "Fare estimation and payment"],
            "non_functional": ["50M riders, 5M drivers", "Match within 10 seconds", "Location updates every 3 seconds", "High availability"]
        },
        "key_decisions": [
            {"topic": "Location Service", "options": ["Geohash + Redis", "QuadTree", "H3 spatial index"], "considerations": "Query efficiency, update frequency, precision"},
            {"topic": "Matching", "options": ["Nearest driver", "Batch matching (Hungarian algorithm)", "ML-based dispatch"], "considerations": "Latency, optimality, supply/demand balance"},
            {"topic": "Real-time Updates", "options": ["WebSocket", "Server-Sent Events", "MQTT"], "considerations": "Mobile battery, connection reliability, scale"}
        ],
        "evaluation_rubric": {
            "must_cover": ["Geospatial indexing", "Driver-rider matching algorithm", "Real-time location tracking", "Trip lifecycle"],
            "bonus": ["Surge pricing", "ETA prediction with ML", "Payment processing"]
        }
    },
    {
        "name": "Design YouTube / Video Streaming",
        "slug": "design-youtube-video-streaming",
        "difficulty": "hard",
        "concepts": ["blob_storage", "cdn", "transcoding", "streaming_protocols"],
        "estimated_minutes": 60,
        "description": "Design a video sharing and streaming platform like YouTube.",
        "requirements": {
            "functional": ["Upload videos", "Stream videos with adaptive bitrate", "Search videos", "Like, comment, subscribe"],
            "non_functional": ["2B users, 800M DAU", "5M video uploads/day", "Support 4K streaming", "Global low-latency playback"]
        },
        "key_decisions": [
            {"topic": "Video Processing", "options": ["FFmpeg pipeline", "AWS Elastic Transcoder", "Custom DAG pipeline"], "considerations": "Multiple resolutions, codec support, processing time"},
            {"topic": "Streaming", "options": ["HLS", "DASH", "WebRTC for live"], "considerations": "Adaptive bitrate, browser support, latency"},
            {"topic": "Storage", "options": ["S3 + CloudFront", "Google Cloud Storage + CDN", "Custom blob store"], "considerations": "Cost at scale, global distribution, hot vs cold storage"}
        ],
        "evaluation_rubric": {
            "must_cover": ["Video upload and processing pipeline", "Adaptive bitrate streaming", "CDN architecture", "Database design for metadata"],
            "bonus": ["Recommendation engine", "Live streaming", "Content moderation pipeline"]
        }
    },
    {
        "name": "Design Google Search",
        "slug": "design-google-search",
        "difficulty": "hard",
        "concepts": ["inverted_index", "ranking", "web_crawling", "distributed_systems"],
        "estimated_minutes": 60,
        "description": "Design a web search engine like Google Search.",
        "requirements": {
            "functional": ["Index billions of web pages", "Return relevant results for text queries", "Autocomplete suggestions", "Spell correction"],
            "non_functional": ["Handle 100K queries/second", "Results in <500ms", "Index freshness within hours", "Highly available globally"]
        },
        "key_decisions": [
            {"topic": "Indexing", "options": ["Inverted index", "Forward index + inverted index", "Elasticsearch cluster"], "considerations": "Index size, update frequency, query speed"},
            {"topic": "Ranking", "options": ["PageRank + BM25", "Learning to Rank (ML)", "Hybrid signals"], "considerations": "Relevance, freshness, authority, personalization"},
            {"topic": "Serving", "options": ["Sharded index servers", "Tiered architecture", "Scatter-gather pattern"], "considerations": "Latency budget, index partitioning, caching"}
        ],
        "evaluation_rubric": {
            "must_cover": ["Web crawler integration", "Inverted index structure", "Ranking algorithm", "Query processing pipeline"],
            "bonus": ["Autocomplete with trie", "Spell correction", "Personalization"]
        }
    },
    {
        "name": "Design Dropbox / File Storage",
        "slug": "design-dropbox-file-storage",
        "difficulty": "medium",
        "concepts": ["blob_storage", "sync", "deduplication", "chunking"],
        "estimated_minutes": 50,
        "description": "Design a cloud file storage and synchronization service like Dropbox or Google Drive.",
        "requirements": {
            "functional": ["Upload/download files", "Sync files across devices", "File sharing with permissions", "Version history"],
            "non_functional": ["500M users, 100M DAU", "Support files up to 50GB", "Reliable sync with conflict resolution", "Bandwidth efficient (delta sync)"]
        },
        "key_decisions": [
            {"topic": "Chunking", "options": ["Fixed-size chunks (4MB)", "Content-defined chunking (Rabin fingerprint)", "Variable-size with dedup"], "considerations": "Deduplication efficiency, upload resumability"},
            {"topic": "Sync Protocol", "options": ["Long polling for changes", "WebSocket notifications", "Periodic polling"], "considerations": "Real-time sync, battery impact, bandwidth"},
            {"topic": "Storage", "options": ["S3 for blocks", "Custom block store", "Tiered storage (hot/cold)"], "considerations": "Cost optimization, durability, retrieval latency"}
        ],
        "evaluation_rubric": {
            "must_cover": ["File chunking and deduplication", "Sync protocol", "Metadata vs block storage separation", "Conflict resolution"],
            "bonus": ["Delta sync (rsync-like)", "Sharing and permissions model", "Offline support"]
        }
    },
    {
        "name": "Design Key-Value Store",
        "slug": "design-key-value-store",
        "difficulty": "medium",
        "concepts": ["consistent_hashing", "replication", "consensus", "lsm_tree"],
        "estimated_minutes": 50,
        "description": "Design a distributed key-value store like DynamoDB or Cassandra.",
        "requirements": {
            "functional": ["put(key, value)", "get(key)", "delete(key)", "Support configurable consistency levels"],
            "non_functional": ["Sub-10ms latency at p99", "High availability (99.99%)", "Horizontal scalability", "Automatic failure detection and recovery"]
        },
        "key_decisions": [
            {"topic": "Partitioning", "options": ["Consistent hashing", "Range-based", "Hash-based"], "considerations": "Data distribution, hot spots, rebalancing"},
            {"topic": "Replication", "options": ["Leader-follower", "Leaderless (quorum)", "Multi-leader"], "considerations": "Consistency vs availability, write conflicts"},
            {"topic": "Storage Engine", "options": ["LSM-tree", "B-tree", "In-memory with WAL"], "considerations": "Write vs read optimization, space amplification"}
        ],
        "evaluation_rubric": {
            "must_cover": ["Consistent hashing", "Replication strategy", "Failure detection (gossip protocol)", "Read/write path"],
            "bonus": ["Vector clocks for conflict resolution", "Merkle trees for anti-entropy", "Compaction strategies"]
        }
    },
    {
        "name": "Design TicketMaster / Booking System",
        "slug": "design-ticketmaster-booking-system",
        "difficulty": "hard",
        "concepts": ["distributed_locking", "inventory_management", "queueing", "payment"],
        "estimated_minutes": 55,
        "description": "Design an event ticketing and booking system like TicketMaster or BookMyShow.",
        "requirements": {
            "functional": ["Browse and search events", "View seating map and availability", "Reserve and purchase tickets", "Handle high-demand on-sale events"],
            "non_functional": ["10M concurrent users during popular sales", "No double-booking (strong consistency for inventory)", "Complete booking within 10 minutes (hold timer)", "Handle 100K bookings/minute peak"]
        },
        "key_decisions": [
            {"topic": "Inventory Locking", "options": ["Pessimistic locking", "Optimistic locking with versioning", "Distributed lock (Redis)"], "considerations": "Contention, timeout handling, deadlock prevention"},
            {"topic": "Queue Management", "options": ["Virtual waiting room", "Token-based queue", "Rate-limited entry"], "considerations": "Fairness, bot prevention, user experience"},
            {"topic": "Database", "options": ["PostgreSQL with row-level locking", "Redis for seat holds", "Hybrid approach"], "considerations": "Consistency, throughput, seat map queries"}
        ],
        "evaluation_rubric": {
            "must_cover": ["Seat reservation with hold timer", "Preventing double booking", "High-traffic queue management", "Payment integration"],
            "bonus": ["Dynamic pricing", "Waitlist functionality", "Bot/scalper prevention"]
        }
    },
    {
        "name": "Design Payment System",
        "slug": "design-payment-system",
        "difficulty": "hard",
        "concepts": ["idempotency", "distributed_transactions", "ledger", "reconciliation"],
        "estimated_minutes": 55,
        "description": "Design a payment processing system like Stripe or PayPal.",
        "requirements": {
            "functional": ["Process payments (credit card, bank transfer)", "Refunds and chargebacks", "Multi-currency support", "Transaction history and reporting"],
            "non_functional": ["99.999% availability", "Exactly-once payment processing", "PCI DSS compliance", "Process 1M transactions/day"]
        },
        "key_decisions": [
            {"topic": "Idempotency", "options": ["Idempotency key per request", "State machine transitions", "Event sourcing"], "considerations": "Duplicate prevention, retry safety, audit trail"},
            {"topic": "Ledger", "options": ["Double-entry bookkeeping", "Event log + materialized view", "Append-only ledger"], "considerations": "Auditability, reconciliation, immutability"},
            {"topic": "Payment Flow", "options": ["Synchronous processing", "Async with webhook callbacks", "Two-phase commit"], "considerations": "Reliability, latency, failure handling"}
        ],
        "evaluation_rubric": {
            "must_cover": ["Payment flow (auth, capture, settle)", "Idempotency handling", "Ledger design", "Failure and retry logic"],
            "bonus": ["Fraud detection", "Multi-currency handling", "Reconciliation pipeline"]
        }
    },
    {
        "name": "Design Distributed Cache",
        "slug": "design-distributed-cache",
        "difficulty": "medium",
        "concepts": ["consistent_hashing", "eviction_policies", "replication", "cache_patterns"],
        "estimated_minutes": 45,
        "description": "Design a distributed caching system like Redis Cluster or Memcached.",
        "requirements": {
            "functional": ["get(key) and set(key, value, ttl)", "Support various data structures (string, list, hash, set)", "Key expiration (TTL)", "Cache invalidation"],
            "non_functional": ["Sub-millisecond latency", "High throughput (1M ops/sec per node)", "Horizontal scalability", "High availability with failover"]
        },
        "key_decisions": [
            {"topic": "Partitioning", "options": ["Consistent hashing with virtual nodes", "Hash slot (Redis Cluster style)", "Client-side sharding"], "considerations": "Rebalancing, hot keys, client complexity"},
            {"topic": "Eviction Policy", "options": ["LRU", "LFU", "Random", "TTL-based"], "considerations": "Hit rate, implementation complexity, memory overhead"},
            {"topic": "Replication", "options": ["Leader-follower async", "Synchronous replication", "No replication"], "considerations": "Consistency, write latency, data loss risk"}
        ],
        "evaluation_rubric": {
            "must_cover": ["Data partitioning across nodes", "Eviction strategy", "Cache consistency patterns (write-through, write-back, write-around)", "Failure handling"],
            "bonus": ["Hot key handling", "Cache stampede prevention", "Pub/sub for invalidation"]
        }
    },
]


def _build_all_dsa():
    """Combine all category lists into one."""
    return (
        ARRAYS_HASHING + TWO_POINTERS + SLIDING_WINDOW + STACK + BINARY_SEARCH
        + LINKED_LIST + TREES + TRIES + HEAP_PQ + BACKTRACKING + GRAPHS
        + ADVANCED_GRAPHS + DP_1D + DP_2D + GREEDY + INTERVALS
        + MATH_GEOMETRY + BIT_MANIPULATION
    )


def seed(mongo_uri: str, drop: bool = False):
    """Connect to MongoDB and seed both collections."""
    import certifi
    client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
    db_name = mongo_uri.rsplit("/", 1)[-1].split("?")[0] or "tutor_v2"
    db = client[db_name]

    # -- dsa_problems --
    col_dsa = db["dsa_problems"]
    if drop:
        col_dsa.drop()
        print("[dsa_problems] Dropped existing collection")

    all_dsa = _build_all_dsa()
    if all_dsa:
        try:
            col_dsa.insert_many(all_dsa, ordered=False)
        except BulkWriteError as e:
            print(f"[dsa_problems] BulkWriteError (duplicates skipped): {e.details.get('nInserted', '?')} inserted")
        else:
            print(f"[dsa_problems] Inserted {len(all_dsa)} problems")
    else:
        print("[dsa_problems] No problems to insert")

    # indexes
    col_dsa.create_index("slug", unique=True)
    col_dsa.create_index("difficulty")
    col_dsa.create_index("topics")
    col_dsa.create_index("lists")
    col_dsa.create_index("num", unique=True)
    print("[dsa_problems] Indexes created (slug, difficulty, topics, lists, num)")

    # -- sd_problems --
    col_sd = db["sd_problems"]
    if drop:
        col_sd.drop()
        print("[sd_problems] Dropped existing collection")

    if SD_PROBLEMS:
        try:
            col_sd.insert_many(SD_PROBLEMS, ordered=False)
        except BulkWriteError as e:
            print(f"[sd_problems] BulkWriteError (duplicates skipped): {e.details.get('nInserted', '?')} inserted")
        else:
            print(f"[sd_problems] Inserted {len(SD_PROBLEMS)} problems")
    else:
        print("[sd_problems] No problems to insert")

    col_sd.create_index("slug", unique=True)
    col_sd.create_index("difficulty")
    col_sd.create_index("concepts")
    print("[sd_problems] Indexes created (slug, difficulty, concepts)")

    print("\nSeeding complete!")
    client.close()


def main():
    parser = argparse.ArgumentParser(description="Seed DSA and System Design problems into MongoDB")
    parser.add_argument("--drop", action="store_true", help="Drop existing collections before seeding")
    parser.add_argument("--uri", default=None, help="MongoDB URI (overrides MONGO_URI env var)")
    args = parser.parse_args()

    mongo_uri = args.uri or os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI", "")
    if not mongo_uri:
        print("ERROR: MONGODB_URI not set. Check backend/.env")
        sys.exit(1)
    print(f"Connecting to: {mongo_uri[:40]}...")
    seed(mongo_uri, drop=args.drop)


if __name__ == "__main__":
    main()
